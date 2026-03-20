"""
Phantom Config Schema
Single source of truth for phantom_config.json structure, field types, and defaults.

phantom_config.json is written atomically at deploy Step 4.5 by ConfigBootstrap
(installer/backend_interface/config_writer.py) and read by every subsequent step.
It must exist before the controller starts (Step 5); no component may silently fall
back to a default value when the file is absent.

Note: This file is separate from llm_config.json (LLM routing) and
worker_registry.json (worker list). Do not conflate them.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

_DEFAULT_CONTROLLER_HOST = "127.0.0.1"
_DEFAULT_CONTROLLER_PORT = 8080
_DEFAULT_SECURITY = "disabled"

_DEFAULT_PORTS: Dict[str, Any] = {
    "controller_api": {"port": 8080, "protocol": "tcp", "required": True},
    "worker_http": {"port": 8090, "protocol": "tcp", "required": True},
    "discovery_udp": {"port": 8095, "protocol": "udp", "required": True},
    "socket_infra": {"port": 8081, "protocol": "tcp", "required": False},
}

_DEFAULT_WORKER: Dict[str, Any] = {
    "readiness_probe_interval_ms": 500,
    "readiness_max_attempts": 20,
    "readiness_attempt_timeout_ms": 1000,
}

_DEFAULT_EXECUTION_MODES: Dict[str, Any] = {
    "default_mode": "manual",
}

CONFIG_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Schema dataclass
# ---------------------------------------------------------------------------


@dataclass
class ControllerConfig:
    host: str = _DEFAULT_CONTROLLER_HOST
    port: int = _DEFAULT_CONTROLLER_PORT
    security: str = _DEFAULT_SECURITY
    identity_fingerprint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "security": self.security,
            "identity_fingerprint": self.identity_fingerprint,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ControllerConfig":
        return cls(
            host=d.get("host", _DEFAULT_CONTROLLER_HOST),
            port=int(d.get("port", _DEFAULT_CONTROLLER_PORT)),
            security=d.get("security", _DEFAULT_SECURITY),
            identity_fingerprint=d.get("identity_fingerprint", ""),
        )


@dataclass
class ConfigSchema:
    """Authoritative schema for phantom_config.json.

    All deploy components (Rust deployer, Python controller, installer) must
    read runtime parameters from this file rather than from hardcoded constants
    or environment variables.
    """

    controller: ControllerConfig = field(default_factory=ControllerConfig)
    ports: Dict[str, Any] = field(default_factory=lambda: dict(_DEFAULT_PORTS))
    worker: Dict[str, Any] = field(default_factory=lambda: dict(_DEFAULT_WORKER))
    execution_modes: Dict[str, Any] = field(
        default_factory=lambda: dict(_DEFAULT_EXECUTION_MODES)
    )
    config_version: str = CONFIG_VERSION
    written_at: str = ""
    written_by_step: str = "4.5"
    # Phase 4 — WAN / TLS (explicit; LAN plaintext default unchanged)
    wan_mode: bool = False
    tls_enabled: bool = False
    tls_cert_path: str = ""
    tls_key_path: str = ""

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "controller": self.controller.to_dict(),
            "ports": self.ports,
            "worker": self.worker,
            "execution_modes": self.execution_modes,
            "config_version": self.config_version,
            "written_at": self.written_at,
            "written_by_step": self.written_by_step,
            "wan_mode": self.wan_mode,
            "tls_enabled": self.tls_enabled,
            "tls_cert_path": self.tls_cert_path,
            "tls_key_path": self.tls_key_path,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConfigSchema":
        controller_block = d.get("controller", {})
        return cls(
            controller=ControllerConfig.from_dict(controller_block),
            ports=d.get("ports", dict(_DEFAULT_PORTS)),
            worker=d.get("worker", dict(_DEFAULT_WORKER)),
            execution_modes=d.get("execution_modes", dict(_DEFAULT_EXECUTION_MODES)),
            config_version=d.get("config_version", CONFIG_VERSION),
            written_at=d.get("written_at", ""),
            written_by_step=d.get("written_by_step", "4.5"),
            wan_mode=bool(d.get("wan_mode", False)),
            tls_enabled=bool(d.get("tls_enabled", False)),
            tls_cert_path=str(d.get("tls_cert_path", "") or ""),
            tls_key_path=str(d.get("tls_key_path", "") or ""),
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Raise ValueError if any required field is invalid.

        Raises:
            ValueError: with a human-readable description of the first
                failing constraint.
        """
        valid_security = {"disabled", "basic", "full", "enhanced", "enterprise"}
        if self.controller.security not in valid_security:
            raise ValueError(
                f"controller.security must be one of {valid_security!r}; "
                f"got {self.controller.security!r}"
            )

        if not (1 <= self.controller.port <= 65535):
            raise ValueError(
                f"controller.port must be 1–65535; got {self.controller.port}"
            )

        if not self.controller.host:
            raise ValueError("controller.host must not be empty")

        required_port_keys = {"controller_api", "worker_http", "discovery_udp"}
        missing = required_port_keys - set(self.ports.keys())
        if missing:
            raise ValueError(f"ports block is missing required entries: {missing!r}")

        required_worker_keys = {
            "readiness_probe_interval_ms",
            "readiness_max_attempts",
            "readiness_attempt_timeout_ms",
        }
        missing_worker = required_worker_keys - set(self.worker.keys())
        if missing_worker:
            raise ValueError(
                f"worker block is missing required keys: {missing_worker!r}"
            )

        from llm_taskmaster.sovereign_compliance import validate_tls_policy

        validate_tls_policy(
            self.wan_mode,
            self.tls_enabled,
            self.tls_cert_path,
            self.tls_key_path,
        )
        if self.tls_enabled:
            from .tls_runtime import validate_tls_paths

            validate_tls_paths(self.tls_cert_path, self.tls_key_path)

    # ------------------------------------------------------------------
    # File I/O helpers
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "ConfigSchema":
        """Load and parse phantom_config.json from *path*.

        Raises:
            FileNotFoundError: if the file does not exist.
            ValueError: if the file fails schema validation.
        """
        if not path.exists():
            raise FileNotFoundError(
                f"phantom_config.json not found at {path}. "
                "The config file must be written at deploy Step 4.5 "
                "(ConfigBootstrap) before the controller starts."
            )
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        schema = cls.from_dict(data)
        schema.validate()
        return schema


# ---------------------------------------------------------------------------
# Convenience: locate phantom_config.json from the environment
# ---------------------------------------------------------------------------


def locate_phantom_config() -> Path:
    """Return the expected path to phantom_config.json.

    Checks (in order):
    1. ``PHANTOM_CONFIG_PATH`` env var (explicit override).
    2. ``PHANTOM_STATE_DIR`` env var → parent directory.
    3. ``~/.phantom/phantom_config.json`` (Tauri default).
    """
    explicit = os.getenv("PHANTOM_CONFIG_PATH")
    if explicit:
        return Path(explicit)

    state_dir = os.getenv("PHANTOM_STATE_DIR")
    if state_dir:
        return Path(state_dir).parent / "phantom_config.json"

    home = Path.home()
    return home / ".phantom" / "phantom_config.json"
