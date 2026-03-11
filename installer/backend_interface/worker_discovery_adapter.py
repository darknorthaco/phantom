#!/usr/bin/env python3
"""
Worker Discovery Adapter — §9 Canonical Discovery.

Uses InstallerDiscoveryClient (UDP 8095, PHANTOM_DISCOVER_WORKERS,
SignedManifest) for worker discovery. Converts results to the display format
expected by the wizard GUI.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Ensure installer root is importable.
_installer_dir = Path(__file__).parent.parent
if str(_installer_dir) not in sys.path:
    sys.path.insert(0, str(_installer_dir))

from backend_interface.discovery_client import InstallerDiscoveryClient  # noqa: E402
from modules.worker_discovery import WorkerDiscovery  # noqa: E402


class WorkerDiscoveryAdapter:
    """§9 — GUI adapter using canonical UDP discovery (port 8095)."""

    # Minimum recommended VRAM (MB) for Task Master role.
    TASK_MASTER_MIN_VRAM_MB = 6_000

    def __init__(self):
        self._udp_client = InstallerDiscoveryClient()
        self._legacy = WorkerDiscovery()

    # ------------------------------------------------------------------ #
    # Network helpers (from legacy for GUI compatibility)
    # ------------------------------------------------------------------ #

    def get_local_network(self):
        """Delegate to legacy backend for network info."""
        return self._legacy.get_local_network()

    def check_worker_port(self, ip: str, port: int = None) -> bool:
        """Delegate to legacy backend for port checks."""
        return self._legacy.check_worker_port(ip, port)

    # ------------------------------------------------------------------ #
    # Discovery — §9 canonical UDP protocol
    # ------------------------------------------------------------------ #

    def discover_comprehensive(
        self, progress_cb: Callable[[str], None] = None
    ) -> List[Dict]:
        """Run discovery via UDP 8095 (canonical §9 protocol)."""
        if progress_cb:
            progress_cb("Discovering workers via UDP broadcast…")
        workers = self._discover_udp(progress_cb)
        if progress_cb:
            progress_cb(f"Scan complete — {len(workers)} worker(s) found.")
        return self._enrich(workers)

    def discover_manual(
        self, progress_cb: Callable[[str], None] = None
    ) -> List[Dict]:
        """Run discovery via UDP 8095 (same protocol as comprehensive)."""
        if progress_cb:
            progress_cb("Discovering workers via UDP broadcast…")
        workers = self._discover_udp(progress_cb)
        if progress_cb:
            progress_cb(f"Scan complete — {len(workers)} worker(s) found.")
        return self._enrich(workers)

    def _discover_udp(
        self, progress_cb: Callable[[str], None] = None
    ) -> List[Dict]:
        """Run InstallerDiscoveryClient and convert to dict format."""
        broadcast_addrs: List[str] = []
        network = self._legacy.get_local_network()
        if network is not None:
            broadcast_addrs.append(str(network.broadcast_address))

        udp_workers = self._udp_client.discover(
            broadcast_addrs=broadcast_addrs or None,
            include_localhost=True,
        )

        # Convert to dict format expected by _enrich
        result: List[Dict] = []
        for w in udp_workers:
            gpu = w.gpu_info or {}
            vram = gpu.get("memory_total") or gpu.get("vram") or gpu.get("vram_total_mb") or 0
            result.append({
                "worker_id": w.worker_id,
                "ip": w.registration_host(),
                "host": w.registration_host(),
                "hostname": w.worker_id,
                "port": w.port,
                "available": True,  # We received a response
                "gpu": gpu.get("name") or gpu.get("gpu") or "Unknown",
                "gpu_info": gpu,
                "vram_total_mb": vram,
                "memory_total": vram,
                "signature_verified": w.signature_verified,
                "public_key_b64": w.public_key_b64,
            })
        return result

    # ------------------------------------------------------------------ #
    # Enrichment helpers
    # ------------------------------------------------------------------ #

    def _enrich(self, workers: List[Dict]) -> List[Dict]:
        """Add display-friendly fields to raw worker dicts."""
        enriched = []
        for raw in workers:
            w = dict(raw)
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
        """Return True if the worker meets Task Master VRAM requirements."""
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
