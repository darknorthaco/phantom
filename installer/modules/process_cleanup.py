#!/usr/bin/env python3
"""
Process Cleanup Module
Enhanced process termination logic assimilated from rm-phantom
"""

import os
import sys
import subprocess
import signal
import time
import platform
from typing import List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class ProcessCleanup:
    """Handles comprehensive process cleanup for Phantom components"""

    PHANTOM_PROCESS_PATTERNS = [
        "phantom",
        "run_integrated_phantom.py",
        "run.py",
        "phantom_controller",
        "phantom_worker",
        "phantom_socket",
    ]

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback or print
        self.os_type = platform.system()
        self.dry_run = False

    def set_dry_run(self, enabled: bool):
        """Enable or disable dry-run mode"""
        self.dry_run = enabled

    def _log(self, message: str):
        """Log progress message"""
        logger.info(message)
        if self.progress_callback:
            self.progress_callback(message)

    def find_phantom_processes(self) -> List[int]:
        """Find all running phantom processes using multiple detection methods"""
        pids = set()

        # Method 1: pgrep-like search for process names
        pids.update(self._find_by_process_name())

        # Method 2: Check for known phantom executables
        pids.update(self._find_by_executable_path())

        # Method 3: Check PID files
        pids.update(self._find_by_pid_files())

        return sorted(list(pids))

    def _find_by_process_name(self) -> List[int]:
        """Find processes by name patterns (equivalent to pgrep -f phantom)"""
        pids = []

        try:
            if self.os_type == "Windows":
                # Use tasklist on Windows
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split(',')
                            if len(parts) >= 2:
                                pid = int(parts[1].strip('"'))
                                # Check command line for phantom patterns
                                try:
                                    cmd_result = subprocess.run(
                                        ["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine"],
                                        capture_output=True,
                                        text=True,
                                        timeout=5
                                    )
                                    if cmd_result.returncode == 0:
                                        cmd_line = cmd_result.stdout.lower()
                                        if any(pattern.lower() in cmd_line for pattern in self.PHANTOM_PROCESS_PATTERNS):
                                            pids.append(pid)
                                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                                    pass
            else:
                # Unix-like systems: use pgrep
                for pattern in self.PHANTOM_PROCESS_PATTERNS:
                    try:
                        result = subprocess.run(
                            ["pgrep", "-f", pattern],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            for line in result.stdout.strip().split('\n'):
                                if line.strip():
                                    try:
                                        pids.append(int(line.strip()))
                                    except ValueError:
                                        pass
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        # pgrep not available, try alternative method
                        pids.extend(self._find_processes_unix_alternative(pattern))
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass

        return pids

    def _find_processes_unix_alternative(self, pattern: str) -> List[int]:
        """Alternative process finding for Unix systems without pgrep"""
        pids = []
        try:
            # Use ps command
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if pattern.lower() in line.lower():
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                pid = int(parts[1])
                                pids.append(pid)
                            except (ValueError, IndexError):
                                pass
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        return pids

    def _find_by_executable_path(self) -> List[int]:
        """Find processes by known phantom executable paths"""
        pids = []
        phantom_paths = [
            "run_integrated_phantom.py",
            "run.py",
            "phantom_integrated.pid",
        ]

        for path in phantom_paths:
            if os.path.exists(path):
                try:
                    # Get PID from file if it's a PID file
                    if path.endswith('.pid'):
                        with open(path, 'r') as f:
                            pid = int(f.read().strip())
                            if self._process_exists(pid):
                                pids.append(pid)
                    else:
                        # For scripts, try to find running instances
                        if self.os_type == "Windows":
                            # Use wmic to find python processes running this script
                            pass  # Simplified for now
                        else:
                            try:
                                result = subprocess.run(
                                    ["pgrep", "-f", os.path.basename(path)],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if result.returncode == 0:
                                    for line in result.stdout.strip().split('\n'):
                                        if line.strip():
                                            pids.append(int(line.strip()))
                            except (subprocess.TimeoutExpired, FileNotFoundError):
                                pass
                except (OSError, ValueError):
                    pass

        return pids

    def _find_by_pid_files(self) -> List[int]:
        """Find processes using PID files"""
        pids = []
        pid_files = [
            "phantom_integrated.pid",
            "phantom_controller.pid",
            "phantom_worker.pid",
        ]

        for pid_file in pid_files:
            if os.path.exists(pid_file):
                try:
                    with open(pid_file, 'r') as f:
                        pid = int(f.read().strip())
                        if self._process_exists(pid):
                            pids.append(pid)
                except (OSError, ValueError):
                    pass

        return pids

    def _process_exists(self, pid: int) -> bool:
        """Check if a process with given PID exists"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def terminate_processes(self, pids: List[int], graceful_timeout: int = 5) -> bool:
        """Terminate processes with graceful shutdown then force kill"""
        if not pids:
            self._log("No processes to terminate")
            return True

        self._log(f"Found phantom processes: {pids}")

        if self.dry_run:
            self._log(f"[DRY RUN] Would terminate PIDs: {pids}")
            return True

        success = True

        # Phase 1: Graceful termination (SIGTERM)
        self._log("Sending SIGTERM to phantom processes...")
        for pid in pids:
            try:
                if self.os_type == "Windows":
                    # On Windows, use taskkill
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T"],
                        capture_output=True,
                        timeout=5
                    )
                else:
                    os.kill(pid, signal.SIGTERM)
                self._log(f"  ✓ Sent SIGTERM to PID {pid}")
            except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                self._log(f"  ✗ Failed to send SIGTERM to PID {pid}: {e}")
                success = False

        # Wait for graceful shutdown
        if graceful_timeout > 0:
            self._log(f"Waiting {graceful_timeout}s for graceful shutdown...")
            time.sleep(graceful_timeout)

        # Phase 2: Check for survivors and force kill (SIGKILL)
        survivors = []
        for pid in pids:
            if self._process_exists(pid):
                survivors.append(pid)

        if survivors:
            self._log(f"Processes still alive after SIGTERM: {survivors}")
            self._log("Sending SIGKILL to survivors...")
            for pid in survivors:
                try:
                    if self.os_type == "Windows":
                        subprocess.run(
                            ["taskkill", "/PID", str(pid), "/T", "/F"],
                            capture_output=True,
                            timeout=5
                        )
                    else:
                        os.kill(pid, signal.SIGKILL)
                    self._log(f"  ✓ Sent SIGKILL to PID {pid}")
                except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                    self._log(f"  ✗ Failed to kill PID {pid}: {e}")
                    success = False

            # Final check
            final_survivors = [pid for pid in survivors if self._process_exists(pid)]
            if final_survivors:
                self._log(f"❌ Some processes could not be killed: {final_survivors}")
                success = False
            else:
                self._log("✅ All phantom processes terminated")
        else:
            self._log("✅ All phantom processes terminated gracefully")

        return success

    def cleanup(self) -> bool:
        """Perform complete process cleanup"""
        self._log("🔍 Searching for phantom processes...")
        pids = self.find_phantom_processes()

        if not pids:
            self._log("✅ No phantom processes found")
            return True

        return self.terminate_processes(pids)
