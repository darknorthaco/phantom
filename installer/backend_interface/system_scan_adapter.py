#!/usr/bin/env python3
"""
System Scan Adapter
Wraps installer/modules/system_check.SystemChecker for GUI use.
Calls existing backend — does NOT implement its own system-check logic.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Dict, List

# Ensure installer root is importable regardless of working directory.
_installer_dir = Path(__file__).parent.parent
if str(_installer_dir) not in sys.path:
    sys.path.insert(0, str(_installer_dir))

from modules.system_check import SystemChecker  # noqa: E402


def run_system_scan(ports: List[int] = None) -> Dict:
    """Run all system checks and return a structured result dict.

    Delegates entirely to the existing ``SystemChecker`` backend.

    Returns a dict with keys:
        ok      – True if no critical checks failed
        checks  – dict keyed by check name, each value is
                  {"name": str, "status": "ok"|"warning"|"fail", "detail": str}
        passed, warnings, failed – raw string lists from SystemChecker
    """
    if ports is None:
        ports = [8080, 8081]

    checker = SystemChecker()

    # --- run individual checks so we can map them to display rows ---

    # OS check
    os_ok = checker.check_os_capabilities()
    os_detail = (
        f"{checker.os_type} {checker.os_version[:60]}"
        if os_ok
        else f"Unsupported OS: {checker.os_type}"
    )

    # Python check
    pv = checker.python_version
    python_ok = checker.check_python_version()
    python_detail = (
        f"{pv.major}.{pv.minor}.{pv.micro}"
        if python_ok
        else f"{pv.major}.{pv.minor}.{pv.micro} (3.8+ required)"
    )

    # Disk check
    disk_ok = checker.check_disk_space(min_gb=5.0)
    disk_detail = ""
    for msg in checker.checks_passed + checker.checks_warnings + checker.checks_failed:
        if "disk" in msg.lower():
            disk_detail = msg
            break
    if not disk_detail:
        disk_detail = "OK" if disk_ok else "Insufficient disk space"

    # Virtual-env check (non-blocking)
    checker.check_virtual_env_capability()

    # Port check
    port_results = checker.check_port_availability(ports)
    all_free = all(port_results.values())
    in_use = [str(p) for p, free in port_results.items() if not free]
    ports_detail = (
        "All required ports available"
        if all_free
        else f"Port(s) in use: {', '.join(in_use)}"
    )

    # GPU detection (best-effort; not critical)
    gpu_status, gpu_detail = _detect_gpu()

    checks = {
        "os": {
            "name": "Operating System",
            "status": "ok" if os_ok else "fail",
            "detail": os_detail,
        },
        "python": {
            "name": "Python Version",
            "status": "ok" if python_ok else "fail",
            "detail": python_detail,
        },
        "disk": {
            "name": "Disk Space (≥ 5 GB)",
            "status": "ok" if disk_ok else "warning",
            "detail": disk_detail,
        },
        "ports": {
            "name": f"Ports {', '.join(str(p) for p in ports)}",
            "status": "ok" if all_free else "warning",
            "detail": ports_detail,
        },
        "gpu": {
            "name": "GPU",
            "status": gpu_status,
            "detail": gpu_detail,
        },
    }

    report = checker.get_report()
    critical_fail = not os_ok or not python_ok

    return {
        "ok": not critical_fail,
        "checks": checks,
        "passed": report["passed"],
        "warnings": report["warnings"],
        "failed": report["failed"],
    }


def _detect_gpu():
    """Best-effort GPU detection. Returns (status, detail) strings."""
    # Try NVIDIA
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            first_line = result.stdout.strip().splitlines()[0]
            return "ok", f"NVIDIA: {first_line}"
    except Exception:
        pass

    # Try AMD ROCm
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return "ok", "AMD GPU detected (ROCm)"
    except Exception:
        pass

    return "warning", "No GPU detected — CPU mode will be used"
