#!/usr/bin/env python3
"""
CLI Wizard
Interactive command-line installation wizard
"""

import platform
from pathlib import Path
from typing import Dict, List, Optional
import sys

# Ensure proper imports when running from different contexts
try:
    from .prompts import Prompts
    from .progress_display import ProgressDisplay
except ImportError:
    from prompts import Prompts
    from progress_display import ProgressDisplay

try:
    from ..modules import (
        SystemChecker,
        ComponentManager,
        WorkerDiscovery,
        SocketManager,
        UIIntegration,
        ConfigGenerator,
        ManifestManager,
    )
except ImportError:
    from modules import (
        SystemChecker,
        ComponentManager,
        WorkerDiscovery,
        SocketManager,
        UIIntegration,
        ConfigGenerator,
        ManifestManager,
    )


class CLIWizard:
    """Interactive CLI installation wizard"""

    def __init__(
        self,
        silent: bool = False,
        install_type: str = "all",
        force: bool = False,
    ):
        self.silent = silent
        self.install_type = install_type
        self.force = force

        self.prompts = Prompts()
        self.progress = ProgressDisplay()
        self.system_checker = SystemChecker()
        self.install_dir = None
        self.component_manager = None
        self.worker_discovery = WorkerDiscovery()
        self.socket_manager = SocketManager()
        self.ui_integration = UIIntegration()
        self.config_generator = None
        self.manifest_manager = None

        self.selected_components = []
        self.controller_host = "localhost"
        self.controller_port = 8080
        self.security_level = "disabled"

    def run(self) -> bool:
        """Run the complete installation wizard"""
        try:
            # Welcome
            self.prompts.welcome()

            # System checks
            if not self._run_system_checks():
                return False

            # Installation directory
            if not self._select_install_directory():
                return False

            # Component selection
            if not self._select_components():
                return False

            # Network configuration
            if not self._configure_network():
                return False

            # Worker discovery
            if not self._discover_workers():
                return False

            # Socket configuration
            if not self._configure_sockets():
                return False

            # UI configuration
            if not self._configure_ui():
                return False

            # Security configuration
            if not self._configure_security():
                return False

            # Confirm installation
            if not self._confirm_installation():
                return False

            # Execute installation
            if not self._execute_installation():
                return False

            # Completion
            self._display_completion()

            return True

        except KeyboardInterrupt:
            print("\n\n⚠️  Installation cancelled by user.")
            return False
        except Exception as e:
            self.prompts.error(f"Installation failed: {e}")
            return False

    def _run_system_checks(self) -> bool:
        """Run system requirement checks"""
        self.prompts.section("System Requirements Check")

        if not self.silent:
            self.progress.spinner("Checking system requirements...", 2)

        if not self.system_checker.run_all_checks():
            self.system_checker.print_report()
            if self.silent and not self.force:
                self.prompts.error(
                    "System check failures detected. Use --force to override."
                )
                return False
            if not self.silent and not self.prompts.confirm(
                "Continue despite failed checks?", False
            ):
                return False
        else:
            self.system_checker.print_report()

        return True

    def _select_install_directory(self) -> bool:
        """Select installation directory"""
        self.prompts.section("Installation Directory")

        default_dir = str(Path.home() / "phantom")
        if platform.system() == "Linux":
            default_dir = "/opt/phantom"
        elif platform.system() == "Windows":
            default_dir = "C:\\Program Files\\Phantom"

        if self.silent:
            # Use the directory already set by --install-dir, or the OS default
            if self.install_dir is None:
                self.install_dir = Path(default_dir)
            print(f"  Installation directory: {self.install_dir}")
        else:
            install_dir = self.prompts.input_text(
                "Enter installation directory", default=default_dir
            )
            self.install_dir = Path(install_dir)

        self.component_manager = ComponentManager(str(self.install_dir), use_git=True)
        self.config_generator = ConfigGenerator(self.install_dir)
        self.manifest_manager = ManifestManager(str(self.install_dir))

        return True

    # Installation type → optional component IDs to auto-select
    _TYPE_COMPONENTS = {
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

    def _select_components(self) -> bool:
        """Select components to install"""
        self.prompts.section("Component Selection")

        components = self.component_manager.list_components()

        print("Select components to install:")
        print("(Required components will be installed automatically)\n")

        for comp in components:
            required = "✓ Required" if comp["required"] else "  Optional"
            os_req = (
                f" [{comp.get('os_required', 'All OS')}]"
                if "os_required" in comp
                else ""
            )
            print(f"  [{required}] {comp['name']}{os_req}")
            print(f"      {comp['description']}")

        print()

        if self.silent:
            # Auto-select based on install_type, skipping components whose OS
            # requirement does not match the current platform (e.g. skip
            # windows_workers on Linux and vice-versa).
            current_os = platform.system()
            comp_defs = {c["id"]: c for c in components}
            auto_select = [
                comp_id
                for comp_id in self._TYPE_COMPONENTS.get(self.install_type, [])
                if comp_defs.get(comp_id, {}).get("os_required") in (None, current_os)
            ]
            for comp_id in auto_select:
                self.component_manager.select_component(comp_id)
            print(
                f"  Installation type '{self.install_type}': "
                f"auto-selected {len(auto_select)} optional component(s)"
            )
        else:
            # Select optional components
            optional_components = [c for c in components if not c["required"]]
            component_names = [c["name"] for c in optional_components]

            if self.prompts.confirm("Install all optional components?", True):
                for comp in optional_components:
                    self.component_manager.select_component(comp["id"])
            else:
                selected_indices = self.prompts.select_multiple(
                    "Select optional components to install:", component_names
                )

                for idx in selected_indices:
                    comp_id = optional_components[idx]["id"]
                    self.component_manager.select_component(comp_id)

        # Validate selection (also ensures required components are included)
        valid, errors = self.component_manager.validate_selection(platform.system())
        if not valid:
            for error in errors:
                self.prompts.error(error)
            return False

        return True

    def _configure_network(self) -> bool:
        """Configure network settings"""
        self.prompts.section("Network Configuration")

        if self.silent:
            print(f"  Controller: {self.controller_host}:{self.controller_port}")
        else:
            self.controller_host = self.prompts.input_text(
                "Controller host address", default="localhost"
            )

            self.controller_port = self.prompts.input_number(
                "Controller port", default=8080, min_val=1024, max_val=65535
            )

        return True

    def _discover_workers(self) -> bool:
        """Discover worker nodes"""
        self.prompts.section("Worker Discovery")

        if self.silent:
            self.worker_discovery.set_discovery_mode("skip")
            print("  Worker discovery skipped (configure workers later)")
            return True

        modes = [
            "Manual selection (basic ping scan)",
            "Comprehensive auto-detection",
            "Skip (configure workers later)",
        ]

        mode_idx = self.prompts.select_option(
            "Select worker discovery mode:", modes, default=2  # Skip by default
        )

        if mode_idx == 0:
            self.worker_discovery.set_discovery_mode("manual")
        elif mode_idx == 1:
            self.worker_discovery.set_discovery_mode("comprehensive")
        else:
            self.worker_discovery.set_discovery_mode("skip")
            return True

        # Run discovery
        workers = self.worker_discovery.run_discovery()

        if not workers:
            self.prompts.warning("No workers discovered")
            return True

        # Display discovered workers
        print("\nDiscovered workers:")
        for i, worker in enumerate(workers, 1):
            status = "✓" if worker.get("available", False) else "✗"
            print(
                f"  {status} [{i}] {worker['ip']} - {worker.get('hostname', 'Unknown')}"
            )
            if worker.get("gpu"):
                print(f"      GPU: {worker['gpu']}")

        # Select workers
        if self.prompts.confirm("\nSelect workers to configure?", True):
            worker_indices = self.prompts.select_multiple(
                "Select workers (enter numbers):",
                [f"{w['ip']} - {w.get('hostname', 'Unknown')}" for w in workers],
            )

            self.worker_discovery.select_workers([i + 1 for i in worker_indices])

        return True

    def _configure_sockets(self) -> bool:
        """Configure socket infrastructure"""
        self.prompts.section("Socket Infrastructure")

        if self.silent:
            self.socket_manager.enable()
            self.socket_manager.configure(port=8081)
            print("  Socket infrastructure enabled on port 8081")
            return True

        if self.prompts.confirm(
            "Enable socket infrastructure for real-time communication?", True
        ):
            self.socket_manager.enable()

            port = self.prompts.input_number(
                "Socket port", default=8081, min_val=1024, max_val=65535
            )

            self.socket_manager.configure(port=port)

        return True

    def _configure_ui(self) -> bool:
        """Configure UI integration"""
        self.prompts.section("RedBlue UI Integration")

        if self.silent:
            # UI configuration skipped in silent mode; RedBlue UI can be set up manually
            print("  RedBlue UI configuration skipped (configure manually if needed)")
            return True

        if "redblue_ui" in self.component_manager.selected_components:
            if self.prompts.confirm("Configure RedBlue UI?", True):
                self.ui_integration.enable()

                port = self.prompts.input_number(
                    "UI port", default=3000, min_val=1024, max_val=65535
                )

                self.ui_integration.configure(port=port)

                if self.socket_manager.enabled:
                    if self.prompts.confirm("Enable socket integration for UI?", True):
                        self.ui_integration.enable_socket_integration()

        return True

    def _configure_security(self) -> bool:
        """Configure security settings"""
        self.prompts.section("Security Configuration")

        if self.silent:
            print(f"  Security level: {self.security_level}")
            return True

        levels = ["Disabled", "Development", "Production"]
        level_idx = self.prompts.select_option(
            "Select security level:", levels, default=0
        )

        self.security_level = levels[level_idx].lower()

        return True

    def _confirm_installation(self) -> bool:
        """Confirm installation settings"""
        self.prompts.section("Installation Summary")

        print(f"Installation Directory: {self.install_dir}")
        print(f"Controller: {self.controller_host}:{self.controller_port}")
        print(f"Security Level: {self.security_level}")
        print(
            f"Socket Infrastructure: {'Enabled' if self.socket_manager.enabled else 'Disabled'}"
        )
        print(f"RedBlue UI: {'Enabled' if self.ui_integration.enabled else 'Disabled'}")
        print(f"\nSelected Components:")

        for comp_id in self.component_manager.selected_components:
            comp = self.component_manager.get_component_info(comp_id)
            print(f"  • {comp['name']}")

        selected_workers = self.worker_discovery.get_selected_workers()
        if selected_workers:
            print(f"\nConfigured Workers: {len(selected_workers)}")
            for worker in selected_workers:
                print(f"  • {worker['ip']} - {worker.get('hostname', 'Unknown')}")

        print()

        if self.silent or self.force:
            print("Proceeding with installation (silent/force mode)...")
            return True

        return self.prompts.confirm("Proceed with installation?", True)

    def _execute_installation(self) -> bool:
        """Execute the installation"""
        self.prompts.section("Installing Phantom")

        self.progress.start(7)

        # Initialize manifest metadata
        self.manifest_manager.set_metadata("installer_version", "1.0.0")
        self.manifest_manager.set_metadata("os_type", platform.system())

        # Step 1: Create directory structure
        self.progress.step("Creating directory structure")
        if not self.component_manager.create_directory_structure():
            self.prompts.error("Failed to create directories")
            return False

        # Track created directories
        for subdir in ["config", "logs", "data", "run"]:
            dir_path = self.install_dir / subdir
            if dir_path.exists():
                self.manifest_manager.add_directory(str(dir_path))

        # Step 2: Install components
        self.progress.step("Installing components")
        success, failed = self.component_manager.install_selected_components(
            progress_callback=self.progress.sub_step
        )

        if failed:
            self.prompts.warning(
                f"Some components failed to install: {', '.join(failed)}"
            )

        # Track installed components
        for comp_id in self.component_manager.installed_components:
            comp_info = self.component_manager.get_component_info(comp_id)
            if comp_info:
                self.manifest_manager.add_component(comp_id, comp_info["name"])

        # Step 3: Generate configurations
        self.progress.step("Generating configurations")

        phantom_config = {
            "controller_host": self.controller_host,
            "controller_port": self.controller_port,
            "security_level": self.security_level,
        }

        worker_configs = self.worker_discovery.get_worker_configs()
        socket_config = self.socket_manager.get_config()
        ui_config = self.ui_integration.get_config()

        if not self.config_generator.generate_all_configs(
            phantom_config, worker_configs, socket_config, ui_config
        ):
            self.prompts.error("Failed to generate configurations")
            return False

        # Track configuration files
        config_files = [
            self.install_dir / "config" / "phantom_config.yaml",
            self.install_dir / "config" / "socket_config.yaml",
            self.install_dir / "config" / "ui_config.yaml",
        ]
        for config_file in config_files:
            if config_file.exists():
                self.manifest_manager.add_config_file(str(config_file))

        # Track worker configs
        for i, _ in enumerate(worker_configs):
            worker_config_file = self.install_dir / "config" / f"worker_{i}.json"
            if worker_config_file.exists():
                self.manifest_manager.add_config_file(str(worker_config_file))

        # Step 4: Create environment scripts
        self.progress.step("Creating environment scripts")
        venv_path = self.install_dir / "venvs" / "phantom"
        self.config_generator.create_environment_script(venv_path)

        # Track venv path
        self.manifest_manager.set_venv_path(str(venv_path))

        # Step 5: Set up virtual environment (placeholder)
        self.progress.step("Virtual environment setup ready")
        self.progress.sub_step("Run venv setup separately after installation")

        # Step 6: Track PID file location
        self.progress.step("Setting up runtime files")
        pid_file = self.install_dir / "run" / "phantom.pid"
        self.manifest_manager.add_pid_file(str(pid_file))

        # Track log files
        log_dir = self.install_dir / "logs"
        if log_dir.exists():
            self.manifest_manager.add_log_file(str(log_dir / "phantom.log"))

        # Step 7: Save manifest
        self.progress.step("Finalizing installation")
        if self.manifest_manager.save_manifest():
            self.progress.sub_step("Installation manifest saved")
        else:
            self.prompts.warning("Failed to save installation manifest")

        self.progress.sub_step("Installation complete!")

        self.progress.complete()

        return True

    def _display_completion(self):
        """Display completion message"""
        self.prompts.completion_message(str(self.install_dir))
