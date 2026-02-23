#!/usr/bin/env python3
"""
Phantom Protocol Adapter
UI-to-phantom protocol bridge for swappable UI architecture
"""

import asyncio
import json
import websockets
import requests
import threading
import time
from typing import Dict, Any, Optional, Callable, List
import logging

logger = logging.getLogger(__name__)


class ProtocolAdapter:
    """
    Protocol adapter for UI-phantom communication.

    Supports multiple transport protocols:
    - WebSocket for real-time communication
    - HTTP REST for request/response
    - Custom protocols via plugins
    """

    def __init__(self, phantom_config: Dict[str, Any]):
        """
        Initialize protocol adapter.

        Args:
            phantom_config: Phantom backend configuration
        """
        self.config = phantom_config
        self.logger = logging.getLogger(__name__)

        # Connection state
        self.websocket_connected = False
        self.websocket = None
        self.http_session = requests.Session()

        # Protocol settings
        self.protocol = phantom_config.get('protocol', 'websocket')
        self.socket_host = phantom_config['socket_host']
        self.socket_port = phantom_config['socket_port']
        self.controller_host = phantom_config['controller_host']
        self.controller_port = phantom_config['controller_port']

        # Message handling
        self.message_handlers: Dict[str, Callable] = {}
        self.response_handlers: Dict[str, Callable] = {}
        self.message_id_counter = 0

        # Threads
        self.websocket_thread: Optional[threading.Thread] = None
        self.running = False

    def connect(self) -> bool:
        """
        Establish connection to phantom backend.

        Returns:
            bool: True if connected successfully
        """
        try:
            if self.protocol == 'websocket':
                return self._connect_websocket()
            elif self.protocol == 'http':
                return self._connect_http()
            else:
                self.logger.error(f"Unsupported protocol: {self.protocol}")
                return False
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from phantom backend.

        Returns:
            bool: True if disconnected successfully
        """
        try:
            if self.protocol == 'websocket':
                return self._disconnect_websocket()
            elif self.protocol == 'http':
                return self._disconnect_http()
            return True
        except Exception as e:
            self.logger.error(f"Disconnect failed: {e}")
            return False

    def _connect_websocket(self) -> bool:
        """Connect via WebSocket."""
        if self.websocket_connected:
            return True

        self.running = True
        self.websocket_thread = threading.Thread(target=self._websocket_loop, daemon=True)
        self.websocket_thread.start()

        # Wait for connection
        timeout = 10
        start_time = time.time()
        while not self.websocket_connected and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        return self.websocket_connected

    def _disconnect_websocket(self) -> bool:
        """Disconnect WebSocket."""
        self.running = False
        if self.websocket:
            try:
                asyncio.run(self.websocket.close())
            except:
                pass
        self.websocket_connected = False
        return True

    def _connect_http(self) -> bool:
        """Connect via HTTP (always "connected" for HTTP)."""
        # Test connection with a ping
        try:
            response = self.http_session.get(
                f"http://{self.controller_host}:{self.controller_port}/status",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

    def _disconnect_http(self) -> bool:
        """Disconnect HTTP (close session)."""
        self.http_session.close()
        return True

    async def _websocket_loop(self):
        """WebSocket connection and message handling loop."""
        uri = f"ws://{self.socket_host}:{self.socket_port}"
        try:
            async with websockets.connect(uri) as websocket:
                self.websocket = websocket
                self.websocket_connected = True
                self.logger.info(f"Connected to Phantom via WebSocket: {uri}")

                while self.running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        self._handle_message(message)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        break

        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {e}")
        finally:
            self.websocket_connected = False
            self.websocket = None

    def _handle_message(self, message: str):
        """Handle incoming message from phantom."""
        try:
            data = json.loads(message)
            msg_type = data.get('type', 'unknown')

            # Handle responses to our requests
            if 'id' in data and data['id'] in self.response_handlers:
                handler = self.response_handlers.pop(data['id'])
                handler(data)
                return

            # Handle general messages
            if msg_type in self.message_handlers:
                self.message_handlers[msg_type](data)
            else:
                self.logger.warning(f"No handler for message type: {msg_type}")

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON message: {e}")
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    def send_message(self, message: Dict[str, Any], response_handler: Optional[Callable] = None) -> bool:
        """
        Send message to phantom backend.

        Args:
            message: Message to send
            response_handler: Callback for response (optional)

        Returns:
            bool: True if sent successfully
        """
        try:
            if self.protocol == 'websocket':
                return self._send_websocket(message, response_handler)
            elif self.protocol == 'http':
                return self._send_http(message, response_handler)
            else:
                self.logger.error(f"Unsupported protocol: {self.protocol}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            return False

    def _send_websocket(self, message: Dict[str, Any], response_handler: Optional[Callable]) -> bool:
        """Send message via WebSocket."""
        if not self.websocket_connected or not self.websocket:
            self.logger.error("WebSocket not connected")
            return False

        # Add message ID for response tracking
        if response_handler:
            message['id'] = self.message_id_counter
            self.response_handlers[self.message_id_counter] = response_handler
            self.message_id_counter += 1

        try:
            asyncio.run(self.websocket.send(json.dumps(message)))
            return True
        except Exception as e:
            self.logger.error(f"WebSocket send failed: {e}")
            return False

    def _send_http(self, message: Dict[str, Any], response_handler: Optional[Callable]) -> bool:
        """Send message via HTTP."""
        try:
            url = f"http://{self.controller_host}:{self.controller_port}/api"
            response = self.http_session.post(
                url,
                json=message,
                timeout=10
            )

            if response_handler:
                response_handler(response.json())

            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"HTTP send failed: {e}")
            return False

    def set_message_handler(self, message_type: str, handler: Callable):
        """
        Set handler for incoming messages.

        Args:
            message_type: Type of message to handle
            handler: Handler function
        """
        self.message_handlers[message_type] = handler

    def submit_task(self, task_data: Dict[str, Any]) -> Optional[str]:
        """
        Submit a task for execution.

        Args:
            task_data: Task specification

        Returns:
            str: Task ID or None if failed
        """
        message = {
            'type': 'submit_task',
            'data': task_data
        }

        task_id = None
        def response_handler(response):
            nonlocal task_id
            if response.get('status') == 'success':
                task_id = response.get('task_id')

        if self.send_message(message, response_handler):
            # Wait for response (simple synchronous approach)
            timeout = 5
            start_time = time.time()
            while task_id is None and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            return task_id

        return None

    def get_system_status(self) -> Optional[Dict[str, Any]]:
        """
        Get current system status.

        Returns:
            dict: System status or None if failed
        """
        message = {
            'type': 'get_status'
        }

        status = None
        def response_handler(response):
            nonlocal status
            if response.get('status') == 'success':
                status = response.get('data', {})

        if self.send_message(message, response_handler):
            # Wait for response
            timeout = 5
            start_time = time.time()
            while status is None and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            return status

        return None

    def set_execution_mode(self, mode: str) -> bool:
        """
        Set execution mode.

        Args:
            mode: Execution mode (AUTO/HYBRID/MANUAL)

        Returns:
            bool: True if set successfully
        """
        message = {
            'type': 'set_mode',
            'mode': mode
        }

        success = False
        def response_handler(response):
            nonlocal success
            success = response.get('status') == 'success'

        if self.send_message(message, response_handler):
            timeout = 5
            start_time = time.time()
            while not success and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            return success

        return False

    def get_available_workers(self) -> List[Dict[str, Any]]:
        """
        Get list of available workers.

        Returns:
            list: Worker information
        """
        message = {
            'type': 'get_workers'
        }

        workers = []
        def response_handler(response):
            nonlocal workers
            if response.get('status') == 'success':
                workers = response.get('data', [])

        if self.send_message(message, response_handler):
            timeout = 5
            start_time = time.time()
            while not workers and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            return workers

        return []

    def approve_task(self, task_id: str, approved: bool, worker_id: Optional[str] = None) -> bool:
        """
        Approve or reject a task.

        Args:
            task_id: Task identifier
            approved: True to approve, False to reject
            worker_id: Specific worker to assign

        Returns:
            bool: True if processed successfully
        """
        message = {
            'type': 'approve_task',
            'task_id': task_id,
            'approved': approved
        }
        if worker_id:
            message['worker_id'] = worker_id

        success = False
        def response_handler(response):
            nonlocal success
            success = response.get('status') == 'success'

        if self.send_message(message, response_handler):
            timeout = 5
            start_time = time.time()
            while not success and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            return success

        return False