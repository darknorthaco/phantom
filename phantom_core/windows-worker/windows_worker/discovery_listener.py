"""
Phantom Windows worker discovery listener.
Responds to DISCOVER_WORKERS UDP broadcast with a signed manifest.
Message format identical to Linux worker.
"""

import json
import logging
import os
import socket
import threading
import time
from pathlib import Path
from typing import Optional

DISCOVERY_PORT = 8095
DISCOVER_PAYLOAD = b"PHANTOM_DISCOVER_WORKERS"

logger = logging.getLogger(__name__)

_signer: Optional[object] = None


def _init_signer(identity_dir: Optional[str] = None) -> Optional[object]:
    """Load or generate a per-worker Ed25519 keypair.
    Windows-safe: uses Path and standard file APIs.
    """
    try:
        import sys
        engine_root = Path(__file__).resolve().parent.parent.parent
        if str(engine_root) not in sys.path:
            sys.path.insert(0, str(engine_root))
        from phantom_core.discovery import ManifestSigner
    except ImportError:
        logger.warning(
            "cryptography library not available — manifests will be unsigned. "
            "Install with: pip install 'cryptography>=41.0.0'"
        )
        return None

    key_dir = Path(identity_dir) if identity_dir else Path.home() / ".phantom" / "identity"
    key_dir.mkdir(parents=True, exist_ok=True)
    priv_path = key_dir / "worker_private.key"

    if priv_path.exists():
        import base64
        raw = base64.b64decode(priv_path.read_bytes())
        return ManifestSigner.from_raw_bytes(raw)

    signer = ManifestSigner.generate()
    import base64
    raw = signer.export_private_key_bytes()
    with open(priv_path, "wb") as f:
        f.write(base64.b64encode(raw))
    os.chmod(priv_path, 0o600) if hasattr(os, "chmod") else None
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
    Windows-safe socket options (SO_REUSEADDR supported on Windows).
    """
    global _signer
    _signer = _init_signer(identity_dir)

    def listen() -> None:
        sock = None
        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", DISCOVERY_PORT))
                sock.settimeout(1.0)
                logger.info("Discovery listener on 0.0.0.0:%s", DISCOVERY_PORT)
                break
            except OSError as e:
                last_error = e
                logger.warning("Discovery listener bind attempt %d/3 failed: %s", attempt, e)
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    sock = None
                if attempt < 3:
                    time.sleep(1)
        else:
            logger.error("Discovery listener failed to bind port %s after 3 attempts: %s", DISCOVERY_PORT, last_error)
            return

        while True:
            try:
                data, addr = sock.recvfrom(512)
                if data == DISCOVER_PAYLOAD:
                    payload_bytes = _build_manifest_payload(worker_id, host, port, gpu_info)
                    sock.sendto(payload_bytes, addr)
                    logger.debug("Sent manifest to %s", addr)
            except socket.timeout:
                continue
            except Exception as e:
                logger.debug("Discovery recv: %s", e)

    t = threading.Thread(target=listen, daemon=True)
    t.start()


def _build_manifest_payload(worker_id: str, host: str, port: int, gpu_info: dict) -> bytes:
    """Build a (possibly signed) manifest payload. Format identical to Linux worker."""
    if _signer is not None:
        try:
            import sys
            engine_root = Path(__file__).resolve().parent.parent.parent
            if str(engine_root) not in sys.path:
                sys.path.insert(0, str(engine_root))
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
            wire["os"] = "windows"
            return json.dumps(wire).encode("utf-8")
        except Exception as exc:
            logger.warning("Signing failed, falling back to unsigned: %s", exc)

    manifest = {
        "type": "WORKER_MANIFEST",
        "worker_id": worker_id,
        "host": host,
        "port": port,
        "gpu_info": gpu_info or {},
        "os": "windows",
    }
    return json.dumps(manifest).encode("utf-8")
