"""
Socket Infrastructure Integration for Phantom Controller
Provides WebSocket communication layer for hybrid AI/programmatic routing
"""

import asyncio
import websockets
import json
import logging
from typing import Dict, Set, Any, Optional
from datetime import datetime
import uuid
import inspect

logger = logging.getLogger(__name__)

# Import orchestrator for worker table integration
try:
    from orchestrator import PhantomOrchestrator

    ORCHESTRATOR_AVAILABLE = True
except Exception:
    ORCHESTRATOR_AVAILABLE = False
    PhantomOrchestrator = None

# Global reference to orchestrator (set by controller_api)
orchestrator_ref = None


class SocketManager:
    """Manages WebSocket connections and message routing"""

    def __init__(self, port: int = 8081):
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.llm_taskmaster_client: Optional[websockets.WebSocketServerProtocol] = None
        self.ui_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.worker_clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        # Optional callback injected by controller; supports sync or async handlers.
        self.set_mode_handler = None
        self.server = None
        self.running = False
        # Pending LLM routing requests: request_id → asyncio.Future
        self._pending_routing: Dict[str, asyncio.Future] = {}

    async def start(self):
        """Start the WebSocket server"""
        try:
            self.server = await websockets.serve(
                self.handle_client, "127.0.0.1", self.port
            )
            self.running = True
            logger.info(f"🔌 Socket server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start socket server: {e}")
            raise

    async def stop(self):
        """Stop the WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.running = False
            logger.info("🔌 Socket server stopped")

    async def handle_client(self, websocket, path):
        """Handle new WebSocket client connections"""
        client_id = str(uuid.uuid4())
        self.clients.add(websocket)

        try:
            logger.info(f"🔌 New client connected: {client_id}")

            # Send welcome message
            await websocket.send(
                json.dumps(
                    {
                        "type": "welcome",
                        "client_id": client_id,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )

            async for message in websocket:
                await self.handle_message(websocket, message, client_id)

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            self.clients.discard(websocket)

            # Remove from specific client lists
            if websocket == self.llm_taskmaster_client:
                self.llm_taskmaster_client = None
                logger.info("🤖 LLM Task Master disconnected")

            self.ui_clients.discard(websocket)

            # Remove from worker clients
            worker_to_remove = None
            for worker_id, client in self.worker_clients.items():
                if client == websocket:
                    worker_to_remove = worker_id
                    break
            if worker_to_remove:
                del self.worker_clients[worker_to_remove]
                logger.info(f"👷 Worker client disconnected: {worker_to_remove}")

    async def handle_message(self, websocket, message: str, client_id: str):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "register":
                await self.handle_registration(websocket, data, client_id)
            elif message_type == "llm_routing_response":
                await self.handle_llm_routing_response(data)
            elif message_type == "worker_status_update":
                await self.handle_worker_status_update(data)
            elif message_type == "ui_command":
                await self.handle_ui_command(data)
            elif message_type == "SET_MODE":
                await self.handle_set_mode(websocket, data, client_id)
            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from client {client_id}: {message}")
        except Exception as e:
            logger.error(f"Error processing message from {client_id}: {e}")

    async def handle_registration(self, websocket, data: Dict, client_id: str):
        """Handle client registration"""
        client_type = data.get("client_type")

        if client_type == "llm_taskmaster":
            self.llm_taskmaster_client = websocket
            logger.info("🤖 LLM Task Master registered")

            # Send current system state
            await websocket.send(
                json.dumps(
                    {
                        "type": "system_state",
                        "workers": len(self.worker_clients),
                        "ui_clients": len(self.ui_clients),
                    }
                )
            )

        elif client_type == "ui":
            self.ui_clients.add(websocket)
            logger.info(f"🖥️ UI client registered: {client_id}")

        elif client_type == "worker":
            worker_id = data.get("worker_id")
            if worker_id:
                self.worker_clients[worker_id] = websocket
                # NEW: Also register with orchestrator if available
                if ORCHESTRATOR_AVAILABLE and orchestrator_ref:
                    try:
                        worker = orchestrator_ref.workers.get(worker_id)
                        if worker:
                            worker.websocket_id = client_id
                            logger.info(
                                f"👷 Worker {worker_id} WebSocket integrated with orchestrator"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Failed to integrate worker {worker_id} with orchestrator: {e}"
                        )
                logger.info(f"👷 Worker registered: {worker_id}")

        # Confirm registration
        await websocket.send(
            json.dumps(
                {
                    "type": "registration_confirmed",
                    "client_type": client_type,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

    async def handle_llm_routing_response(self, data: Dict):
        """Resolve the pending Future for the matching request_id."""
        request_id = data.get("request_id")
        if not request_id:
            logger.warning("🤖 LLM routing response missing request_id — discarding")
            return

        future = self._pending_routing.get(request_id)
        if future is None:
            logger.warning(f"🤖 No pending request for id {request_id} — discarding")
            return

        if not future.done():
            future.set_result(data)
            logger.info(f"🤖 LLM routing response resolved for request {request_id}")

    async def handle_worker_status_update(self, data: Dict):
        """Handle status updates from workers"""
        worker_id = data.get("worker_id")
        status = data.get("status")

        # Broadcast to UI clients
        await self.broadcast_to_ui(
            {
                "type": "worker_status_update",
                "worker_id": worker_id,
                "status": status,
                "timestamp": datetime.now().isoformat(),
            }
        )

    async def handle_ui_command(self, data: Dict):
        """Handle commands from UI clients"""
        command = data.get("command")

        if command == "get_system_status":
            # Send system status to requesting UI
            # This would be handled by the main controller
            pass
        elif command == "set_mode":
            await self.handle_set_mode(
                None,
                {
                    "mode": data.get("mode"),
                    "session_id": data.get("session_id"),
                },
                "ui_command",
            )

    async def handle_set_mode(self, websocket, data: Dict, client_id: str):
        """Handle mode set requests from UI clients"""
        mode = data.get("mode")
        session_id = data.get("session_id")
        if not mode:
            if websocket:
                await websocket.send(
                    json.dumps({"type": "MODE_SET_ERROR", "error": "mode is required"})
                )
            return

        if not self.set_mode_handler:
            if websocket:
                await websocket.send(
                    json.dumps(
                        {
                            "type": "MODE_SET_ERROR",
                            "error": "mode handler is not configured",
                        }
                    )
                )
            return

        result = self.set_mode_handler(mode, session_id, "websocket")
        if inspect.isawaitable(result):
            result = await result

        response = {
            "type": "MODE_SET",
            "mode": result.get("mode", mode),
            "previous_mode": result.get("previous_mode"),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "client_id": client_id,
        }
        if websocket:
            await websocket.send(json.dumps(response))
        await self.broadcast_to_ui(response)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.clients:
            return

        message_json = json.dumps(message)
        disconnected_clients = set()

        for client in self.clients:
            try:
                await client.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected_clients.add(client)

        # Clean up disconnected clients
        for client in disconnected_clients:
            self.clients.discard(client)

    async def broadcast_to_ui(self, message: Dict[str, Any]):
        """Broadcast message specifically to UI clients"""
        if not self.ui_clients:
            return

        message_json = json.dumps(message)
        disconnected_clients = set()

        for client in self.ui_clients:
            try:
                await client.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error broadcasting to UI client: {e}")
                disconnected_clients.add(client)

        # Clean up disconnected clients
        for client in disconnected_clients:
            self.ui_clients.discard(client)

    async def send_to_llm_taskmaster(self, message: Dict[str, Any]):
        """Send message specifically to LLM Task Master"""
        if not self.llm_taskmaster_client:
            return False

        try:
            await self.llm_taskmaster_client.send(json.dumps(message))
            return True
        except websockets.exceptions.ConnectionClosed:
            self.llm_taskmaster_client = None
            logger.warning("🤖 LLM Task Master connection lost")
            return False
        except Exception as e:
            logger.error(f"Error sending to LLM Task Master: {e}")
            return False

    async def send_to_worker(self, worker_id: str, message: Dict[str, Any]):
        """Send message to specific worker"""
        if worker_id not in self.worker_clients:
            return False

        try:
            await self.worker_clients[worker_id].send(json.dumps(message))
            return True
        except websockets.exceptions.ConnectionClosed:
            del self.worker_clients[worker_id]
            logger.warning(f"👷 Worker {worker_id} connection lost")
            return False
        except Exception as e:
            logger.error(f"Error sending to worker {worker_id}: {e}")
            return False

    async def request_llm_routing(
        self, routing_request: Dict[str, Any], timeout_seconds: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """Request worker selection from LLM Task Master.

        Sends a routing_request message, registers a Future keyed by the
        request_id, and awaits the Future.  handle_llm_routing_response()
        resolves the Future when the LLM Task Master replies with a matching
        request_id.  Returns the response dict, or None on timeout/error.
        """
        if not self.llm_taskmaster_client:
            return None

        request_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_routing[request_id] = future

        message = {
            "type": "routing_request",
            "request_id": request_id,
            "data": routing_request,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            success = await self.send_to_llm_taskmaster(message)
            if not success:
                return None

            response = await asyncio.wait_for(future, timeout=timeout_seconds)
            logger.info(
                f"🤖 LLM routing completed for request {request_id}: "
                f"worker={response.get('selected_worker')}"
            )
            return response

        except asyncio.TimeoutError:
            logger.warning(
                f"🤖 LLM routing request {request_id} timed out after "
                f"{timeout_seconds}s — falling back to programmatic routing"
            )
            return None
        except Exception as e:
            logger.error(f"🤖 LLM routing request {request_id} failed: {e}")
            return None
        finally:
            self._pending_routing.pop(request_id, None)

    async def get_status(self) -> Dict[str, Any]:
        """Get current socket infrastructure status"""
        return {
            "running": self.running,
            "port": self.port,
            "clients": {
                "total": len(self.clients),
                "ui": len(self.ui_clients),
                "workers": len(self.worker_clients),
                "llm_taskmaster": self.llm_taskmaster_client is not None,
            },
            "worker_ids": list(self.worker_clients.keys()),
        }


# WebSocket client utilities for workers and UI
class SocketClient:
    """Base WebSocket client for connecting to Phantom socket infrastructure"""

    def __init__(self, server_host: str = "localhost", server_port: int = 8081):
        self.server_host = server_host
        self.server_port = server_port
        self.websocket = None
        self.client_type = None
        self.running = False

    async def connect(self, client_type: str, **kwargs):
        """Connect to the socket server"""
        self.client_type = client_type

        try:
            uri = f"ws://{self.server_host}:{self.server_port}"
            self.websocket = await websockets.connect(uri)
            self.running = True

            # Register with server
            await self.send({"type": "register", "client_type": client_type, **kwargs})

            logger.info(f"🔌 Connected to socket server as {client_type}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to socket server: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the socket server"""
        if self.websocket:
            await self.websocket.close()
            self.running = False
            logger.info("🔌 Disconnected from socket server")

    async def send(self, message: Dict[str, Any]):
        """Send message to server"""
        if not self.websocket:
            return False

        try:
            await self.websocket.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def listen(self, message_handler):
        """Listen for messages from server"""
        if not self.websocket:
            return

        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await message_handler(data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {message}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 Connection to server closed")
            self.running = False
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
            self.running = False


# Example usage for workers
class WorkerSocketClient(SocketClient):
    """Socket client specifically for workers"""

    def __init__(
        self, worker_id: str, server_host: str = "localhost", server_port: int = 8081
    ):
        super().__init__(server_host, server_port)
        self.worker_id = worker_id

    async def connect_as_worker(self):
        """Connect as a worker client"""
        return await self.connect("worker", worker_id=self.worker_id)

    async def send_status_update(self, status: str, additional_info: Dict = None):
        """Send status update to controller"""
        message = {
            "type": "worker_status_update",
            "worker_id": self.worker_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }

        if additional_info:
            message.update(additional_info)

        await self.send(message)


# Example usage for LLM Task Master
class LLMTaskMasterClient(SocketClient):
    """Socket client for LLM Task Master"""

    async def connect_as_llm_taskmaster(self):
        """Connect as LLM Task Master"""
        return await self.connect("llm_taskmaster")

    async def handle_routing_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle routing request from controller"""
        # This would contain the actual LLM logic
        # For now, return a simple response
        task = data.get("task", {})  # noqa: F841
        available_workers = data.get("available_workers", {})

        # Simple selection logic (would be replaced with LLM inference)
        if available_workers:
            selected_worker = list(available_workers.keys())[0]
            return {
                "type": "llm_routing_response",
                "request_id": data.get("request_id"),
                "selected_worker": selected_worker,
                "confidence": 0.8,
                "reasoning": "Selected based on availability",
            }

        return {
            "type": "llm_routing_response",
            "request_id": data.get("request_id"),
            "selected_worker": None,
            "error": "No workers available",
        }
