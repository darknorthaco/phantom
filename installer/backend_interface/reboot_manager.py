#!/usr/bin/env python3
"""
Reboot Manager
Manages the installer's reboot-resume lifecycle.

GOVERNANCE:
    • This module NEVER triggers a reboot.
    • This module NEVER writes to the Windows registry.
    • This module NEVER executes Restart-Computer or shutdown commands.
    • The ONLY auto-resume mechanism is a user-space Startup folder shortcut.
    • All state is persisted to a plain JSON file.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Installer phases (state machine)
# ---------------------------------------------------------------------------

class InstallerPhase(str, Enum):
    """Deterministic phase identifiers for the installer state machine."""

    INIT = "INIT"
    SYSTEM_SCAN = "SYSTEM_SCAN"
    DEPENDENCY_FETCH = "DEPENDENCY_FETCH"
    REBOOT_PENDING = "REBOOT_PENDING"
    REBOOT_RESUME = "REBOOT_RESUME"
    VENV_SETUP = "VENV_SETUP"
    COMPONENT_INSTALL = "COMPONENT_INSTALL"
    MODEL_FETCH = "MODEL_FETCH"
    WORKER_BOOTSTRAP = "WORKER_BOOTSTRAP"
    VALIDATION = "VALIDATION"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


# Ordered progression (excluding conditional / terminal phases).
PHASE_ORDER: List[InstallerPhase] = [
    InstallerPhase.INIT,
    InstallerPhase.SYSTEM_SCAN,
    InstallerPhase.DEPENDENCY_FETCH,
    InstallerPhase.VENV_SETUP,
    InstallerPhase.COMPONENT_INSTALL,
    InstallerPhase.MODEL_FETCH,
    InstallerPhase.WORKER_BOOTSTRAP,
    InstallerPhase.VALIDATION,
    InstallerPhase.COMPLETE,
]


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

_DEFAULT_STATE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Phantom"
STATE_FILENAME = "installer_state.json"


class InstallerState:
    """Serialisable state for the installer state machine.

    This object is flushed to disk after every phase transition.
    It is the single source of truth for reboot-resume.
    """

    def __init__(self, install_dir: Optional[Path] = None):
        self.version: str = "1.0.0"
        self.schema: str = "phantom-installer-state-v1"
        self.install_id: str = str(uuid.uuid4())
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.updated_at: str = self.created_at

        self.current_phase: InstallerPhase = InstallerPhase.INIT
        self.completed_phases: List[str] = []

        self.install_dir: str = str(install_dir or (Path.home() / "phantom"))
        self.install_type: str = "all"
        self.selected_components: List[str] = []

        self.system_scan_result: Dict[str, Any] = {}
        self.reboot_required: bool = False
        self.resume_after_reboot: bool = False
        self.resume_phase: Optional[str] = None
        self.reboot_reason: Optional[str] = None
        self.reboot_requested_at: Optional[str] = None
        self.resume_shortcut_path: Optional[str] = None

        self.model_selection: Optional[Dict] = None
        self.worker_configs: List[Dict] = []

        self.error_log: List[Dict] = []
        self.rollback_manifest: List[Dict] = []

    def to_dict(self) -> Dict:
        return {
            "$schema": self.schema,
            "version": self.version,
            "install_id": self.install_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_phase": self.current_phase.value if isinstance(self.current_phase, InstallerPhase) else self.current_phase,
            "completed_phases": self.completed_phases,
            "install_dir": self.install_dir,
            "install_type": self.install_type,
            "selected_components": self.selected_components,
            "system_scan_result": self.system_scan_result,
            "reboot_required": self.reboot_required,
            "resume_after_reboot": self.resume_after_reboot,
            "resume_phase": self.resume_phase,
            "reboot_reason": self.reboot_reason,
            "reboot_requested_at": self.reboot_requested_at,
            "resume_shortcut_path": self.resume_shortcut_path,
            "model_selection": self.model_selection,
            "worker_configs": self.worker_configs,
            "error_log": self.error_log,
            "rollback_manifest": self.rollback_manifest,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "InstallerState":
        state = cls()
        state.version = data.get("version", "1.0.0")
        state.schema = data.get("$schema", "phantom-installer-state-v1")
        state.install_id = data.get("install_id", str(uuid.uuid4()))
        state.created_at = data.get("created_at", state.created_at)
        state.updated_at = data.get("updated_at", state.updated_at)
        try:
            state.current_phase = InstallerPhase(data.get("current_phase", "INIT"))
        except ValueError:
            state.current_phase = InstallerPhase.INIT
        state.completed_phases = data.get("completed_phases", [])
        state.install_dir = data.get("install_dir", str(Path.home() / "phantom"))
        state.install_type = data.get("install_type", "all")
        state.selected_components = data.get("selected_components", [])
        state.system_scan_result = data.get("system_scan_result", {})
        state.reboot_required = data.get("reboot_required", False)
        state.resume_after_reboot = data.get("resume_after_reboot", False)
        state.resume_phase = data.get("resume_phase")
        state.reboot_reason = data.get("reboot_reason")
        state.reboot_requested_at = data.get("reboot_requested_at")
        state.resume_shortcut_path = data.get("resume_shortcut_path")
        state.model_selection = data.get("model_selection")
        state.worker_configs = data.get("worker_configs", [])
        state.error_log = data.get("error_log", [])
        state.rollback_manifest = data.get("rollback_manifest", [])
        return state


# ---------------------------------------------------------------------------
# Reboot Manager
# ---------------------------------------------------------------------------

class RebootManager:
    """Manages installer state persistence and reboot-resume lifecycle.

    CRITICAL CONSTRAINTS:
        • NEVER triggers a system reboot.
        • NEVER writes to Windows registry (HKLM / HKCU).
        • ONLY writes a .lnk shortcut to the user-space Startup folder.
        • All state is in a single JSON file.
    """

    def __init__(self, state_dir: Optional[Path] = None):
        self._state_dir = Path(state_dir) if state_dir else _DEFAULT_STATE_DIR
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._state_dir / STATE_FILENAME
        self._state: Optional[InstallerState] = None

    # ------------------------------------------------------------------ #
    # State persistence
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> InstallerState:
        if self._state is None:
            self._state = self.load_state() or InstallerState()
        return self._state

    def load_state(self) -> Optional[InstallerState]:
        """Load installer state from disk.  Returns None if no state file."""
        if not self._state_file.exists():
            return None
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            self._state = InstallerState.from_dict(data)
            return self._state
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def save_state(self) -> Path:
        """Flush current state to disk.  Returns path to state file."""
        self.state.updated_at = datetime.now(timezone.utc).isoformat()
        self._state_file.write_text(
            json.dumps(self.state.to_dict(), indent=2),
            encoding="utf-8",
        )
        return self._state_file

    def has_resume_state(self) -> bool:
        """Return True if a valid resume state exists on disk."""
        loaded = self.load_state()
        if loaded is None:
            return False
        return loaded.resume_phase is not None and loaded.resume_after_reboot

    def delete_state(self) -> None:
        """Remove the state file (e.g. after successful completion)."""
        if self._state_file.exists():
            self._state_file.unlink()
        self._state = None

    # ------------------------------------------------------------------ #
    # Phase transitions
    # ------------------------------------------------------------------ #

    def advance_phase(self, new_phase: InstallerPhase) -> None:
        """Record a phase transition and persist to disk."""
        old = self.state.current_phase
        if isinstance(old, InstallerPhase):
            old_value = old.value
        else:
            old_value = str(old)

        if old_value not in self.state.completed_phases:
            self.state.completed_phases.append(old_value)

        self.state.current_phase = new_phase
        self.save_state()

    def record_error(self, phase: str, error: str, action: str = "logged") -> None:
        """Append an error to the state's error log."""
        self.state.error_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": phase,
            "error": str(error),
            "action": action,
            "resolved": False,
        })
        self.save_state()

    def add_rollback_entry(
        self,
        phase: str,
        created_dirs: List[str] = None,
        created_files: List[str] = None,
        rollback_action: str = "delete_listed",
    ) -> None:
        """Record what a phase created, for rollback on failure."""
        self.state.rollback_manifest.append({
            "phase": phase,
            "created_dirs": created_dirs or [],
            "created_files": created_files or [],
            "rollback_action": rollback_action,
        })
        self.save_state()

    # ------------------------------------------------------------------ #
    # Reboot preparation (NON-PRIVILEGED)
    # ------------------------------------------------------------------ #

    def prepare_reboot_resume(
        self,
        reason: str,
        exe_path: Optional[str] = None,
    ) -> str:
        """Prepare for a user-initiated reboot.

        DOES NOT trigger a reboot.  Only:
            1. Records reboot state.
            2. Creates a Startup-folder shortcut for auto-resume.

        Args:
            reason:   Human-readable reason for the reboot.
            exe_path: Path to the installer EXE (or script) for the shortcut.
                      Defaults to sys.executable + current script.

        Returns:
            Path to the created startup shortcut (or empty string if creation
            was skipped / failed).
        """
        self.state.reboot_required = True
        self.state.resume_after_reboot = False  # Set to True after actual reboot
        self.state.resume_phase = InstallerPhase.REBOOT_RESUME.value
        self.state.reboot_reason = reason
        self.state.reboot_requested_at = datetime.now(timezone.utc).isoformat()

        shortcut_path = self._create_startup_shortcut(exe_path)
        self.state.resume_shortcut_path = shortcut_path

        self.advance_phase(InstallerPhase.REBOOT_PENDING)
        return shortcut_path

    def complete_resume(self) -> None:
        """Called after a successful post-reboot resume verification.

        Cleans up the startup shortcut and resets reboot flags.
        """
        self.state.resume_after_reboot = False
        self.state.resume_phase = None
        self.state.reboot_required = False

        # Remove Startup shortcut
        shortcut = self.state.resume_shortcut_path
        if shortcut and Path(shortcut).exists():
            try:
                Path(shortcut).unlink()
            except OSError:
                pass
        self.state.resume_shortcut_path = None
        self.save_state()

    # ------------------------------------------------------------------ #
    # Startup folder shortcut (NON-PRIVILEGED)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_startup_folder() -> Path:
        """Return the per-user Startup folder path.

        This is %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup
        on Windows.  Non-admin writable.
        """
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        # Fallback for non-Windows or missing APPDATA
        return Path.home() / ".config" / "autostart"

    def _create_startup_shortcut(self, exe_path: Optional[str] = None) -> str:
        """Create a .lnk shortcut in the Startup folder for auto-resume.

        This is the NON-PRIVILEGED resume mechanism — it runs at user
        logon without requiring admin.  The shortcut invokes:
            <exe_path> --resume

        Returns:
            Path to the shortcut file, or empty string on failure.
        """
        startup_dir = self._get_startup_folder()
        if not startup_dir.exists():
            try:
                startup_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                return ""

        shortcut_path = startup_dir / "PhantomInstallerResume.lnk"

        # Determine the target executable
        if exe_path is None:
            # Running from script: use python + phantom_wizard.py --resume
            exe_path = sys.executable

        # Try to create a Windows .lnk via PowerShell (non-privileged)
        if sys.platform == "win32":
            return self._create_lnk_windows(shortcut_path, exe_path)
        else:
            # On non-Windows, create a .desktop or shell script
            return self._create_resume_script(shortcut_path, exe_path)

    def _create_lnk_windows(self, shortcut_path: Path, exe_path: str) -> str:
        """Create a .lnk shortcut using PowerShell WScript.Shell COM.

        This is a non-privileged operation — WScript.Shell is available
        to standard users.
        """
        import subprocess

        # Determine arguments
        # If exe_path is python.exe, pass the wizard script as arg
        installer_dir = Path(__file__).parent.parent
        wizard_script = installer_dir / "phantom_wizard.py"

        if "python" in Path(exe_path).name.lower():
            target = exe_path
            arguments = f'"{wizard_script}" --resume'
        else:
            target = exe_path
            arguments = "--resume"

        working_dir = str(self._state_dir)

        # PowerShell script to create shortcut (non-privileged)
        ps_script = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$sc = $ws.CreateShortcut("{shortcut_path}"); '
            f'$sc.TargetPath = "{target}"; '
            f'$sc.Arguments = \'{arguments}\'; '
            f'$sc.WorkingDirectory = "{working_dir}"; '
            f'$sc.Description = "Phantom Installer - Resume after reboot"; '
            f'$sc.Save()'
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and shortcut_path.exists():
                return str(shortcut_path)
        except Exception:
            pass

        # Fallback: create a .bat file instead of .lnk
        bat_path = shortcut_path.with_suffix(".bat")
        try:
            bat_path.write_text(
                f'@echo off\n'
                f'cd /d "{working_dir}"\n'
                f'"{target}" {arguments}\n',
                encoding="utf-8",
            )
            return str(bat_path)
        except OSError:
            return ""

    def _create_resume_script(self, shortcut_path: Path, exe_path: str) -> str:
        """Create a shell script for non-Windows auto-resume."""
        script_path = shortcut_path.with_suffix(".sh")
        installer_dir = Path(__file__).parent.parent
        wizard_script = installer_dir / "phantom_wizard.py"

        try:
            script_path.write_text(
                f'#!/bin/sh\n'
                f'"{exe_path}" "{wizard_script}" --resume\n',
                encoding="utf-8",
            )
            script_path.chmod(0o755)
            return str(script_path)
        except OSError:
            return ""

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    def get_resume_screen_index(self) -> int:
        """Map the current phase to the wizard screen index for resume.

        Returns the screen index where the wizard should open after resume.
        The mapping corresponds to the extended screen list:
            0=Welcome, 1=SystemScan, 2=DependencyFetch, 3=RebootPrompt,
            4=Resume, 5=WorkerDiscovery, 6=WorkerSelection,
            7=ModelSelection, 8=ModelDownload, 9=Installation,
            10=Completion
        """
        phase = self.state.current_phase
        if isinstance(phase, str):
            try:
                phase = InstallerPhase(phase)
            except ValueError:
                return 0

        screen_map = {
            InstallerPhase.INIT: 0,
            InstallerPhase.SYSTEM_SCAN: 1,
            InstallerPhase.DEPENDENCY_FETCH: 2,
            InstallerPhase.REBOOT_PENDING: 3,
            InstallerPhase.REBOOT_RESUME: 4,
            InstallerPhase.VENV_SETUP: 5,
            InstallerPhase.COMPONENT_INSTALL: 5,
            InstallerPhase.MODEL_FETCH: 7,
            InstallerPhase.WORKER_BOOTSTRAP: 9,
            InstallerPhase.VALIDATION: 9,
            InstallerPhase.COMPLETE: 10,
        }
        return screen_map.get(phase, 0)

    @property
    def state_file_path(self) -> Path:
        return self._state_file
