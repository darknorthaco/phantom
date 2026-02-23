#!/usr/bin/env python3
"""
Component Manager
Handles installation and management of Phantom ecosystem components
"""

import os
import subprocess
import urllib.request
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class ComponentManager:
    """Manages Phantom ecosystem components"""

    # Component definitions
    COMPONENTS = {
        "phantom_core": {
            "name": "Phantom Core",
            "required": True,
            "repo": "https://github.com/darknorthaco/phantom_ptr.git",
            "description": "Core distributed compute fabric",
        },
        "llm_taskmaster": {
            "name": "LLM Task Master",
            "required": False,
            "repo": None,  # Already included in main repo
            "description": "AI-powered intelligent task routing",
        },
        "linux_workers": {
            "name": "Linux Workers",
            "required": False,
            "repo": None,  # Already included in main repo
            "description": "Linux worker nodes with GPU support",
            "os_required": "Linux",
        },
        "windows_workers": {
            "name": "Windows Workers",
            "required": False,
            "repo": None,  # Already included in main repo
            "description": "Windows worker nodes with GPU support",
            "os_required": "Windows",
        },
        "security_framework": {
            "name": "Security Framework",
            "required": False,
            "repo": None,  # Already included in main repo
            "description": "Multi-level security with authentication",
        },
        "socket_infrastructure": {
            "name": "Socket Infrastructure",
            "required": False,
            "repo": None,  # Already included in main repo
            "description": "WebSocket-based real-time communication",
        },
        "redblue_ui": {
            "name": "RedBlue UI",
            "required": False,
            "repo": "https://github.com/darknorthaco/redblue-private",
            "description": "Web-based monitoring and control UI",
        },
    }

    def __init__(self, install_dir: str, use_git: bool = True):
        self.install_dir = Path(install_dir)
        self.use_git = use_git
        self.selected_components = set()
        self.installed_components = set()

    def select_component(self, component_id: str):
        """Select a component for installation"""
        if component_id in self.COMPONENTS:
            self.selected_components.add(component_id)

    def deselect_component(self, component_id: str):
        """Deselect a component"""
        if component_id in self.selected_components:
            self.selected_components.remove(component_id)

    def get_component_info(self, component_id: str) -> Optional[Dict]:
        """Get information about a component"""
        return self.COMPONENTS.get(component_id)

    def list_components(self) -> List[Dict]:
        """List all available components"""
        return [
            {"id": comp_id, **comp_info}
            for comp_id, comp_info in self.COMPONENTS.items()
        ]

    def validate_selection(self, os_type: str) -> Tuple[bool, List[str]]:
        """Validate component selection for the current OS"""
        errors = []

        # Check OS-specific requirements
        for comp_id in self.selected_components:
            comp = self.COMPONENTS[comp_id]
            if "os_required" in comp and comp["os_required"] != os_type:
                errors.append(
                    f"{comp['name']} requires {comp['os_required']}, but running on {os_type}"
                )

        # Ensure required components are selected
        for comp_id, comp in self.COMPONENTS.items():
            if comp["required"] and comp_id not in self.selected_components:
                self.selected_components.add(comp_id)

        return len(errors) == 0, errors

    def clone_repository(self, repo_url: str, target_dir: Path) -> bool:
        """Clone a git repository"""
        try:
            if not self.use_git:
                return False

            result = subprocess.run(
                ["git", "clone", repo_url, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Git clone failed: {e}")
            return False

    def download_archive(self, url: str, target_file: Path) -> bool:
        """Download an archive file"""
        try:
            urllib.request.urlretrieve(url, str(target_file))
            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    def install_component(self, component_id: str, progress_callback=None) -> bool:
        """Install a single component"""
        comp = self.COMPONENTS.get(component_id)
        if not comp:
            return False

        if progress_callback:
            progress_callback(f"Installing {comp['name']}...")

        # If component is already in main repo, mark as installed
        if comp["repo"] is None:
            if progress_callback:
                progress_callback(
                    f"{comp['name']} - Already available in main installation"
                )
            self.installed_components.add(component_id)
            return True

        # Clone or download component
        comp_dir = self.install_dir / component_id

        if comp["repo"]:
            if self.use_git:
                success = self.clone_repository(comp["repo"], comp_dir)
            else:
                # Fallback: try to download as archive
                # This is a placeholder - actual implementation would need release URLs
                success = False

            if success:
                if progress_callback:
                    progress_callback(f"{comp['name']} - Installed successfully")
                self.installed_components.add(component_id)
                return True
            else:
                if progress_callback:
                    progress_callback(f"{comp['name']} - Installation failed")
                return False

        return False

    def install_selected_components(
        self, progress_callback=None
    ) -> Tuple[List[str], List[str]]:
        """Install all selected components"""
        success = []
        failed = []

        for comp_id in self.selected_components:
            if self.install_component(comp_id, progress_callback):
                success.append(comp_id)
            else:
                failed.append(comp_id)

        return success, failed

    def create_directory_structure(self) -> bool:
        """Create base directory structure"""
        try:
            directories = [
                self.install_dir,
                self.install_dir / "config",
                self.install_dir / "logs",
                self.install_dir / "data",
                self.install_dir / "venvs",
            ]

            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)

            return True
        except Exception as e:
            print(f"Failed to create directory structure: {e}")
            return False

    def get_installation_summary(self) -> Dict:
        """Get summary of installation"""
        return {
            "install_dir": str(self.install_dir),
            "selected": list(self.selected_components),
            "installed": list(self.installed_components),
            "failed": list(self.selected_components - self.installed_components),
        }
