"""
Phantom Installer Modules
Core modules for the unified installation wizard
"""

__version__ = "1.0.0"

from .system_check import SystemChecker
from .component_manager import ComponentManager
from .socket_manager import SocketManager
from .worker_discovery import WorkerDiscovery
from .venv_setup import VenvSetup
from .ui_integration import UIIntegration
from .config_generator import ConfigGenerator
from .manifest_manager import ManifestManager
from .uninstall_manager import UninstallManager

__all__ = [
    "SystemChecker",
    "ComponentManager",
    "SocketManager",
    "WorkerDiscovery",
    "VenvSetup",
    "UIIntegration",
    "ConfigGenerator",
    "ManifestManager",
    "UninstallManager",
]
