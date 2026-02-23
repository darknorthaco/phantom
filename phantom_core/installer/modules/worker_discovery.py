#!/usr/bin/env python3
"""
Worker Discovery Module
Discovers and configures worker nodes on the network
"""

import socket
import subprocess
import ipaddress
from typing import Dict, List, Optional, Tuple
import json
import time


class WorkerDiscovery:
    """Worker discovery and configuration"""

    DISCOVERY_PORT = 8090  # Default worker port
    TIMEOUT = 2  # seconds

    def __init__(self):
        self.discovered_workers = []
        self.selected_workers = []
        self.mode = "skip"  # 'manual', 'comprehensive', or 'skip'

    def get_local_network(self) -> Optional[ipaddress.IPv4Network]:
        """Get local network CIDR"""
        try:
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()

            # Assume /24 network
            network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            return network
        except Exception as e:
            print(f"Could not determine local network: {e}")
            return None

    def ping_host(self, ip: str, timeout: int = 1) -> bool:
        """Ping a host to check if it's alive"""
        try:
            import platform

            param = "-n" if platform.system().lower() == "windows" else "-c"
            timeout_param = "-w" if platform.system().lower() == "windows" else "-W"
            timeout_value = (
                str(timeout * 1000)
                if platform.system().lower() == "windows"
                else str(timeout)
            )

            command = ["ping", param, "1", timeout_param, timeout_value, ip]
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout + 1,
            )
            return result.returncode == 0
        except Exception:
            return False

    def check_worker_port(self, ip: str, port: int = None) -> bool:
        """Check if worker port is open"""
        if port is None:
            port = self.DISCOVERY_PORT

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.TIMEOUT)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def discover_workers_manual(
        self, network: Optional[ipaddress.IPv4Network] = None
    ) -> List[Dict]:
        """Manual discovery mode - basic ping scan"""
        if network is None:
            network = self.get_local_network()

        if network is None:
            return []

        workers = []
        print(f"\n🔍 Scanning network {network}...")

        # Ping sweep
        alive_hosts = []
        for ip in network.hosts():
            ip_str = str(ip)
            if self.ping_host(ip_str, timeout=1):
                alive_hosts.append(ip_str)
                print(f"  Found: {ip_str}")

        # Check for worker ports
        for i, ip in enumerate(alive_hosts, 1):
            worker_info = {
                "id": i,
                "ip": ip,
                "hostname": self._get_hostname(ip),
                "port": self.DISCOVERY_PORT,
                "available": self.check_worker_port(ip),
                "gpu": "Unknown",
            }
            workers.append(worker_info)

        self.discovered_workers = workers
        return workers

    def discover_workers_comprehensive(
        self, network: Optional[ipaddress.IPv4Network] = None
    ) -> List[Dict]:
        """Comprehensive discovery mode - detailed worker detection"""
        if network is None:
            network = self.get_local_network()

        if network is None:
            return []

        workers = []
        print(f"\n🔍 Auto-discovering Phantom workers on {network}...")

        # Scan for workers on common ports
        worker_ports = [8090, 8091, 8092, 8093, 8094]

        for ip in network.hosts():
            ip_str = str(ip)

            for port in worker_ports:
                if self.check_worker_port(ip_str, port):
                    worker_info = self._query_worker_info(ip_str, port)
                    if worker_info:
                        workers.append(worker_info)
                        print(
                            f"  ✓ Found: {ip_str}:{port} - {worker_info.get('name', 'Unknown')}"
                        )
                        break

        self.discovered_workers = workers
        return workers

    def _get_hostname(self, ip: str) -> str:
        """Get hostname for IP address"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except Exception:
            return ip

    def _query_worker_info(self, ip: str, port: int) -> Optional[Dict]:
        """Query worker for detailed information"""
        try:
            # Try to connect and get worker info
            # This is a placeholder - actual implementation would use the Phantom protocol
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.TIMEOUT)
            sock.connect((ip, port))

            # Send info request
            request = json.dumps({"action": "get_info"}).encode("utf-8")
            sock.send(request)

            # Receive response
            response = sock.recv(4096).decode("utf-8")
            sock.close()

            info = json.loads(response)
            return {
                "ip": ip,
                "port": port,
                "name": info.get("worker_id", "Unknown"),
                "hostname": self._get_hostname(ip),
                "gpu": info.get("gpu_name", "Unknown"),
                "available": True,
            }
        except Exception:
            # Fallback if query fails
            return {
                "ip": ip,
                "port": port,
                "name": f"Worker-{ip}",
                "hostname": self._get_hostname(ip),
                "gpu": "Unknown",
                "available": True,
            }

    def select_workers(self, indices: List[int]):
        """Select workers by index"""
        self.selected_workers = []
        for idx in indices:
            if 0 < idx <= len(self.discovered_workers):
                self.selected_workers.append(self.discovered_workers[idx - 1])

    def select_all_workers(self):
        """Select all discovered workers"""
        self.selected_workers = self.discovered_workers.copy()

    def get_selected_workers(self) -> List[Dict]:
        """Get list of selected workers"""
        return self.selected_workers

    def get_worker_configs(self) -> List[Dict]:
        """Generate configuration for selected workers"""
        configs = []

        for i, worker in enumerate(self.selected_workers):
            config = {
                "worker_id": worker.get("name", f"worker-{i+1}"),
                "controller_host": "localhost",  # Will be updated by config generator
                "controller_port": 8080,
                "worker_host": worker["ip"],
                "worker_port": worker["port"],
                "gpu_name": worker.get("gpu", "Unknown"),
            }
            configs.append(config)

        return configs

    def set_discovery_mode(self, mode: str):
        """Set discovery mode: 'manual', 'comprehensive', or 'skip'"""
        if mode in ["manual", "comprehensive", "skip"]:
            self.mode = mode
        else:
            raise ValueError(f"Invalid mode: {mode}")

    def run_discovery(self) -> List[Dict]:
        """Run discovery based on selected mode"""
        if self.mode == "manual":
            return self.discover_workers_manual()
        elif self.mode == "comprehensive":
            return self.discover_workers_comprehensive()
        else:  # skip
            return []
