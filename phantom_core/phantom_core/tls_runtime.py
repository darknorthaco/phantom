"""
Controller TLS runtime helpers (Phase 4).

Loads transport policy from ``phantom_config.json`` and produces uvicorn SSL kwargs.
LAN default remains plaintext; WAN requires TLS (enforced via ``validate_tls_policy``).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def load_tls_config(config_path: Path) -> Dict[str, Any]:
    """Read ``wan_mode``, ``tls_enabled``, ``tls_cert_path``, ``tls_key_path`` from config file.

    If the file is missing, returns safe LAN defaults (plaintext).
    """
    if not config_path.exists():
        return {
            "wan_mode": False,
            "tls_enabled": False,
            "tls_cert_path": "",
            "tls_key_path": "",
        }
    with open(config_path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {
        "wan_mode": bool(data.get("wan_mode", False)),
        "tls_enabled": bool(data.get("tls_enabled", False)),
        "tls_cert_path": str(data.get("tls_cert_path", "") or ""),
        "tls_key_path": str(data.get("tls_key_path", "") or ""),
    }


def validate_tls_paths(cert_path: str, key_path: str) -> None:
    """Ensure certificate and private key files exist and are non-empty.

    Raises:
        FileNotFoundError: if either path is missing.
        ValueError: if paths are empty strings.
    """
    if not cert_path or not key_path:
        raise ValueError("tls_cert_path and tls_key_path must be non-empty when TLS is enabled")
    cp = Path(cert_path)
    kp = Path(key_path)
    if not cp.is_file():
        raise FileNotFoundError(f"TLS certificate not found: {cert_path}")
    if not kp.is_file():
        raise FileNotFoundError(f"TLS private key not found: {key_path}")


def uvicorn_ssl_kwargs(config_path: Path) -> Dict[str, str]:
    """Return ``ssl_certfile`` / ``ssl_keyfile`` kwargs for uvicorn, or {} if HTTP-only.

    Validates sovereign TLS policy and paths before returning SSL parameters.
    """
    from llm_taskmaster.sovereign_compliance import validate_tls_policy

    cfg = load_tls_config(config_path)
    validate_tls_policy(
        cfg["wan_mode"],
        cfg["tls_enabled"],
        cfg["tls_cert_path"],
        cfg["tls_key_path"],
    )

    if cfg["wan_mode"]:
        logger.warning(
            "PHANTOM WAN MODE: TLS required — tls_enabled=%s (controller binding)",
            cfg["tls_enabled"],
        )

    if not cfg["tls_enabled"]:
        logger.info(
            "PHANTOM TLS: disabled (plaintext HTTP) — wan_mode=%s",
            cfg["wan_mode"],
        )
        return {}

    validate_tls_paths(cfg["tls_cert_path"], cfg["tls_key_path"])
    logger.info(
        "PHANTOM TLS: HTTPS enabled — cert=%s",
        cfg["tls_cert_path"],
    )
    return {
        "ssl_certfile": cfg["tls_cert_path"],
        "ssl_keyfile": cfg["tls_key_path"],
    }


def log_tls_state(config_path: Path) -> None:
    """Emit a single diagnostic line about effective TLS flags (after validation)."""
    cfg = load_tls_config(config_path)
    logger.info(
        "PHANTOM TLS state: wan_mode=%s tls_enabled=%s cert_configured=%s",
        cfg["wan_mode"],
        cfg["tls_enabled"],
        bool(cfg["tls_cert_path"] and cfg["tls_key_path"]),
    )
