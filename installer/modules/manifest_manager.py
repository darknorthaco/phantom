#!/usr/bin/env python3
"""
Manifest Manager
Tracks installed files, directories, services, and configurations for safe uninstallation
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime


class ManifestManager:
    """Manages installation manifest for tracking installed components"""

    MANIFEST_FILENAME = ".phantom_install_manifest.json"

    def __init__(self, install_dir: str):
        self.install_dir = Path(install_dir)
        self.manifest_path = self.install_dir / self.MANIFEST_FILENAME
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> Dict:
        """Load existing manifest or create new one"""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️  Warning: Could not load manifest: {e}")
                return self._create_empty_manifest()
        return self._create_empty_manifest()

    def _create_empty_manifest(self) -> Dict:
        """Create empty manifest structure"""
        return {
            "version": "1.0",
            "install_date": datetime.now().isoformat(),
            "install_dir": str(self.install_dir),
            "components": [],
            "files": [],
            "directories": [],
            "services": [],
            "config_files": [],
            "pid_files": [],
            "log_files": [],
            "venv_path": None,
            "metadata": {},
        }

    def save_manifest(self) -> bool:
        """Save manifest to disk"""
        try:
            self.install_dir.mkdir(parents=True, exist_ok=True)
            with open(self.manifest_path, "w") as f:
                json.dump(self.manifest, f, indent=2)
            return True
        except IOError as e:
            print(f"❌ Error saving manifest: {e}")
            return False

    def add_component(self, component_id: str, component_name: str):
        """Add installed component to manifest"""
        if not any(c["id"] == component_id for c in self.manifest["components"]):
            self.manifest["components"].append(
                {
                    "id": component_id,
                    "name": component_name,
                    "installed_at": datetime.now().isoformat(),
                }
            )

    def add_file(self, file_path: str):
        """Track installed file"""
        file_str = str(file_path)
        if file_str not in self.manifest["files"]:
            self.manifest["files"].append(file_str)

    def add_directory(self, dir_path: str):
        """Track created directory"""
        dir_str = str(dir_path)
        if dir_str not in self.manifest["directories"]:
            self.manifest["directories"].append(dir_str)

    def add_service(
        self, service_name: str, service_file: str, service_type: str = "systemd"
    ):
        """Track installed service"""
        service_info = {
            "name": service_name,
            "file": service_file,
            "type": service_type,
        }
        if service_info not in self.manifest["services"]:
            self.manifest["services"].append(service_info)

    def add_config_file(self, config_path: str):
        """Track configuration file"""
        config_str = str(config_path)
        if config_str not in self.manifest["config_files"]:
            self.manifest["config_files"].append(config_str)

    def add_pid_file(self, pid_path: str):
        """Track PID file"""
        pid_str = str(pid_path)
        if pid_str not in self.manifest["pid_files"]:
            self.manifest["pid_files"].append(pid_str)

    def add_log_file(self, log_path: str):
        """Track log file"""
        log_str = str(log_path)
        if log_str not in self.manifest["log_files"]:
            self.manifest["log_files"].append(log_str)

    def set_venv_path(self, venv_path: str):
        """Set virtual environment path"""
        self.manifest["venv_path"] = str(venv_path)

    def set_metadata(self, key: str, value):
        """Set arbitrary metadata"""
        self.manifest["metadata"][key] = value

    def get_components(self) -> List[Dict]:
        """Get list of installed components"""
        return self.manifest.get("components", [])

    def get_files(self) -> List[str]:
        """Get list of tracked files"""
        return self.manifest.get("files", [])

    def get_directories(self) -> List[str]:
        """Get list of tracked directories"""
        return self.manifest.get("directories", [])

    def get_services(self) -> List[Dict]:
        """Get list of installed services"""
        return self.manifest.get("services", [])

    def get_config_files(self) -> List[str]:
        """Get list of configuration files"""
        return self.manifest.get("config_files", [])

    def get_pid_files(self) -> List[str]:
        """Get list of PID files"""
        return self.manifest.get("pid_files", [])

    def get_log_files(self) -> List[str]:
        """Get list of log files"""
        return self.manifest.get("log_files", [])

    def get_venv_path(self) -> Optional[str]:
        """Get virtual environment path"""
        return self.manifest.get("venv_path")

    def has_manifest(self) -> bool:
        """Check if manifest file exists"""
        return self.manifest_path.exists()

    def get_install_date(self) -> Optional[str]:
        """Get installation date"""
        return self.manifest.get("install_date")

    def remove_manifest(self) -> bool:
        """Remove manifest file"""
        try:
            if self.manifest_path.exists():
                self.manifest_path.unlink()
            return True
        except IOError as e:
            print(f"⚠️  Warning: Could not remove manifest: {e}")
            return False
