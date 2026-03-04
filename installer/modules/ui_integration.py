#!/usr/bin/env python3
"""
UI Integration Module
Manages RedBlue UI integration configuration
"""

from typing import Dict, Optional, Tuple


class UIIntegration:
    """RedBlue UI integration manager"""

    DEFAULT_UI_PORT = 3000
    DEFAULT_UI_HOST = "127.0.0.1"

    def __init__(self):
        self.enabled = False
        self.host = self.DEFAULT_UI_HOST
        self.port = self.DEFAULT_UI_PORT
        self.socket_integration = False
        self.controller_url = "http://localhost:8080"

    def enable(self):
        """Enable UI integration"""
        self.enabled = True

    def disable(self):
        """Disable UI integration"""
        self.enabled = False

    def configure(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        controller_url: Optional[str] = None,
    ):
        """Configure UI settings"""
        if host:
            self.host = host
        if port:
            self.port = port
        if controller_url:
            self.controller_url = controller_url

    def enable_socket_integration(self):
        """Enable socket integration for real-time updates"""
        self.socket_integration = True

    def disable_socket_integration(self):
        """Disable socket integration"""
        self.socket_integration = False

    def get_config(self) -> Dict:
        """Get UI configuration"""
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "socket_integration": self.socket_integration,
            "controller_url": self.controller_url,
        }

    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """Validate UI configuration"""
        if not self.enabled:
            return True, None

        if self.port < 1024 or self.port > 65535:
            return False, f"Invalid port number: {self.port}"

        return True, None
