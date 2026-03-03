#!/usr/bin/env python3
"""
Config Writer
Writes llm_config.json and worker_registry.json during installation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


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
        """
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

    def write_worker_registry(
        self, workers: List[Dict], task_master: Dict
    ) -> Path:
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
