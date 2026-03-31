"""
Authoritative task ledger for the Phantom controller.

Execution lifecycle states (canonical):
  QUEUED → RUNNING → COMPLETED | FAILED

Workflow states (unchanged): pending_approval, expired, cancelled, rejected

Persisted via StateManager (tasks.json). See controller/task_ledger.md.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

TASK_QUEUED = "QUEUED"
TASK_RUNNING = "RUNNING"
TASK_COMPLETED = "COMPLETED"
TASK_FAILED = "FAILED"

TASK_PENDING_APPROVAL = "pending_approval"
TASK_EXPIRED = "expired"
TASK_CANCELLED = "cancelled"
TASK_REJECTED = "rejected"

_LEGACY_TO_CANONICAL = {
    "queued": TASK_QUEUED,
    "running": TASK_RUNNING,
    "completed": TASK_COMPLETED,
    "failed": TASK_FAILED,
}


def normalize_task_status(status: Optional[str]) -> str:
    """Map legacy lowercase statuses to canonical ledger values."""
    if not status:
        return TASK_QUEUED
    lowered = status.lower()
    return _LEGACY_TO_CANONICAL.get(lowered, status)


def is_terminal_execution_status(status: str) -> bool:
    return status in (TASK_COMPLETED, TASK_FAILED)


def is_terminal_any_status(status: str) -> bool:
    return status in (
        TASK_COMPLETED,
        TASK_FAILED,
        TASK_CANCELLED,
        TASK_EXPIRED,
        TASK_REJECTED,
    )


def default_running_timeout_sec() -> float:
    return float(os.environ.get("PHANTOM_TASK_RUNNING_TIMEOUT_SEC", "86400"))


def _parse_started_at(started_at: str) -> Optional[datetime]:
    if not started_at:
        return None
    try:
        s = started_at.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def apply_worker_completion(
    tasks: Dict[str, Any],
    task_id: str,
    worker_id: str,
    result: Dict[str, Any],
    timestamp_iso: str,
) -> Tuple[bool, str]:
    """
    Apply completion callback. Idempotent if already COMPLETED for this task.

    Returns (success, reason_code).
    """
    if task_id not in tasks:
        return False, "unknown_task"
    rec = tasks[task_id]
    if rec.get("worker_id") != worker_id:
        logger.warning(
            "Task %s completion worker mismatch: expected %r got %r",
            task_id,
            rec.get("worker_id"),
            worker_id,
        )
        return False, "worker_mismatch"
    st = rec.get("status", "")
    if st == TASK_COMPLETED:
        return True, "idempotent"
    if is_terminal_any_status(st) and st != TASK_RUNNING:
        if st == TASK_FAILED:
            logger.warning("Ignoring late completion for failed task %s", task_id)
        return False, "invalid_state"
    if st != TASK_RUNNING:
        return False, f"invalid_state:{st}"
    rec["status"] = TASK_COMPLETED
    rec["result"] = result
    rec["completed_at"] = timestamp_iso
    rec.pop("error", None)
    return True, "ok"


def apply_worker_failure(
    tasks: Dict[str, Any],
    task_id: str,
    worker_id: str,
    error: str,
    timestamp_iso: str,
    *,
    reason_code: str = "worker_reported",
) -> Tuple[bool, str]:
    """Apply failure callback. Idempotent if already FAILED."""
    if task_id not in tasks:
        return False, "unknown_task"
    rec = tasks[task_id]
    if rec.get("worker_id") != worker_id:
        logger.warning(
            "Task %s failure worker mismatch: expected %r got %r",
            task_id,
            rec.get("worker_id"),
            worker_id,
        )
        return False, "worker_mismatch"
    st = rec.get("status", "")
    if st == TASK_FAILED:
        return True, "idempotent"
    if st == TASK_COMPLETED:
        logger.warning(
            "Ignoring failure callback after completion for task %s", task_id
        )
        return False, "already_completed"
    if is_terminal_any_status(st) and st not in (TASK_RUNNING, TASK_QUEUED):
        return False, f"invalid_state:{st}"
    if st not in (TASK_RUNNING, TASK_QUEUED):
        return False, f"invalid_state:{st}"
    rec["status"] = TASK_FAILED
    rec["error"] = error
    rec["failed_at"] = timestamp_iso
    rec["failure_reason"] = reason_code
    return True, "ok"


def reconcile_stale_running_tasks(
    tasks: Dict[str, Any],
    now: Optional[datetime] = None,
    timeout_sec: Optional[float] = None,
) -> List[str]:
    """
    Mark RUNNING tasks as FAILED when elapsed time since started_at exceeds timeout.

    Returns list of task_ids updated.
    """
    now = now or datetime.now()
    timeout_sec = (
        timeout_sec if timeout_sec is not None else default_running_timeout_sec()
    )
    updated: List[str] = []
    for tid, rec in list(tasks.items()):
        if not isinstance(rec, dict):
            continue
        if rec.get("status") != TASK_RUNNING:
            continue
        started = _parse_started_at(rec.get("started_at", ""))
        if started is None:
            continue
        # Compare naive vs aware safely
        if started.tzinfo is not None:
            now_cmp = now.astimezone(started.tzinfo)
            elapsed = (now_cmp - started).total_seconds()
        else:
            elapsed = (
                now.replace(tzinfo=None) - started.replace(tzinfo=None)
            ).total_seconds()
        if elapsed > timeout_sec:
            rec["status"] = TASK_FAILED
            rec["error"] = "timeout/no-callback"
            rec["failure_reason"] = "timeout/no-callback"
            rec["failed_at"] = now.isoformat()
            updated.append(tid)
            logger.warning(
                "Task %s marked FAILED: timeout/no-callback (%.0fs > %.0fs)",
                tid,
                elapsed,
                timeout_sec,
            )
    return updated
