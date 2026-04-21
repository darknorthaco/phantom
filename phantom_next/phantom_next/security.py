"""Security policy primitives for Phantom vNext."""

from pathlib import Path


def validate_tls_policy(
    *,
    wan_mode: bool,
    tls_enabled: bool,
    tls_cert_path: str = "",
    tls_key_path: str = "",
) -> None:
    """
    Enforce fail-closed network policy.

    - WAN mode requires TLS.
    - TLS mode requires cert and key files to exist.
    """
    if wan_mode and not tls_enabled:
        raise ValueError("wan_mode requires tls_enabled")

    if tls_enabled:
        if not tls_cert_path or not tls_key_path:
            raise ValueError("tls_enabled requires tls_cert_path and tls_key_path")
        if not Path(tls_cert_path).exists():
            raise ValueError(f"tls_cert_path does not exist: {tls_cert_path}")
        if not Path(tls_key_path).exists():
            raise ValueError(f"tls_key_path does not exist: {tls_key_path}")
