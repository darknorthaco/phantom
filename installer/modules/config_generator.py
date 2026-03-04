#!/usr/bin/env python3
"""
Configuration Generator
Generates configuration files for Phantom components
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional


class ConfigGenerator:
    """Generates configuration files for the Phantom ecosystem"""

    def __init__(self, install_dir: Path):
        self.install_dir = install_dir
        self.config_dir = install_dir / "config"

    def generate_phantom_config(
        self,
        controller_host: str = "localhost",
        controller_port: int = 8080,
        security_level: str = "disabled",
    ) -> Dict:
        """Generate main Phantom configuration"""
        config = {
            "controller": {
                "host": controller_host,
                "port": controller_port,
                "api_version": "v1",
            },
            "security": {
                "level": security_level,  # disabled, development, production
                "authentication": "none" if security_level == "disabled" else "api_key",
            },
            "logging": {
                "level": "INFO",
                "file": str(self.install_dir / "logs" / "phantom.log"),
            },
            "data": {
                "storage_dir": str(self.install_dir / "data"),
            },
        }
        return config

    def generate_worker_config(
        self,
        worker_id: str,
        controller_host: str,
        controller_port: int,
        worker_port: int,
        gpu_index: int = 0,
    ) -> Dict:
        """Generate worker configuration"""
        config = {
            "worker_id": worker_id,
            "controller_host": controller_host,
            "controller_port": controller_port,
            "worker_port": worker_port,
            "gpu_index": gpu_index,
            "max_concurrent_tasks": 1,
            "log_level": "INFO",
        }
        return config

    def generate_socket_config(self, socket_config: Dict) -> Dict:
        """Generate socket infrastructure configuration"""
        return {
            "socket": {
                "enabled": socket_config.get("enabled", False),
                "host": socket_config.get("host", "127.0.0.1"),
                "port": socket_config.get("port", 8081),
                "ssl_enabled": socket_config.get("ssl_enabled", False),
                "ssl_cert": socket_config.get("ssl_cert"),
                "ssl_key": socket_config.get("ssl_key"),
            }
        }

    def generate_ui_config(self, ui_config: Dict) -> Dict:
        """Generate UI configuration"""
        return {
            "ui": {
                "enabled": ui_config.get("enabled", False),
                "host": ui_config.get("host", "127.0.0.1"),
                "port": ui_config.get("port", 3000),
                "controller_url": ui_config.get(
                    "controller_url", "http://localhost:8080"
                ),
                "socket_integration": ui_config.get("socket_integration", False),
            }
        }

    def save_config(self, config: Dict, filename: str, format: str = "yaml") -> bool:
        """Save configuration to file"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            filepath = self.config_dir / filename

            with open(filepath, "w") as f:
                if format == "yaml":
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                elif format == "json":
                    json.dump(config, f, indent=2)
                else:
                    return False

            return True
        except Exception as e:
            print(f"Failed to save config {filename}: {e}")
            return False

    def generate_all_configs(
        self,
        phantom_config: Dict,
        worker_configs: List[Dict],
        socket_config: Dict,
        ui_config: Dict,
    ) -> bool:
        """Generate and save all configuration files"""
        try:
            # Generate main phantom config
            main_config = self.generate_phantom_config(
                controller_host=phantom_config.get("controller_host", "localhost"),
                controller_port=phantom_config.get("controller_port", 8080),
                security_level=phantom_config.get("security_level", "disabled"),
            )

            # Add socket config to main config
            socket_cfg = self.generate_socket_config(socket_config)
            main_config.update(socket_cfg)

            # Add UI config to main config
            ui_cfg = self.generate_ui_config(ui_config)
            main_config.update(ui_cfg)

            # Save main config
            self.save_config(main_config, "phantom_config.yaml", "yaml")

            # Generate and save worker configs
            for i, worker_cfg in enumerate(worker_configs):
                worker_config = self.generate_worker_config(
                    worker_id=worker_cfg.get("worker_id", f"worker-{i+1}"),
                    controller_host=worker_cfg.get("controller_host", "localhost"),
                    controller_port=worker_cfg.get("controller_port", 8080),
                    worker_port=worker_cfg.get("worker_port", 8090 + i),
                    gpu_index=worker_cfg.get("gpu_index", i),
                )
                self.save_config(worker_config, f"worker_{i+1}_config.json", "json")

            return True
        except Exception as e:
            print(f"Failed to generate configs: {e}")
            return False

    def create_environment_script(self, venv_path: Path) -> bool:
        """Create environment setup script"""
        try:
            # Linux/Mac script
            if os.name != "nt":
                script_path = self.install_dir / "environment.sh"
                with open(script_path, "w") as f:
                    f.write("#!/bin/bash\n")
                    f.write(f'export PHANTOM_HOME="{self.install_dir}"\n')
                    f.write(f'export PHANTOM_CONFIG="{self.config_dir}"\n')
                    f.write(f'export PHANTOM_VENV="{venv_path}"\n')
                    f.write(f'source "{venv_path}/bin/activate"\n')
                script_path.chmod(0o755)

            # Windows script
            else:
                script_path = self.install_dir / "environment.ps1"
                with open(script_path, "w") as f:
                    f.write(f'$env:PHANTOM_HOME = "{self.install_dir}"\n')
                    f.write(f'$env:PHANTOM_CONFIG = "{self.config_dir}"\n')
                    f.write(f'$env:PHANTOM_VENV = "{venv_path}"\n')
                    f.write(f'& "{venv_path}\\Scripts\\Activate.ps1"\n')

            return True
        except Exception as e:
            print(f"Failed to create environment script: {e}")
            return False
