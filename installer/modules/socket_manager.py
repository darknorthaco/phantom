#!/usr/bin/env python3
"""
Socket Manager
Configures socket infrastructure for real-time communication
"""

from typing import Dict, Optional, Tuple


class SocketManager:
    """Manages socket infrastructure configuration"""

    DEFAULT_SOCKET_PORT = 8081
    DEFAULT_SOCKET_HOST = "127.0.0.1"

    def __init__(self):
        self.enabled = False
        self.host = self.DEFAULT_SOCKET_HOST
        self.port = self.DEFAULT_SOCKET_PORT
        self.ssl_enabled = False
        self.ssl_cert = None
        self.ssl_key = None

    def enable(self):
        """Enable socket infrastructure"""
        self.enabled = True

    def disable(self):
        """Disable socket infrastructure"""
        self.enabled = False

    def configure(self, host: Optional[str] = None, port: Optional[int] = None):
        """Configure socket settings"""
        if host:
            self.host = host
        if port:
            self.port = port

    def enable_ssl(self, cert_path: str, key_path: str):
        """Enable SSL for socket connections"""
        self.ssl_enabled = True
        self.ssl_cert = cert_path
        self.ssl_key = key_path

    def disable_ssl(self):
        """Disable SSL for socket connections"""
        self.ssl_enabled = False
        self.ssl_cert = None
        self.ssl_key = None

    def get_config(self) -> Dict:
        """Get socket configuration"""
        config = {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "ssl_enabled": self.ssl_enabled,
        }

        if self.ssl_enabled:
            config["ssl_cert"] = self.ssl_cert
            config["ssl_key"] = self.ssl_key

        return config

    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """Validate socket configuration"""
        if not self.enabled:
            return True, None

        if self.port < 1024 or self.port > 65535:
            return False, f"Invalid port number: {self.port}"

        if self.ssl_enabled:
            if not self.ssl_cert or not self.ssl_key:
                return False, "SSL enabled but certificate or key path not provided"

        return True, None
