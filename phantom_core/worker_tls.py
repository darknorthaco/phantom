"""
Worker ↔ controller HTTP(S) helpers (Phase 4).

Imported by linux-worker and windows-worker when PYTHONPATH includes the
``phantom_core`` tree root (same layout as ``run.py``).
"""

from __future__ import annotations

from pathlib import Path


def controller_base_url(host: str, port: int, tls_enabled: bool) -> str:
    """Build base URL with explicit scheme — no silent HTTPS→HTTP downgrade."""
    scheme = "https" if tls_enabled else "http"
    return f"{scheme}://{host}:{port}"


def httpx_verify_for_worker(tls_enabled: bool, tls_controller_cert_path: str):
    """Return httpx ``verify`` argument: ``True`` for HTTP; cert path for HTTPS pin."""
    if not tls_enabled:
        return True
    if not tls_controller_cert_path:
        raise ValueError(
            "tls_controller_cert_path is required when tls_enabled is true (WAN/LAN TLS)."
        )
    p = Path(tls_controller_cert_path)
    if not p.is_file():
        raise FileNotFoundError(
            f"tls_controller_cert_path does not exist: {tls_controller_cert_path}"
        )
    return str(p)
