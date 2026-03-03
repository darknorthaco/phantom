#!/usr/bin/env python3
"""
Worker Discovery Adapter
Wraps installer/modules/worker_discovery.WorkerDiscovery for GUI use.

The wizard MUST NOT implement its own scanning logic.
This adapter delegates entirely to the existing WorkerDiscovery backend.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Ensure installer root is importable.
_installer_dir = Path(__file__).parent.parent
if str(_installer_dir) not in sys.path:
    sys.path.insert(0, str(_installer_dir))

from modules.worker_discovery import WorkerDiscovery  # noqa: E402


class WorkerDiscoveryAdapter:
    """GUI adapter for the existing WorkerDiscovery backend.

    All discovery calls are forwarded verbatim to WorkerDiscovery.
    This class only adds display-friendly enrichment and Task Master
    suitability checks on top of the raw backend results.
    """

    # Minimum recommended VRAM (MB) for Task Master role.
    # A value of 0 means VRAM is unknown — allowed with a warning.
    TASK_MASTER_MIN_VRAM_MB = 6_000

    def __init__(self):
        self._backend = WorkerDiscovery()

    # ------------------------------------------------------------------ #
    # Direct backend delegation
    # ------------------------------------------------------------------ #

    def get_local_network(self):
        """Delegate to backend get_local_network()."""
        return self._backend.get_local_network()

    def check_worker_port(self, ip: str, port: int = None) -> bool:
        """Delegate to backend check_worker_port()."""
        return self._backend.check_worker_port(ip, port)

    # ------------------------------------------------------------------ #
    # Discovery modes (delegate to backend, then enrich)
    # ------------------------------------------------------------------ #

    def discover_comprehensive(
        self, progress_cb: Callable[[str], None] = None
    ) -> List[Dict]:
        """Run comprehensive discovery via backend.discover_workers_comprehensive()."""
        if progress_cb:
            progress_cb("Starting comprehensive worker scan…")
        workers = self._backend.discover_workers_comprehensive()
        if progress_cb:
            progress_cb(f"Scan complete — {len(workers)} worker(s) found.")
        return self._enrich(workers)

    def discover_manual(
        self, progress_cb: Callable[[str], None] = None
    ) -> List[Dict]:
        """Run manual discovery via backend.discover_workers_manual()."""
        if progress_cb:
            progress_cb("Starting manual network scan (ping sweep)…")
        workers = self._backend.discover_workers_manual()
        if progress_cb:
            progress_cb(f"Scan complete — {len(workers)} worker(s) found.")
        return self._enrich(workers)

    # ------------------------------------------------------------------ #
    # Enrichment helpers
    # ------------------------------------------------------------------ #

    def _enrich(self, workers: List[Dict]) -> List[Dict]:
        """Add display-friendly fields to raw backend worker dicts."""
        enriched = []
        for raw in workers:
            w = dict(raw)
            # Normalise VRAM field — backend may use different key names.
            vram_mb = (
                raw.get("vram_total_mb")
                or raw.get("memory_total")
                or 0
            )
            w["gpu_name"] = raw.get("gpu") or raw.get("gpu_name") or "Unknown"
            w["vram_total_mb"] = vram_mb
            w["vram_display"] = (
                f"{vram_mb / 1024:.1f} GB" if vram_mb > 0 else "Unknown"
            )
            w["health"] = "Healthy" if raw.get("available", False) else "Unknown"
            enriched.append(w)
        return enriched

    # ------------------------------------------------------------------ #
    # Task Master suitability
    # ------------------------------------------------------------------ #

    def is_suitable_task_master(self, worker: Dict) -> bool:
        """Return True if the worker meets Task Master VRAM requirements.

        Workers with unknown VRAM (0) are allowed with a warning.
        """
        vram_mb = worker.get("vram_total_mb", 0)
        return vram_mb == 0 or vram_mb >= self.TASK_MASTER_MIN_VRAM_MB

    def get_task_master_message(
        self, worker: Dict, model_vram_min_gb: float
    ) -> str:
        """Return a human-readable validation message for Task Master assignment."""
        vram_mb = worker.get("vram_total_mb", 0)
        if vram_mb == 0:
            return "⚠  VRAM unknown — compatibility cannot be verified."
        required_mb = model_vram_min_gb * 1024
        if vram_mb >= required_mb:
            return (
                f"✓  Task Master has sufficient VRAM "
                f"({vram_mb / 1024:.1f} GB ≥ {model_vram_min_gb:.0f} GB required)"
            )
        return (
            f"⚠  Task Master may have insufficient VRAM "
            f"({vram_mb / 1024:.1f} GB < {model_vram_min_gb:.0f} GB required)"
        )
