"""Lean GPU-aware task routing primitives for Phantom vNext."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional, Set


ML_TASK_TYPES: Set[str] = {"training", "ml_inference", "large_model_inference"}


class WorkerStatus(str, Enum):
    ACTIVE = "active"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class GPUInfo:
    name: str
    memory_total: int
    memory_free: int
    utilization: float = 0.0


@dataclass
class WorkerInfo:
    worker_id: str
    gpu_info: GPUInfo
    status: WorkerStatus
    current_tasks: int = 0
    max_concurrent_tasks: int = 1


@dataclass
class TaskRequest:
    task_id: str
    task_type: str
    min_memory_mb: int = 0


def smart_worker_selection(
    task: TaskRequest, active_workers: Iterable[WorkerInfo]
) -> Optional[str]:
    """Select worker with highest deterministic score."""

    scored: Dict[str, float] = {}
    for worker in active_workers:
        if worker.status != WorkerStatus.ACTIVE:
            continue
        if worker.current_tasks >= worker.max_concurrent_tasks:
            continue
        if task.min_memory_mb and worker.gpu_info.memory_free < task.min_memory_mb:
            continue
        scored[worker.worker_id] = _score_worker(task, worker)

    if not scored:
        return None
    return max(scored.items(), key=lambda item: item[1])[0]


def _score_worker(task: TaskRequest, worker: WorkerInfo) -> float:
    gpu = worker.gpu_info

    # Normalize around 8GB so mixed devices can be compared.
    base_score = max(1.0, gpu.memory_total / 8192.0)
    if task.task_type in ML_TASK_TYPES and gpu.memory_total > 0:
        base_score *= max(0.0, gpu.memory_free / gpu.memory_total)

    load_factor = 1.0 - (worker.current_tasks / max(1, worker.max_concurrent_tasks))
    utilization_factor = 1.0 - (gpu.utilization / 100.0)

    return base_score * max(0.0, load_factor) * max(0.0, utilization_factor)
