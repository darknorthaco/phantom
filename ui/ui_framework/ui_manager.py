#!/usr/bin/env python3
"""
Phantom UI Manager
Discovers, loads, and manages swappable UI implementations
"""

import os
import sys
import importlib
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional, Type
import logging

from .base_ui import PhantomUI

logger = logging.getLogger(__name__)


class UIManager:
    """
    Manages discovery and loading of Phantom UI implementations.

    Supports:
    - Automatic discovery of UI modules
    - Dynamic loading of UI classes
    - UI registration and selection
    - Configuration management
    """

    def __init__(self, ui_base_path: Optional[str] = None):
        """
        Initialize UI manager.

        Args:
            ui_base_path: Base path for UI discovery (defaults to ui/ directory)
        """
        self.ui_base_path = Path(ui_base_path) if ui_base_path else Path(__file__).parent.parent
        self.discovered_uis: Dict[str, Type[PhantomUI]] = {}
        self.loaded_uis: Dict[str, PhantomUI] = {}
        self.logger = logging.getLogger(__name__)

    def discover_uis(self) -> Dict[str, Type[PhantomUI]]:
        """
        Discover available UI implementations.

        Returns:
            dict: Mapping of UI names to UI classes
        """
        self.discovered_uis.clear()

        # Discover in ui/redblue_matrix/
        redblue_path = self.ui_base_path / "redblue_matrix"
        if redblue_path.exists():
            self._discover_in_directory(redblue_path, "redblue_matrix")

        # Discover in ui/examples/
        examples_path = self.ui_base_path / "examples"
        if examples_path.exists():
            for example_dir in examples_path.iterdir():
                if example_dir.is_dir():
                    self._discover_in_directory(example_dir, f"examples.{example_dir.name}")

        # Discover in custom locations
        self._discover_custom_uis()

        self.logger.info(f"Discovered {len(self.discovered_uis)} UI implementations")
        return self.discovered_uis.copy()

    def _discover_in_directory(self, directory: Path, module_prefix: str):
        """Discover UIs in a specific directory."""
        if not directory.exists():
            return

        # Look for Python files that might contain UI classes
        for py_file in directory.glob("*.py"):
            if py_file.name.startswith('_'):
                continue

            module_name = f"{module_prefix}.{py_file.stem}"
            try:
                self._load_ui_from_module(module_name, py_file)
            except Exception as e:
                self.logger.warning(f"Failed to load UI from {py_file}: {e}")

        # Look for subdirectories with __init__.py
        for subdir in directory.iterdir():
            if subdir.is_dir() and (subdir / "__init__.py").exists():
                module_name = f"{module_prefix}.{subdir.name}"
                try:
                    self._load_ui_from_module(module_name, subdir / "__init__.py")
                except Exception as e:
                    self.logger.warning(f"Failed to load UI from {subdir}: {e}")

    def _load_ui_from_module(self, module_name: str, file_path: Path):
        """Load UI class from a Python module."""
        try:
            # Add the module's directory to Python path temporarily
            module_dir = file_path.parent
            if str(module_dir) not in sys.path:
                sys.path.insert(0, str(module_dir))

            # Import the module
            module = importlib.import_module(module_name)

            # Find UI classes in the module
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    issubclass(obj, PhantomUI) and
                    obj != PhantomUI):
                    ui_name = getattr(obj, 'UI_NAME', name.lower())
                    self.discovered_uis[ui_name] = obj
                    self.logger.debug(f"Discovered UI: {ui_name} ({obj.__name__})")

        except ImportError as e:
            self.logger.warning(f"Could not import module {module_name}: {e}")
        except Exception as e:
            self.logger.warning(f"Error loading UI from {module_name}: {e}")

    def _discover_custom_uis(self):
        """Discover UIs in custom locations (environment variable, config file, etc.)."""
        # Check environment variable
        custom_paths = os.environ.get('PHANTOM_UI_PATHS', '')
        if custom_paths:
            for path_str in custom_paths.split(':'):
                path = Path(path_str).expanduser()
                if path.exists():
                    self._discover_in_directory(path, f"custom.{path.name}")

    def get_available_uis(self) -> List[str]:
        """
        Get list of available UI names.

        Returns:
            list: Available UI names
        """
        return list(self.discovered_uis.keys())

    def get_ui_info(self, ui_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific UI.

        Args:
            ui_name: Name of the UI

        Returns:
            dict: UI information or None if not found
        """
        ui_class = self.discovered_uis.get(ui_name)
        if ui_class:
            try:
                # Create a temporary instance to get info
                temp_config = {
                    'socket_host': 'localhost',
                    'socket_port': 8082,
                    'controller_host': 'localhost',
                    'controller_port': 8765,
                    'execution_mode': 'AUTO'
                }
                temp_ui = ui_class(temp_config)
                return temp_ui.get_ui_info()
            except Exception as e:
                self.logger.error(f"Error getting info for UI {ui_name}: {e}")
                return None
        return None

    def load_ui(self, ui_name: str, config: Dict[str, Any]) -> Optional[PhantomUI]:
        """
        Load and initialize a UI implementation.

        Args:
            ui_name: Name of the UI to load
            config: Configuration for the UI

        Returns:
            PhantomUI: Initialized UI instance or None if failed
        """
        ui_class = self.discovered_uis.get(ui_name)
        if not ui_class:
            self.logger.error(f"UI '{ui_name}' not found. Available: {list(self.discovered_uis.keys())}")
            return None

        try:
            ui_instance = ui_class(config)
            if not ui_instance.validate_config():
                self.logger.error(f"Invalid configuration for UI '{ui_name}'")
                return None

            self.loaded_uis[ui_name] = ui_instance
            self.logger.info(f"Loaded UI: {ui_name}")
            return ui_instance

        except Exception as e:
            self.logger.error(f"Failed to load UI '{ui_name}': {e}")
            return None

    def unload_ui(self, ui_name: str) -> bool:
        """
        Unload a UI implementation.

        Args:
            ui_name: Name of the UI to unload

        Returns:
            bool: True if unloaded successfully
        """
        ui_instance = self.loaded_uis.get(ui_name)
        if ui_instance:
            try:
                ui_instance.stop()
                del self.loaded_uis[ui_name]
                self.logger.info(f"Unloaded UI: {ui_name}")
                return True
            except Exception as e:
                self.logger.error(f"Error unloading UI '{ui_name}': {e}")
                return False
        return False

    def get_loaded_uis(self) -> List[str]:
        """
        Get list of currently loaded UIs.

        Returns:
            list: Loaded UI names
        """
        return list(self.loaded_uis.keys())

    def start_ui(self, ui_name: str) -> bool:
        """
        Start a loaded UI.

        Args:
            ui_name: Name of the UI to start

        Returns:
            bool: True if started successfully
        """
        ui_instance = self.loaded_uis.get(ui_name)
        if ui_instance:
            try:
                return ui_instance.start()
            except Exception as e:
                self.logger.error(f"Error starting UI '{ui_name}': {e}")
                return False
        return False

    def stop_ui(self, ui_name: str) -> bool:
        """
        Stop a loaded UI.

        Args:
            ui_name: Name of the UI to stop

        Returns:
            bool: True if stopped successfully
        """
        ui_instance = self.loaded_uis.get(ui_name)
        if ui_instance:
            try:
                return ui_instance.stop()
            except Exception as e:
                self.logger.error(f"Error stopping UI '{ui_name}': {e}")
                return False
        return False

    def start_all_uis(self) -> Dict[str, bool]:
        """
        Start all loaded UIs.

        Returns:
            dict: Mapping of UI names to success status
        """
        results = {}
        for ui_name in self.loaded_uis.keys():
            results[ui_name] = self.start_ui(ui_name)
        return results

    def stop_all_uis(self) -> Dict[str, bool]:
        """
        Stop all loaded UIs.

        Returns:
            dict: Mapping of UI names to success status
        """
        results = {}
        for ui_name in self.loaded_uis.keys():
            results[ui_name] = self.stop_ui(ui_name)
        return results