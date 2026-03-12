"""
Configuration loader for Phantom Windows worker.
Reuses Linux-worker config logic; adjusts paths for Windows defaults.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load worker configuration from JSON file.

    Args:
        config_path: Path to worker configuration JSON (Windows or POSIX).

    Returns:
        Config dict with worker_id, controller_host, controller_port, worker_port, etc.

    Raises:
        FileNotFoundError: If config file does not exist.
        json.JSONDecodeError: If config is invalid JSON.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in config %s: %s", config_path, e)
        raise

    return _normalize_config(data)


def _normalize_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize config with Windows-friendly defaults."""
    return {
        "worker_id": data.get("worker_id"),
        "controller_host": data.get("controller_host", "127.0.0.1"),
        "controller_port": int(data.get("controller_port", 8080)),
        "worker_port": int(data.get("worker_port", 8090)),
        "log_level": data.get("log_level", "INFO"),
        **{k: v for k, v in data.items() if k not in ("worker_id", "controller_host", "controller_port", "worker_port", "log_level")},
    }
