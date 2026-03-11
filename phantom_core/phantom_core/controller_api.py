"""
Phantom Distributed Controller API
Enhanced version with socket integration support
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from typing import Dict, Any, Optional, List
from collections import deque
from enum import Enum
from phantom_core.orchestrator import (
    Orchestrator,
    WorkerInfo as OrchestratorWorkerInfo,
    GPUInfo as OrchestratorGPUInfo,
    WorkerStatus as OrchestratorWorkerStatus,
)
from phantom_core.state import StateManager
from phantom_core.trust_store import TrustStore, TrustLevel
from phantom_core.config_schema import ConfigSchema, locate_phantom_config
import httpx
import logging
import os
from datetime import datetime
import json
import uuid

# Configure logging early so the except blocks below can use logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import socket integration if available
try:
    from socket_integration import SocketManager

    SOCKET_AVAILABLE = True
except ImportError:
    SOCKET_AVAILABLE = False
    SocketManager = None

# Import security framework if available
try:
    from security_framework.integrated_security import SecurityManager

    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    SecurityManager = None

# Import execution mode support
try:
    from execution_modes import (
        ApprovalRequest,
        RejectionRequest,
        BatchApprovalRequest,
        get_system_execution_mode,
        generate_worker_proposal,
        validate_manual_worker_selection,
        store_proposal,
        get_proposal,
        get_pending_proposals,
        expire_old_proposals,
        delete_proposal,
    )

    EXECUTION_MODES_AVAILABLE = True
except ImportError:
    logger.warning("Execution modes module not available")
    EXECUTION_MODES_AVAILABLE = False

    class ApprovalRequest(BaseModel):  # type: ignore[no-redef]
        approved_worker: Optional[str] = None
        approval_reason: Optional[str] = None
        approver: str = ""

    class RejectionRequest(BaseModel):  # type: ignore[no-redef]
        rejection_reason: str = ""
        rejector: str = ""

    class BatchApprovalRequest(BaseModel):  # type: ignore[no-redef]
        task_ids: List[str] = []
        approver: str = ""
        approval_reason: Optional[str] = None

    def get_system_execution_mode():
        return "auto"

    async def generate_worker_proposal(*args, **kwargs):
        raise RuntimeError("execution_modes not available")

    async def validate_manual_worker_selection(*args, **kwargs):
        raise RuntimeError("execution_modes not available")

    def store_proposal(*args, **kwargs):
        pass

    def get_proposal(*args, **kwargs):
        return None

    def get_pending_proposals():
        return []

    def expire_old_proposals():
        return []

    def delete_proposal(*args, **kwargs):
        pass


app = FastAPI(
    title="Phantom Distributed Controller",
    description="Enhanced distributed computing controller with socket and security integration",
    version="2.0.0",
)

# CORS middleware - configurable via PHANTOM_CORS_ORIGINS env var
_cors_origins = os.getenv(
    "PHANTOM_CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
)
CORS_ORIGINS = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Global state
workers = {}
tasks = {}
socket_manager = None
orchestrator = None
security_manager = None
state_manager: StateManager | None = None
trust_store: TrustStore | None = None
queue_paused = False
mode_audit_log: deque = deque(maxlen=1000)


class ExecutionMode(str, Enum):
    AUTO = "AUTO"
    HYBRID = "HYBRID"
    MANUAL = "MANUAL"


execution_mode: ExecutionMode = ExecutionMode.AUTO

MODE_SOCKET_SCHEMAS: Dict[ExecutionMode, Dict[str, Any]] = {
    ExecutionMode.AUTO: {
        "type": "AUTO_TASK_SUBMIT",
        "required_fields": [
            "task_id",
            "task_type",
            "worker_id",
            "status",
            "eta_seconds",
        ],
    },
    ExecutionMode.HYBRID: {
        "type": "HYBRID_TASK_PLAN",
        "required_fields": [
            "task_id",
            "task_type",
            "recommended_worker_id",
            "eta_seconds",
            "impact_report",
            "approval_required",
        ],
    },
    ExecutionMode.MANUAL: {
        "type": "MANUAL_TASK_OPTIONS",
        "required_fields": [
            "task_id",
            "task_type",
            "available_workers",
            "approval_required",
            "selected_worker_id",
        ],
    },
}


# Initialize integrated components
@app.on_event("startup")
async def startup_event():
    global socket_manager, security_manager, orchestrator, state_manager, trust_store

    # Restore persisted state
    state_dir = os.getenv("PHANTOM_STATE_DIR")
    state_manager = StateManager(state_dir) if state_dir else StateManager()
    trust_store = TrustStore(str(state_manager.state_dir))
    workers.update(state_manager.load_workers())
    tasks.update(state_manager.load_tasks())
    logger.info("💾 State restored (%d workers, %d tasks)", len(workers), len(tasks))

    # Initialize socket manager if integrated mode
    if SOCKET_AVAILABLE and os.getenv("PHANTOM_INTEGRATED") == "true":
        socket_manager = SocketManager()
        socket_manager.set_mode_handler = _set_execution_mode
        await socket_manager.start()
        logger.info("🔌 Socket infrastructure initialized")

    # Initialize security manager
    if SECURITY_AVAILABLE:
        # Prefer phantom_config.json (written at deploy Step 4.5).
        # Fall back to PHANTOM_SECURITY env var for dev / legacy environments,
        # but log a deprecation warning so operators know to migrate.
        _config_path = locate_phantom_config()
        if _config_path and _config_path.exists():
            try:
                _phantom_cfg = ConfigSchema.load(_config_path)
                security_level = _phantom_cfg.controller.security
                logger.info(
                    "🔒 Security level read from phantom_config.json: %s",
                    security_level,
                )
            except Exception as _cfg_err:
                logger.warning(
                    "⚠️  Failed to read security level from phantom_config.json "
                    "(%s); falling back to PHANTOM_SECURITY env var.",
                    _cfg_err,
                )
                security_level = os.getenv("PHANTOM_SECURITY", "basic")
        else:
            security_level = os.getenv("PHANTOM_SECURITY", "basic")
            if security_level != "basic":
                logger.warning(
                    "⚠️  phantom_config.json not found at %s; "
                    "using PHANTOM_SECURITY env var ('%s'). "
                    "Run deploy Step 4.5 (ConfigBootstrap) to create the config file.",
                    _config_path,
                    security_level,
                )
        if security_level != "disabled":
            security_manager = SecurityManager(security_level)
            await security_manager.initialize()
            logger.info(f"🔒 Security framework initialized (level: {security_level})")

    # Initialize orchestrator
    try:
        orchestrator = Orchestrator()
        logger.info("🎯 Orchestrator initialized")
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    # Persist state before shutting down
    if state_manager:
        state_manager.save_workers(workers)
        state_manager.save_tasks(tasks)
        logger.info("💾 State persisted on shutdown")
    if socket_manager:
        await socket_manager.stop()
        logger.info("🔌 Socket infrastructure stopped")


# Pydantic models
_MAX_PAYLOAD_BYTES = 65_536  # 64 KB max for dict payloads


class ApproveWorkerRequest(BaseModel):
    """§5 — Request to record user approval for a worker (pre-registration)."""

    worker_id: str = Field(..., max_length=128)
    public_key: str = Field("", max_length=512)


class WorkerInfo(BaseModel):
    worker_id: str = Field(..., max_length=128)
    host: str = Field(..., max_length=253)
    port: int = Field(..., ge=1, le=65535)
    gpu_info: Dict[str, Any]
    status: str = Field("active", max_length=32)
    last_heartbeat: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_gpu_info_size(self) -> "WorkerInfo":
        if len(json.dumps(self.gpu_info)) > _MAX_PAYLOAD_BYTES:
            raise ValueError("gpu_info payload exceeds maximum allowed size")
        return self


class TaskRequest(BaseModel):
    task_type: str = Field(..., max_length=128)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(1, ge=1, le=10)
    target_worker: Optional[str] = Field(None, max_length=128)

    @model_validator(mode="after")
    def validate_parameters_size(self) -> "TaskRequest":
        if len(json.dumps(self.parameters)) > _MAX_PAYLOAD_BYTES:
            raise ValueError("parameters payload exceeds maximum allowed size")
        return self


class TaskResponse(BaseModel):
    task_id: str
    status: str
    worker_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# NEW: Heartbeat request model
class HeartbeatRequest(BaseModel):
    gpu_status: Dict[str, Any]
    timestamp: datetime


class ModeRequest(BaseModel):
    mode: ExecutionMode
    session_id: Optional[str] = None


class TaskApprovalRequest(BaseModel):
    worker_id: Optional[str] = None
    session_id: Optional[str] = None


class QueueActionRequest(BaseModel):
    session_id: Optional[str] = None


# Security dependency
async def get_current_user(request):
    if security_manager:
        return await security_manager.authenticate_request(request)
    return {"user_id": "anonymous", "permissions": ["all"]}


def _record_audit(event_type: str, payload: Dict[str, Any]):
    mode_audit_log.append(
        {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "payload": payload,
        }
    )


def _set_execution_mode(
    mode: ExecutionMode | str, session_id: Optional[str], source: str
) -> Dict[str, Any]:
    global execution_mode
    mode = ExecutionMode(mode)
    previous_mode = execution_mode
    execution_mode = mode

    audit_payload = {
        "session_id": session_id or "unknown",
        "source": source,
        "previous_mode": previous_mode.value,
        "mode": mode.value,
    }
    _record_audit("mode_changed", audit_payload)

    return {
        "status": "mode_set",
        "mode": mode.value,
        "previous_mode": previous_mode.value,
        "session_id": session_id,
        "source": source,
    }


def _get_available_worker_options(
    task: Optional[TaskRequest] = None,
) -> List[Dict[str, Any]]:
    options: List[Dict[str, Any]] = []
    for worker_id, worker in workers.items():
        gpu_info = worker.get("gpu_info", {})
        memory_free = gpu_info.get("memory_free", 0)
        status = worker.get("status", "offline")

        color = "red"
        if status == "active":
            if (
                task
                and task.task_type in {"training", "ml_inference"}
                and memory_free < 8192
            ):
                color = "yellow"
            else:
                color = "green"

        options.append(
            {
                "worker_id": worker_id,
                "model": gpu_info.get("name", "Unknown"),
                "status": status,
                "color": color,
            }
        )
    return options


def _task_status_counts() -> Dict[str, int]:
    counts = {"running": 0, "queued": 0, "pending_approval": 0}
    for task_record in tasks.values():
        status = task_record.get("status")
        if status in counts:
            counts[status] += 1
    return counts


def _is_valid_manual_target_worker(task: TaskRequest) -> bool:
    if not task.target_worker:
        return False
    if task.target_worker not in workers:
        return False
    return workers[task.target_worker].get("status") == "active"


def _predict_eta_seconds(
    task: TaskRequest,
    worker_id: Optional[str],
    status_counts: Optional[Dict[str, int]] = None,
) -> int:
    status_counts = status_counts or _task_status_counts()
    running_count = status_counts["running"]
    queue_count = status_counts["queued"]
    base_seconds = 30

    if task.task_type in {"training", "ml_inference"}:
        base_seconds = 90
    elif task.task_type == "image_processing":
        base_seconds = 45

    if worker_id and worker_id in workers:
        memory_free = workers[worker_id].get("gpu_info", {}).get("memory_free", 0)
        if memory_free and memory_free < 8192:
            base_seconds += 20

    return base_seconds + (running_count * 20) + (queue_count * 10)


def _build_impact_report(
    task: TaskRequest,
    worker_id: Optional[str],
    status_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    status_counts = status_counts or _task_status_counts()
    worker_load = len(
        [
            t
            for t in tasks.values()
            if worker_id and t["worker_id"] == worker_id and t["status"] == "running"
        ]
    )
    return {
        "mode": execution_mode.value,
        "priority": task.priority,
        "queue_depth": status_counts["queued"],
        "active_tasks": status_counts["running"],
        "worker_load": worker_load,
    }


# Core API endpoints
@app.get("/")
async def root():
    return {
        "message": "Phantom Distributed Controller",
        "version": "2.0.0",
        "execution_mode": execution_mode.value,
        "features": {
            "socket_infrastructure": SOCKET_AVAILABLE and socket_manager is not None,
            "security_framework": SECURITY_AVAILABLE and security_manager is not None,
            "integrated_mode": os.getenv("PHANTOM_INTEGRATED") == "true",
            "modes_supported": [mode.value for mode in ExecutionMode],
        },
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "execution_mode": execution_mode.value,
        "queue_paused": queue_paused,
        "workers_count": len(workers),
        "active_tasks": len([t for t in tasks.values() if t["status"] == "running"]),
    }


@app.get("/mode")
async def get_mode():
    return {
        "mode": execution_mode.value,
        "schemas": {mode.value: MODE_SOCKET_SCHEMAS[mode] for mode in ExecutionMode},
    }


@app.post("/mode")
async def set_mode(mode_request: ModeRequest):
    response = _set_execution_mode(
        mode_request.mode, mode_request.session_id, source="rest_api"
    )
    if socket_manager:
        await socket_manager.broadcast_to_ui(
            {
                "type": "MODE_CHANGED",
                "mode": execution_mode.value,
                "session_id": mode_request.session_id,
                "timestamp": datetime.now().isoformat(),
            }
        )
    return response


@app.post("/workers/approve")
async def approve_worker(req: ApproveWorkerRequest):
    """§5 — Record user approval for a worker. Required before registration."""
    if not trust_store:
        raise HTTPException(status_code=503, detail="Trust store not initialized")
    trust_store.approve_worker_with_key(req.worker_id, req.public_key)
    logger.info("Worker %s approved for registration", req.worker_id)
    return {"status": "approved", "worker_id": req.worker_id}


@app.post("/workers/register")
async def register_worker(worker: WorkerInfo):
    """Register a new worker with the controller. §5: requires TrustRecord(approved)."""
    if trust_store:
        level = trust_store.get_current_level(worker.worker_id)
        if level not in (TrustLevel.APPROVED.value, TrustLevel.REGISTERED.value):
            logger.warning("Registration rejected: worker %s not approved (level=%s)", worker.worker_id, level)
            raise HTTPException(
                status_code=403,
                detail=f"Worker {worker.worker_id} must be approved before registration",
            )
    worker.last_heartbeat = datetime.now()
    workers[worker.worker_id] = worker.dict()

    # Notify socket clients if available
    if socket_manager:
        await socket_manager.broadcast(
            {
                "type": "worker_registered",
                "worker_id": worker.worker_id,
                "gpu_info": worker.gpu_info,
            }
        )

    # Forward registration to orchestrator (if available)
    if orchestrator:
        gpu = worker.gpu_info or {}

        gpu_info = OrchestratorGPUInfo(
            name=gpu.get("name", ""),
            memory_total=gpu.get("memory_total", 0),
            memory_free=gpu.get("memory_free", 0),
            compute_capability=gpu.get("compute_capability", ""),
            driver_version=gpu.get("driver_version", ""),
            utilization=gpu.get("utilization", 0.0),
        )

        worker_info = OrchestratorWorkerInfo(
            worker_id=worker.worker_id,
            host=worker.host,
            port=worker.port,
            gpu_info=gpu_info,
            status=OrchestratorWorkerStatus.ACTIVE,
        )

        orchestrator.register_worker(worker_info)

    if trust_store:
        trust_store.record_registration(worker.worker_id)
    logger.info(f"Worker registered: {worker.worker_id} at {worker.host}:{worker.port}")
    if state_manager:
        state_manager.save_workers(workers)
    return {"status": "registered", "worker_id": worker.worker_id}


@app.get("/workers")
async def list_workers():
    """List all registered workers"""
    return {"workers": list(workers.values())}


@app.get("/workers/{worker_id}")
async def get_worker(worker_id: str):
    """Get specific worker information"""
    if worker_id not in workers:
        raise HTTPException(status_code=404, detail="Worker not found")
    return workers[worker_id]


@app.delete("/workers/{worker_id}")
async def unregister_worker(worker_id: str):
    """Unregister a worker"""
    if worker_id not in workers:
        raise HTTPException(status_code=404, detail="Worker not found")

    del workers[worker_id]

    # Notify socket clients if available
    if socket_manager:
        await socket_manager.broadcast(
            {"type": "worker_unregistered", "worker_id": worker_id}
        )

    logger.info(f"Worker unregistered: {worker_id}")
    if state_manager:
        state_manager.save_workers(workers)
    return {"status": "unregistered"}


@app.post("/workers/{worker_id}/heartbeat")
async def worker_heartbeat(worker_id: str):
    """Update worker heartbeat"""
    if worker_id not in workers:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Parse heartbeat payload
    heartbeat = HeartbeatRequest(
        gpu_status=workers[worker_id]["gpu_info"], timestamp=datetime.now()
    )

    # Update controller state
    workers[worker_id]["last_heartbeat"] = heartbeat.timestamp.isoformat()
    workers[worker_id]["status"] = "active"

    # Forward heartbeat to orchestrator
    if orchestrator:
        orchestrator.update_heartbeat(worker_id, heartbeat)

    return {"status": "heartbeat_received", "worker_id": worker_id}


@app.post("/tasks/submit")
async def submit_task(task: TaskRequest, background_tasks: BackgroundTasks):
    """Submit a new task for processing"""
    task_id = str(uuid.uuid4())

    # Check if queue is paused
    if queue_paused:
        raise HTTPException(status_code=503, detail="Task queue is paused")

    # Select worker
    selected_worker = await select_worker_for_task(task)
    if not selected_worker:
        raise HTTPException(status_code=503, detail="No available workers")

    status_counts = _task_status_counts()
    eta_seconds = _predict_eta_seconds(task, selected_worker, status_counts)
    socket_type = MODE_SOCKET_SCHEMAS[execution_mode]["type"]

    if execution_mode == ExecutionMode.HYBRID and EXECUTION_MODES_AVAILABLE:
        # Generate proposal for human approval
        active_workers = {
            wid: w for wid, w in workers.items() if w.get("status") == "active"
        }
        try:
            proposal = await generate_worker_proposal(
                task, active_workers, smart_worker_selection
            )
        except ValueError:
            raise HTTPException(status_code=503, detail="No workers available")

        impact_report = _build_impact_report(
            task, proposal.proposed_worker, status_counts
        )
        task_record = {
            "task_id": task_id,
            "task_type": task.task_type,
            "parameters": task.parameters,
            "priority": task.priority,
            "worker_id": proposal.proposed_worker,
            "status": "pending_approval",
            "created_at": datetime.now().isoformat(),
            "eta_seconds": eta_seconds,
        }
        tasks[task_id] = task_record
        store_proposal(task_id, proposal)

        if socket_manager:
            socket_payload = {
                "type": socket_type,
                "task_id": task_id,
                "task_type": task.task_type,
                "recommended_worker_id": proposal.proposed_worker,
                "eta_seconds": eta_seconds,
                "impact_report": impact_report,
                "approval_required": True,
            }
            await socket_manager.broadcast(socket_payload)

        if state_manager:
            state_manager.save_tasks(tasks)

        logger.info(
            f"Task {task_id} pending approval, proposed worker: {proposal.proposed_worker}"
        )
        return {
            "task_id": task_id,
            "status": "pending_approval",
            "proposed_worker": proposal.proposed_worker,
            "eta_seconds": eta_seconds,
            "approval_required": True,
        }

    elif execution_mode == ExecutionMode.MANUAL and EXECUTION_MODES_AVAILABLE:
        available_workers = _get_available_worker_options(task)
        if task.target_worker:
            if not _is_valid_manual_target_worker(task):
                raise HTTPException(
                    status_code=400,
                    detail=f"Target worker {task.target_worker} is not available",
                )
            task_record = {
                "task_id": task_id,
                "task_type": task.task_type,
                "parameters": task.parameters,
                "priority": task.priority,
                "worker_id": task.target_worker,
                "status": "queued",
                "created_at": datetime.now().isoformat(),
                "eta_seconds": eta_seconds,
            }
            tasks[task_id] = task_record
            background_tasks.add_task(execute_task, task_id, task.target_worker, task)

            if socket_manager:
                socket_payload = {
                    "type": socket_type,
                    "task_id": task_id,
                    "task_type": task.task_type,
                    "available_workers": available_workers,
                    "approval_required": False,
                    "selected_worker_id": task.target_worker,
                }
                await socket_manager.broadcast(socket_payload)

            if state_manager:
                state_manager.save_tasks(tasks)

            return {
                "task_id": task_id,
                "status": "queued",
                "worker_id": task.target_worker,
                "eta_seconds": eta_seconds,
            }
        else:
            # No target worker specified; return options for manual selection
            task_record = {
                "task_id": task_id,
                "task_type": task.task_type,
                "parameters": task.parameters,
                "priority": task.priority,
                "worker_id": None,
                "status": "pending_approval",
                "created_at": datetime.now().isoformat(),
                "eta_seconds": eta_seconds,
            }
            tasks[task_id] = task_record

            if socket_manager:
                socket_payload = {
                    "type": socket_type,
                    "task_id": task_id,
                    "task_type": task.task_type,
                    "available_workers": available_workers,
                    "approval_required": True,
                    "selected_worker_id": None,
                }
                await socket_manager.broadcast(socket_payload)

            if state_manager:
                state_manager.save_tasks(tasks)

            return {
                "task_id": task_id,
                "status": "pending_approval",
                "available_workers": available_workers,
                "approval_required": True,
                "eta_seconds": eta_seconds,
            }

    else:
        # AUTO mode (default)
        task_record = {
            "task_id": task_id,
            "task_type": task.task_type,
            "parameters": task.parameters,
            "priority": task.priority,
            "worker_id": selected_worker,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "eta_seconds": eta_seconds,
        }
        tasks[task_id] = task_record
        background_tasks.add_task(execute_task, task_id, selected_worker, task)

        if socket_manager:
            socket_payload = {
                "type": socket_type,
                "task_id": task_id,
                "task_type": task.task_type,
                "worker_id": selected_worker,
                "status": task_record["status"],
                "eta_seconds": eta_seconds,
            }
            await socket_manager.broadcast(socket_payload)

        if state_manager:
            state_manager.save_tasks(tasks)

        logger.info(f"Task {task_id} queued, assigned to {selected_worker}")
        return {
            "task_id": task_id,
            "status": "queued",
            "worker_id": selected_worker,
            "eta_seconds": eta_seconds,
        }


@app.get("/tasks")
async def list_tasks():
    """List all tasks"""
    return {"tasks": list(tasks.values())}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get specific task information"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]


@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task_record = tasks[task_id]
    if task_record["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")

    # Cancel task on worker
    worker_id = task_record["worker_id"]
    if worker_id in workers:
        try:
            worker = workers[worker_id]
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"http://{worker['host']}:{worker['port']}/tasks/{task_id}"
                )
        except Exception as e:
            logger.warning(f"Failed to cancel task on worker: {e}")

    task_record["status"] = "cancelled"

    # Notify socket clients if available
    if socket_manager:
        await socket_manager.broadcast({"type": "task_cancelled", "task_id": task_id})

    return {"status": "cancelled"}


# Socket infrastructure endpoints
if SOCKET_AVAILABLE:

    @app.get("/socket/status")
    async def socket_status():
        """Get socket infrastructure status"""
        if not socket_manager:
            return {"status": "disabled"}
        return await socket_manager.get_status()

    @app.post("/socket/broadcast")
    async def socket_broadcast(message: Dict[str, Any]):
        """Broadcast message to all socket clients"""
        if not socket_manager:
            raise HTTPException(
                status_code=503, detail="Socket infrastructure not available"
            )
        await socket_manager.broadcast(message)
        return {"status": "broadcasted"}


# Enhanced worker selection logic
async def select_worker_for_task(task: TaskRequest) -> Optional[str]:
    """Enhanced worker selection with GPU-aware routing"""

    # If specific worker requested
    if task.target_worker and task.target_worker in workers:
        worker = workers[task.target_worker]
        if worker["status"] == "active":
            return task.target_worker

    # Filter active workers
    active_workers = {
        wid: worker for wid, worker in workers.items() if worker["status"] == "active"
    }

    if not active_workers:
        return None

    # Use LLM task master if available and socket infrastructure is running
    if socket_manager and task.task_type in [
        "ml_inference",
        "training",
        "image_processing",
    ]:
        llm_selection = await request_llm_worker_selection(task, active_workers)
        if llm_selection:
            return llm_selection

    # Fallback to smart programming-based selection
    return smart_worker_selection(task, active_workers)


async def request_llm_worker_selection(
    task: TaskRequest, active_workers: Dict
) -> Optional[str]:
    """Request worker selection from LLM task master via socket"""
    try:
        if not socket_manager:
            return None

        response = await socket_manager.request_llm_routing(
            {
                "task": task.dict(),
                "available_workers": active_workers,
                "execution_mode": execution_mode.value,
                "approval_required": execution_mode != ExecutionMode.AUTO,
            }
        )

        if response and "selected_worker" in response:
            return response["selected_worker"]
    except Exception as e:
        logger.warning(f"LLM task master selection failed: {e}")

    return None


def smart_worker_selection(task: TaskRequest, active_workers: Dict) -> str:
    """Smart programming-based worker selection"""

    # Score workers based on reported GPU capabilities and current load.
    # Using memory capacity as a hardware proxy avoids hardcoding specific
    # GPU model names, so any discovered GPU is scored fairly.
    worker_scores = {}
    for worker_id, worker in active_workers.items():
        gpu_info = worker.get("gpu_info", {})
        memory_total = gpu_info.get("memory_total", 0)
        memory_free = gpu_info.get("memory_free", 0)

        # Baseline score: normalized to 8 GB (= 1.0); memory_total is in MB
        base_score = max(1.0, memory_total / 8192)

        # Prefer workers with more free memory for memory-intensive tasks
        if task.task_type in {"training", "ml_inference", "large_model_inference"}:
            if memory_total > 0:
                base_score *= memory_free / memory_total

        # Adjust for current load (simplified)
        current_tasks = len(
            [
                t
                for t in tasks.values()
                if t["worker_id"] == worker_id and t["status"] == "running"
            ]
        )
        load_penalty = current_tasks * 0.1

        worker_scores[worker_id] = base_score - load_penalty

    # Select worker with highest score
    if worker_scores:
        return max(worker_scores.items(), key=lambda x: x[1])[0]

    # Fallback to first available worker
    return list(active_workers.keys())[0]


async def execute_task(task_id: str, worker_id: str, task: TaskRequest):
    """Execute task on selected worker"""
    try:
        tasks[task_id]["status"] = "running"

        # Notify socket clients if available
        if socket_manager:
            await socket_manager.broadcast(
                {"type": "task_started", "task_id": task_id, "worker_id": worker_id}
            )

        worker = workers[worker_id]

        # Send task to worker
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"http://{worker['host']}:{worker['port']}/tasks/execute",
                json={
                    "task_id": task_id,
                    "task_type": task.task_type,
                    "parameters": task.parameters,
                },
            )

            if response.status_code == 200:
                result = response.json()
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["result"] = result

                # Notify socket clients if available
                if socket_manager:
                    await socket_manager.broadcast(
                        {"type": "task_completed", "task_id": task_id, "result": result}
                    )

                logger.info(f"Task {task_id} completed successfully")
            else:
                raise Exception(f"Worker returned status {response.status_code}")

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)

        # Notify socket clients if available
        if socket_manager:
            await socket_manager.broadcast(
                {"type": "task_failed", "task_id": task_id, "error": str(e)}
            )

        logger.error(f"Task {task_id} failed: {e}")


# Execution mode endpoints
@app.get("/tasks/proposals")
async def list_proposals():
    """List all pending proposals (HYBRID mode)"""
    if not EXECUTION_MODES_AVAILABLE:
        raise HTTPException(status_code=501, detail="Execution modes not available")

    # Expire old proposals first
    expired = expire_old_proposals()

    # Update task status for expired proposals
    for task_id in expired:
        if task_id in tasks:
            tasks[task_id]["status"] = "expired"
            if socket_manager:
                await socket_manager.broadcast(
                    {
                        "type": "proposal_expired",
                        "task_id": task_id,
                        "expired_at": datetime.now().isoformat(),
                    }
                )

    # Get pending proposals
    pending = get_pending_proposals()

    return {
        "proposals": pending,
        "count": len(pending),
        "expired_count": len(expired),
    }


@app.post("/tasks/{task_id}/approve")
async def approve_proposal(
    task_id: str, approval: ApprovalRequest, background_tasks: BackgroundTasks
):
    """Approve a task proposal (HYBRID mode)"""
    if not EXECUTION_MODES_AVAILABLE:
        raise HTTPException(status_code=501, detail="Execution modes not available")

    # Check if task exists
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task_record = tasks[task_id]

    # Check if task is pending approval
    if task_record["status"] != "pending_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Task is not pending approval (status: {task_record['status']})",
        )

    # Get proposal
    proposal = get_proposal(task_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found or expired")

    # Check if proposal expired
    if proposal.expires_at < datetime.now():
        task_record["status"] = "expired"
        delete_proposal(task_id)
        raise HTTPException(status_code=410, detail="Proposal has expired")

    # Determine worker (use approved_worker if provided, else proposed)
    approved_worker = approval.approved_worker or proposal.proposed_worker

    # Validate worker still available
    if approved_worker not in workers or workers[approved_worker]["status"] != "active":
        raise HTTPException(
            status_code=400, detail=f"Worker {approved_worker} is not available"
        )

    # Update task record
    task_record["status"] = "queued"
    task_record["worker_id"] = approved_worker
    task_record["approved_at"] = datetime.now().isoformat()
    task_record["approved_by"] = approval.approver
    task_record["approval_reason"] = approval.approval_reason

    # Delete proposal
    delete_proposal(task_id)

    # Execute task
    task_req = TaskRequest(
        task_type=task_record["task_type"],
        parameters=task_record["parameters"],
        priority=task_record["priority"],
    )
    background_tasks.add_task(execute_task, task_id, approved_worker, task_req)

    # Notify socket clients
    if socket_manager:
        await socket_manager.broadcast(
            {
                "type": "proposal_approved",
                "task_id": task_id,
                "approved_worker": approved_worker,
                "approved_by": approval.approver,
                "approved_at": task_record["approved_at"],
            }
        )

    if state_manager:
        state_manager.save_tasks(tasks)

    logger.info(
        f"Task {task_id} approved by {approval.approver}, assigned to {approved_worker}"
    )

    return {
        "status": "approved",
        "task_id": task_id,
        "worker_id": approved_worker,
        "approved_at": task_record["approved_at"],
        "approved_by": approval.approver,
    }


@app.post("/tasks/{task_id}/reject")
async def reject_proposal(task_id: str, rejection: RejectionRequest):
    """Reject a task proposal (HYBRID mode)"""
    if not EXECUTION_MODES_AVAILABLE:
        raise HTTPException(status_code=501, detail="Execution modes not available")

    # Check if task exists
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task_record = tasks[task_id]

    # Check if task is pending approval
    if task_record["status"] != "pending_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Task is not pending approval (status: {task_record['status']})",
        )

    # Update task record
    task_record["status"] = "rejected"
    task_record["rejected_at"] = datetime.now().isoformat()
    task_record["rejected_by"] = rejection.rejector
    task_record["rejection_reason"] = rejection.rejection_reason

    # Delete proposal
    delete_proposal(task_id)

    # Notify socket clients
    if socket_manager:
        await socket_manager.broadcast(
            {
                "type": "proposal_rejected",
                "task_id": task_id,
                "rejected_by": rejection.rejector,
                "rejected_at": task_record["rejected_at"],
                "reason": rejection.rejection_reason,
            }
        )

    if state_manager:
        state_manager.save_tasks(tasks)

    logger.info(
        f"Task {task_id} rejected by {rejection.rejector}: {rejection.rejection_reason}"
    )

    return {
        "status": "rejected",
        "task_id": task_id,
        "rejected_at": task_record["rejected_at"],
        "rejected_by": rejection.rejector,
    }


@app.post("/tasks/batch-approve")
async def batch_approve(batch: BatchApprovalRequest, background_tasks: BackgroundTasks):
    """Batch approve multiple proposals (HYBRID mode)"""
    if not EXECUTION_MODES_AVAILABLE:
        raise HTTPException(status_code=501, detail="Execution modes not available")

    results = []
    approved_count = 0
    failed_count = 0

    for task_id in batch.task_ids:
        try:
            # Create approval request
            approval = ApprovalRequest(
                approver=batch.approver,
                approval_reason=batch.approval_reason,
            )

            # Approve task
            result = await approve_proposal(task_id, approval, background_tasks)
            results.append({"task_id": task_id, "status": "approved", "result": result})
            approved_count += 1
        except HTTPException as e:
            results.append({"task_id": task_id, "status": "failed", "error": e.detail})
            failed_count += 1
        except Exception as e:
            results.append({"task_id": task_id, "status": "failed", "error": str(e)})
            failed_count += 1

    return {
        "approved_count": approved_count,
        "failed_count": failed_count,
        "results": results,
    }


@app.get("/workers/available")
async def list_available_workers():
    """List all available workers (useful for MANUAL mode)"""
    active_workers = [
        {"worker_id": wid, **worker}
        for wid, worker in workers.items()
        if worker.get("status") == "active"
    ]

    return {"workers": active_workers, "count": len(active_workers)}


@app.post("/workers/validate")
async def validate_worker(request: Dict[str, Any]):
    """Validate worker selection (MANUAL mode)"""
    if not EXECUTION_MODES_AVAILABLE:
        raise HTTPException(status_code=501, detail="Execution modes not available")

    worker_id = request.get("worker_id")
    task_type = request.get("task_type", "general")

    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")

    validation = await validate_manual_worker_selection(worker_id, task_type, workers)

    return validation.dict()


@app.get("/system/execution-mode")
async def get_execution_mode():
    """Get current system execution mode"""
    mode = get_system_execution_mode()
    return {
        "execution_mode": mode,
        "available_modes": ["auto", "hybrid", "manual"],
    }


@app.post("/system/execution-mode")
async def set_execution_mode(request: Dict[str, Any]):
    """Set system execution mode (requires admin)"""
    import os

    new_mode = request.get("mode")
    reason = request.get("reason", "No reason provided")
    changed_by = request.get("changed_by", "unknown")

    if new_mode not in ["auto", "hybrid", "manual"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {new_mode}. Must be 'auto', 'hybrid', or 'manual'",
        )

    previous_mode = get_system_execution_mode()

    # Set environment variable (note: this only affects current process)
    os.environ["PHANTOM_EXECUTION_MODE"] = new_mode

    # Log mode change
    mode_change_log = {
        "timestamp": datetime.now().isoformat(),
        "previous_mode": previous_mode,
        "new_mode": new_mode,
        "changed_by": changed_by,
        "reason": reason,
    }

    logger.info(f"Execution mode changed: {previous_mode} → {new_mode} by {changed_by}")

    # Notify socket clients
    if socket_manager:
        await socket_manager.broadcast(
            {
                "type": "mode_changed",
                "previous_mode": previous_mode,
                "new_mode": new_mode,
                "timestamp": mode_change_log["timestamp"],
            }
        )

    return mode_change_log


# Additional utility endpoints
@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    total_workers = len(workers)
    active_workers = len([w for w in workers.values() if w["status"] == "active"])
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks.values() if t["status"] == "completed"])
    running_tasks = len([t for t in tasks.values() if t["status"] == "running"])

    return {
        "workers": {"total": total_workers, "active": active_workers},
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "running": running_tasks,
        },
        "features": {
            "socket_infrastructure": socket_manager is not None,
            "security_framework": security_manager is not None,
            "execution_mode": execution_mode.value,
            "queue_paused": queue_paused,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
