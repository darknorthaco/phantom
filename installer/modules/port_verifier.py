#!/usr/bin/env python3
"""
Port Verifier Module
Port verification and cleanup logic assimilated from rm-phantom
"""

import os
import sys
import subprocess
import socket
import platform
from typing import List, Dict, Optional, Callable, Tuple
import logging

logger = logging.getLogger(__name__)


class PortVerifier:
    """Handles port verification and cleanup for Phantom components"""

    PHANTOM_PORTS = [8080, 8081, 3000]

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

    def check_ports(self, ports: Optional[List[int]] = None) -> Dict[int, Dict]:
        """Check status of phantom ports"""
        if ports is None:
            ports = self.PHANTOM_PORTS

        results = {}
        for port in ports:
            results[port] = self._check_single_port(port)

        return results

    def _check_single_port(self, port: int) -> Dict:
        """Check if a specific port is in use"""
        result = {
            "port": port,
            "in_use": False,
            "process_info": None,
            "error": None
        }

        try:
            # Method 1: Try to bind to the port (quick check)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                sock.bind(('127.0.0.1', port))
                sock.close()
                result["in_use"] = False
                return result
            except OSError:
                # Port is in use
                result["in_use"] = True
                sock.close()

            # Method 2: Get detailed process information
            process_info = self._get_port_process_info(port)
            if process_info:
                result["process_info"] = process_info

        except Exception as e:
            result["error"] = str(e)

        return result

    def _get_port_process_info(self, port: int) -> Optional[Dict]:
        """Get process information for a port using system tools"""
        try:
            if self.os_type == "Windows":
                return self._get_port_info_windows(port)
            else:
                return self._get_port_info_unix(port)
        except Exception as e:
            logger.warning(f"Failed to get process info for port {port}: {e}")
            return None

    def _get_port_info_unix(self, port: int) -> Optional[Dict]:
        """Get port process info on Unix-like systems"""
        # Try ss command first (modern)
        try:
            result = subprocess.run(
                ["ss", "-tlnp", f"sport = :{port}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse ss output
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if f":{port}" in line and "LISTEN" in line:
                        parts = line.split()
                        if len(parts) >= 6:
                            peer_info = parts[5]  # users:(("process",pid,...))
                            if "users:" in peer_info:
                                # Extract PID from users field
                                import re
                                pid_match = re.search(r'pid=(\d+)', peer_info)
                                if pid_match:
                                    pid = int(pid_match.group(1))
                                    return {
                                        "pid": pid,
                                        "command": self._get_process_command(pid),
                                        "tool": "ss"
                                    }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback to lsof
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Skip header
                    parts = lines[1].split()
                    if len(parts) >= 2:
                        pid = int(parts[1])
                        return {
                            "pid": pid,
                            "command": parts[0] if len(parts) > 0 else "unknown",
                            "tool": "lsof"
                        }
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass

        # Fallback to netstat
        try:
            result = subprocess.run(
                ["netstat", "-tlnp"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if f":{port}" in line and "LISTEN" in line:
                        parts = line.split()
                        if len(parts) >= 7:
                            pid_program = parts[6]
                            if '/' in pid_program:
                                pid, program = pid_program.split('/', 1)
                                return {
                                    "pid": int(pid),
                                    "command": program,
                                    "tool": "netstat"
                                }
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass

        return None

    def _get_port_info_windows(self, port: int) -> Optional[Dict]:
        """Get port process info on Windows"""
        try:
            # Use netstat on Windows
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if f":{port}" in line and "LISTENING" in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = int(parts[4])
                            # Get process name
                            try:
                                task_result = subprocess.run(
                                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if task_result.returncode == 0:
                                    task_parts = task_result.stdout.strip().split(',')
                                    if len(task_parts) >= 1:
                                        process_name = task_parts[0].strip('"')
                                        return {
                                            "pid": pid,
                                            "command": process_name,
                                            "tool": "netstat+tasklist"
                                        }
                            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                                pass
                            return {
                                "pid": pid,
                                "command": "unknown",
                                "tool": "netstat"
                            }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

        return None

    def _get_process_command(self, pid: int) -> str:
        """Get command line for a process"""
        try:
            if self.os_type == "Windows":
                result = subprocess.run(
                    ["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        return lines[1].strip()
            else:
                with open(f"/proc/{pid}/cmdline", 'r') as f:
                    cmdline = f.read().replace('\0', ' ').strip()
                    return cmdline
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        return "unknown"

    def verify_ports_free(self, ports: Optional[List[int]] = None) -> Tuple[bool, List[int]]:
        """Verify that phantom ports are free"""
        if ports is None:
            ports = self.PHANTOM_PORTS

        self._log("🔍 Verifying phantom ports are free...")
        results = self.check_ports(ports)

        in_use_ports = []
        all_free = True

        for port, info in results.items():
            if info["in_use"]:
                self._log(f"❌ Port {port} is in use")
                if info["process_info"]:
                    proc = info["process_info"]
                    self._log(f"   Process: {proc['command']} (PID: {proc['pid']})")
                in_use_ports.append(port)
                all_free = False
            else:
                self._log(f"✅ Port {port} is free")

        if all_free:
            self._log("✅ All phantom ports are free")
        else:
            self._log(f"❌ Ports in use: {in_use_ports}")

        return all_free, in_use_ports

    def wait_for_ports_free(self, ports: Optional[List[int]] = None, timeout: int = 30) -> bool:
        """Wait for ports to become free"""
        if ports is None:
            ports = self.PHANTOM_PORTS

        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            all_free, _ = self.verify_ports_free(ports)
            if all_free:
                return True
            time.sleep(1)

        return False
