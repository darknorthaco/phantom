"""
Hybrid Socket Server for Phantom Distributed System
Provides WebSocket communication layer for hybrid AI/programmatic routing
"""

import asyncio
import websockets
import json
import logging
from typing import Dict, Set, Any, Optional, List
from datetime import datetime
import uuid
import signal
import argparse

# Import the socket integration from phantom_core
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "phantom_core"))

try:
    from socket_integration import SocketManager
except ImportError:
    # Fallback implementation if socket_integration is not available
    from .fallback_socket_manager import SocketManager

logger = logging.getLogger(__name__)


class HybridSocketServer:
    """Standalone hybrid socket server for Phantom distributed system"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8081):
        self.host = host
        self.port = port
        self.socket_manager = SocketManager(port)
        self.running = False
        self.server = None

        # Enhanced client tracking
        self.client_registry = {}
        self.message_history = []
        self.max_history = 1000

        # Performance metrics
        self.metrics = {
            "messages_processed": 0,
            "clients_connected": 0,
            "clients_disconnected": 0,
            "errors": 0,
            "uptime_start": datetime.now(),
        }

    async def start(self):
        """Start the hybrid socket server"""
        try:
            logger.info(f"🔌 Starting Hybrid Socket Server on {self.host}:{self.port}")

            # Start the socket manager
            await self.socket_manager.start()

            # Set up signal handlers for graceful shutdown
            self.setup_signal_handlers()

            self.running = True
            logger.info(f"✅ Hybrid Socket Server started successfully")

            # Keep the server running
            await self.run_forever()

        except Exception as e:
            logger.error(f"Failed to start Hybrid Socket Server: {e}")
            raise

    async def stop(self):
        """Stop the hybrid socket server"""
        logger.info("🛑 Stopping Hybrid Socket Server...")

        self.running = False

        if self.socket_manager:
            await self.socket_manager.stop()

        logger.info("✅ Hybrid Socket Server stopped")

    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run_forever(self):
        """Keep the server running and handle periodic tasks"""
        try:
            while self.running:
                # Periodic maintenance tasks
                await self.periodic_maintenance()
                await asyncio.sleep(30)  # Run maintenance every 30 seconds

        except asyncio.CancelledError:
            logger.info("Server run loop cancelled")
        except Exception as e:
            logger.error(f"Error in server run loop: {e}")

    async def periodic_maintenance(self):
        """Perform periodic maintenance tasks"""
        try:
            # Clean up old message history
            if len(self.message_history) > self.max_history:
                self.message_history = self.message_history[-self.max_history // 2 :]

            # Update metrics
            current_time = datetime.now()
            uptime = current_time - self.metrics["uptime_start"]

            # Log status periodically
            if uptime.total_seconds() % 300 == 0:  # Every 5 minutes
                await self.log_status()

        except Exception as e:
            logger.warning(f"Error in periodic maintenance: {e}")

    async def log_status(self):
        """Log current server status"""
        status = await self.get_status()
        logger.info(
            f"📊 Server Status: {status['clients']['total']} clients, "
            f"{status['metrics']['messages_processed']} messages processed, "
            f"uptime: {status['uptime']}"
        )

    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive server status"""
        socket_status = await self.socket_manager.get_status()

        uptime = datetime.now() - self.metrics["uptime_start"]

        return {
            "server": {
                "host": self.host,
                "port": self.port,
                "running": self.running,
                "uptime": str(uptime),
            },
            "socket_manager": socket_status,
            "clients": socket_status.get("clients", {}),
            "metrics": self.metrics,
            "message_history_size": len(self.message_history),
        }

    async def broadcast_system_message(self, message: Dict[str, Any]):
        """Broadcast a system message to all clients"""
        system_message = {
            "type": "system_message",
            "timestamp": datetime.now().isoformat(),
            "message": message,
        }

        await self.socket_manager.broadcast(system_message)
        self.message_history.append(system_message)

    async def handle_admin_command(
        self, command: str, parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle administrative commands"""
        try:
            if command == "status":
                return await self.get_status()

            elif command == "broadcast":
                message = parameters.get("message", "Admin broadcast")
                await self.broadcast_system_message({"admin_message": message})
                return {"status": "broadcasted", "message": message}

            elif command == "metrics":
                return {"metrics": self.metrics}

            elif command == "clients":
                status = await self.socket_manager.get_status()
                return {"clients": status.get("clients", {})}

            elif command == "shutdown":
                asyncio.create_task(self.stop())
                return {"status": "shutdown_initiated"}

            else:
                return {"error": f"Unknown command: {command}"}

        except Exception as e:
            logger.error(f"Error handling admin command {command}: {e}")
            return {"error": str(e)}


class FallbackSocketManager:
    """Fallback socket manager implementation"""

    def __init__(self, port: int = 8081):
        self.port = port
        self.clients = set()
        self.running = False
        self.server = None

    async def start(self):
        """Start the fallback socket server"""
        self.server = await websockets.serve(self.handle_client, "127.0.0.1", self.port)
        self.running = True
        logger.info(f"🔌 Fallback socket server started on port {self.port}")

    async def stop(self):
        """Stop the fallback socket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.running = False
            logger.info("🔌 Fallback socket server stopped")

    async def handle_client(self, websocket, path):
        """Handle client connections"""
        client_id = str(uuid.uuid4())
        self.clients.add(websocket)

        try:
            logger.info(f"🔌 Client connected: {client_id}")

            # Send welcome message
            await websocket.send(
                json.dumps(
                    {
                        "type": "welcome",
                        "client_id": client_id,
                        "server": "fallback",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )

            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.debug(
                        f"Received message from {client_id}: {data.get('type', 'unknown')}"
                    )
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client {client_id}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            self.clients.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all clients"""
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

    async def get_status(self) -> Dict[str, Any]:
        """Get fallback server status"""
        return {
            "running": self.running,
            "port": self.port,
            "clients": {
                "total": len(self.clients),
                "ui": 0,
                "workers": 0,
                "llm_taskmaster": False,
            },
            "fallback_mode": True,
        }


# CLI interface for standalone operation
async def main():
    """Main entry point for standalone socket server"""
    parser = argparse.ArgumentParser(description="Phantom Hybrid Socket Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8081, help="Port to bind to")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and start server
    server = HybridSocketServer(args.host, args.port)

    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
