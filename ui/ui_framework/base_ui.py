#!/usr/bin/env python3
"""
Phantom UI Framework - Base UI Interface
Swappable UI architecture for custom Phantom interfaces
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class PhantomUI(ABC):
    """
    Abstract base class for Phantom UI implementations.

    This framework allows different UI implementations (web, terminal, mobile, etc.)
    to be plugged into the Phantom system while maintaining consistent behavior
    and protocol abstraction.
    """

    def __init__(self, phantom_config: Dict[str, Any]):
        """
        Initialize the UI with phantom backend configuration.

        Args:
            phantom_config: Configuration dict containing:
                - socket_host: Host for phantom socket connection
                - socket_port: Port for phantom socket connection
                - controller_host: Host for phantom controller
                - controller_port: Port for phantom controller
                - protocol: Protocol type (websocket, http, etc.)
                - execution_mode: Default execution mode (AUTO/HYBRID/MANUAL)
        """
        self.config = phantom_config
        self.logger = logging.getLogger(self.__class__.__name__)

        # UI state
        self.connected = False
        self.execution_mode = phantom_config.get('execution_mode', 'AUTO')

        # Callbacks
        self.on_task_received: Optional[Callable] = None
        self.on_task_completed: Optional[Callable] = None
        self.on_system_status: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    @abstractmethod
    def start(self) -> bool:
        """
        Start the UI.

        Returns:
            bool: True if UI started successfully
        """
        pass

    @abstractmethod
    def stop(self) -> bool:
        """
        Stop the UI.

        Returns:
            bool: True if UI stopped successfully
        """
        pass

    @abstractmethod
    def connect_to_phantom(self) -> bool:
        """
        Establish connection to phantom backend.

        Returns:
            bool: True if connection established
        """
        pass

    @abstractmethod
    def disconnect_from_phantom(self) -> bool:
        """
        Disconnect from phantom backend.

        Returns:
            bool: True if disconnected successfully
        """
        pass

    @abstractmethod
    def submit_task(self, task_data: Dict[str, Any]) -> str:
        """
        Submit a task for execution.

        Args:
            task_data: Task specification

        Returns:
            str: Task ID
        """
        pass

    @abstractmethod
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get current system status.

        Returns:
            dict: System status information
        """
        pass

    @abstractmethod
    def set_execution_mode(self, mode: str) -> bool:
        """
        Set execution mode (AUTO/HYBRID/MANUAL).

        Args:
            mode: Execution mode

        Returns:
            bool: True if mode set successfully
        """
        pass

    @abstractmethod
    def get_available_workers(self) -> List[Dict[str, Any]]:
        """
        Get list of available workers.

        Returns:
            list: Worker information
        """
        pass

    @abstractmethod
    def approve_task(self, task_id: str, approved: bool, worker_id: Optional[str] = None) -> bool:
        """
        Approve or reject a task (for HYBRID mode).

        Args:
            task_id: Task identifier
            approved: True to approve, False to reject
            worker_id: Specific worker to assign (optional)

        Returns:
            bool: True if approval processed
        """
        pass

    def set_callback(self, event: str, callback: Callable):
        """
        Set event callback.

        Args:
            event: Event name ('task_received', 'task_completed', 'system_status', 'error')
            callback: Callback function
        """
        if event == 'task_received':
            self.on_task_received = callback
        elif event == 'task_completed':
            self.on_task_completed = callback
        elif event == 'system_status':
            self.on_system_status = callback
        elif event == 'error':
            self.on_error = callback
        else:
            raise ValueError(f"Unknown event: {event}")

    def _trigger_callback(self, event: str, *args, **kwargs):
        """Trigger a callback if set."""
        callback = getattr(self, f'on_{event}', None)
        if callback:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in {event} callback: {e}")

    def validate_config(self) -> bool:
        """
        Validate UI configuration.

        Returns:
            bool: True if configuration is valid
        """
        required_keys = ['socket_host', 'socket_port', 'controller_host', 'controller_port']
        for key in required_keys:
            if key not in self.config:
                self.logger.error(f"Missing required config key: {key}")
                return False

        mode = self.config.get('execution_mode', 'AUTO')
        if mode not in ['AUTO', 'HYBRID', 'MANUAL']:
            self.logger.error(f"Invalid execution mode: {mode}")
            return False

        return True

    def get_supported_protocols(self) -> List[str]:
        """
        Get list of supported protocols for this UI.

        Returns:
            list: Supported protocol names
        """
        return ['websocket', 'http']  # Default protocols

    def get_ui_info(self) -> Dict[str, Any]:
        """
        Get information about this UI implementation.

        Returns:
            dict: UI information
        """
        return {
            'name': self.__class__.__name__,
            'version': getattr(self, 'VERSION', '1.0.0'),
            'supported_protocols': self.get_supported_protocols(),
            'execution_modes': ['AUTO', 'HYBRID', 'MANUAL'],
            'connected': self.connected,
            'current_mode': self.execution_mode
        }