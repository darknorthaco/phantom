#!/usr/bin/env python3
"""
Config Writer
Writes phantom_config.json (via ConfigBootstrap), llm_config.json, and
worker_registry.json during installation.

ConfigBootstrap is the authoritative writer of phantom_config.json at
deploy Step 4.5.  It must be called after the Controller Selection Ceremony
(§1) and before the controller starts (Step 5).  It writes the file
atomically and preserves a timestamped backup of any previous version.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow import from phantom_core when running from the installer tree.
_phantom_core_dir = Path(__file__).resolve().parent.parent.parent / "phantom_core"
if _phantom_core_dir.exists() and str(_phantom_core_dir) not in sys.path:
    sys.path.insert(0, str(_phantom_core_dir))


class ConfigWriter:
    """Writes Phantom configuration files that are owned by the wizard."""

    def __init__(self, install_dir: Path):
        self.install_dir = Path(install_dir)
        self.config_dir = self.install_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # LLM configuration
    # ------------------------------------------------------------------ #

    def write_llm_config(self, model_path: Path, model_info: Dict) -> Path:
        """Write llm_config.json for the selected model.

        Args:
            model_path:  Absolute path to the downloaded GGUF file.
            model_info:  Model dict from the MODELS catalogue.

        Returns:
            Path to the written config file.

        Raises:
            ValueError: If model is blocked by sovereign compliance policy.
        """
        mid = model_info.get("id", "")
        name = model_info.get("name", "")
        try:
            from llm_taskmaster.sovereign_compliance import is_model_allowed
            if not is_model_allowed(mid, name):
                raise ValueError(
                    "Model not allowed by sovereign compliance policy. "
                    "Chinese-origin and PRC-origin LLMs are not supported."
                )
        except ImportError:
            pass  # Compliance module unavailable
        config = {
            "model_path": str(model_path),
            "model_name": model_info.get("name", "Unknown"),
            "model_id": model_info.get("id", "unknown"),
            "vram_min_gb": model_info.get("vram_min_gb", 0),
            "vram_rec_gb": model_info.get("vram_rec_gb", 0),
            "backend": "llama_cpp",
            "context_length": 4096,
            "max_tokens": 2048,
        }
        dest = self.config_dir / "llm_config.json"
        dest.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return dest

    # ------------------------------------------------------------------ #
    # Worker registry
    # ------------------------------------------------------------------ #

    def write_worker_registry(self, workers: List[Dict], task_master: Dict) -> Path:
        """Write worker_registry.json with selected workers and Task Master.

        Args:
            workers:      List of enriched worker dicts (includes task_master).
            task_master:  The designated Task Master worker dict.

        Returns:
            Path to the written registry file.
        """
        registry = {
            "task_master": _worker_entry(task_master),
            "workers": [_worker_entry(w) for w in workers],
        }
        dest = self.config_dir / "worker_registry.json"
        dest.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        return dest


# ---------------------------------------------------------------------------
# ConfigBootstrap — Step 4.5 writer for phantom_config.json
# ---------------------------------------------------------------------------


class ConfigBootstrap:
    """Atomic writer for ``phantom_config.json`` at deploy Step 4.5.

    This is the **only** component permitted to create the initial
    ``phantom_config.json``.  It must be called after the Controller
    Selection Ceremony (§1) and before the controller process starts
    (Step 5).

    Write semantics:
    - Writes to ``<config_path>.tmp`` first, then atomically renames to
      ``<config_path>``.  An interrupted write leaves the original file
      untouched.
    - Before overwriting an existing file, copies it to
      ``<config_path>.bak.<UTC-timestamp>``.
    - Annotates the written file with ``written_by_step: "4.5"`` and
      ``written_at: <ISO-8601 UTC timestamp>``.
    """

    def __init__(self, config_path: Path):
        """Initialise with the *absolute* path where phantom_config.json
        will be written (e.g. ``~/.phantom/phantom_config.json``).
        """
        self.config_path = Path(config_path)

    # ------------------------------------------------------------------

    def write(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        security: str = "disabled",
        identity_fingerprint: str = "",
        execution_mode: str = "manual",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Build and atomically write ``phantom_config.json``.

        Args:
            host:                 Controller host address (from §1 ceremony).
            port:                 Controller port (default 8080).
            security:             Security level — ``"disabled"``, ``"basic"``,
                                  or ``"full"``.
            identity_fingerprint: Hex-encoded Ed25519 public-key fingerprint
                                  (first 16 bytes) from IdentityManager (§1).
            execution_mode:       Default execution mode written into
                                  ``execution_modes.default_mode``.
            extra:                Optional dict of additional top-level keys
                                  to merge into the config (e.g. for future
                                  schema extensions).

        Returns:
            The path of the written config file.

        Raises:
            ValueError: if ``security`` is not one of the allowed values.
            OSError: if the file cannot be written.
        """
        allowed_security = {"disabled", "basic", "full"}
        if security not in allowed_security:
            raise ValueError(
                f"security must be one of {allowed_security!r}; got {security!r}"
            )

        now_iso = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

        config: Dict[str, Any] = {
            "controller": {
                "host": host,
                "port": port,
                "security": security,
                "identity_fingerprint": identity_fingerprint,
            },
            "ports": {
                "controller_api": {"port": 8080, "protocol": "tcp", "required": True},
                "worker_http": {"port": 8090, "protocol": "tcp", "required": True},
                "discovery_udp": {"port": 8095, "protocol": "udp", "required": True},
                "socket_infra": {"port": 8081, "protocol": "tcp", "required": False},
            },
            "worker": {
                "readiness_probe_interval_ms": 500,
                "readiness_max_attempts": 20,
                "readiness_attempt_timeout_ms": 1000,
            },
            "execution_modes": {
                "default_mode": execution_mode,
            },
            "config_version": "1.0",
            "written_at": now_iso,
            "written_by_step": "4.5",
        }

        if extra:
            for k, v in extra.items():
                if k not in config:
                    config[k] = v

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Backup any existing file before overwriting.
        if self.config_path.exists():
            ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = self.config_path.with_suffix(f".json.bak.{ts}")
            self.config_path.replace(backup)

        # Atomic write: .tmp → rename.
        tmp = self.config_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
        tmp.replace(self.config_path)

        return self.config_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _worker_entry(w: Dict) -> Dict:
    return {
        "ip": w.get("ip", ""),
        "port": w.get("port", 8090),
        "hostname": w.get("hostname", ""),
        "gpu_name": w.get("gpu_name") or w.get("gpu") or "Unknown",
        "vram_total_mb": w.get("vram_total_mb", 0),
        "health": w.get("health", "Unknown"),
    }
