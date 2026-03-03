"""
Phantom Installer GUI Screens
"""

from .base import WizardScreen
from .welcome import WelcomeScreen
from .system_scan import SystemScanScreen
from .worker_discovery import WorkerDiscoveryScreen
from .worker_selection import WorkerSelectionScreen
from .model_selection import ModelSelectionScreen
from .model_download import ModelDownloadScreen
from .installation import InstallationScreen
from .completion import CompletionScreen
from .dependency_fetch import DependencyFetchScreen
from .reboot_prompt import RebootPromptScreen
from .resume import ResumeScreen

__all__ = [
    "WizardScreen",
    "WelcomeScreen",
    "SystemScanScreen",
    "DependencyFetchScreen",
    "RebootPromptScreen",
    "ResumeScreen",
    "WorkerDiscoveryScreen",
    "WorkerSelectionScreen",
    "ModelSelectionScreen",
    "ModelDownloadScreen",
    "InstallationScreen",
    "CompletionScreen",
]
