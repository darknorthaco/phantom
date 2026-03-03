#!/usr/bin/env python3
"""
WSL Orchestrator — READ-ONLY
Detects WSL2 status and provides user-facing instructions.

GOVERNANCE:
    • This module NEVER runs ``wsl --install``.
    • This module NEVER runs ``Enable-WindowsOptionalFeature``.
    • This module NEVER runs ``DISM``.
    • This module NEVER modifies any Windows feature.
    • All "actions" are returned as display-only instruction strings.
    • All checks are read-only subprocess queries.
"""
from __future__ import annotations

import subprocess
import sys
from enum import Enum
from typing import Optional, Tuple


class WSLStatus(Enum):
    """Read-only WSL2 availability status."""

    NOT_AVAILABLE = "not_available"        # wsl.exe not found on PATH
    FEATURE_DISABLED = "feature_disabled"  # Windows feature not enabled
    KERNEL_MISSING = "kernel_missing"      # WSL2 kernel not installed
    NO_DISTRO = "no_distro"               # No Linux distribution installed
    READY = "ready"                        # WSL2 is operational


# ---------------------------------------------------------------------------
# User-facing instruction strings (NEVER executed)
# ---------------------------------------------------------------------------

_INSTRUCTIONS = {
    WSLStatus.NOT_AVAILABLE: (
        "WSL is not available on this system.\n\n"
        "To enable WSL, open PowerShell as Administrator and run:\n"
        "    wsl --install\n\n"
        "This requires a system restart after completion."
    ),
    WSLStatus.FEATURE_DISABLED: (
        "The Windows Subsystem for Linux feature is not enabled.\n\n"
        "To enable it:\n"
        "  1. Open Settings → Apps → Optional Features\n"
        "  2. Click 'More Windows features'\n"
        "  3. Enable 'Windows Subsystem for Linux'\n"
        "  4. Enable 'Virtual Machine Platform'\n"
        "  5. Restart your computer\n\n"
        "Alternatively, open PowerShell as Administrator and run:\n"
        "    wsl --install"
    ),
    WSLStatus.KERNEL_MISSING: (
        "The WSL2 Linux kernel update is required.\n\n"
        "Download and install it from:\n"
        "    https://aka.ms/wsl2kernel\n\n"
        "After installation, restart your computer."
    ),
    WSLStatus.NO_DISTRO: (
        "No Linux distribution is installed in WSL.\n\n"
        "To install one:\n"
        "  1. Open the Microsoft Store\n"
        "  2. Search for 'Ubuntu 22.04 LTS'\n"
        "  3. Click Install\n"
        "  4. Launch Ubuntu and set up a user account\n\n"
        "Alternatively, open PowerShell and run:\n"
        "    wsl --install -d Ubuntu-22.04"
    ),
    WSLStatus.READY: (
        "WSL2 is installed and operational.\n"
        "No action required."
    ),
}


