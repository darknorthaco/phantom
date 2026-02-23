#!/usr/bin/env python3
"""
Health Check Script
Verifies Phantom installation and components
"""

import sys
import os
import json
import time
import socket
from pathlib import Path
from typing import Dict, List, Tuple
import urllib.request
import urllib.error


class HealthChecker:
    """Installation health checker"""

    def __init__(self, install_dir: str):
        self.install_dir = Path(install_dir)
        self.checks_passed = []
        self.checks_failed = []
        self.checks_warnings = []

    def check_directory_structure(self) -> bool:
        """Check if directory structure is correct"""
        required_dirs = [
            "config",
            "logs",
            "data",
            "venvs",
        ]

        all_exist = True
        for dirname in required_dirs:
            dirpath = self.install_dir / dirname
            if dirpath.exists():
                self.checks_passed.append(f"Directory exists: {dirname}/")
            else:
                self.checks_failed.append(f"Missing directory: {dirname}/")
                all_exist = False

        return all_exist

    def check_config_files(self) -> bool:
        """Check if configuration files exist"""
        config_dir = self.install_dir / "config"
        expected_files = [
            "phantom_config.yaml",
        ]

        all_exist = True
        for filename in expected_files:
            filepath = config_dir / filename
            if filepath.exists():
                self.checks_passed.append(f"Config file exists: {filename}")
            else:
                self.checks_warnings.append(f"Config file missing: {filename}")

        return True  # Non-critical

    def check_venv(self) -> bool:
        """Check if virtual environment exists"""
        venv_dir = self.install_dir / "venvs" / "phantom"

        if venv_dir.exists():
            self.checks_passed.append("Virtual environment exists")

            # Check for Python executable
            if sys.platform == "win32":
                python_exe = venv_dir / "Scripts" / "python.exe"
            else:
                python_exe = venv_dir / "bin" / "python"

            if python_exe.exists():
                self.checks_passed.append("Python executable found in venv")
                return True
            else:
                self.checks_failed.append("Python executable missing in venv")
                return False
        else:
            self.checks_warnings.append("Virtual environment not created yet")
            return True  # Non-critical during initial installation

    def check_controller_health(
        self, host: str = "localhost", port: int = 8080
    ) -> bool:
        """Check if controller is running and healthy"""
        try:
            url = f"http://{host}:{port}/health"
            req = urllib.request.Request(url, method="GET")

            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    self.checks_passed.append(
                        f"Controller is running and healthy at {host}:{port}"
                    )
                    return True
                else:
                    self.checks_warnings.append(
                        f"Controller responded with status {response.status}"
                    )
                    return False
        except urllib.error.URLError:
            self.checks_warnings.append(
                f"Controller not running at {host}:{port} (this is OK if not started yet)"
            )
            return True  # Non-critical
        except Exception as e:
            self.checks_warnings.append(f"Could not check controller health: {e}")
            return True  # Non-critical

    def check_ports(self, ports: List[int]) -> Dict[int, bool]:
        """Check if ports are available"""
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
                    self.checks_warnings.append(f"Port {port} is in use")
                    results[port] = False
            except Exception as e:
                self.checks_warnings.append(f"Could not check port {port}: {e}")
                results[port] = True  # Assume available

        return results

    def run_all_checks(self, check_controller: bool = False) -> bool:
        """Run all health checks"""
        checks = [
            self.check_directory_structure(),
            self.check_config_files(),
            self.check_venv(),
        ]

        # Check ports
        self.check_ports([8080, 8081, 3000])

        # Optionally check controller
        if check_controller:
            self.check_controller_health()

        return all(checks)

    def print_report(self):
        """Print health check report"""
        print("\n" + "=" * 60)
        print("HEALTH CHECK REPORT")
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
            print("✅ Installation health check passed!")
        else:
            print("❌ Some checks failed. Please review and fix issues.")

        print("=" * 60 + "\n")

        return len(self.checks_failed) == 0


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        install_dir = sys.argv[1]
    else:
        install_dir = os.getcwd()

    print(f"Checking Phantom installation at: {install_dir}\n")

    checker = HealthChecker(install_dir)

    # Check if controller should be checked
    check_controller = "--check-controller" in sys.argv

    success = checker.run_all_checks(check_controller=check_controller)
    checker.print_report()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
