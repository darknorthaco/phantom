"""
Phase 4 TLS tests — no external network (loopback only).

Covers: sovereign TLS policy, path validation, worker URL/verify helpers,
local HTTPS handshake via stdlib + cryptography-generated PEM.
"""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import ssl
import sys
import threading
import types
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

# Repo root: phantom_core/ (sibling of llm_taskmaster/, worker_tls.py, phantom_core package dir)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_flat(name: str, rel: Path):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_phantom_core_submodules():
    """Load ``phantom_core.tls_runtime`` and ``phantom_core.config_schema`` without importing ``phantom_core`` package ``__init__`` (avoids FastAPI)."""
    pkg_name = "phantom_core"
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(ROOT / "phantom_core")]
        sys.modules[pkg_name] = pkg

    tr_path = ROOT / "phantom_core" / "tls_runtime.py"
    if "phantom_core.tls_runtime" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "phantom_core.tls_runtime", tr_path
        )
        assert spec and spec.loader
        tr = importlib.util.module_from_spec(spec)
        sys.modules["phantom_core.tls_runtime"] = tr
        spec.loader.exec_module(tr)

    cs_path = ROOT / "phantom_core" / "config_schema.py"
    if "phantom_core.config_schema" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "phantom_core.config_schema", cs_path
        )
        assert spec and spec.loader
        cs = importlib.util.module_from_spec(spec)
        sys.modules["phantom_core.config_schema"] = cs
        spec.loader.exec_module(cs)


_ensure_phantom_core_submodules()
_sc = _load_flat(
    "sovereign_compliance_flat", Path("llm_taskmaster") / "sovereign_compliance.py"
)
validate_tls_policy = _sc.validate_tls_policy

_tls = sys.modules["phantom_core.tls_runtime"]
load_tls_config = _tls.load_tls_config
validate_tls_paths = _tls.validate_tls_paths
uvicorn_ssl_kwargs = _tls.uvicorn_ssl_kwargs

_cfg = sys.modules["phantom_core.config_schema"]
ConfigSchema = _cfg.ConfigSchema

_wt = _load_flat("worker_tls_flat", Path("worker_tls.py"))
controller_base_url = _wt.controller_base_url
httpx_verify_for_worker = _wt.httpx_verify_for_worker


def _write_rsa_self_signed_pem(tmp: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=2))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
            ),
            False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp / "srv.crt"
    key_path = tmp / "srv.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class _QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D401
        return

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


@pytest.fixture()
def https_server(tmp_path):
    cert_path, key_path = _write_rsa_self_signed_pem(tmp_path)
    httpd = HTTPServer(("127.0.0.1", 0), _QuietHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert_path), str(key_path))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port, cert_path, key_path
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def test_validate_tls_policy_wan_requires_tls():
    with pytest.raises(ValueError, match="wan_mode requires tls_enabled"):
        validate_tls_policy(True, False, "/x.crt", "/x.key")


def test_validate_tls_policy_tls_requires_paths():
    with pytest.raises(ValueError, match="tls_cert_path"):
        validate_tls_policy(False, True, "", "/x.key")
    with pytest.raises(ValueError, match="tls_key_path"):
        validate_tls_policy(False, True, "/x.crt", "")


def test_validate_tls_paths_missing(tmp_path):
    c = tmp_path / "a.pem"
    k = tmp_path / "b.pem"
    c.write_text("x")
    with pytest.raises(FileNotFoundError):
        validate_tls_paths(str(c), str(k))


def test_validate_tls_paths_empty_raises():
    with pytest.raises(ValueError):
        validate_tls_paths("", "")


def test_load_tls_config_missing_file_defaults(tmp_path):
    cfg = load_tls_config(tmp_path / "nope.json")
    assert cfg == {
        "wan_mode": False,
        "tls_enabled": False,
        "tls_cert_path": "",
        "tls_key_path": "",
    }


def test_uvicorn_ssl_kwargs_lan_plaintext(tmp_path):
    p = tmp_path / "phantom_config.json"
    p.write_text(
        json.dumps(
            {
                "wan_mode": False,
                "tls_enabled": False,
                "tls_cert_path": "",
                "tls_key_path": "",
            }
        ),
        encoding="utf-8",
    )
    assert uvicorn_ssl_kwargs(p) == {}


def test_uvicorn_ssl_kwargs_wan_without_tls_raises(tmp_path):
    p = tmp_path / "phantom_config.json"
    p.write_text(
        json.dumps(
            {
                "wan_mode": True,
                "tls_enabled": False,
                "tls_cert_path": "",
                "tls_key_path": "",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="wan_mode requires"):
        uvicorn_ssl_kwargs(p)


def test_uvicorn_ssl_kwargs_https(tmp_path):
    cert_path, key_path = _write_rsa_self_signed_pem(tmp_path)
    p = tmp_path / "phantom_config.json"
    p.write_text(
        json.dumps(
            {
                "wan_mode": False,
                "tls_enabled": True,
                "tls_cert_path": str(cert_path),
                "tls_key_path": str(key_path),
            }
        ),
        encoding="utf-8",
    )
    kw = uvicorn_ssl_kwargs(p)
    assert kw == {
        "ssl_certfile": str(cert_path),
        "ssl_keyfile": str(key_path),
    }


def test_controller_base_url_scheme():
    assert controller_base_url("10.0.0.1", 8080, False) == "http://10.0.0.1:8080"
    assert controller_base_url("10.0.0.1", 8080, True) == "https://10.0.0.1:8080"


def test_httpx_verify_tls_requires_controller_cert_path():
    with pytest.raises(ValueError, match="tls_controller_cert_path"):
        httpx_verify_for_worker(True, "")


def test_httpx_verify_tls_missing_file(tmp_path):
    p = tmp_path / "missing.crt"
    with pytest.raises(FileNotFoundError):
        httpx_verify_for_worker(True, str(p))


def test_config_schema_tls_wan_invalid(tmp_path):
    cert_path, key_path = _write_rsa_self_signed_pem(tmp_path)
    cfg = ConfigSchema(
        wan_mode=True,
        tls_enabled=False,
        tls_cert_path=str(cert_path),
        tls_key_path=str(key_path),
    )
    with pytest.raises(ValueError, match="wan_mode requires"):
        cfg.validate()


def test_worker_https_callback_local(https_server):
    port, cert_path, _key_path = https_server
    base = controller_base_url("127.0.0.1", port, tls_enabled=True)
    httpx_verify_for_worker(True, str(cert_path))
    ctx = ssl.create_default_context(cafile=str(cert_path))
    with httpx.Client(verify=ctx, timeout=5.0) as client:
        r = client.get(f"{base}/")
        assert r.status_code == 200


def test_invalid_pem_not_accepted_as_verify_path(tmp_path, https_server):
    """Wrong pinned cert must not validate the running server."""
    port, good_cert, _ = https_server
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other_cert, _ = _write_rsa_self_signed_pem(other_dir)
    assert other_cert.resolve() != good_cert.resolve()
    base = controller_base_url("127.0.0.1", port, tls_enabled=True)
    httpx_verify_for_worker(True, str(other_cert))
    ctx = ssl.create_default_context(cafile=str(other_cert))
    with httpx.Client(verify=ctx, timeout=5.0) as client:
        with pytest.raises(httpx.HTTPError):
            client.get(f"{base}/")
