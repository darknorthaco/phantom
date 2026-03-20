#!/usr/bin/env python3
"""
Windows-Specific Installation Logic
Handles Windows-specific configurations and setup
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

_installer_dir = Path(__file__).resolve().parent
if str(_installer_dir) not in sys.path:
    sys.path.insert(0, str(_installer_dir))
from legacy_installer_gate import exit_if_legacy_installer_disabled


class WindowsInstaller:
    """Windows-specific installation logic"""

    def __init__(self, install_dir: Path):
        self.install_dir = install_dir

    def check_execution_policy(self) -> bool:
        """Check PowerShell execution policy"""
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-ExecutionPolicy"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            policy = result.stdout.strip()

            if policy in ["Restricted", "AllSigned"]:
                print(f"⚠️  Current PowerShell execution policy: {policy}")
                print("You may need to change it to run installation scripts.")
                print("Run as Administrator:")
                print(
                    "  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
                )
                return False

            return True
        except Exception as e:
            print(f"Could not check execution policy: {e}")
            return True  # Non-critical

    def create_windows_service_config(self) -> bool:
        """Create Windows service configuration"""
        try:
            service_script = self.install_dir / "install_service.ps1"

            with open(service_script, "w") as f:
                f.write("# Install Phantom as Windows Service\n")
                f.write("# Run this script as Administrator\n\n")
                f.write('$ErrorActionPreference = "Stop"\n\n')
                f.write(f'$InstallDir = "{self.install_dir}"\n')
                f.write(
                    '$VenvPython = "$InstallDir\\venvs\\phantom\\Scripts\\python.exe"\n'
                )
                f.write('$RunScript = "$InstallDir\\run_integrated_phantom.py"\n\n')
                f.write("# Create service wrapper script\n")
                f.write('$ServiceScript = "$InstallDir\\phantom_service.ps1"\n')
                f.write('@"\n')
                f.write('Set-Location "$InstallDir"\n')
                f.write('& "$VenvPython" "$RunScript"\n')
                f.write('"@ | Out-File -FilePath $ServiceScript -Encoding UTF8\n\n')
                f.write("# Install service\n")
                f.write('New-Service -Name "PhantomController" `\n')
                f.write(
                    '    -BinaryPathName "powershell.exe -ExecutionPolicy Bypass -File $ServiceScript" `\n'
                )
                f.write('    -DisplayName "Phantom Distributed Compute Controller" `\n')
                f.write(
                    '    -Description "Phantom distributed compute fabric controller service" `\n'
                )
                f.write("    -StartupType Automatic\n\n")
                f.write('Write-Host "Service installed successfully!"\n')
                f.write('Write-Host "To start: Start-Service PhantomController"\n')

            return True
        except Exception as e:
            print(f"Failed to create service config: {e}")
            return False

    def create_registry_entries(self) -> bool:
        """Create Windows registry entries (optional)"""
        # This is optional functionality
        # Not implemented to keep installer simple
        return True

    def add_to_path(self) -> bool:
        """Add installation directory to PATH (optional)"""
        # This is optional functionality
        # User can add manually if needed
        print("\n💡 TIP: You can add Phantom to your PATH:")
        print(f'   $env:Path += ";{self.install_dir}"')
        return True

    def create_desktop_shortcut(self) -> bool:
        """Create desktop shortcut (optional)"""
        # This is optional functionality
        # Not implemented to keep installer simple
        return True

    def setup_windows_firewall(self) -> bool:
        """Setup Windows Firewall rules (optional)"""
        print("\n💡 TIP: You may need to configure Windows Firewall to allow Phantom:")
        print("   Run as Administrator:")
        print(
            f'   New-NetFirewallRule -DisplayName "Phantom Controller" -Direction Inbound -Port 8080 -Protocol TCP -Action Allow'
        )
        return True


def main():
    """Main entry point for Windows-specific setup"""
    exit_if_legacy_installer_disabled()
    if len(sys.argv) > 1:
        install_dir = Path(sys.argv[1])
    else:
        install_dir = Path.cwd()

    print("Windows-Specific Setup")
    print("=" * 60)

    installer = WindowsInstaller(install_dir)

    # Run Windows-specific checks and setup
    installer.check_execution_policy()
    installer.create_windows_service_config()
    installer.add_to_path()
    installer.setup_windows_firewall()

    print("\n✅ Windows-specific setup complete!")


if __name__ == "__main__":
    main()