class WSLOrchestrator:
    """Read-only WSL2 status detection.

    This class performs ONLY non-modifying checks to determine the
    current state of WSL on the host system.  It never alters system
    configuration.
    """

    def __init__(self):
        self._cached_status: Optional[WSLStatus] = None
        self._cached_version: Optional[str] = None
        self._cached_distro: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def detect_wsl_status(self) -> WSLStatus:
        """Detect current WSL2 status using read-only queries.

        Returns:
            WSLStatus enum indicating the current state.
        """
        if sys.platform != "win32":
            self._cached_status = WSLStatus.NOT_AVAILABLE
            return self._cached_status

        # Check 1: Does wsl.exe exist?
        if not self._wsl_exe_exists():
            self._cached_status = WSLStatus.NOT_AVAILABLE
            return self._cached_status

        # Check 2: Can we query WSL status?
        status_ok, status_output = self._run_wsl_status()
        if not status_ok:
            # wsl.exe exists but --status fails → feature likely disabled
            self._cached_status = WSLStatus.FEATURE_DISABLED
            return self._cached_status

        # Check 3: Is the kernel installed?
        if not self._kernel_installed(status_output):
            self._cached_status = WSLStatus.KERNEL_MISSING
            return self._cached_status

        # Check 4: Is a default distro available?
        if not self._distro_available():
            self._cached_status = WSLStatus.NO_DISTRO
            return self._cached_status

        self._cached_status = WSLStatus.READY
        return self._cached_status

    def get_user_instructions(self, status: Optional[WSLStatus] = None) -> str:
        """Return human-readable instructions for the given status.

        If status is None, uses the last detected status.
        These instructions are NEVER executed — they are display-only.
        """
        if status is None:
            status = self._cached_status or self.detect_wsl_status()
        return _INSTRUCTIONS.get(status, "Unknown WSL status.")

    def is_reboot_required(self, status: Optional[WSLStatus] = None) -> bool:
        """Return True if the WSL status typically requires a reboot.

        A reboot is expected after:
            - Enabling the WSL Windows feature (FEATURE_DISABLED)
            - Installing the WSL2 kernel (KERNEL_MISSING)
        """
        if status is None:
            status = self._cached_status or self.detect_wsl_status()
        return status in (WSLStatus.FEATURE_DISABLED, WSLStatus.KERNEL_MISSING)

    def get_status_summary(self) -> dict:
        """Return a dict summarising WSL status for the GUI."""
        status = self._cached_status or self.detect_wsl_status()
        return {
            "status": status.value,
            "status_display": status.name.replace("_", " ").title(),
            "ready": status == WSLStatus.READY,
            "reboot_required": self.is_reboot_required(status),
            "instructions": self.get_user_instructions(status),
            "kernel_version": self._cached_version or "Unknown",
            "default_distro": self._cached_distro or "None",
        }

    # ------------------------------------------------------------------ #
    # Read-only detection helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _wsl_exe_exists() -> bool:
        """Check if wsl.exe is on the system PATH (read-only)."""
        import shutil
        return shutil.which("wsl") is not None

    @staticmethod
    def _run_wsl_status() -> Tuple[bool, str]:
        """Run ``wsl --status`` and return (success, stdout).

        This is a read-only query — it does not modify the system.
        """
        try:
            result = subprocess.run(
                ["wsl", "--status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0, result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False, ""

    def _kernel_installed(self, status_output: str) -> bool:
        """Parse wsl --status output to check for kernel version."""
        # WSL --status output typically contains "Kernel version: x.y.z"
        for line in status_output.splitlines():
            lower = line.lower().strip()
            if "kernel version" in lower or "kernel" in lower:
                # Extract version if present
                parts = line.split(":", 1)
                if len(parts) > 1:
                    version = parts[1].strip()
                    if version and version[0].isdigit():
                        self._cached_version = version
                        return True
        # If wsl --status succeeded but no kernel line found, assume kernel exists
        # (newer WSL versions don't always show kernel line)
        if status_output.strip():
            return True
        return False

    def _distro_available(self) -> bool:
        """Check if any Linux distribution is installed (read-only).

        Uses ``wsl --list --quiet`` which is a non-modifying command.
        """
        try:
            result = subprocess.run(
                ["wsl", "--list", "--quiet"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False

            # Filter empty lines and "Windows Subsystem for Linux" header
            distros = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and "windows subsystem" not in line.lower()
            ]
            # wsl --list output on Windows may contain null bytes (UTF-16)
            # Try decoding if needed
            if not distros and result.stdout:
                try:
                    decoded = result.stdout.encode("utf-8").decode("utf-16-le", errors="ignore")
                    distros = [
                        line.strip()
                        for line in decoded.splitlines()
                        if line.strip() and "windows subsystem" not in line.lower()
                    ]
                except (UnicodeDecodeError, UnicodeEncodeError):
                    pass

            if distros:
                self._cached_distro = distros[0]
                return True
            return False

        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False
