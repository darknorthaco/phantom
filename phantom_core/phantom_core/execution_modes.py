"""
Execution Mode Support for Phantom Controller
Implements HYBRID and MANUAL execution modes
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Global state for proposals (in production, use proper storage)
proposals = {}


class ExecutionMode:
    """Execution mode enumeration"""

    AUTO = "auto"
    HYBRID = "hybrid"
    MANUAL = "manual"


class WorkerProposal(BaseModel):
    """Worker selection proposal for HYBRID mode"""

    proposed_worker: str
    reasoning: str
    score: float
    alternatives: List[Dict[str, Any]] = []
    generated_at: datetime
    expires_at: datetime


class ApprovalRequest(BaseModel):
    """Approval request for HYBRID mode"""

    approved_worker: Optional[str] = None  # Override proposed worker
    approval_reason: Optional[str] = None
    approver: str


class RejectionRequest(BaseModel):
    """Rejection request for HYBRID mode"""

    rejection_reason: str
    rejector: str


class BatchApprovalRequest(BaseModel):
    """Batch approval request"""

    task_ids: List[str]
    approver: str
    approval_reason: Optional[str] = None


class ManualValidation(BaseModel):
    """Validation result for MANUAL mode"""

    valid: bool
    worker_id: str
    available: bool
    warnings: List[Dict[str, Any]] = []
    performance_estimate: Optional[Dict[str, Any]] = None


def get_system_execution_mode() -> str:
    """Get system-wide execution mode from environment"""
    import os

    return os.getenv("PHANTOM_EXECUTION_MODE", ExecutionMode.AUTO)


def get_proposal_timeout() -> int:
    """Get proposal timeout in seconds"""
    import os

    return int(os.getenv("HYBRID_PROPOSAL_TIMEOUT", "300"))


async def generate_worker_proposal(
    task: Any, active_workers: Dict[str, Any], selection_algorithm: callable
) -> WorkerProposal:
    """
    Generate worker selection proposal for HYBRID mode

    Args:
        task: Task request
        active_workers: Dictionary of available workers
        selection_algorithm: Function to score and select workers

    Returns:
        WorkerProposal with recommendation and alternatives
    """
    # Score workers based on GPU, load, etc.
    worker_scores = {}
    for worker_id, worker in active_workers.items():
        gpu_info = worker.get("gpu_info", {})
        gpu_name = gpu_info.get("name", "Unknown")

        # Simple scoring (GPU performance hierarchy)
        base_score = 0.5  # Default
        if "RTX 5080" in gpu_name:
            base_score = 1.0
        elif "RTX 5060" in gpu_name:
            base_score = 0.9
        elif "GTX 1080" in gpu_name:
            base_score = 0.7
        elif "FirePro" in gpu_name:
            base_score = 0.6

        worker_scores[worker_id] = base_score

    # Select best worker
    if not worker_scores:
        raise ValueError("No workers available for proposal")

    best_worker_id = max(worker_scores.items(), key=lambda x: x[1])[0]
    best_worker = active_workers[best_worker_id]
    best_score = worker_scores[best_worker_id]

    # Generate reasoning
    gpu_name = best_worker.get("gpu_info", {}).get("name", "Unknown GPU")
    reasoning = (
        f"{gpu_name} selected as optimal for task type '{task.task_type}'. "
        f"Score: {best_score:.2f}. Available memory and current load considered."
    )

    # Generate alternatives
    alternatives = []
    sorted_workers = sorted(worker_scores.items(), key=lambda x: x[1], reverse=True)[
        1:4
    ]  # Top 3 alternatives

    for alt_worker_id, alt_score in sorted_workers:
        alt_worker = active_workers[alt_worker_id]
        alt_gpu = alt_worker.get("gpu_info", {}).get("name", "Unknown")
        alternatives.append(
            {
                "worker_id": alt_worker_id,
                "score": alt_score,
                "reason": f"{alt_gpu} alternative (score: {alt_score:.2f})",
            }
        )

    # Create proposal
    now = datetime.now()
    timeout_seconds = get_proposal_timeout()

    proposal = WorkerProposal(
        proposed_worker=best_worker_id,
        reasoning=reasoning,
        score=best_score,
        alternatives=alternatives,
        generated_at=now,
        expires_at=now + timedelta(seconds=timeout_seconds),
    )

    return proposal


async def validate_manual_worker_selection(
    worker_id: str, task_type: str, workers: Dict[str, Any]
) -> ManualValidation:
    """
    Validate manual worker selection

    Args:
        worker_id: Worker selected by human
        task_type: Type of task
        workers: Available workers dictionary

    Returns:
        ManualValidation with warnings and recommendations
    """
    warnings = []

    # Check if worker exists
    if worker_id not in workers:
        return ManualValidation(
            valid=False,
            worker_id=worker_id,
            available=False,
            warnings=[
                {"level": "error", "message": f"Worker '{worker_id}' does not exist"}
            ],
        )

    worker = workers[worker_id]

    # Check if worker is active
    if worker.get("status") != "active":
        return ManualValidation(
            valid=False,
            worker_id=worker_id,
            available=False,
            warnings=[
                {
                    "level": "error",
                    "message": f"Worker '{worker_id}' is not active (status: {worker.get('status')})",
                }
            ],
        )

    # Worker is valid and available
    valid = True
    available = True

    # Generate warnings for suboptimal selection
    gpu_info = worker.get("gpu_info", {})
    gpu_name = gpu_info.get("name", "Unknown")

    # Check if worker is optimal for task type
    optimal_gpus = {
        "ml_inference": ["RTX 5080", "RTX 5060"],
        "training": ["RTX 5080", "RTX 5060"],
        "image_processing": ["RTX 5080", "RTX 5060"],
        "data_processing": ["FirePro", "RTX 5080"],
    }

    task_optimal = optimal_gpus.get(task_type, [])
    is_optimal = any(gpu in gpu_name for gpu in task_optimal)

    if not is_optimal and task_optimal:
        warnings.append(
            {
                "level": "warning",
                "message": f"Worker '{worker_id}' ({gpu_name}) may be suboptimal for task type '{task_type}'",
                "recommendation": f"Consider workers with: {', '.join(task_optimal)}",
            }
        )

    # Check GPU memory (example warning)
    memory_free = gpu_info.get("memory_free", 0)
    if memory_free < 4000:  # Less than 4GB free
        warnings.append(
            {
                "level": "warning",
                "message": f"Worker '{worker_id}' has low available GPU memory ({memory_free}MB)",
                "recommendation": "Consider a worker with more available memory",
            }
        )

    # Performance estimate
    score = 0.5  # Default
    if "RTX 5080" in gpu_name:
        score = 1.0
    elif "RTX 5060" in gpu_name:
        score = 0.9
    elif "GTX 1080" in gpu_name:
        score = 0.7
    elif "FirePro" in gpu_name:
        score = 0.6

    performance_estimate = {
        "expected_score": score,
        "optimal_score": 1.0,
        "efficiency": f"{int(score * 100)}%",
    }

    return ManualValidation(
        valid=valid,
        worker_id=worker_id,
        available=available,
        warnings=warnings,
        performance_estimate=performance_estimate,
    )


def store_proposal(task_id: str, proposal: WorkerProposal):
    """Store proposal for later approval"""
    proposals[task_id] = proposal
    logger.info(f"Stored proposal for task {task_id}, expires at {proposal.expires_at}")


def get_proposal(task_id: str) -> Optional[WorkerProposal]:
    """Retrieve stored proposal"""
    return proposals.get(task_id)


def get_pending_proposals() -> List[Dict[str, Any]]:
    """Get all pending proposals that haven't expired"""
    now = datetime.now()
    pending = []

    for task_id, proposal in proposals.items():
        if proposal.expires_at > now:
            pending.append({"task_id": task_id, "proposal": proposal.dict()})

    return pending


def expire_old_proposals():
    """Clean up expired proposals"""
    now = datetime.now()
    expired_tasks = [
        task_id for task_id, proposal in proposals.items() if proposal.expires_at <= now
    ]

    for task_id in expired_tasks:
        del proposals[task_id]
        logger.info(f"Expired proposal for task {task_id}")

    return expired_tasks


def delete_proposal(task_id: str):
    """Delete proposal after approval/rejection"""
    if task_id in proposals:
        del proposals[task_id]
        logger.info(f"Deleted proposal for task {task_id}")
