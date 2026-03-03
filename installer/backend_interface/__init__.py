"""
Phantom Installer Backend Interface
Adapters that wrap existing installer modules for GUI use.
"""

from .system_scan_adapter import run_system_scan
from .worker_discovery_adapter import WorkerDiscoveryAdapter
from .model_downloader import ModelDownloader, MODELS, DownloadError
from .config_writer import ConfigWriter
from .installer_driver import InstallerDriver, INSTALL_STAGES

__all__ = [
    "run_system_scan",
    "WorkerDiscoveryAdapter",
    "ModelDownloader",
    "MODELS",
    "DownloadError",
    "ConfigWriter",
    "InstallerDriver",
    "INSTALL_STAGES",
]
