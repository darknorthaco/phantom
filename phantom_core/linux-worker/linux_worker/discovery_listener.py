"""
Phantom worker discovery listener. Responds to DISCOVER_WORKERS UDP broadcast
with a signed manifest. Workers self-identify; no controller host probing.

§3 integration: the manifest is now a SignedManifest — includes Ed25519
public_key, signature, and signed_at timestamp.
"""

import json
import logging
import os
import socket
import threading
from pathlib import Path
from typing import Optional

DISCOVERY_PORT = 8095
DISCOVER_PAYLOAD = b"PHANTOM_DISCOVER_WORKERS"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Worker identity (Ed25519 keypair)
# ---------------------------------------------------------------------------

_signer = None  # type: Optional[object]


def _init_signer(identity_dir: Optional[str] = None) -> Optional[object]:
    """Load or generate a per-worker Ed25519 keypair.

    Returns a ManifestSigner or None if the cryptography library is unavailable.
    """
    try:
        from phantom_core.discovery import ManifestSigner
    except ImportError:
        # Graceful degradation: worker can still respond unsigned
        logger.info("cryptography not available — manifests will be unsigned")
        return None

    key_dir = (
        Path(identity_dir) if identity_dir else Path.home() / ".phantom" / "identity"
    )
    key_dir.mkdir(parents=True, exist_ok=True)
    priv_path = key_dir / "worker_private.key"

    if priv_path.exists():
        import base64

        raw = base64.b64decode(priv_path.read_bytes())
        return ManifestSigner.from_raw_bytes(raw)

    signer = ManifestSigner.generate()
    # Persist private key (base64-encoded raw 32 bytes) with restricted permissions
    import base64

    raw = signer.export_private_key_bytes()
    fd = os.open(str(priv_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(base64.b64encode(raw))
    logger.info("Generated new worker identity in %s", key_dir)
    return signer


def run_discovery_listener(
    worker_id: str,
    host: str,
    port: int,
    gpu_info: dict,
    identity_dir: Optional[str] = None,
) -> None:
    """Run UDP listener on DISCOVERY_PORT. Respond to DISCOVER_WORKERS with manifest.

    If the ``cryptography`` package is available, responses are signed
    (SignedManifest).  Otherwise, falls back to unsigned legacy format.
    """
    global _signer
    _signer = _init_signer(identity_dir)

    def listen() -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", DISCOVERY_PORT))
            sock.settimeout(1.0)
            logger.info("Discovery listener on 0.0.0.0:%s", DISCOVERY_PORT)
        except OSError as e:
            logger.warning("Discovery listener failed to bind: %s", e)
            return

        while True:
            try:
                data, addr = sock.recvfrom(512)
                if data == DISCOVER_PAYLOAD:
                    payload_bytes = _build_manifest_payload(
                        worker_id, host, port, gpu_info
                    )
                    sock.sendto(payload_bytes, addr)
                    logger.debug("Sent manifest to %s", addr)
            except socket.timeout:
                continue
            except Exception as e:
                logger.debug("Discovery recv: %s", e)

    t = threading.Thread(target=listen, daemon=True)
    t.start()


def _build_manifest_payload(
    worker_id: str, host: str, port: int, gpu_info: dict
) -> bytes:
    """Build a (possibly signed) manifest payload."""
    if _signer is not None:
        try:
            from phantom_core.discovery import SignedManifest

            manifest = SignedManifest(
                worker_id=worker_id,
                address=host,
                capabilities=gpu_info or {},
                msg_type="WORKER_MANIFEST",
            )
            manifest = _signer.sign(manifest)
            wire = manifest.to_wire_dict()
            wire["port"] = port
            return json.dumps(wire).encode("utf-8")
        except Exception as exc:
            logger.warning("Signing failed, falling back to unsigned: %s", exc)

    # Fallback: legacy unsigned manifest
    manifest = {
        "type": "WORKER_MANIFEST",
        "worker_id": worker_id,
        "host": host,
        "port": port,
        "gpu_info": gpu_info or {},
    }
    return json.dumps(manifest).encode("utf-8")
