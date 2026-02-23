#!/usr/bin/env python3
"""
System Requirements Checker
Validates system capabilities before installation
"""

import sys
import os
import platform
import subprocess
import shutil
from typing import Dict, List, Tuple, Optional


class SystemChecker:
    """System requirements validation"""

    def __init__(self):
        self.os_type = platform.system()
        self.os_version = platform.version()
        self.architecture = platform.machine()
        self.python_version = sys.version_info
        self.checks_passed = []
        self.checks_failed = []
        self.checks_warnings = []

    def check_python_version(self, min_version: Tuple[int, int] = (3, 8)) -> bool:
        """Check if Python version meets minimum requirements"""
        if self.python_version >= min_version:
            self.checks_passed.append(
                f"Python {self.python_version.major}.{self.python_version.minor}.{self.python_version.micro} (>= {min_version[0]}.{min_version[1]})"
            )
            return True
        else:
            self.checks_failed.append(
                f"Python {self.python_version.major}.{self.python_version.minor}.{self.python_version.micro} "
                f"does not meet minimum requirement {min_version[0]}.{min_version[1]}"
            )
            return False

    def check_os_capabilities(self) -> bool:
        """Check OS-specific capabilities"""
        if self.os_type in ["Linux", "Darwin", "Windows"]:
            self.checks_passed.append(
                f"Operating System: {self.os_type} {self.os_version}"
            )
            return True
        else:
            self.checks_failed.append(f"Unsupported OS: {self.os_type}")
            return False

    def check_disk_space(self, min_gb: float = 5.0) -> bool:
        """Check available disk space"""
        try:
            if self.os_type == "Windows":
                import ctypes

                free_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(os.getcwd()),
                    None,
                    None,
                    ctypes.pointer(free_bytes),
                )
                free_gb = free_bytes.value / (1024**3)
            else:
                stat = os.statvfs(os.getcwd())
                free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)

            if free_gb >= min_gb:
                self.checks_passed.append(
                    f"Disk space: {free_gb:.2f} GB available (>= {min_gb} GB)"
                )
                return True
            else:
                self.checks_failed.append(
                    f"Insufficient disk space: {free_gb:.2f} GB (need >= {min_gb} GB)"
                )
                return False
        except Exception as e:
            self.checks_warnings.append(f"Could not check disk space: {e}")
            return True  # Non-critical

    def check_port_availability(self, ports: List[int]) -> Dict[int, bool]:
        """Check if required ports are available"""
        import socket

        results = {}

        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(("localhost", port))
                sock.close()

                if result != 0:
                    self.checks_passed.append(f"Port {port} is available")
                    results[port] = True
                else:
                    self.checks_warnings.append(f"Port {port} is already in use")
                    results[port] = False
            except Exception as e:
                self.checks_warnings.append(f"Could not check port {port}: {e}")
                results[port] = True  # Assume available

        return results

    def check_network_connectivity(self) -> bool:
        """Check basic network connectivity"""
        import socket

        try:
            # Try to resolve a hostname
            socket.gethostbyname("github.com")
            self.checks_passed.append("Network connectivity: OK")
            return True
        except socket.gaierror:
            self.checks_warnings.append(
                "Network connectivity issue (offline mode available)"
            )
            return False

    def check_command_availability(self, commands: List[str]) -> Dict[str, bool]:
        """Check if system commands are available"""
        results = {}

        for cmd in commands:
            path = shutil.which(cmd)
            if path:
                self.checks_passed.append(f"Command '{cmd}' available at {path}")
                results[cmd] = True
            else:
                self.checks_warnings.append(f"Command '{cmd}' not found")
                results[cmd] = False

        return results

    def check_git_availability(self) -> bool:
        """Check if git is available"""
        git_available = shutil.which("git") is not None
        if git_available:
            try:
                result = subprocess.run(
                    ["git", "--version"], capture_output=True, text=True, timeout=5
                )
                version = result.stdout.strip()
                self.checks_passed.append(f"Git: {version}")
                return True
            except Exception as e:
                self.checks_warnings.append(f"Git check failed: {e}")
                return False
        else:
            self.checks_warnings.append(
                "Git not found (will use fallback download method)"
            )
            return False

    def check_virtual_env_capability(self) -> bool:
        """Check if virtual environment can be created"""
        try:
            import venv

            self.checks_passed.append("Virtual environment support: Available")
            return True
        except ImportError:
            self.checks_failed.append("Virtual environment support not available")
            return False

    def run_all_checks(self, ports: Optional[List[int]] = None) -> bool:
        """Run all system checks"""
        if ports is None:
            ports = [8080, 8081, 3000, 5000]  # Default ports

        checks = [
            self.check_python_version(),
            self.check_os_capabilities(),
            self.check_disk_space(),
            self.check_virtual_env_capability(),
        ]

        # Non-critical checks
        self.check_port_availability(ports)
        self.check_network_connectivity()
        self.check_git_availability()
        self.check_command_availability(["curl", "wget", "tar", "unzip"])

        # All critical checks must pass
        return all(checks)

    def get_report(self) -> Dict[str, List[str]]:
        """Get detailed check report"""
        return {
            "passed": self.checks_passed,
            "failed": self.checks_failed,
            "warnings": self.checks_warnings,
        }

    def print_report(self):
        """Print formatted check report"""
        print("\n" + "=" * 60)
        print("SYSTEM REQUIREMENTS CHECK")
        print("=" * 60)

        if self.checks_passed:
            print("\n✅ PASSED:")
            for check in self.checks_passed:
                print(f"  • {check}")

        if self.checks_warnings:
            print("\n⚠️  WARNINGS:")
            for check in self.checks_warnings:
                print(f"  • {check}")

        if self.checks_failed:
            print("\n❌ FAILED:")
            for check in self.checks_failed:
                print(f"  • {check}")

        print("\n" + "=" * 60)

        if not self.checks_failed:
            print("✅ All critical checks passed!")
        else:
            print(
                "❌ Some critical checks failed. Please resolve them before continuing."
            )

        print("=" * 60 + "\n")
