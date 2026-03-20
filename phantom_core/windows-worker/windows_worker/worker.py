"""
Phantom Windows Worker - GPU-aware worker implementation.
Mirrors linux_worker.worker; OS field in manifest = "windows".
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import psutil
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .gpu.gpu_info_windows import GPUDetector
from .discovery_listener import run_discovery_listener

# Add engine root and linux-worker for phantom_core and plugins
_engine_root = Path(__file__).resolve().parent.parent.parent
if str(_engine_root) not in sys.path:
    sys.path.insert(0, str(_engine_root))
if str(_engine_root / "linux-worker") not in sys.path:
    sys.path.insert(0, str(_engine_root / "linux-worker"))

from worker_tls import controller_base_url, httpx_verify_for_worker

try:
    from plugins.plugin_manager import PluginManager
except ImportError:
    PluginManager = None  # type: ignore

try:
    sys.path.insert(0, str(_engine_root))
    from socket_integration import WorkerSocketClient
    SOCKET_AVAILABLE = True
except ImportError:
    SOCKET_AVAILABLE = False
    WorkerSocketClient = None

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


class PhantomWindowsWorker:
    """Windows worker with GPU optimization and plugin system."""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        controller_host: str = "localhost",
        controller_port: int = 8080,
        worker_port: int = 8090,
        tls_enabled: bool = False,
        tls_controller_cert_path: str = "",
    ):
        self.worker_id = worker_id or f"windows-worker-{uuid.uuid4().hex[:8]}"
        self.controller_host = controller_host
        self.controller_port = controller_port
        self.worker_port = worker_port
        self.tls_enabled = bool(tls_enabled)
        self.tls_controller_cert_path = str(tls_controller_cert_path or "")

        self.gpu_detector = GPUDetector()
        self.plugin_manager = PluginManager() if PluginManager else None
        self.socket_client = None

        self.gpu_info: Optional[Dict[str, Any]] = None
        self.current_tasks: Dict[str, Dict[str, Any]] = {}
        self.max_concurrent_tasks = 1
        self.status = "initializing"
        self.performance_metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_processing_time": 0.0,
            "avg_processing_time": 0.0,
        }

        self.app = FastAPI(title=f"Phantom Windows Worker - {self.worker_id}")
        self.setup_routes()

        self.heartbeat_task = None
        self.monitoring_task = None

    def _controller_api(self, path: str) -> str:
        base = controller_base_url(
            self.controller_host, self.controller_port, self.tls_enabled
        )
        return f"{base}{path}" if path.startswith("/") else f"{base}/{path}"

    def _http_client(self, timeout: float = 30.0):
        verify = httpx_verify_for_worker(
            self.tls_enabled, self.tls_controller_cert_path
        )
        return httpx.AsyncClient(verify=verify, timeout=timeout)

    def setup_routes(self) -> None:
        """Setup FastAPI routes — same API as Linux worker."""

        @self.app.get("/")
        async def root():
            return {
                "worker_id": self.worker_id,
                "status": self.status,
                "os": "windows",
                "gpu_info": self.gpu_info,
                "current_tasks": len(self.current_tasks),
                "max_concurrent_tasks": self.max_concurrent_tasks,
            }

        @self.app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "worker_id": self.worker_id,
                "os": "windows",
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
            plugin_status = self.plugin_manager.get_status() if self.plugin_manager else {}
            return {
                "performance": self.performance_metrics,
                "gpu_info": self.gpu_info,
                "system_metrics": self.get_system_metrics(),
                "plugin_status": plugin_status,
            }

        @self.app.get("/manifest")
        async def manifest():
            return self._build_manifest()

    def _build_manifest(self) -> Dict[str, Any]:
        """Build worker manifest with os=windows."""
        return {
            "worker_id": self.worker_id,
            "host": "0.0.0.0",
            "port": self.worker_port,
            "os": "windows",
            "gpu_info": self.gpu_info or {},
            "status": self.status,
            "max_concurrent_tasks": self.max_concurrent_tasks,
        }

    async def initialize(self) -> None:
        """Initialize the worker."""
        try:
            logger.info("Initializing worker %s (Windows)", self.worker_id)
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
                logger.info("No GPU detected — running in CPU mode")
            else:
                logger.info("Detected GPU: %s (%s MB)", self.gpu_info.get("name"), self.gpu_info.get("memory_total"))

            if self.plugin_manager:
                await self.plugin_manager.initialize(self.gpu_info)

            self.max_concurrent_tasks = self.calculate_max_concurrent_tasks()

            if SOCKET_AVAILABLE and WorkerSocketClient:
                self.socket_client = WorkerSocketClient(self.worker_id, self.controller_host, 8081)
                try:
                    connected = await self.socket_client.connect_as_worker()
                    if connected:
                        logger.info("Connected to socket infrastructure")
                    else:
                        self.socket_client = None
                except Exception as e:
                    logger.warning("Socket connection failed: %s", e)
                    self.socket_client = None

            self.status = "active"
            logger.info("Worker %s initialized successfully", self.worker_id)
        except Exception as e:
            self.status = "error"
            logger.error("Worker initialization failed: %s", e)
            raise

    def calculate_max_concurrent_tasks(self) -> int:
        """Calculate max concurrent tasks based on GPU memory."""
        if not self.gpu_info:
            return 1
        memory_gb = self.gpu_info.get("memory_total", 4000) / 1024
        max_tasks = max(1, int(memory_gb / 4))
        gpu_name = self.gpu_info.get("name", "")
        if "RTX 5080" in gpu_name:
            max_tasks = min(max_tasks, 4)
        elif "RTX 5060" in gpu_name:
            max_tasks = min(max_tasks, 3)
        elif "GTX 1080" in gpu_name:
            max_tasks = min(max_tasks, 2)
        return max_tasks

    async def register_with_controller(self) -> bool:
        """Register with controller; include os=windows."""
        try:
            registration_data = {
                "worker_id": self.worker_id,
                "host": "0.0.0.0",
                "port": self.worker_port,
                "os": "windows",
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
                    logger.info("Successfully registered with controller")
                    return True
                logger.error("Registration failed: %s - %s", response.status_code, response.text)
                return False
        except Exception as e:
            logger.error("Failed to register with controller: %s", e)
            return False

    async def start_background_tasks(self) -> None:
        """Start discovery listener and heartbeat/monitoring loops."""
        run_discovery_listener(self.worker_id, "0.0.0.0", self.worker_port, self.gpu_info or {})
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        self.monitoring_task = asyncio.create_task(self.monitoring_loop())
        logger.info("Background tasks started")

    async def stop_background_tasks(self) -> None:
        """Stop background tasks."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.monitoring_task:
            self.monitoring_task.cancel()
        if self.socket_client:
            await self.socket_client.disconnect()
        logger.info("Background tasks stopped")

    async def heartbeat_loop(self) -> None:
        """Send periodic heartbeats to controller."""
        while True:
            try:
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
                if self.socket_client:
                    await self.socket_client.send_status_update(
                        self.status,
                        {"current_tasks": len(self.current_tasks), "gpu_utilization": self.get_gpu_utilization()},
                    )
                await asyncio.sleep(5)
            except Exception as e:
                logger.warning("Heartbeat failed: %s", e)
                await asyncio.sleep(5)

    async def monitoring_loop(self) -> None:
        """Monitor system resources."""
        while True:
            try:
                if self.gpu_detector:
                    updated = await self.gpu_detector.get_current_utilization()
                    if updated and self.gpu_info:
                        self.gpu_info.update(updated)
                if len(self.current_tasks) >= self.max_concurrent_tasks:
                    self.status = "busy"
                else:
                    self.status = "active"
                await asyncio.sleep(10)
            except Exception as e:
                logger.warning("Monitoring loop error: %s", e)
                await asyncio.sleep(30)

    async def handle_task_execution(self, task: TaskRequest) -> TaskResponse:
        """Handle task execution request."""
        try:
            if len(self.current_tasks) >= self.max_concurrent_tasks:
                raise HTTPException(status_code=503, detail="Worker at maximum capacity")
            task_record = {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "parameters": task.parameters,
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "worker_id": self.worker_id,
            }
            self.current_tasks[task.task_id] = task_record
            logger.info("Starting task %s (%s)", task.task_id, task.task_type)
            asyncio.create_task(self.execute_task_async(task))
            return TaskResponse(task_id=task.task_id, status="running")
        except Exception as e:
            logger.error("Failed to start task %s: %s", task.task_id, e)
            return TaskResponse(task_id=task.task_id, status="failed", error=str(e))

    async def execute_task_async(self, task: TaskRequest) -> None:
        """Execute task asynchronously."""
        start_time = time.time()
        try:
            plugin = self.plugin_manager.get_plugin_for_task(task.task_type) if self.plugin_manager else None
            if not plugin:
                raise Exception(f"No plugin available for task type: {task.task_type}")
            result = await plugin.execute_task(task.parameters)
            task_record = self.current_tasks[task.task_id]
            task_record["status"] = "completed"
            task_record["completed_at"] = datetime.now().isoformat()
            task_record["result"] = result
            processing_time = time.time() - start_time
            self.performance_metrics["tasks_completed"] += 1
            self.performance_metrics["total_processing_time"] += processing_time
            self.performance_metrics["avg_processing_time"] = (
                self.performance_metrics["total_processing_time"] / self.performance_metrics["tasks_completed"]
            )
            logger.info("Task %s completed in %.2fs", task.task_id, processing_time)
            await self.notify_controller_completion(task.task_id, result)
        except Exception as e:
            task_record = self.current_tasks.get(task.task_id)
            if task_record:
                task_record["status"] = "failed"
                task_record["completed_at"] = datetime.now().isoformat()
                task_record["error"] = str(e)
            self.performance_metrics["tasks_failed"] += 1
            logger.error("Task %s failed: %s", task.task_id, e)
            await self.notify_controller_failure(task.task_id, str(e))
        finally:
            await asyncio.sleep(60)
            if task.task_id in self.current_tasks:
                del self.current_tasks[task.task_id]

    async def handle_task_cancellation(self, task_id: str) -> Dict[str, Any]:
        """Handle task cancellation."""
        if task_id not in self.current_tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        task_record = self.current_tasks[task_id]
        if task_record["status"] in ("completed", "failed", "cancelled"):
            raise HTTPException(status_code=400, detail="Task cannot be cancelled")
        task_record["status"] = "cancelled"
        task_record["completed_at"] = datetime.now().isoformat()
        logger.info("Task %s cancelled", task_id)
        return {"status": "cancelled", "task_id": task_id}

    async def notify_controller_completion(self, task_id: str, result: Dict[str, Any]) -> None:
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

    async def notify_controller_failure(self, task_id: str, error: str) -> None:
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
        """Get current GPU utilization."""
        if self.gpu_info:
            return float(self.gpu_info.get("utilization", 0.0))
        return 0.0

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics. Windows-safe paths."""
        try:
            if os.name == "nt":
                root = os.path.splitdrive(os.getcwd())[0] + "\\" if os.getcwd() else "C:\\"
            else:
                root = "/"
            disk = psutil.disk_usage(root)
            disk_pct = disk.percent
        except Exception:
            disk_pct = 0.0
        load_avg = (psutil.getloadavg()[0],) if hasattr(psutil, "getloadavg") else (0.0,)
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": disk_pct,
            "load_average": load_avg[0] if load_avg else 0.0,
        }

    def _format_gpu_status(self) -> Dict[str, Any]:
        """Format gpu_status for heartbeat."""
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
        """Get available GPU memory in MB."""
        if not self.gpu_info:
            return 0
        return max(0, self.gpu_info.get("memory_total", 0) - self.gpu_info.get("memory_used", 0))

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("Shutting down worker %s", self.worker_id)
        await self.stop_background_tasks()
        for task_id, task_record in list(self.current_tasks.items()):
            if task_record.get("status") == "running":
                task_record["status"] = "cancelled"
                task_record["completed_at"] = datetime.now().isoformat()
        try:
            async with self._http_client(10.0) as client:
                await client.delete(
                    self._controller_api(f"/workers/{self.worker_id}")
                )
        except Exception as e:
            logger.warning("Failed to unregister from controller: %s", e)
        logger.info("Worker %s shutdown complete", self.worker_id)


def create_worker(config: Dict[str, Any]) -> PhantomWindowsWorker:
    """Create a Windows worker instance from configuration."""
    return PhantomWindowsWorker(
        worker_id=config.get("worker_id"),
        controller_host=config.get("controller_host", "localhost"),
        controller_port=config.get("controller_port", 8080),
        worker_port=config.get("worker_port", 8090),
        tls_enabled=bool(config.get("tls_enabled", False)),
        tls_controller_cert_path=str(config.get("tls_controller_cert_path", "") or ""),
    )
