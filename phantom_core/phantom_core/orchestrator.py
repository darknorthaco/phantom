"""
Phantom Distributed Orchestrator
Enhanced version with intelligent task routing and GPU optimization
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import httpx
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerStatus(Enum):
    ACTIVE = "active"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class GPUInfo:
    name: str
    memory_total: int
    memory_free: int
    compute_capability: str
    driver_version: str
    utilization: float = 0.0


@dataclass
class WorkerInfo:
    worker_id: str
    host: str
    port: int
    gpu_info: GPUInfo
    status: WorkerStatus
    heartbeat_missed_count: int = 0
    gpu_status_cached: Optional[Dict] = None
    websocket_id: Optional[str] = None
    registration_timestamp: Optional[datetime] = None
    current_tasks: int = 0
    max_concurrent_tasks: int = 1
    last_heartbeat: datetime = None
    performance_score: float = 1.0


@dataclass
class Task:
    task_id: str
    task_type: str
    parameters: Dict[str, Any]
    priority: int
    status: TaskStatus
    worker_id: Optional[str] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PhantomOrchestrator:
    """Enhanced orchestrator with intelligent task routing and GPU optimization"""

    def __init__(self):
        self.workers: Dict[str, WorkerInfo] = {}
        self.tasks: Dict[str, Task] = {}
        self.task_queue: List[str] = []
        self.running = False

        # Performance tracking
        self.task_history: List[Dict] = []
        self.worker_performance: Dict[str, List[float]] = {}

        # GPU performance profiles — capability lookup table used to score
        # auto-discovered hardware. The orchestrator matches discovered GPU names
        # against this table at runtime. Unknown GPUs get a default baseline score.
        self.gpu_profiles = {
            "RTX 5080": {
                "ml_inference": 10.0,
                "training": 9.5,
                "image_processing": 9.0,
                "data_processing": 8.0,
                "memory_capacity": 24000,  # MB
            },
            "RTX 5060": {
                "ml_inference": 7.0,
                "training": 6.5,
                "image_processing": 7.5,
                "data_processing": 6.0,
                "memory_capacity": 16000,  # MB
            },
            "GTX 1080": {
                "ml_inference": 5.0,
                "training": 4.5,
                "image_processing": 6.0,
                "data_processing": 5.5,
                "memory_capacity": 8000,  # MB
            },
            "AMD FirePro W9100": {
                "ml_inference": 3.0,
                "training": 2.5,
                "image_processing": 4.0,
                "data_processing": 8.0,  # Excellent for data processing
                "memory_capacity": 16000,  # MB
            },
        }

    async def start(self):
        """Start the orchestrator"""
        self.running = True
        logger.info("🎯 Phantom Orchestrator started")

        # Start background tasks
        asyncio.create_task(self.task_scheduler())
        asyncio.create_task(self.worker_health_monitor())
        asyncio.create_task(self.performance_analyzer())

    async def stop(self):
        """Stop the orchestrator"""
        self.running = False
        logger.info("🎯 Phantom Orchestrator stopped")

    # NEW: Heartbeat update handler
    def update_heartbeat(self, worker_id: str, heartbeat):
        """Update worker heartbeat and GPU status"""
        if worker_id not in self.workers:
            return

        worker = self.workers[worker_id]

        # Update heartbeat timestamp
        worker.last_heartbeat = heartbeat.timestamp

        # Cache GPU status
        worker.gpu_status_cached = heartbeat.gpu_status

        # Reset missed heartbeat counter
        worker.heartbeat_missed_count = 0

        # Adjust performance score (simple heuristic)
        worker.performance_score = max(0.1, worker.performance_score * 0.99)

        logger.debug(f"❤️ Heartbeat updated for worker {worker_id}")

    def register_worker(self, worker_info: WorkerInfo):
        """Register a new worker"""
        self.workers[worker_info.worker_id] = worker_info
        self.worker_performance[worker_info.worker_id] = []
        logger.info(
            f"👷 Worker registered: {worker_info.worker_id} ({worker_info.gpu_info.name})"
        )

    def unregister_worker(self, worker_id: str):
        """Unregister a worker"""
        if worker_id in self.workers:
            del self.workers[worker_id]
            if worker_id in self.worker_performance:
                del self.worker_performance[worker_id]
            logger.info(f"👷 Worker unregistered: {worker_id}")

    def submit_task(self, task: Task) -> str:
        """Submit a new task"""
        if task.created_at is None:
            task.created_at = datetime.now()

        self.tasks[task.task_id] = task
        self.task_queue.append(task.task_id)

        logger.info(f"📋 Task submitted: {task.task_id} ({task.task_type})")
        return task.task_id

    async def task_scheduler(self):
        """Main task scheduling loop"""
        while self.running:
            try:
                if self.task_queue:
                    await self.process_task_queue()
                await asyncio.sleep(1.0)  # Check every second
            except Exception as e:
                logger.error(f"Error in task scheduler: {e}")
                await asyncio.sleep(5.0)

    async def process_task_queue(self):
        """Process pending tasks in the queue"""
        # Sort tasks by priority (higher priority first)
        self.task_queue.sort(key=lambda tid: self.tasks[tid].priority, reverse=True)

        tasks_to_remove = []

        for task_id in self.task_queue:
            task = self.tasks[task_id]

            if task.status != TaskStatus.PENDING:
                tasks_to_remove.append(task_id)
                continue

            # Find best worker for this task
            selected_worker = await self.select_optimal_worker(task)

            if selected_worker:
                await self.assign_task_to_worker(task, selected_worker)
                tasks_to_remove.append(task_id)

        # Remove processed tasks from queue
        for task_id in tasks_to_remove:
            if task_id in self.task_queue:
                self.task_queue.remove(task_id)

    async def select_optimal_worker(self, task: Task) -> Optional[str]:
        """Select the optimal worker for a task using enhanced algorithms"""

        # Filter available workers
        available_workers = {
            wid: worker
            for wid, worker in self.workers.items()
            if (
                worker.status == WorkerStatus.ACTIVE
                and worker.current_tasks < worker.max_concurrent_tasks
            )
        }

        if not available_workers:
            return None

        # Calculate scores for each worker
        worker_scores = {}

        for worker_id, worker in available_workers.items():
            score = await self.calculate_worker_score(task, worker)
            worker_scores[worker_id] = score

        # Select worker with highest score
        if worker_scores:
            best_worker = max(worker_scores.items(), key=lambda x: x[1])
            logger.debug(
                f"Selected worker {best_worker[0]} with score {best_worker[1]:.2f} for task {task.task_id}"
            )
            return best_worker[0]

        return None

    async def calculate_worker_score(self, task: Task, worker: WorkerInfo) -> float:
        """Calculate a score for how suitable a worker is for a task"""

        # Base score from GPU performance profile
        gpu_name = worker.gpu_info.name
        base_score = 1.0

        # Find matching GPU profile
        for profile_name, profile in self.gpu_profiles.items():
            if profile_name in gpu_name:
                task_type_score = profile.get(task.task_type, 1.0)
                base_score = task_type_score
                break

        # Adjust for current load
        load_factor = 1.0 - (worker.current_tasks / worker.max_concurrent_tasks)

        # Adjust for historical performance
        performance_factor = worker.performance_score

        # Adjust for memory requirements
        memory_factor = 1.0
        if task.parameters.get("memory_required"):
            required_memory = task.parameters["memory_required"]
            if worker.gpu_info.memory_free < required_memory:
                memory_factor = 0.1  # Heavily penalize insufficient memory
            else:
                memory_factor = min(1.0, worker.gpu_info.memory_free / required_memory)

        # Adjust for GPU utilization
        utilization_factor = 1.0 - (worker.gpu_info.utilization / 100.0)

        # Calculate final score
        final_score = (
            base_score
            * load_factor
            * performance_factor
            * memory_factor
            * utilization_factor
        )

        logger.debug(
            f"Worker {worker.worker_id} score: base={base_score:.2f}, "
            f"load={load_factor:.2f}, perf={performance_factor:.2f}, "
            f"mem={memory_factor:.2f}, util={utilization_factor:.2f}, "
            f"final={final_score:.2f}"
        )

        return final_score

    async def assign_task_to_worker(self, task: Task, worker_id: str):
        """Assign a task to a specific worker"""
        worker = self.workers[worker_id]

        try:
            # Update task status
            task.status = TaskStatus.QUEUED
            task.worker_id = worker_id
            task.started_at = datetime.now()

            # Update worker status
            worker.current_tasks += 1
            if worker.current_tasks >= worker.max_concurrent_tasks:
                worker.status = WorkerStatus.BUSY

            # Send task to worker
            await self.send_task_to_worker(task, worker)

            # Update task status to running
            task.status = TaskStatus.RUNNING

            logger.info(f"📋 Task {task.task_id} assigned to worker {worker_id}")

        except Exception as e:
            # Rollback on error
            task.status = TaskStatus.PENDING
            task.worker_id = None
            task.started_at = None
            worker.current_tasks = max(0, worker.current_tasks - 1)

            logger.error(
                f"Failed to assign task {task.task_id} to worker {worker_id}: {e}"
            )
            raise

    async def send_task_to_worker(self, task: Task, worker: WorkerInfo):
        """Send task to worker via HTTP"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"http://{worker.host}:{worker.port}/tasks/execute",
                    json={
                        "task_id": task.task_id,
                        "task_type": task.task_type,
                        "parameters": task.parameters,
                        "priority": task.priority,
                    },
                )

                if response.status_code != 200:
                    raise Exception(
                        f"Worker returned status {response.status_code}: {response.text}"
                    )

        except Exception as e:
            logger.error(f"Failed to send task to worker {worker.worker_id}: {e}")
            raise

    async def handle_task_completion(self, task_id: str, result: Dict[str, Any]):
        """Handle task completion from worker"""
        if task_id not in self.tasks:
            logger.warning(f"Received completion for unknown task: {task_id}")
            return

        task = self.tasks[task_id]
        worker = self.workers.get(task.worker_id)

        # Update task
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.result = result

        # Update worker
        if worker:
            worker.current_tasks = max(0, worker.current_tasks - 1)
            if (
                worker.status == WorkerStatus.BUSY
                and worker.current_tasks < worker.max_concurrent_tasks
            ):
                worker.status = WorkerStatus.ACTIVE

        # Record performance metrics
        await self.record_task_performance(task)

        logger.info(f"✅ Task {task_id} completed successfully")

    async def handle_task_failure(self, task_id: str, error: str):
        """Handle task failure from worker"""
        if task_id not in self.tasks:
            logger.warning(f"Received failure for unknown task: {task_id}")
            return

        task = self.tasks[task_id]
        worker = self.workers.get(task.worker_id)

        # Update task
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now()
        task.error = error

        # Update worker
        if worker:
            worker.current_tasks = max(0, worker.current_tasks - 1)
            if (
                worker.status == WorkerStatus.BUSY
                and worker.current_tasks < worker.max_concurrent_tasks
            ):
                worker.status = WorkerStatus.ACTIVE

        # Record performance metrics (negative impact)
        await self.record_task_performance(task, success=False)

        logger.error(f"❌ Task {task_id} failed: {error}")

    async def record_task_performance(self, task: Task, success: bool = True):
        """Record task performance metrics"""
        if not task.started_at or not task.completed_at:
            return

        duration = (task.completed_at - task.started_at).total_seconds()

        # Record in task history
        self.task_history.append(
            {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "worker_id": task.worker_id,
                "duration": duration,
                "success": success,
                "timestamp": task.completed_at.isoformat(),
            }
        )

        # Update worker performance
        if task.worker_id and task.worker_id in self.worker_performance:
            # Simple performance scoring: faster = better, success = better
            if success:
                # Normalize duration (assuming 60s is baseline)
                performance_score = max(0.1, min(2.0, 60.0 / max(1.0, duration)))
            else:
                performance_score = 0.1  # Penalty for failure

            self.worker_performance[task.worker_id].append(performance_score)

            # Keep only recent performance data (last 100 tasks)
            if len(self.worker_performance[task.worker_id]) > 100:
                self.worker_performance[task.worker_id] = self.worker_performance[
                    task.worker_id
                ][-100:]

            # Update worker's performance score (moving average)
            worker = self.workers.get(task.worker_id)
            if worker:
                recent_scores = self.worker_performance[task.worker_id][
                    -10:
                ]  # Last 10 tasks
                worker.performance_score = sum(recent_scores) / len(recent_scores)

    async def worker_health_monitor(self):
        """Monitor worker health and update status"""
        while self.running:
            try:
                current_time = datetime.now()

                for worker_id, worker in self.workers.items():
                    if worker.last_heartbeat:
                        time_since_heartbeat = current_time - worker.last_heartbeat

                        if time_since_heartbeat > timedelta(minutes=5):
                            if worker.status != WorkerStatus.OFFLINE:
                                logger.warning(
                                    f"Worker {worker_id} appears offline (no heartbeat for {time_since_heartbeat})"
                                )
                                worker.status = WorkerStatus.OFFLINE
                        elif worker.status == WorkerStatus.OFFLINE:
                            logger.info(f"Worker {worker_id} is back online")
                            worker.status = WorkerStatus.ACTIVE

                await asyncio.sleep(30.0)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in worker health monitor: {e}")
                await asyncio.sleep(60.0)

    async def heartbeat_collection_loop(self):
        """Collect heartbeats from registered workers every 5 seconds.

        Calls each worker's heartbeat endpoint and updates internal worker
        records. Marks a worker OFFLINE after 3 consecutive missed heartbeats.
        """
        while self.running:
            try:
                current_time = datetime.now()

                for worker_id, worker in list(self.workers.items()):
                    try:
                        async with httpx.AsyncClient(timeout=2.0) as client:
                            response = await client.post(
                                f"http://{worker.host}:{worker.port}/workers/{worker_id}/heartbeat",
                                timeout=2.0,
                            )

                        if response.status_code == 200:
                            worker.last_heartbeat = current_time
                            worker.heartbeat_missed_count = 0
                            # Parse optional gpu_status
                            try:
                                data = response.json()
                                if isinstance(data, dict) and "gpu_status" in data:
                                    worker.gpu_status_cached = data.get("gpu_status")
                            except Exception:
                                pass

                            if worker.status == WorkerStatus.OFFLINE:
                                worker.status = WorkerStatus.ACTIVE
                                logger.info(
                                    f"👷 Worker {worker_id} recovered (back online)"
                                )
                        else:
                            worker.heartbeat_missed_count += 1
                    except (httpx.TimeoutException, httpx.ConnectError):
                        worker.heartbeat_missed_count += 1
                    except Exception as e:
                        logger.debug(f"Heartbeat check error for {worker_id}: {e}")

                    if worker.heartbeat_missed_count >= 3:
                        if worker.status != WorkerStatus.OFFLINE:
                            worker.status = WorkerStatus.OFFLINE
                            logger.warning(
                                f"👷 Worker {worker_id} marked OFFLINE "
                                f"({worker.heartbeat_missed_count} missed heartbeats)"
                            )

                await asyncio.sleep(5.0)
            except Exception as e:
                logger.error(f"Error in heartbeat collection loop: {e}")
                await asyncio.sleep(5.0)

    async def performance_analyzer(self):
        """Analyze system performance and optimize"""
        while self.running:
            try:
                await asyncio.sleep(300.0)  # Run every 5 minutes

                # Analyze task completion rates
                recent_tasks = [
                    t
                    for t in self.task_history
                    if datetime.fromisoformat(t["timestamp"])
                    > datetime.now() - timedelta(hours=1)
                ]

                if recent_tasks:
                    success_rate = sum(1 for t in recent_tasks if t["success"]) / len(
                        recent_tasks
                    )
                    avg_duration = sum(t["duration"] for t in recent_tasks) / len(
                        recent_tasks
                    )

                    logger.info(
                        f"📊 Performance metrics: {len(recent_tasks)} tasks, "
                        f"{success_rate:.1%} success rate, "
                        f"{avg_duration:.1f}s avg duration"
                    )

                # Analyze worker performance
                for worker_id, scores in self.worker_performance.items():
                    if scores:
                        avg_score = sum(scores) / len(scores)
                        logger.debug(
                            f"Worker {worker_id} avg performance: {avg_score:.2f}"
                        )

            except Exception as e:
                logger.error(f"Error in performance analyzer: {e}")

    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        total_workers = len(self.workers)
        active_workers = sum(
            1 for w in self.workers.values() if w.status == WorkerStatus.ACTIVE
        )
        busy_workers = sum(
            1 for w in self.workers.values() if w.status == WorkerStatus.BUSY
        )
        offline_workers = sum(
            1 for w in self.workers.values() if w.status == WorkerStatus.OFFLINE
        )

        total_tasks = len(self.tasks)
        completed_tasks = sum(
            1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED
        )
        running_tasks = sum(
            1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING
        )
        failed_tasks = sum(
            1 for t in self.tasks.values() if t.status == TaskStatus.FAILED
        )

        # Recent performance
        recent_tasks = [
            t
            for t in self.task_history
            if datetime.fromisoformat(t["timestamp"])
            > datetime.now() - timedelta(hours=1)
        ]

        success_rate = 0.0
        avg_duration = 0.0
        if recent_tasks:
            success_rate = sum(1 for t in recent_tasks if t["success"]) / len(
                recent_tasks
            )
            avg_duration = sum(t["duration"] for t in recent_tasks) / len(recent_tasks)

        return {
            "workers": {
                "total": total_workers,
                "active": active_workers,
                "busy": busy_workers,
                "offline": offline_workers,
            },
            "tasks": {
                "total": total_tasks,
                "completed": completed_tasks,
                "running": running_tasks,
                "failed": failed_tasks,
                "queued": len(self.task_queue),
            },
            "performance": {
                "recent_tasks_1h": len(recent_tasks),
                "success_rate": success_rate,
                "avg_duration_seconds": avg_duration,
            },
            "gpu_distribution": {
                gpu_name: sum(
                    1 for w in self.workers.values() if w.gpu_info.name == gpu_name
                )
                for gpu_name in {w.gpu_info.name for w in self.workers.values()}
            },
        }


# Global orchestrator instance

# Alias required by controller_api import
Orchestrator = PhantomOrchestrator

orchestrator = PhantomOrchestrator()
