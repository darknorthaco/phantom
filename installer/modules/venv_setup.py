#!/usr/bin/env python3
"""
Virtual Environment Setup
Manages Python virtual environment creation and configuration
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional


class VenvSetup:
    """Virtual environment setup and management"""

    def __init__(self, install_dir: Path):
        self.install_dir = install_dir
        self.venv_dir = install_dir / "venvs" / "phantom"
        self.python_executable = sys.executable

    def create_venv(self, progress_callback=None) -> bool:
        """Create virtual environment"""
        try:
            if progress_callback:
                progress_callback("Creating virtual environment...")

            # Create venv directory
            self.venv_dir.parent.mkdir(parents=True, exist_ok=True)

            # Create virtual environment
            result = subprocess.run(
                [self.python_executable, "-m", "venv", str(self.venv_dir)],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                if progress_callback:
                    progress_callback(f"Failed to create venv: {result.stderr}")
                return False

            if progress_callback:
                progress_callback("Virtual environment created successfully")

            return True
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error creating venv: {e}")
            return False

    def get_venv_python(self) -> Path:
        """Get path to Python executable in venv"""
        if sys.platform == "win32":
            return self.venv_dir / "Scripts" / "python.exe"
        else:
            return self.venv_dir / "bin" / "python"

    def get_venv_pip(self) -> Path:
        """Get path to pip executable in venv"""
        if sys.platform == "win32":
            return self.venv_dir / "Scripts" / "pip.exe"
        else:
            return self.venv_dir / "bin" / "pip"

    def install_requirements(
        self, requirements_file: Path, progress_callback=None
    ) -> bool:
        """Install requirements in virtual environment"""
        try:
            if progress_callback:
                progress_callback("Installing Python dependencies...")

            pip_path = self.get_venv_pip()

            if not pip_path.exists():
                if progress_callback:
                    progress_callback("Virtual environment not found")
                return False

            result = subprocess.run(
                [str(pip_path), "install", "-r", str(requirements_file)],
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                if progress_callback:
                    progress_callback(
                        f"Failed to install requirements: {result.stderr}"
                    )
                return False

            if progress_callback:
                progress_callback("Dependencies installed successfully")

            return True
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error installing requirements: {e}")
            return False

    def create_activation_script(self) -> bool:
        """Create convenience activation script"""
        try:
            # Linux/Mac activation script
            if sys.platform != "win32":
                activate_script = self.install_dir / "activate_phantom.sh"
                with open(activate_script, "w") as f:
                    f.write("#!/bin/bash\n")
                    f.write(f'source "{self.venv_dir}/bin/activate"\n')
                    f.write('echo "Phantom virtual environment activated"\n')
                activate_script.chmod(0o755)

            # Windows activation script
            if sys.platform == "win32":
                activate_script = self.install_dir / "activate_phantom.bat"
                with open(activate_script, "w") as f:
                    f.write("@echo off\n")
                    f.write(f'call "{self.venv_dir}\\Scripts\\activate.bat"\n')
                    f.write("echo Phantom virtual environment activated\n")

            return True
        except Exception as e:
            print(f"Failed to create activation script: {e}")
            return False

    def get_venv_path(self) -> Path:
        """Get virtual environment directory path"""
        return self.venv_dir
