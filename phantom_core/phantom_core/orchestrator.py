"""
Phantom Distributed Orchestrator
Enhanced version with intelligent task routing and GPU optimization.

Supports adaptive routing via Thompson Sampling when enabled.
Set PHANTOM_ADAPTIVE_ROUTING=true to activate online learning
over worker-selection strategies.
"""

import asyncio
import logging
import os
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
    """Enhanced orchestrator with intelligent task routing and GPU optimization.

    When PHANTOM_ADAPTIVE_ROUTING=true (or adaptive_routing=True is passed),
    the orchestrator uses Thompson Sampling to learn which worker-scoring
    strategy produces the best task outcomes. Otherwise, falls back to the
    original multiplicative scoring.
    """

    def __init__(self, adaptive_routing: Optional[bool] = None, state_dir: Optional[str] = None):
        self.workers: Dict[str, WorkerInfo] = {}
        self.tasks: Dict[str, Task] = {}
        self.task_queue: List[str] = []
        self.running = False

        # Performance tracking
        self.task_history: List[Dict] = []
        self.worker_performance: Dict[str, List[float]] = {}

        # Adaptive routing (Thompson Sampling)
        _enable = adaptive_routing if adaptive_routing is not None else (
            os.getenv("PHANTOM_ADAPTIVE_ROUTING", "").lower() in ("true", "1", "yes")
        )
        self.adaptive_router = None
        self._active_strategies: Dict[str, str] = {}  # task_id -> strategy_name

        if _enable:
            try:
                from phantom_core.adaptive_router import TaskTypeRouter
                _state_dir = state_dir or os.getenv("PHANTOM_STATE_DIR")
                self.adaptive_router = TaskTypeRouter(
                    state_dir=_state_dir,
                    discount=0.995,  # Slow decay — worker pool changes slowly
                )
                logger.info("Adaptive routing ENABLED (per-task-type Thompson Sampling)")
            except Exception as e:
                logger.warning("Failed to initialize adaptive router: %s", e)

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
        """Select the optimal worker for a task.

        When adaptive routing is enabled, Thompson Sampling selects the
        scoring strategy and the router applies learned weights. Otherwise,
        falls back to the original multiplicative scoring.
        """

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

        # Select routing strategy (adaptive or fixed)
        strategy = None
        if self.adaptive_router:
            strategy = self.adaptive_router.select_strategy(task.task_type)

        # Calculate scores for each worker
        worker_scores = {}

        for worker_id, worker in available_workers.items():
            if strategy and self.adaptive_router:
                score = self._score_worker_adaptive(task, worker, strategy)
            else:
                score = await self.calculate_worker_score(task, worker)
            worker_scores[worker_id] = score

        # Select worker with highest score
        if worker_scores:
            best_worker = max(worker_scores.items(), key=lambda x: x[1])

            # Log decision for the adaptive router
            if strategy and self.adaptive_router:
                self._active_strategies[task.task_id] = strategy
                self.adaptive_router.log_decision(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    strategy=strategy,
                    worker_id=best_worker[0],
                    worker_scores=worker_scores,
                )

            logger.debug(
                "Selected worker %s with score %.2f for task %s%s",
                best_worker[0], best_worker[1], task.task_id,
                f" (strategy: {strategy})" if strategy else "",
            )
            return best_worker[0]

        return None

    def _compute_factor_scores(self, task: Task, worker: WorkerInfo) -> Dict[str, float]:
        """Compute normalized scoring factors for a worker.

        Returns a dict with keys {gpu, load, perf, memory, util}, each
        a float typically in [0, 1]. Used by both adaptive and legacy scoring.
        """
        # GPU capability from profile
        gpu_name = worker.gpu_info.name
        gpu_score = 1.0
        max_profile_score = 10.0  # Normalize against max possible

        for profile_name, profile in self.gpu_profiles.items():
            if profile_name in gpu_name:
                gpu_score = profile.get(task.task_type, 1.0) / max_profile_score
                break
        else:
            gpu_score = 1.0 / max_profile_score  # Unknown GPU gets baseline

        # Load factor
        if worker.max_concurrent_tasks > 0:
            load_score = 1.0 - (worker.current_tasks / worker.max_concurrent_tasks)
        else:
            load_score = 0.0

        # Historical performance
        perf_score = min(1.0, worker.performance_score)

        # Memory availability
        memory_score = 1.0
        if task.parameters.get("memory_required"):
            required_memory = task.parameters["memory_required"]
            if worker.gpu_info.memory_free < required_memory:
                memory_score = 0.1
            else:
                memory_score = min(1.0, worker.gpu_info.memory_free / required_memory)

        # GPU utilization headroom
        util_score = 1.0 - (worker.gpu_info.utilization / 100.0)

        return {
            "gpu": gpu_score,
            "load": load_score,
            "perf": perf_score,
            "memory": memory_score,
            "util": util_score,
        }

    def _score_worker_adaptive(
        self, task: Task, worker: WorkerInfo, strategy: str,
    ) -> float:
        """Score a worker using the adaptive router's learned weights."""
        factors = self._compute_factor_scores(task, worker)
        score = self.adaptive_router.score_worker(task.task_type, strategy, factors)

        logger.debug(
            "Worker %s adaptive score: strategy=%s, factors=%s, final=%.4f",
            worker.worker_id, strategy,
            {k: f"{v:.2f}" for k, v in factors.items()}, score,
        )
        return score

    async def calculate_worker_score(self, task: Task, worker: WorkerInfo) -> float:
        """Legacy multiplicative scoring (used when adaptive routing is off)."""
        factors = self._compute_factor_scores(task, worker)

        # Original multiplicative formula (denormalize gpu back to raw scale)
        base_score = factors["gpu"] * 10.0  # Reverse the normalization
        final_score = (
            base_score
            * factors["load"]
            * factors["perf"]
            * factors["memory"]
            * factors["util"]
        )

        logger.debug(
            "Worker %s legacy score: base=%.2f, load=%.2f, perf=%.2f, "
            "mem=%.2f, util=%.2f, final=%.2f",
            worker.worker_id, base_score, factors["load"], factors["perf"],
            factors["memory"], factors["util"], final_score,
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

        # Update adaptive router with success signal
        self._update_adaptive_router(task, success=True)

        logger.info(f"Task {task_id} completed successfully")

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

        # Update adaptive router with failure signal
        self._update_adaptive_router(task, success=False)

        logger.error(f"Task {task_id} failed: {error}")

    def _update_adaptive_router(self, task: Task, success: bool):
        """Feed task outcome back to the adaptive router's bandit."""
        if not self.adaptive_router:
            return

        strategy = self._active_strategies.pop(task.task_id, None)
        if not strategy:
            return

        # Compute duration
        duration = 60.0  # default baseline
        if task.started_at and task.completed_at:
            duration = (task.completed_at - task.started_at).total_seconds()

        from phantom_core.adaptive_router import AdaptiveRouter
        reward = AdaptiveRouter.compute_reward(
            success=success,
            duration_seconds=duration,
        )

        self.adaptive_router.update(task.task_type, strategy, reward)
        self.adaptive_router.record_outcome(task.task_type, task.task_id, reward)

        logger.debug(
            "Adaptive router updated: task=%s, type=%s, strategy=%s, "
            "success=%s, duration=%.1fs, reward=%.3f",
            task.task_id, task.task_type, strategy, success, duration, reward,
        )

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
