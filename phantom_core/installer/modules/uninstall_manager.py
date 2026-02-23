#!/usr/bin/env python3
"""
Uninstall Manager
Handles safe and complete uninstallation of Phantom components
"""

import os
import sys
import subprocess
import shutil
import signal
from pathlib import Path
from typing import List, Dict, Optional, Callable
import platform


class UninstallManager:
    """Manages uninstallation of Phantom components"""

    def __init__(
        self,
        install_dir: str,
        manifest_manager,
        progress_callback: Optional[Callable] = None,
    ):
        self.install_dir = Path(install_dir)
        self.manifest = manifest_manager
        self.progress_callback = progress_callback or print
        self.os_type = platform.system()
        self.dry_run = False
        self.backup_dir = None

    def set_dry_run(self, enabled: bool):
        """Enable or disable dry-run mode"""
        self.dry_run = enabled

    def set_backup_dir(self, backup_dir: Optional[str]):
        """Set directory for backing up configurations"""
        self.backup_dir = Path(backup_dir) if backup_dir else None

    def _log(self, message: str):
        """Log progress message"""
        if self.progress_callback:
            self.progress_callback(message)

    def _execute_command(self, cmd: List[str], check: bool = False) -> bool:
        """Execute shell command"""
        if self.dry_run:
            self._log(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            return True

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=check,
            )
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            self._log(f"⚠️  Command failed: {e}")
            return False
        except FileNotFoundError:
            self._log(f"⚠️  Command not found: {cmd[0]}")
            return False

    def stop_services(self) -> bool:
        """Stop all Phantom services"""
        self._log("\n🛑 Stopping services...")
        services = self.manifest.get_services()

        if not services:
            self._log("  No services found in manifest")
            return True

        success = True
        for service in services:
            service_name = service.get("name")
            service_type = service.get("type", "systemd")

            if service_type == "systemd" and self.os_type == "Linux":
                success &= self._stop_systemd_service(service_name)
            elif service_type == "windows_service" and self.os_type == "Windows":
                success &= self._stop_windows_service(service_name)
            elif service_type == "launchd" and self.os_type == "Darwin":
                success &= self._stop_launchd_service(service_name)

        return success

    def _stop_systemd_service(self, service_name: str) -> bool:
        """Stop systemd service"""
        self._log(f"  Stopping systemd service: {service_name}")

        # Check if service is active
        if not self.dry_run:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode != 0:
                self._log(f"    Service {service_name} is not running")
                return True

        # Stop the service
        if self._execute_command(["sudo", "systemctl", "stop", service_name]):
            self._log(f"    ✓ Stopped {service_name}")
            return True
        else:
            self._log(f"    ✗ Failed to stop {service_name}")
            return False

    def _stop_windows_service(self, service_name: str) -> bool:
        """Stop Windows service"""
        self._log(f"  Stopping Windows service: {service_name}")
        if self._execute_command(["sc", "stop", service_name]):
            self._log(f"    ✓ Stopped {service_name}")
            return True
        else:
            self._log(f"    ✗ Failed to stop {service_name}")
            return False

    def _stop_launchd_service(self, service_name: str) -> bool:
        """Stop launchd service (macOS)"""
        self._log(f"  Stopping launchd service: {service_name}")
        if self._execute_command(["launchctl", "stop", service_name]):
            self._log(f"    ✓ Stopped {service_name}")
            return True
        else:
            self._log(f"    ✗ Failed to stop {service_name}")
            return False

    def stop_processes_by_pid(self) -> bool:
        """Stop processes using PID files"""
        self._log("\n🛑 Stopping processes...")
        pid_files = self.manifest.get_pid_files()

        if not pid_files:
            self._log("  No PID files found in manifest")
            # Fallback: look for common PID files
            pid_files = self._find_pid_files()

        success = True
        for pid_file in pid_files:
            success &= self._stop_process_by_pid_file(pid_file)

        return success

    def _find_pid_files(self) -> List[str]:
        """Find PID files in installation directory"""
        pid_files = []
        if self.install_dir.exists():
            for pid_file in self.install_dir.rglob("*.pid"):
                pid_files.append(str(pid_file))
        return pid_files

    def _stop_process_by_pid_file(self, pid_file: str) -> bool:
        """Stop process using PID file"""
        pid_path = Path(pid_file)

        if not pid_path.exists():
            self._log(f"  PID file not found: {pid_file}")
            return True

        try:
            with open(pid_path, "r") as f:
                pid = int(f.read().strip())

            self._log(f"  Stopping process with PID {pid} from {pid_file}")

            if self.dry_run:
                self._log(f"    [DRY RUN] Would kill PID {pid}")
                return True

            # Try graceful termination first (SIGTERM)
            try:
                os.kill(pid, signal.SIGTERM)
                self._log(f"    ✓ Sent SIGTERM to PID {pid}")

                # Wait briefly for process to exit
                import time

                time.sleep(2)

                # Check if process still exists
                # Note: os.kill(pid, 0) doesn't send a signal; it's a special case
                # that checks if the process exists. Raises ProcessLookupError if not.
                try:
                    os.kill(pid, 0)  # Check process existence
                    # Process still exists, force kill
                    os.kill(pid, signal.SIGKILL)
                    self._log(f"    ✓ Sent SIGKILL to PID {pid}")
                except ProcessLookupError:
                    # Process terminated successfully after SIGTERM
                    pass

                return True

            except ProcessLookupError:
                self._log(f"    Process {pid} not running")
                return True
            except PermissionError:
                self._log(f"    ✗ Permission denied to kill PID {pid}")
                return False

        except (ValueError, IOError) as e:
            self._log(f"  ⚠️  Error reading PID file {pid_file}: {e}")
            return False

    def backup_configs(self) -> bool:
        """Backup configuration files before removal"""
        if not self.backup_dir:
            return True

        self._log("\n💾 Backing up configurations...")
        config_files = self.manifest.get_config_files()

        if not config_files:
            self._log("  No configuration files to backup")
            return True

        if self.dry_run:
            self._log(
                f"  [DRY RUN] Would backup {len(config_files)} config files to {self.backup_dir}"
            )
            return True

        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            backed_up = 0

            for config_file in config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    backup_path = self.backup_dir / config_path.name
                    shutil.copy2(config_path, backup_path)
                    backed_up += 1
                    self._log(f"  ✓ Backed up: {config_path.name}")

            self._log(
                f"  Backed up {backed_up} configuration files to {self.backup_dir}"
            )
            return True

        except (IOError, OSError) as e:
            self._log(f"  ✗ Backup failed: {e}")
            return False

    def remove_pid_files(self) -> bool:
        """Remove PID files"""
        self._log("\n🧹 Removing PID files...")
        pid_files = self.manifest.get_pid_files()

        if not pid_files:
            pid_files = self._find_pid_files()

        if not pid_files:
            self._log("  No PID files to remove")
            return True

        success = True
        for pid_file in pid_files:
            pid_path = Path(pid_file)
            if pid_path.exists():
                if self.dry_run:
                    self._log(f"  [DRY RUN] Would remove: {pid_file}")
                else:
                    try:
                        pid_path.unlink()
                        self._log(f"  ✓ Removed: {pid_file}")
                    except OSError as e:
                        self._log(f"  ✗ Failed to remove {pid_file}: {e}")
                        success = False

        return success

    def remove_log_files(self, preserve_logs: bool = False) -> bool:
        """Remove log files (optional)"""
        if preserve_logs:
            self._log("\n📝 Preserving log files (as requested)")
            return True

        self._log("\n🧹 Removing log files...")
        log_files = self.manifest.get_log_files()

        if not log_files:
            self._log("  No log files to remove")
            return True

        success = True
        for log_file in log_files:
            log_path = Path(log_file)
            if log_path.exists():
                if self.dry_run:
                    self._log(f"  [DRY RUN] Would remove: {log_file}")
                else:
                    try:
                        log_path.unlink()
                        self._log(f"  ✓ Removed: {log_file}")
                    except OSError as e:
                        self._log(f"  ✗ Failed to remove {log_file}: {e}")
                        success = False

        return success

    def remove_services(self) -> bool:
        """Remove service definitions"""
        self._log("\n🧹 Removing services...")
        services = self.manifest.get_services()

        if not services:
            self._log("  No services to remove")
            return True

        success = True
        for service in services:
            service_file = service.get("file")
            service_type = service.get("type", "systemd")
            service_name = service.get("name")

            if service_type == "systemd" and self.os_type == "Linux":
                success &= self._remove_systemd_service(service_name, service_file)
            elif service_type == "windows_service" and self.os_type == "Windows":
                success &= self._remove_windows_service(service_name)
            elif service_type == "launchd" and self.os_type == "Darwin":
                success &= self._remove_launchd_service(service_name, service_file)

        return success

    def _remove_systemd_service(self, service_name: str, service_file: str) -> bool:
        """Remove systemd service"""
        self._log(f"  Removing systemd service: {service_name}")

        # Disable service
        self._execute_command(["sudo", "systemctl", "disable", service_name])

        # Remove service file
        service_path = Path(service_file)
        if service_path.exists():
            if self.dry_run:
                self._log(f"    [DRY RUN] Would remove: {service_file}")
            else:
                try:
                    if service_path.parent == Path("/etc/systemd/system"):
                        self._execute_command(["sudo", "rm", str(service_path)])
                    else:
                        service_path.unlink()
                    self._log(f"    ✓ Removed service file: {service_file}")
                except OSError as e:
                    self._log(f"    ✗ Failed to remove service file: {e}")
                    return False

        # Reload systemd
        self._execute_command(["sudo", "systemctl", "daemon-reload"])
        return True

    def _remove_windows_service(self, service_name: str) -> bool:
        """Remove Windows service"""
        self._log(f"  Removing Windows service: {service_name}")
        if self._execute_command(["sc", "delete", service_name]):
            self._log(f"    ✓ Removed {service_name}")
            return True
        else:
            self._log(f"    ✗ Failed to remove {service_name}")
            return False

    def _remove_launchd_service(self, service_name: str, service_file: str) -> bool:
        """Remove launchd service (macOS)"""
        self._log(f"  Removing launchd service: {service_name}")

        # Unload service
        self._execute_command(["launchctl", "unload", service_file])

        # Remove plist file
        service_path = Path(service_file)
        if service_path.exists():
            if self.dry_run:
                self._log(f"    [DRY RUN] Would remove: {service_file}")
            else:
                try:
                    service_path.unlink()
                    self._log(f"    ✓ Removed service file: {service_file}")
                except OSError as e:
                    self._log(f"    ✗ Failed to remove service file: {e}")
                    return False

        return True

    def remove_venv(self) -> bool:
        """Remove virtual environment"""
        venv_path = self.manifest.get_venv_path()

        if not venv_path:
            self._log("\n📦 No virtual environment to remove")
            return True

        venv_dir = Path(venv_path)
        if not venv_dir.exists():
            self._log(f"\n📦 Virtual environment not found: {venv_path}")
            return True

        self._log(f"\n🧹 Removing virtual environment: {venv_path}")

        if self.dry_run:
            self._log("  [DRY RUN] Would remove virtual environment")
            return True

        try:
            shutil.rmtree(venv_dir)
            self._log("  ✓ Virtual environment removed")
            return True
        except OSError as e:
            self._log(f"  ✗ Failed to remove virtual environment: {e}")
            return False

    def remove_files(self, preserve_data: bool = False) -> bool:
        """Remove installed files"""
        self._log("\n🧹 Removing files...")
        files = self.manifest.get_files()

        if not files:
            self._log("  No files to remove")
            return True

        success = True
        removed_count = 0

        for file_path in files:
            path = Path(file_path)

            # Skip data files if preserve_data is True
            if preserve_data and "data" in path.parts:
                continue

            if path.exists():
                if self.dry_run:
                    self._log(f"  [DRY RUN] Would remove: {file_path}")
                    removed_count += 1
                else:
                    try:
                        path.unlink()
                        removed_count += 1
                    except OSError as e:
                        self._log(f"  ✗ Failed to remove {file_path}: {e}")
                        success = False

        self._log(
            f"  {'Would remove' if self.dry_run else 'Removed'} {removed_count} files"
        )
        return success

    def remove_directories(self, preserve_configs: bool = False) -> bool:
        """Remove installation directories"""
        self._log("\n🧹 Removing directories...")

        if self.dry_run:
            self._log(
                f"  [DRY RUN] Would remove installation directory: {self.install_dir}"
            )
            return True

        if not self.install_dir.exists():
            self._log(f"  Installation directory not found: {self.install_dir}")
            return True

        # If preserving configs, only remove specific subdirectories
        if preserve_configs:
            dirs_to_remove = ["venv", "logs", "tmp", "cache"]
            success = True

            for dir_name in dirs_to_remove:
                dir_path = self.install_dir / dir_name
                if dir_path.exists():
                    try:
                        shutil.rmtree(dir_path)
                        self._log(f"  ✓ Removed: {dir_name}/")
                    except OSError as e:
                        self._log(f"  ✗ Failed to remove {dir_name}: {e}")
                        success = False

            return success

        # Full removal
        try:
            shutil.rmtree(self.install_dir)
            self._log(f"  ✓ Removed installation directory: {self.install_dir}")
            return True
        except OSError as e:
            self._log(f"  ✗ Failed to remove installation directory: {e}")
            return False

    def remove_manifest(self) -> bool:
        """Remove installation manifest"""
        if self.dry_run:
            self._log("\n[DRY RUN] Would remove installation manifest")
            return True

        self._log("\n🧹 Removing installation manifest...")
        return self.manifest.remove_manifest()
