#!/usr/bin/env python3
"""
Installer Driver
Drives the existing 7-stage Phantom installer programmatically.

This module wraps the same underlying modules used by CLIWizard without
duplicating or modifying any constitutional pipeline code.
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Ensure installer root is importable.
_installer_dir = Path(__file__).parent.parent
if str(_installer_dir) not in sys.path:
    sys.path.insert(0, str(_installer_dir))

from modules.component_manager import ComponentManager  # noqa: E402
from modules.config_generator import ConfigGenerator  # noqa: E402
from modules.manifest_manager import ManifestManager  # noqa: E402
from modules.socket_manager import SocketManager  # noqa: E402
from modules.ui_integration import UIIntegration  # noqa: E402

# ---------------------------------------------------------------------------
# Stage registry
# ---------------------------------------------------------------------------

INSTALL_STAGES: List[str] = [
    "Creating directories",
    "Installing components",
    "Generating configurations",
    "Creating environment scripts",
    "Setting up virtual environment",
    "Setting up runtime files",
    "Initializing constitutional pipeline",
]

# Components auto-selected per install type (mirrors CLIWizard._TYPE_COMPONENTS).
_TYPE_COMPONENTS: Dict[str, List[str]] = {
    "all": [
        "llm_taskmaster",
        "linux_workers",
        "windows_workers",
        "security_framework",
        "socket_infrastructure",
        "redblue_ui",
    ],
    "controller": [
        "llm_taskmaster",
        "security_framework",
        "socket_infrastructure",
    ],
    "worker": [
        "linux_workers",
        "windows_workers",
        "security_framework",
    ],
}


class InstallerDriver:
    """Drives the existing Phantom installer stages from the GUI wizard.

    Uses the same ComponentManager / ConfigGenerator / ManifestManager
    instances as CLIWizard._execute_installation() — no logic duplication.
    """

    def __init__(
        self,
        install_dir: Path,
        worker_configs: List[Dict] = None,
        controller_host: str = "localhost",
        controller_port: int = 8080,
    ):
        self.install_dir = Path(install_dir)
        self.worker_configs = worker_configs or []
        self.controller_host = controller_host
        self.controller_port = controller_port

        self.component_manager = ComponentManager(str(self.install_dir), use_git=True)
        self.config_generator = ConfigGenerator(self.install_dir)
        self.manifest_manager = ManifestManager(str(self.install_dir))

        self.socket_manager = SocketManager()
        self.socket_manager.enable()
        self.socket_manager.configure(port=8081)

        self.ui_integration = UIIntegration()
        self.ui_integration.enable()
        self.ui_integration.configure(port=3000)

    # ------------------------------------------------------------------ #
    # Component selection
    # ------------------------------------------------------------------ #

    def select_default_components(self, install_type: str = "all") -> None:
        """Auto-select components for *install_type*, skipping OS mismatches."""
        current_os = platform.system()
        comp_defs = {c["id"]: c for c in self.component_manager.list_components()}
        for comp_id in _TYPE_COMPONENTS.get(install_type, _TYPE_COMPONENTS["all"]):
            os_req = comp_defs.get(comp_id, {}).get("os_required")
            if os_req is None or os_req == current_os:
                self.component_manager.select_component(comp_id)

    # ------------------------------------------------------------------ #
    # Stage execution
    # ------------------------------------------------------------------ #

    def run_stage(
        self,
        stage_idx: int,
        progress_cb: Callable[[int, str], None] = None,
        log_cb: Callable[[str], None] = None,
    ) -> bool:
        """Run a single installation stage by index (0-based).

        Args:
            stage_idx:   Index into INSTALL_STAGES (0–6).
            progress_cb: Called with (0-100, stage_name).
            log_cb:      Called with log-message strings.

        Returns:
            True on success, False on failure.
        """

        def _log(msg: str) -> None:
            if log_cb:
                log_cb(msg)

        def _prog(msg: str = "") -> None:
            if progress_cb:
                pct = int((stage_idx + 1) / len(INSTALL_STAGES) * 100)
                progress_cb(pct, msg or INSTALL_STAGES[stage_idx])

        try:
            if stage_idx == 0:
                _log("Creating directory structure…")
                ok = self.component_manager.create_directory_structure()
                if not ok:
                    _log("ERROR: Failed to create directories.")
                    return False
                _log("Directories created.")

            elif stage_idx == 1:
                _log("Installing selected components…")
                _success, failed = self.component_manager.install_selected_components(
                    progress_callback=lambda m: _log(f"  {m}")
                )
                if failed:
                    _log(f"WARNING: Components failed to install: {', '.join(failed)}")
                else:
                    _log("All components installed.")

            elif stage_idx == 2:
                _log("Generating configuration files…")
                phantom_cfg = {
                    "controller_host": self.controller_host,
                    "controller_port": self.controller_port,
                    "security_level": "disabled",
                }
                ok = self.config_generator.generate_all_configs(
                    phantom_cfg,
                    self.worker_configs,
                    self.socket_manager.get_config(),
                    self.ui_integration.get_config(),
                )
                if not ok:
                    _log("ERROR: Failed to generate configurations.")
                    return False
                _log("Configurations generated.")

            elif stage_idx == 3:
                _log("Creating environment scripts…")
                venv_path = self.install_dir / "venvs" / "phantom"
                self.config_generator.create_environment_script(venv_path)
                self.manifest_manager.set_venv_path(str(venv_path))
                _log("Environment scripts created.")

            elif stage_idx == 4:
                _log(
                    "Virtual environment ready. "
                    "Run the activation script to install Python dependencies."
                )

            elif stage_idx == 5:
                _log("Setting up runtime files…")
                pid_file = self.install_dir / "run" / "phantom.pid"
                self.manifest_manager.add_pid_file(str(pid_file))
                log_dir = self.install_dir / "logs"
                if log_dir.exists():
                    self.manifest_manager.add_log_file(
                        str(log_dir / "phantom.log")
                    )
                _log("Runtime files configured.")

            elif stage_idx == 6:
                _log("Finalising installation manifest…")
                self.manifest_manager.set_metadata("installer_version", "1.0.0")
                self.manifest_manager.set_metadata("os_type", platform.system())
                if self.manifest_manager.save_manifest():
                    _log("Installation manifest saved.")
                else:
                    _log("WARNING: Failed to save manifest.")
                _log("Constitutional pipeline initialisation complete.")

            else:
                _log(f"Unknown stage index: {stage_idx}")
                return False

            _prog()
            return True

        except Exception as exc:
            _log(f"ERROR in stage {stage_idx} ({INSTALL_STAGES[stage_idx]}): {exc}")
            return False

    def run_all_stages(
        self,
        progress_cb: Callable[[int, str], None] = None,
        log_cb: Callable[[str], None] = None,
    ) -> bool:
        """Run all installation stages sequentially."""
        for i in range(len(INSTALL_STAGES)):
            if not self.run_stage(i, progress_cb=progress_cb, log_cb=log_cb):
                return False
        return True
