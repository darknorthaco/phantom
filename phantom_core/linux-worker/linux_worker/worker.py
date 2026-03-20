"""
Phantom Linux Worker - Enhanced GPU-aware worker implementation
"""

import asyncio
import logging
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Phase 4 — controller URL scheme + cert pin (engine root on path)
_phantom_core_root = Path(__file__).resolve().parent.parent.parent
if str(_phantom_core_root) not in sys.path:
    sys.path.insert(0, str(_phantom_core_root))
from worker_tls import controller_base_url, httpx_verify_for_worker
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import psutil
import threading
import time

# Import GPU detection and plugins
from .gpu.gpu_info_linux import GPUDetector

# plugins/ lives at the linux-worker/ root (one level above this package),
# so it is reachable as a top-level package via PYTHONPATH / sys.path.
from plugins.plugin_manager import PluginManager

from .discovery_listener import run_discovery_listener

# Import socket client if available
try:
    import sys
    import os

    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "phantom_core"))
    from socket_integration import WorkerSocketClient

    SOCKET_AVAILABLE = True
except ImportError:
    SOCKET_AVAILABLE = False
    WorkerSocketClient = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskRequest(BaseModel):
    task_id: str
    task_type: str
    parameters: Dict[str, Any]
    priority: int = 1


class TaskResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PhantomLinuxWorker:
    """Enhanced Linux worker with GPU optimization and plugin system"""

    def __init__(
        self,
        worker_id: str = None,
        controller_host: str = "localhost",
        controller_port: int = 8080,
        worker_port: int = 8090,
        tls_enabled: bool = False,
        tls_controller_cert_path: str = "",
    ):
        self.worker_id = worker_id or f"linux-worker-{uuid.uuid4().hex[:8]}"
        self.controller_host = controller_host
        self.controller_port = controller_port
        self.worker_port = worker_port
        self.tls_enabled = bool(tls_enabled)
        self.tls_controller_cert_path = str(tls_controller_cert_path or "")

        # Initialize components
        self.gpu_detector = GPUDetector()
        self.plugin_manager = PluginManager()
        self.socket_client = None

        # Worker state
        self.gpu_info = None
        self.current_tasks = {}
        self.max_concurrent_tasks = 1
        self.status = "initializing"
        self.performance_metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_processing_time": 0.0,
            "avg_processing_time": 0.0,
        }

        # FastAPI app
        self.app = FastAPI(title=f"Phantom Linux Worker - {self.worker_id}")
        self.setup_routes()

        # Background tasks
        self.heartbeat_task = None
        self.monitoring_task = None

    def _controller_api(self, path: str) -> str:
        """HTTPS or HTTP base + path — no scheme downgrade."""
        base = controller_base_url(
            self.controller_host, self.controller_port, self.tls_enabled
        )
        return f"{base}{path}" if path.startswith("/") else f"{base}/{path}"

    def _http_client(self, timeout: float = 30.0):
        verify = httpx_verify_for_worker(
            self.tls_enabled, self.tls_controller_cert_path
        )
        return httpx.AsyncClient(verify=verify, timeout=timeout)

    def setup_routes(self):
        """Setup FastAPI routes"""

        @self.app.get("/")
        async def root():
            return {
                "worker_id": self.worker_id,
                "status": self.status,
                "gpu_info": self.gpu_info,
                "current_tasks": len(self.current_tasks),
                "max_concurrent_tasks": self.max_concurrent_tasks,
            }

        @self.app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "worker_id": self.worker_id,
                "timestamp": datetime.now().isoformat(),
                "gpu_utilization": self.get_gpu_utilization(),
                "system_metrics": self.get_system_metrics(),
            }

        @self.app.post("/tasks/execute")
        async def execute_task(task: TaskRequest):
            return await self.handle_task_execution(task)

        @self.app.get("/tasks/{task_id}")
        async def get_task_status(task_id: str):
            if task_id not in self.current_tasks:
                raise HTTPException(status_code=404, detail="Task not found")
            return self.current_tasks[task_id]

        @self.app.delete("/tasks/{task_id}")
        async def cancel_task(task_id: str):
            return await self.handle_task_cancellation(task_id)

        @self.app.get("/metrics")
        async def get_metrics():
            return {
                "performance": self.performance_metrics,
                "gpu_info": self.gpu_info,
                "system_metrics": self.get_system_metrics(),
                "plugin_status": self.plugin_manager.get_status(),
            }

    async def initialize(self):
        """Initialize the worker"""
        try:
            logger.info(f"🚀 Initializing worker {self.worker_id}")

            # Detect GPU; fall back to CPU if none found
            self.gpu_info = await self.gpu_detector.detect_gpu()
            if not self.gpu_info:
                self.gpu_info = {
                    "name": "CPU",
                    "memory_total": 0,
                    "memory_free": 0,
                    "memory_used": 0,
                    "utilization": 0.0,
                    "driver_version": "",
                    "compute_capability": "",
                }
                logger.info("📋 No GPU detected — running in CPU mode")
            else:
                logger.info(
                    f"🎮 Detected GPU: {self.gpu_info['name']} ({self.gpu_info['memory_total']}MB)"
                )

            # Initialize plugins
            await self.plugin_manager.initialize(self.gpu_info)

            # Set max concurrent tasks based on GPU memory
            self.max_concurrent_tasks = self.calculate_max_concurrent_tasks()

            # Initialize socket client if available
            if SOCKET_AVAILABLE:
                self.socket_client = WorkerSocketClient(
                    self.worker_id, self.controller_host, 8081  # Socket port
                )

                try:
                    connected = await self.socket_client.connect_as_worker()
                    if connected:
                        logger.info("🔌 Connected to socket infrastructure")
                    else:
                        logger.warning("🔌 Failed to connect to socket infrastructure")
                        self.socket_client = None
                except Exception as e:
                    logger.warning(f"🔌 Socket connection failed: {e}")
                    self.socket_client = None

            self.status = "active"
            logger.info(f"✅ Worker {self.worker_id} initialized successfully")

        except Exception as e:
            self.status = "error"
            logger.error(f"❌ Worker initialization failed: {e}")
            raise

    def calculate_max_concurrent_tasks(self) -> int:
        """Calculate maximum concurrent tasks based on GPU memory"""
        if not self.gpu_info:
            return 1

        memory_gb = self.gpu_info.get("memory_total", 4000) / 1024

        # Conservative estimation: 1 task per 4GB of VRAM
        max_tasks = max(1, int(memory_gb / 4))

        # Cap based on GPU type
        gpu_name = self.gpu_info.get("name", "")
        if "RTX 5080" in gpu_name:
            max_tasks = min(max_tasks, 4)  # High-end can handle more
        elif "RTX 5060" in gpu_name:
            max_tasks = min(max_tasks, 3)
        elif "GTX 1080" in gpu_name:
            max_tasks = min(max_tasks, 2)
        elif "FirePro" in gpu_name:
            max_tasks = min(max_tasks, 2)  # Conservative for professional card

        logger.info(f"🎯 Max concurrent tasks set to {max_tasks}")
        return max_tasks

    async def register_with_controller(self):
        """Register this worker with the controller"""
        try:
            registration_data = {
                "worker_id": self.worker_id,
                "host": "0.0.0.0",  # Will be replaced by controller with actual IP
                "port": self.worker_port,
                "gpu_info": self.gpu_info,
                "status": self.status,
                "max_concurrent_tasks": self.max_concurrent_tasks,
            }

            async with self._http_client(30.0) as client:
                response = await client.post(
                    self._controller_api("/workers/register"),
                    json=registration_data,
                )

                if response.status_code == 200:
                    logger.info(f"✅ Successfully registered with controller")
                    return True
                else:
                    logger.error(
                        f"❌ Registration failed: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"❌ Failed to register with controller: {e}")
            return False

    async def start_background_tasks(self):
        """Start background monitoring and heartbeat tasks"""
        run_discovery_listener(
            self.worker_id,
            "0.0.0.0",
            self.worker_port,
            self.gpu_info or {},
        )
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        self.monitoring_task = asyncio.create_task(self.monitoring_loop())
        logger.info("🔄 Background tasks started")

    async def stop_background_tasks(self):
        """Stop background tasks"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.monitoring_task:
            self.monitoring_task.cancel()

        if self.socket_client:
            await self.socket_client.disconnect()

        logger.info("🛑 Background tasks stopped")

    async def heartbeat_loop(self):
        """Send periodic heartbeats to controller"""
        """Send periodic heartbeats to controller with gpu_status and metrics

        Sends every 5 seconds (synchronized with orchestrator's heartbeat collection loop).
        Includes canonical gpu_status format (internal, not broadcast).
        """
        while True:
            try:
                # Prepare heartbeat payload with canonical gpu_status
                heartbeat_data = {
                    "gpu_status": self._format_gpu_status(),
                    "current_tasks": len(self.current_tasks),
                    "memory_available": self._get_available_memory(),
                }

                async with self._http_client(5.0) as client:
                    await client.post(
                        self._controller_api(f"/workers/{self.worker_id}/heartbeat"),
                        json=heartbeat_data,
                    )

                # Send socket status update if available
                if self.socket_client:
                    await self.socket_client.send_status_update(
                        self.status,
                        {
                            "current_tasks": len(self.current_tasks),
                            "gpu_utilization": self.get_gpu_utilization(),
                        },
                    )

                await asyncio.sleep(5)  # Heartbeat every 5 seconds

            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
                await asyncio.sleep(5)  # Retry after 5 seconds on failure

    async def monitoring_loop(self):
        """Monitor system resources and update status"""
        while True:
            try:
                # Update GPU utilization
                if self.gpu_detector:
                    updated_gpu_info = await self.gpu_detector.get_current_utilization()
                    if updated_gpu_info:
                        self.gpu_info.update(updated_gpu_info)

                # Update worker status based on load
                if len(self.current_tasks) >= self.max_concurrent_tasks:
                    self.status = "busy"
                elif len(self.current_tasks) == 0:
                    self.status = "active"
                else:
                    self.status = "active"

                await asyncio.sleep(10)  # Monitor every 10 seconds

            except Exception as e:
                logger.warning(f"Monitoring loop error: {e}")
                await asyncio.sleep(30)

    async def handle_task_execution(self, task: TaskRequest) -> TaskResponse:
        """Handle task execution request"""
        try:
            # Check if we can accept more tasks
            if len(self.current_tasks) >= self.max_concurrent_tasks:
                raise HTTPException(
                    status_code=503, detail="Worker at maximum capacity"
                )

            # Create task record
            task_record = {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "parameters": task.parameters,
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "worker_id": self.worker_id,
            }

            self.current_tasks[task.task_id] = task_record

            logger.info(f"📋 Starting task {task.task_id} ({task.task_type})")

            # Execute task asynchronously
            asyncio.create_task(self.execute_task_async(task))

            return TaskResponse(task_id=task.task_id, status="running")

        except Exception as e:
            logger.error(f"❌ Failed to start task {task.task_id}: {e}")
            return TaskResponse(task_id=task.task_id, status="failed", error=str(e))

    async def execute_task_async(self, task: TaskRequest):
        """Execute task asynchronously"""
        start_time = time.time()

        try:
            # Get appropriate plugin for task
            plugin = self.plugin_manager.get_plugin_for_task(task.task_type)
            if not plugin:
                raise Exception(f"No plugin available for task type: {task.task_type}")

            # Execute task using plugin
            result = await plugin.execute_task(task.parameters)

            # Update task record
            task_record = self.current_tasks[task.task_id]
            task_record["status"] = "completed"
            task_record["completed_at"] = datetime.now().isoformat()
            task_record["result"] = result

            # Update performance metrics
            processing_time = time.time() - start_time
            self.performance_metrics["tasks_completed"] += 1
            self.performance_metrics["total_processing_time"] += processing_time
            self.performance_metrics["avg_processing_time"] = (
                self.performance_metrics["total_processing_time"]
                / self.performance_metrics["tasks_completed"]
            )

            logger.info(f"✅ Task {task.task_id} completed in {processing_time:.2f}s")

            # Notify controller of completion
            await self.notify_controller_completion(task.task_id, result)

        except Exception as e:
            # Update task record
            task_record = self.current_tasks[task.task_id]
            task_record["status"] = "failed"
            task_record["completed_at"] = datetime.now().isoformat()
            task_record["error"] = str(e)

            # Update performance metrics
            self.performance_metrics["tasks_failed"] += 1

            logger.error(f"❌ Task {task.task_id} failed: {e}")

            # Notify controller of failure
            await self.notify_controller_failure(task.task_id, str(e))

        finally:
            # Clean up completed task after a delay
            await asyncio.sleep(60)  # Keep record for 1 minute
            if task.task_id in self.current_tasks:
                del self.current_tasks[task.task_id]

    async def handle_task_cancellation(self, task_id: str) -> Dict[str, Any]:
        """Handle task cancellation request"""
        if task_id not in self.current_tasks:
            raise HTTPException(status_code=404, detail="Task not found")

        task_record = self.current_tasks[task_id]

        if task_record["status"] in ["completed", "failed", "cancelled"]:
            raise HTTPException(status_code=400, detail="Task cannot be cancelled")

        # Mark as cancelled
        task_record["status"] = "cancelled"
        task_record["completed_at"] = datetime.now().isoformat()

        logger.info(f"🚫 Task {task_id} cancelled")

        return {"status": "cancelled", "task_id": task_id}

    async def notify_controller_completion(self, task_id: str, result: Dict[str, Any]):
        """POST authoritative completion to controller (/api/worker/completion)."""
        url = self._controller_api("/api/worker/completion")
        payload = {
            "task_id": task_id,
            "worker_id": self.worker_id,
            "timestamp": datetime.now().isoformat(),
            "result": result if result is not None else {},
        }
        headers = {}
        secret = os.environ.get("PHANTOM_WORKER_CALLBACK_SECRET")
        if secret:
            headers["X-Phantom-Callback-Key"] = secret
        try:
            async with self._http_client(30.0) as client:
                r = await client.post(url, json=payload, headers=headers)
                if r.status_code not in (200, 201, 204):
                    logger.warning(
                        "Controller completion callback HTTP %s: %s",
                        r.status_code,
                        r.text[:500],
                    )
        except Exception as e:
            logger.warning("Failed to notify controller of completion: %s", e)

    async def notify_controller_failure(self, task_id: str, error: str):
        """POST authoritative failure to controller (/api/worker/failure)."""
        url = self._controller_api("/api/worker/failure")
        payload = {
            "task_id": task_id,
            "worker_id": self.worker_id,
            "timestamp": datetime.now().isoformat(),
            "error": error[:16384],
        }
        headers = {}
        secret = os.environ.get("PHANTOM_WORKER_CALLBACK_SECRET")
        if secret:
            headers["X-Phantom-Callback-Key"] = secret
        try:
            async with self._http_client(30.0) as client:
                r = await client.post(url, json=payload, headers=headers)
                if r.status_code not in (200, 201, 204):
                    logger.warning(
                        "Controller failure callback HTTP %s: %s",
                        r.status_code,
                        r.text[:500],
                    )
        except Exception as e:
            logger.warning("Failed to notify controller of failure: %s", e)

    def get_gpu_utilization(self) -> float:
        """Get current GPU utilization"""
        if self.gpu_info:
            return self.gpu_info.get("utilization", 0.0)
        return 0.0

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage("/").percent,
            "load_average": (
                psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else 0.0
            ),
        }

    def _format_gpu_status(self) -> Dict[str, Any]:
        """Format gpu_info in canonical gpu_status format for heartbeat

        Returns dict with gpu_id → {utilization, temperature, memory_used, memory_total}
        This is the canonical format used internally (NOT broadcast as gpu_metrics).
        """
        if not self.gpu_info:
            return {}

        return {
            "type": "gpu_status",
            "gpus": {
                "gpu-0": {
                    "utilization": self.gpu_info.get("utilization", 0.0),
                    "temperature": self.gpu_info.get("temperature", 0.0),
                    "memory_used": self.gpu_info.get("memory_used", 0),
                    "memory_total": self.gpu_info.get("memory_total", 0),
                }
            },
            "timestamp": datetime.now().isoformat(),
        }

    def _get_available_memory(self) -> int:
        """Get available GPU memory in MB for task assignment decisions"""
        if not self.gpu_info:
            return 0

        memory_total = self.gpu_info.get("memory_total", 0)
        memory_used = self.gpu_info.get("memory_used", 0)

        return max(0, memory_total - memory_used)

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info(f"🛑 Shutting down worker {self.worker_id}")

        # Stop background tasks
        await self.stop_background_tasks()

        # Cancel running tasks
        for task_id, task_record in self.current_tasks.items():
            if task_record["status"] == "running":
                task_record["status"] = "cancelled"
                task_record["completed_at"] = datetime.now().isoformat()

        # Unregister from controller
        try:
            async with self._http_client(10.0) as client:
                await client.delete(
                    self._controller_api(f"/workers/{self.worker_id}")
                )
        except Exception as e:
            logger.warning(f"Failed to unregister from controller: {e}")

        logger.info(f"✅ Worker {self.worker_id} shutdown complete")


# Worker factory function
def create_worker(config: Dict[str, Any]) -> PhantomLinuxWorker:
    """Create a worker instance from configuration"""
    return PhantomLinuxWorker(
        worker_id=config.get("worker_id"),
        controller_host=config.get("controller_host", "localhost"),
        controller_port=config.get("controller_port", 8080),
        worker_port=config.get("worker_port", 8090),
        tls_enabled=bool(config.get("tls_enabled", False)),
        tls_controller_cert_path=str(config.get("tls_controller_cert_path", "") or ""),
    )
