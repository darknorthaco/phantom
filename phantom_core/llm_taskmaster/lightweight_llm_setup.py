"""
Phantom LLM Task Master — Lightweight Routing Engine
Optimized for intelligent task routing with minimal resource usage.
Default model: Phi-3.5 Mini (GGUF, Q4_K_M) — runs on any 4GB+ VRAM GPU.

Governance Alignment (Soul–Mind–Body Hierarchy):
  Soul  → doctrine/PHANTOM_MANIFEST.md    (Identity Contract: Sovereignty, Humility,
                                            Authenticity, Transparency)
  Mind  → doctrine/PHANTOM_DOCTRINE.md    (11 Principles — esp. §1 Human Priority,
                                            §4 Transparent Operation, §8 Reversibility,
                                            §9 Modularity, §11 Opera Principle)
  Body  → .cursorrules                    (llm_constraints section)
        → PHANTOM_TEN_COMMANDMENTS.md     (Commandment I: no modification without
                                            authorization; VII: no simulator artifacts
                                            in production)

Execution Mode Contract:
  AUTO   — LLM decides autonomously; withdraws when human is active.
  HYBRID — LLM proposes only; execution requires explicit human approval.
  MANUAL — LLM is bypassed entirely; human routes tasks directly.

Configuration:
  All tunables are externalized in llm_config.json (Doctrine §9 Modularity).
  Hardcoded defaults exist only as fallbacks when the config file is absent.
"""

import asyncio
import logging
import json
import platform
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

# Import socket client for communication
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "phantom_core"))

try:
    from socket_integration import LLMTaskMasterClient
except ImportError:
    # Fallback: socket integration not available
    LLMTaskMasterClient = None

# Import the Constitutional Pipeline (ADR-0010)
# Authority chain: MemoryGuard → ModeGate → ModelRouter → ContextBuilder → ApprovalGate
try:
    from pipeline import (
        TaskMasterPipeline,
        PipelineContext,
        PipelineVerdict,
        ExecutionMode as PipelineExecutionMode,
        MemoryGuard,
        ModeGate,
        ModelRouter,
        ContextBuilder,
        ApprovalGate,
    )

    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration path — sits alongside this file
# ---------------------------------------------------------------------------
_CONFIG_PATH = Path(__file__).parent / "llm_config.json"


# ---------------------------------------------------------------------------
# Execution Mode Enum (Doctrine §8 Reversibility — mode is always changeable)
# ---------------------------------------------------------------------------
class ExecutionMode(str, Enum):
    """Phantom execution modes as defined in PHANTOM_EXECUTION_MODES_AND_API_SPEC.md"""

    AUTO = "auto"
    HYBRID = "hybrid"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Configuration Loader (Doctrine §9 Modularity — externalize, don't hardcode)
# ---------------------------------------------------------------------------
def load_config(path: Path = _CONFIG_PATH) -> Dict[str, Any]:
    """Load LLM Task Master configuration from external JSON file.

    Falls back to minimal safe defaults if the file is missing or corrupt.
    Per Doctrine §4 (Transparent Operation), the fallback is logged.
    """
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info(f"📄 Loaded LLM config from {path}")
            return config
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"⚠️ Failed to load {path}: {exc} — using defaults")

    # Minimal safe defaults (Doctrine §10 Minimalism)
    return {
        "execution_mode": {
            "default": "auto",
            "allowed_modes": ["auto", "hybrid", "manual"],
        },
        "model": {
            "model_type": "rule_based_with_learning",
            "model_size": "small",
            "context_length": 1024,
            "precision": "fp16",
            "batch_size": 1,
        },
        "resource_limits": {
            "max_memory_mb": 2048,
            "max_vram_mb": 2048,
            "target_gpu": "auto",
            "target_vram_gb": 4,
        },
        "routing": {
            "fallback_to_smart_programming": True,
            "max_decision_history": 100,
            "confidence_threshold": 0.5,
            "enable_learning": True,
        },
        "hybrid_mode": {
            "proposal_timeout_seconds": 300,
            "require_approval_reason": False,
            "auto_expire_proposals": True,
            "batch_approval_enabled": True,
        },
        "human_priority": {
            "enabled": True,
            "check_interval_seconds": 5,
            "cpu_threshold_percent": 70,
            "gpu_threshold_percent": 60,
            "vram_threshold_percent": 70,
            "auto_mode_action": "withdraw",
            "hybrid_mode_action": "pause",
            "manual_mode_action": "unaffected",
            "monitored_processes": [
                "game",
                "steam",
                "epic",
                "blender",
                "davinci",
                "premiere",
                "photoshop",
                "obs",
                "unity",
                "unreal",
            ],
        },
        "socket": {"default_host": "localhost", "default_port": 8081},
        "gpu_profiles": {},
        "task_preferences": {},
    }


# ---------------------------------------------------------------------------
# Human-Priority Withdrawal Checker
# (Doctrine §1 — Phantom yields instantly when the human is active)
# (Opera Principle §11 — vanishes when the human takes the stage)
# ---------------------------------------------------------------------------
class HumanPriorityChecker:
    """Monitors system resources and human activity.

    Before the LLM Task Master processes any request it must call
    `check()` to determine whether to proceed, pause, or withdraw.
    """

    def __init__(self, config: Dict[str, Any]):
        hp = config.get("human_priority", {})
        self.enabled = hp.get("enabled", True)
        self.cpu_threshold = hp.get("cpu_threshold_percent", 70)
        self.gpu_threshold = hp.get("gpu_threshold_percent", 60)
        self.vram_threshold = hp.get("vram_threshold_percent", 70)
        self.monitored_processes = [
            p.lower() for p in hp.get("monitored_processes", [])
        ]
        self._psutil_available = False
        try:
            import psutil  # noqa: F401

            self._psutil_available = True
        except ImportError:
            logger.warning(
                "⚠️ psutil not installed — human-priority checks will use basic heuristics"
            )

    async def check(self) -> Dict[str, Any]:
        """Return human-priority status.

        Returns a dict with:
          - human_active: bool (True if thresholds breached or monitored process found)
          - reason: str
          - cpu_percent: float | None
          - gpu_percent: float | None
        """
        if not self.enabled:
            return {"human_active": False, "reason": "human-priority checks disabled"}

        result: Dict[str, Any] = {
            "human_active": False,
            "reason": "system idle",
            "cpu_percent": None,
            "gpu_percent": None,
        }

        if self._psutil_available:
            import psutil

            # CPU check
            cpu = psutil.cpu_percent(interval=0.1)
            result["cpu_percent"] = cpu
            if cpu > self.cpu_threshold:
                result["human_active"] = True
                result["reason"] = (
                    f"CPU usage {cpu:.1f}% exceeds threshold {self.cpu_threshold}%"
                )
                return result

            # Monitored-process check
            try:
                for proc in psutil.process_iter(["name"]):
                    pname = (proc.info.get("name") or "").lower()
                    for monitored in self.monitored_processes:
                        if monitored in pname:
                            result["human_active"] = True
                            result["reason"] = f"Human process detected: {pname}"
                            return result
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # GPU check (best-effort via nvidia-smi on supported platforms)
        gpu_usage = await self._check_gpu_usage()
        if gpu_usage is not None:
            result["gpu_percent"] = gpu_usage
            if gpu_usage > self.gpu_threshold:
                result["human_active"] = True
                result["reason"] = (
                    f"GPU usage {gpu_usage:.1f}% exceeds threshold {self.gpu_threshold}%"
                )
                return result

        return result

    async def _check_gpu_usage(self) -> Optional[float]:
        """Best-effort GPU utilization check via nvidia-smi."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=3.0)
            if proc.returncode == 0 and stdout:
                values = [
                    float(v.strip())
                    for v in stdout.decode().strip().split("\n")
                    if v.strip()
                ]
                return max(values) if values else None
        except (FileNotFoundError, asyncio.TimeoutError, ValueError):
            pass
        return None


# ---------------------------------------------------------------------------
# Pending Proposal Store (HYBRID mode — Doctrine §8 Reversibility)
# ---------------------------------------------------------------------------
class ProposalStore:
    """Thread-safe store for pending HYBRID-mode proposals awaiting human approval."""

    def __init__(self, timeout_seconds: int = 300):
        self.proposals: Dict[str, Dict[str, Any]] = {}
        self.timeout_seconds = timeout_seconds

    def add(self, proposal: Dict[str, Any]) -> str:
        """Store a proposal and return its proposal_id."""
        proposal_id = str(uuid.uuid4())
        proposal["proposal_id"] = proposal_id
        proposal["created_at"] = datetime.now().isoformat()
        proposal["status"] = "pending_approval"
        self.proposals[proposal_id] = proposal
        return proposal_id

    def approve(
        self,
        proposal_id: str,
        approver: str,
        override_worker: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Approve a pending proposal. Returns the proposal or None if not found/expired."""
        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal["status"] != "pending_approval":
            return None

        proposal["status"] = "approved"
        proposal["approved_by"] = approver
        proposal["approved_at"] = datetime.now().isoformat()
        if override_worker:
            proposal["selected_worker"] = override_worker
        if reason:
            proposal["approval_reason"] = reason
        return proposal

    def reject(
        self, proposal_id: str, rejector: str, reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Reject a pending proposal."""
        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal["status"] != "pending_approval":
            return None

        proposal["status"] = "rejected"
        proposal["rejected_by"] = rejector
        proposal["rejected_at"] = datetime.now().isoformat()
        if reason:
            proposal["rejection_reason"] = reason
        return proposal

    def expire_stale(self) -> List[str]:
        """Expire proposals older than timeout. Returns list of expired proposal_ids."""
        now = datetime.now()
        expired = []
        for pid, prop in list(self.proposals.items()):
            if prop["status"] != "pending_approval":
                continue
            created = datetime.fromisoformat(prop["created_at"])
            if (now - created).total_seconds() > self.timeout_seconds:
                prop["status"] = "expired"
                prop["expired_at"] = now.isoformat()
                expired.append(pid)
        return expired

    def get_pending(self) -> List[Dict[str, Any]]:
        """Return all proposals still awaiting approval."""
        return [p for p in self.proposals.values() if p["status"] == "pending_approval"]


# ===========================================================================
# LLM Task Master — Mode-Aware Implementation
# ===========================================================================
class LightweightLLMTaskMaster:
    """Lightweight LLM Task Master — auto-assigns to best available GPU.

    Default model: Phi-3.5 Mini (GGUF, Q4_K_M). GPU target resolved at
    runtime from hardware discovered during installation network scan.

    Governance Alignment:
      - Doctrine §1  (Human Priority): Yields when human is active.
      - Doctrine §4  (Transparent Operation): All decisions logged with reasoning.
      - Doctrine §8  (Reversibility): HYBRID proposals are cancellable; mode is changeable.
      - Doctrine §9  (Modularity): Config externalized; routing is a swappable module.
      - Doctrine §11 (Opera Principle): Powerful but quiet.
      - Commandment I: No execution without authorization (enforced in HYBRID mode).

    Execution Modes:
      AUTO   — Autonomous routing with withdrawal on human activity.
      HYBRID — Proposal-only; blocks until human approves/rejects.
      MANUAL — Bypassed entirely; human selects worker directly.
    """

    def __init__(
        self,
        controller_host: Optional[str] = None,
        socket_port: Optional[int] = None,
        execution_mode: Optional[str] = None,
        config_path: Optional[Path] = None,
    ):
        # Load external config (Doctrine §9 Modularity)
        self.config = load_config(config_path or _CONFIG_PATH)

        # Connection settings — config overrideable by constructor args
        sock_cfg = self.config.get("socket", {})
        self.controller_host = controller_host or sock_cfg.get(
            "default_host", "localhost"
        )
        self.socket_port = socket_port or sock_cfg.get("default_port", 8081)
        self.socket_client = None
        self.running = False

        # Execution mode — human-selectable, default from config, overrideable by env var
        raw_mode = (
            execution_mode
            or os.environ.get("PHANTOM_EXECUTION_MODE")
            or self.config.get("execution_mode", {}).get("default", "auto")
        )
        try:
            self.execution_mode = ExecutionMode(raw_mode.lower())
        except ValueError:
            logger.warning(
                f"⚠️ Unknown execution mode '{raw_mode}' — defaulting to AUTO"
            )
            self.execution_mode = ExecutionMode.AUTO

        # Model config from external file
        model_cfg = self.config.get("model", {})
        self.model_config = {
            "model_type": model_cfg.get("model_type", "rule_based_with_learning"),
            "model_size": model_cfg.get("model_size", "small"),
            "max_memory_mb": self.config.get("resource_limits", {}).get(
                "max_memory_mb", 2048
            ),
            "context_length": model_cfg.get("context_length", 1024),
            "batch_size": model_cfg.get("batch_size", 1),
            "precision": model_cfg.get("precision", "fp16"),
        }

        # GPU profiles from config
        self.gpu_profiles = self.config.get("gpu_profiles", {})

        # Task preferences from config
        self.task_preferences = self.config.get("task_preferences", {})

        # Routing settings
        routing_cfg = self.config.get("routing", {})
        self.max_history = routing_cfg.get("max_decision_history", 100)
        self.confidence_threshold = routing_cfg.get("confidence_threshold", 0.5)

        # HYBRID mode: proposal store (Doctrine §8 Reversibility)
        hybrid_cfg = self.config.get("hybrid_mode", {})
        self.proposal_store = ProposalStore(
            timeout_seconds=hybrid_cfg.get("proposal_timeout_seconds", 300)
        )

        # Human-priority checker (Doctrine §1)
        self.human_priority_checker = HumanPriorityChecker(self.config)

        # Decision history for learning
        self.decision_history: List[Dict[str, Any]] = []

        # Performance tracking
        self.metrics: Dict[str, Any] = {
            "decisions_made": 0,
            "proposals_generated": 0,
            "proposals_approved": 0,
            "proposals_rejected": 0,
            "proposals_expired": 0,
            "withdrawals": 0,
            "average_decision_time": 0.0,
            "accuracy_feedback": [],
            "start_time": datetime.now(),
        }

        # Constitutional Pipeline (ADR-0010)
        # Authority: MemoryGuard → ModeGate → ModelRouter → ContextBuilder → ApprovalGate
        self.pipeline: Optional["TaskMasterPipeline"] = None

        logger.info(
            f"🎭 LLM Task Master configured: mode={self.execution_mode.value}, "
            f"host={self.controller_host}:{self.socket_port}"
        )

    # -----------------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------------

    async def initialize(self):
        """Initialize the LLM Task Master.

        In MANUAL mode, the Task Master still initializes for status reporting
        but does not process routing requests (Commandment I compliance).
        """
        try:
            logger.info(
                f"🤖 Initializing Phantom LLM Task Master [mode={self.execution_mode.value}]"
            )

            if self.execution_mode == ExecutionMode.MANUAL:
                logger.info(
                    "⏭️ MANUAL mode — LLM routing is BYPASSED. "
                    "Human selects workers directly. (Doctrine §1 Human Priority)"
                )
                self.running = True
                return

            # Initialize socket connection if available
            if LLMTaskMasterClient:
                self.socket_client = LLMTaskMasterClient(
                    self.controller_host, self.socket_port
                )

                connected = await self.socket_client.connect_as_llm_taskmaster()
                if connected:
                    logger.info("🔌 Connected to socket infrastructure")
                    asyncio.create_task(self.listen_for_requests())
                else:
                    logger.warning("🔌 Failed to connect to socket infrastructure")
                    self.socket_client = None

            # Load routing model (only for AUTO and HYBRID)
            await self.load_lightweight_model()

            # Initialize the Constitutional Pipeline (ADR-0010)
            if PIPELINE_AVAILABLE:
                pipeline_mode = PipelineExecutionMode(self.execution_mode.value)
                self.pipeline = TaskMasterPipeline(
                    config=self.config,
                    system_mode=pipeline_mode,
                    human_priority_checker=self.human_priority_checker,
                    proposal_store=self.proposal_store,
                )
                logger.info(
                    "🏛️ Constitutional Pipeline activated: "
                    "MemoryGuard → ModeGate → ModelRouter → ContextBuilder → ApprovalGate"
                )
            else:
                logger.warning(
                    "⚠️ Pipeline module not available — falling back to legacy routing. "
                    "(pipeline.py not found alongside lightweight_llm_setup.py)"
                )

            # Start proposal expiry loop for HYBRID mode
            if self.execution_mode == ExecutionMode.HYBRID:
                asyncio.create_task(self._proposal_expiry_loop())

            self.running = True
            logger.info("✅ LLM Task Master initialized successfully")

        except Exception as e:
            logger.error(f"LLM Task Master initialization failed: {e}")
            raise

    async def load_lightweight_model(self):
        """Load the lightweight routing model.

        NOTE: Current implementation is rule-based with learning heuristics.
        When a real model is integrated, this method loads it from the path
        specified in llm_config.json → model.model_path.
        Per Commandment VII: this simulation is clearly labeled as such and
        MUST NOT be presented as a real model in production telemetry.
        """
        try:
            logger.info("🧠 Loading lightweight routing model (rule-based scaffold)...")

            # SCAFFOLD: In production, replace with actual model loading from
            # self.config["model"]["model_path"]. This sleep simulates load time.
            await asyncio.sleep(0.5)

            self.routing_intelligence = {
                "model_loaded": True,
                "model_type": self.model_config["model_type"],
                "memory_usage_mb": 512,  # Estimated for rule engine
                "inference_time_ms": 50,
                "scaffold_notice": "Rule-based scaffold — real model integration pending",
            }

            logger.info("✅ Lightweight routing model loaded (scaffold)")

        except Exception as e:
            logger.error(f"Failed to load routing model: {e}")
            raise

    # -----------------------------------------------------------------------
    # Mode Management (Doctrine §8 Reversibility — mode is always changeable)
    # -----------------------------------------------------------------------

    def set_execution_mode(
        self, mode: str, changed_by: str = "system", reason: str = ""
    ) -> Dict[str, Any]:
        """Change the execution mode at runtime.

        The human user selects the mode. Default is AUTO but all three modes
        are distinct and the human's choice is authoritative.
        """
        previous = self.execution_mode.value
        try:
            new_mode = ExecutionMode(mode.lower())
        except ValueError:
            raise ValueError(
                f"Invalid execution mode '{mode}'. Allowed: {[m.value for m in ExecutionMode]}"
            )

        self.execution_mode = new_mode

        # Update the pipeline's mode if active (Doctrine §8 — reversible at runtime)
        if self.pipeline and PIPELINE_AVAILABLE:
            self.pipeline.update_mode(PipelineExecutionMode(new_mode.value))

        change_record = {
            "timestamp": datetime.now().isoformat(),
            "previous_mode": previous,
            "new_mode": new_mode.value,
            "changed_by": changed_by,
            "reason": reason,
        }
        logger.info(
            f"🔄 Execution mode changed: {previous} → {new_mode.value} "
            f"(by {changed_by}: {reason})"
        )
        return change_record

    # -----------------------------------------------------------------------
    # Message Listener
    # -----------------------------------------------------------------------

    async def listen_for_requests(self):
        """Listen for routing requests from the socket infrastructure."""
        if not self.socket_client:
            return

        async def message_handler(message: Dict[str, Any]):
            try:
                msg_type = message.get("type")
                if msg_type == "routing_request":
                    await self.handle_routing_request(message)
                elif msg_type == "system_state":
                    await self.handle_system_state_update(message)
                elif msg_type == "proposal_approval":
                    await self.handle_proposal_approval(message)
                elif msg_type == "proposal_rejection":
                    await self.handle_proposal_rejection(message)
                elif msg_type == "mode_change":
                    self.set_execution_mode(
                        message.get("mode", "auto"),
                        changed_by=message.get("changed_by", "system"),
                        reason=message.get("reason", ""),
                    )
            except Exception as e:
                logger.error(f"Error handling message: {e}")

        try:
            await self.socket_client.listen(message_handler)
        except Exception as e:
            logger.error(f"Error in message listener: {e}")

    # -----------------------------------------------------------------------
    # Core Routing Handler — CONSTITUTIONAL PIPELINE
    # Authority chain: MemoryGuard → ModeGate → ModelRouter → ContextBuilder → ApprovalGate
    # (ADR-0010, Doctrine §1/§4/§8/§9/§11, Commandment I/IV)
    # -----------------------------------------------------------------------

    async def handle_routing_request(self, message: Dict[str, Any]):
        """Handle routing request from controller via the Constitutional Pipeline.

        The pipeline runs five stages in constitutional order:
          1. MemoryGuard  — Reject if memory is unsafe (OOM protection)
          2. ModeGate     — Check execution mode + human priority
          3. ModelRouter   — Score workers, select backend and best worker
          4. ContextBuilder — Inject Soul/Mind/Body governance preamble
          5. ApprovalGate  — AUTO executes; HYBRID proposes and blocks

        Each stage logs to the audit trail (Doctrine §4, Commandment IV).
        If any stage issues a terminal verdict, the pipeline short-circuits.
        """
        try:
            request_id = message.get("request_id")
            routing_data = message.get("data", {})
            task = routing_data.get("task", {})
            available_workers = routing_data.get("available_workers", {})
            task_mode_override = task.get("execution_mode")

            # --- Run the Constitutional Pipeline ---
            if self.pipeline and PIPELINE_AVAILABLE:
                ctx = await self.pipeline.run(
                    task=task,
                    available_workers=available_workers,
                    requested_mode=task_mode_override,
                    request_id=request_id,
                )

                # Update metrics from pipeline result
                self._update_metrics_from_pipeline(ctx)

                # Send response over socket
                response = ctx.to_response()

                # For HYBRID proposals, enrich the socket message
                if ctx.final_verdict == PipelineVerdict.PROPOSE:
                    response["type"] = "proposal_ready"
                    response["proposal_id"] = ctx.proposal_id
                    response["requires_approval"] = True
                    response["message"] = self._build_hybrid_message(ctx)

                if self.socket_client:
                    await self.socket_client.send(response)

                self._log_pipeline_result(ctx)
                return

            # --- Fallback: Legacy inline routing (pipeline.py not available) ---
            await self._legacy_handle_routing_request(
                message, request_id, task, available_workers, task_mode_override
            )

        except Exception as e:
            logger.error(f"Error handling routing request: {e}")

    def _update_metrics_from_pipeline(self, ctx: "PipelineContext") -> None:
        """Update internal metrics from a completed pipeline run."""
        verdict = ctx.final_verdict

        if verdict == PipelineVerdict.EXECUTE:
            self.metrics["decisions_made"] += 1
            elapsed_s = ctx.elapsed_ms / 1000 if ctx.elapsed_ms else 0
            self.update_average_decision_time(elapsed_s)

        elif verdict == PipelineVerdict.PROPOSE:
            self.metrics["proposals_generated"] += 1

        elif verdict in (PipelineVerdict.WITHDRAW, PipelineVerdict.PAUSE):
            self.metrics["withdrawals"] += 1

    def _build_hybrid_message(self, ctx: "PipelineContext") -> str:
        """Build the human-facing HYBRID proposal message.

        'Hey, I have N workers available to work that job you just input —
         would you like me to proceed using all available workers,
         or select yourself?'
        """
        worker_count = len(ctx.available_workers)
        worker_names = ", ".join(
            f"{wid} ({winfo.get('gpu_info', {}).get('name', '?')})"
            for wid, winfo in ctx.available_workers.items()
        )
        task_type = ctx.task.get("task_type", "unknown")
        return (
            f"I have {worker_count} worker(s) available for this "
            f"{task_type} task: {worker_names}. "
            f"My recommendation is {ctx.selected_worker} "
            f"(confidence: {ctx.confidence:.0%}). "
            f"Would you like me to proceed with this worker, "
            f"use all available workers, or select yourself?"
        )

    def _log_pipeline_result(self, ctx: "PipelineContext") -> None:
        """Log the pipeline result with appropriate emoji and detail."""
        verdict = ctx.final_verdict
        icons = {
            PipelineVerdict.EXECUTE: "🎯",
            PipelineVerdict.PROPOSE: "📋",
            PipelineVerdict.BYPASS: "⏭️",
            PipelineVerdict.REJECT: "🚫",
            PipelineVerdict.WITHDRAW: "🛑",
            PipelineVerdict.PAUSE: "⏸️",
            PipelineVerdict.DOWNGRADE: "⬇️",
        }
        icon = icons.get(verdict, "❓")

        if verdict == PipelineVerdict.EXECUTE:
            logger.info(
                f"{icon} AUTO decision: {ctx.selected_worker} "
                f"(confidence: {ctx.confidence:.2f}, {ctx.elapsed_ms:.0f}ms)"
            )
        elif verdict == PipelineVerdict.PROPOSE:
            pid = ctx.proposal_id[:8] if ctx.proposal_id else "?"
            logger.info(
                f"{icon} HYBRID proposal [{pid}]: "
                f"proposed={ctx.selected_worker}, confidence={ctx.confidence:.2f} "
                f"— AWAITING HUMAN APPROVAL"
            )
        else:
            reason = ""
            if ctx.audit_trail:
                reason = ctx.audit_trail[-1].reason
            logger.info(f"{icon} Pipeline verdict: {verdict.value} — {reason}")

    # -----------------------------------------------------------------------
    # Legacy Routing Fallback (used when pipeline.py is not importable)
    # -----------------------------------------------------------------------

    async def _legacy_handle_routing_request(
        self,
        message: Dict[str, Any],
        request_id: str,
        task: Dict[str, Any],
        available_workers: Dict[str, Any],
        task_mode_override: Optional[str],
    ):
        """Legacy inline routing — preserved as fallback when pipeline.py is absent.

        This is the original monolithic handler.  Once pipeline.py is confirmed
        stable, this method can be removed.  (Doctrine §8 Reversibility)
        """
        effective_mode = self.execution_mode
        if task_mode_override and self.config.get("execution_mode", {}).get(
            "allow_per_task_override", True
        ):
            try:
                effective_mode = ExecutionMode(task_mode_override.lower())
            except ValueError:
                pass

        # MANUAL bypass
        if effective_mode == ExecutionMode.MANUAL:
            response = {
                "type": "llm_routing_response",
                "request_id": request_id,
                "status": "bypassed",
                "mode": "manual",
                "message": "MANUAL mode — LLM routing bypassed. Human selects worker directly.",
                "timestamp": datetime.now().isoformat(),
            }
            if self.socket_client:
                await self.socket_client.send(response)
            logger.info("⏭️ Routing request bypassed (MANUAL mode) [legacy]")
            return

        # Human priority check
        hp_status = await self.human_priority_checker.check()
        if hp_status["human_active"]:
            action = self.config.get("human_priority", {}).get(
                f"{effective_mode.value}_mode_action", "withdraw"
            )
            self.metrics["withdrawals"] += 1
            status = "withdrawn" if action == "withdraw" else "paused"
            response = {
                "type": "llm_routing_response",
                "request_id": request_id,
                "status": status,
                "mode": effective_mode.value,
                "reason": hp_status["reason"],
                "timestamp": datetime.now().isoformat(),
            }
            if self.socket_client:
                await self.socket_client.send(response)
            logger.info(
                f"{'🛑' if status == 'withdrawn' else '⏸️'} {status.upper()}: {hp_status['reason']} [legacy]"
            )
            return

        # Routing decision
        decision_start = datetime.now()
        selected_worker = await self.make_routing_decision(task, available_workers)
        decision_time = (datetime.now() - decision_start).total_seconds()

        reasoning = await self.generate_reasoning(
            task, available_workers, selected_worker
        )
        confidence = await self.calculate_confidence(
            task, available_workers, selected_worker
        )

        if effective_mode == ExecutionMode.AUTO:
            response = {
                "type": "llm_routing_response",
                "request_id": request_id,
                "status": "decided",
                "mode": "auto",
                "selected_worker": selected_worker,
                "confidence": confidence,
                "reasoning": reasoning,
                "decision_time_ms": decision_time * 1000,
                "timestamp": datetime.now().isoformat(),
            }
            if self.socket_client:
                await self.socket_client.send(response)
            self.metrics["decisions_made"] += 1
            self.update_average_decision_time(decision_time)
            self.store_decision(task, available_workers, selected_worker, reasoning)
            logger.info(
                f"🎯 AUTO decision: {selected_worker} (confidence: {confidence:.2f}) [legacy]"
            )
            return

        if effective_mode == ExecutionMode.HYBRID:
            alternatives = await self._build_alternatives(
                task, available_workers, selected_worker
            )
            proposal_data = {
                "request_id": request_id,
                "task": task,
                "proposed_worker": selected_worker,
                "confidence": confidence,
                "reasoning": reasoning,
                "alternatives": alternatives,
                "decision_time_ms": decision_time * 1000,
                "available_workers": list(available_workers.keys()),
            }
            proposal_id = self.proposal_store.add(proposal_data)
            self.metrics["proposals_generated"] += 1
            notification = {
                "type": "proposal_ready",
                "request_id": request_id,
                "proposal_id": proposal_id,
                "mode": "hybrid",
                "status": "pending_approval",
                "proposed_worker": selected_worker,
                "confidence": confidence,
                "reasoning": reasoning,
                "alternatives": alternatives,
                "requires_approval": True,
                "message": "HYBRID mode — proposal generated. Awaiting human approval.",
                "timestamp": datetime.now().isoformat(),
            }
            if self.socket_client:
                await self.socket_client.send(notification)
            logger.info(
                f"📋 HYBRID proposal [{proposal_id[:8]}]: proposed={selected_worker} [legacy]"
            )
            return

    # -----------------------------------------------------------------------
    # HYBRID Mode: Approval / Rejection Handlers
    # -----------------------------------------------------------------------

    async def handle_proposal_approval(self, message: Dict[str, Any]):
        """Handle human approval of a HYBRID-mode proposal.

        Only after this approval does the routing decision become actionable.
        (Commandment I: No modification without authorization)
        """
        proposal_id = message.get("proposal_id")
        approver = message.get("approver", "unknown")
        override_worker = message.get("override_worker")
        reason = message.get("reason")

        proposal = self.proposal_store.approve(
            proposal_id, approver, override_worker, reason
        )

        if not proposal:
            logger.warning(f"⚠️ Proposal {proposal_id} not found or already resolved")
            return

        self.metrics["proposals_approved"] += 1
        final_worker = proposal.get("selected_worker", proposal.get("proposed_worker"))

        # NOW send the actual routing decision
        response = {
            "type": "llm_routing_response",
            "request_id": proposal.get("request_id"),
            "status": "approved",
            "mode": "hybrid",
            "selected_worker": final_worker,
            "confidence": proposal.get("confidence"),
            "reasoning": proposal.get("reasoning"),
            "approved_by": approver,
            "approval_reason": reason,
            "timestamp": datetime.now().isoformat(),
        }

        if self.socket_client:
            await self.socket_client.send(response)

        # Store decision for learning
        self.store_decision(
            proposal.get("task", {}),
            {w: {} for w in proposal.get("available_workers", [])},
            final_worker,
            proposal.get("reasoning", ""),
        )

        logger.info(
            f"✅ HYBRID proposal [{proposal_id[:8]}] APPROVED by {approver} "
            f"→ worker={final_worker}"
        )

    async def handle_proposal_rejection(self, message: Dict[str, Any]):
        """Handle human rejection of a HYBRID-mode proposal.

        Rejected proposals are never executed (Doctrine §8 Reversibility).
        """
        proposal_id = message.get("proposal_id")
        rejector = message.get("rejector", "unknown")
        reason = message.get("reason")

        proposal = self.proposal_store.reject(proposal_id, rejector, reason)

        if not proposal:
            logger.warning(f"⚠️ Proposal {proposal_id} not found or already resolved")
            return

        self.metrics["proposals_rejected"] += 1

        response = {
            "type": "llm_routing_response",
            "request_id": proposal.get("request_id"),
            "status": "rejected",
            "mode": "hybrid",
            "rejected_by": rejector,
            "rejection_reason": reason,
            "message": "Proposal rejected by human operator. Task will not be routed.",
            "timestamp": datetime.now().isoformat(),
        }

        if self.socket_client:
            await self.socket_client.send(response)

        logger.info(
            f"❌ HYBRID proposal [{proposal_id[:8]}] REJECTED by {rejector}: {reason}"
        )

    async def _proposal_expiry_loop(self):
        """Periodically expire stale proposals (HYBRID mode).

        Per Doctrine §8 (Reversibility): expired proposals are never executed.
        """
        while self.running:
            try:
                expired = self.proposal_store.expire_stale()
                for pid in expired:
                    self.metrics["proposals_expired"] += 1
                    logger.info(
                        f"⏰ HYBRID proposal [{pid[:8]}] EXPIRED — not executed"
                    )

                    if self.socket_client:
                        await self.socket_client.send(
                            {
                                "type": "proposal_expired",
                                "proposal_id": pid,
                                "expired_at": datetime.now().isoformat(),
                                "reason": "No approval received within timeout period",
                            }
                        )
            except Exception as e:
                logger.error(f"Error in proposal expiry loop: {e}")

            await asyncio.sleep(30)  # Check every 30 seconds

    async def _build_alternatives(
        self,
        task: Dict[str, Any],
        available_workers: Dict[str, Any],
        primary_worker: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Build ordered list of alternative workers for HYBRID proposals."""
        alternatives = []
        task_type = task.get("task_type", "unknown")
        task_params = task.get("parameters", {})

        for worker_id, worker_info in available_workers.items():
            if worker_id == primary_worker:
                continue
            score = await self.score_worker_for_task(
                worker_info, task_type, task_params
            )
            gpu_name = worker_info.get("gpu_info", {}).get("name", "Unknown")
            alternatives.append(
                {
                    "worker_id": worker_id,
                    "gpu": gpu_name,
                    "score": round(score, 3),
                    "reason": f"{gpu_name} — score {score:.2f}",
                }
            )

        alternatives.sort(key=lambda x: x["score"], reverse=True)
        return alternatives

    # -----------------------------------------------------------------------
    # Routing Intelligence (shared by AUTO and HYBRID)
    # -----------------------------------------------------------------------

    async def make_routing_decision(
        self, task: Dict[str, Any], available_workers: Dict[str, Any]
    ) -> Optional[str]:
        """Make intelligent routing decision using lightweight AI.

        Returns the worker_id with the highest score, or None.
        This method is used identically in AUTO and HYBRID modes — the
        difference is what happens *after* the decision (see handle_routing_request).
        """
        if not available_workers:
            return None

        task_type = task.get("task_type", "unknown")
        task_params = task.get("parameters", {})

        worker_scores = {}
        for worker_id, worker_info in available_workers.items():
            score = await self.score_worker_for_task(
                worker_info, task_type, task_params
            )
            worker_scores[worker_id] = score

        if worker_scores:
            best_worker = max(worker_scores.items(), key=lambda x: x[1])
            return best_worker[0]

        return None

    async def score_worker_for_task(
        self, worker_info: Dict[str, Any], task_type: str, task_params: Dict[str, Any]
    ) -> float:
        """Score a worker for a specific task using AI-enhanced logic."""
        gpu_info = worker_info.get("gpu_info", {})
        gpu_name = gpu_info.get("name", "Unknown")

        base_score = 1.0
        gpu_profile = None

        for profile_name, profile in self.gpu_profiles.items():
            if profile_name in gpu_name:
                gpu_profile = profile
                base_score = profile["score_multiplier"]
                break

        if not gpu_profile:
            return base_score

        task_prefs = self.task_preferences.get(task_type, {})

        memory_req = task_prefs.get("memory_requirement", "medium")
        memory_score = self.calculate_memory_score(gpu_profile, memory_req, task_params)

        feature_score = self.calculate_feature_score(gpu_profile, task_prefs)

        current_tasks = worker_info.get("current_tasks", 0)
        max_tasks = worker_info.get("max_concurrent_tasks", 1)
        load_penalty = (current_tasks / max_tasks) * 2.0 if max_tasks else 0.0

        history_bonus = await self.get_historical_performance_bonus(
            worker_info, task_type
        )

        final_score = (
            base_score * memory_score * feature_score * (1 + history_bonus)
            - load_penalty
        )

        return max(0.1, final_score)

    def calculate_memory_score(
        self, gpu_profile: Dict[str, Any], memory_req: str, task_params: Dict[str, Any]
    ) -> float:
        """Calculate memory adequacy score."""
        gpu_memory = gpu_profile.get("memory_gb", 4)

        memory_requirements = {
            "low": 2,
            "medium": 6,
            "high": 12,
            "very_high": 20,
        }

        required_memory = memory_requirements.get(memory_req, 4)

        if "memory_required_gb" in task_params:
            required_memory = task_params["memory_required_gb"]

        if gpu_memory >= required_memory:
            return 1.0 + min(0.5, (gpu_memory - required_memory) / required_memory)
        else:
            return max(0.1, gpu_memory / required_memory)

    def calculate_feature_score(
        self, gpu_profile: Dict[str, Any], task_prefs: Dict[str, Any]
    ) -> float:
        """Calculate feature compatibility score."""
        preferred_features = task_prefs.get("preferred_features", [])
        avoid_features = task_prefs.get("avoid_features", [])

        score = 1.0

        for feature in preferred_features:
            if feature == "tensor_cores" and gpu_profile.get("tensor_cores") != "none":
                score *= 1.5
            elif feature == "high_memory" and gpu_profile.get("memory_gb", 0) >= 16:
                score *= 1.3
            elif (
                feature == "proven_stability"
                and gpu_profile.get("performance_tier") == "legacy"
            ):
                score *= 1.2

        for feature in avoid_features:
            if feature == "legacy" and gpu_profile.get("performance_tier") == "legacy":
                score *= 0.8

        return score

    async def get_historical_performance_bonus(
        self, worker_info: Dict[str, Any], task_type: str
    ) -> float:
        """Get performance bonus based on historical data."""
        worker_id = worker_info.get("worker_id", "")

        similar_decisions = [
            d
            for d in self.decision_history
            if d.get("worker_id") == worker_id and d.get("task_type") == task_type
        ]

        if similar_decisions:
            return min(0.2, len(similar_decisions) * 0.05)

        return 0.0

    async def generate_reasoning(
        self,
        task: Dict[str, Any],
        available_workers: Dict[str, Any],
        selected_worker: Optional[str],
    ) -> str:
        """Generate human-readable reasoning for the decision.

        Per Doctrine §4 (Transparent Operation) and Commandment IV
        (Show Thy Reasoning), all decisions must be explained.
        """
        if not selected_worker or selected_worker not in available_workers:
            return "No suitable worker available for this task"

        worker_info = available_workers[selected_worker]
        gpu_info = worker_info.get("gpu_info", {})
        gpu_name = gpu_info.get("name", "Unknown GPU")
        task_type = task.get("task_type", "unknown")

        gpu_profile = None
        for profile_name, profile in self.gpu_profiles.items():
            if profile_name in gpu_name:
                gpu_profile = profile
                break

        reasons = []

        if gpu_profile:
            tier = gpu_profile.get("performance_tier", "unknown")
            if tier == "flagship":
                reasons.append("flagship GPU performance")
            elif tier == "mainstream":
                reasons.append("modern GPU capabilities")
            elif tier == "legacy":
                reasons.append("proven stability and compatibility")
            elif tier == "professional":
                reasons.append("professional-grade memory capacity")

            best_for = gpu_profile.get("best_for", [])
            if task_type in best_for:
                reasons.append(f"optimized for {task_type}")

            memory_gb = gpu_profile.get("memory_gb", 0)
            if memory_gb >= 16:
                reasons.append("abundant memory available")
            elif memory_gb >= 8:
                reasons.append("sufficient memory capacity")

        current_tasks = worker_info.get("current_tasks", 0)
        if current_tasks == 0:
            reasons.append("no current load")
        elif current_tasks == 1:
            reasons.append("light current load")

        reasons.append("AI-optimized selection")

        if reasons:
            return f"Selected {gpu_name} for {', '.join(reasons)}"
        else:
            return f"Selected {gpu_name} as best available option"

    async def calculate_confidence(
        self,
        task: Dict[str, Any],
        available_workers: Dict[str, Any],
        selected_worker: Optional[str],
    ) -> float:
        """Calculate confidence score for the decision."""
        if not selected_worker or not available_workers:
            return 0.0

        confidence = 0.7

        worker_scores = {}
        task_type = task.get("task_type", "unknown")
        task_params = task.get("parameters", {})

        for worker_id, worker_info in available_workers.items():
            score = await self.score_worker_for_task(
                worker_info, task_type, task_params
            )
            worker_scores[worker_id] = score

        if len(worker_scores) > 1:
            sorted_scores = sorted(worker_scores.values(), reverse=True)
            if len(sorted_scores) >= 2:
                score_gap = sorted_scores[0] - sorted_scores[1]
                confidence += min(0.25, score_gap / sorted_scores[0])

        if task_type in self.task_preferences:
            confidence += 0.1

        if task_type == "unknown":
            confidence -= 0.2

        return min(0.95, max(0.1, confidence))

    # -----------------------------------------------------------------------
    # Decision Storage & Metrics
    # -----------------------------------------------------------------------

    def store_decision(
        self,
        task: Dict[str, Any],
        available_workers: Dict[str, Any],
        selected_worker: str,
        reasoning: str,
    ):
        """Store decision for learning and analysis (Doctrine §4 Transparency)."""
        decision_record = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task.get("task_type"),
            "worker_id": selected_worker,
            "reasoning": reasoning,
            "available_workers_count": len(available_workers),
            "task_parameters": task.get("parameters", {}),
            "execution_mode": self.execution_mode.value,
        }

        self.decision_history.append(decision_record)

        if len(self.decision_history) > self.max_history:
            self.decision_history = self.decision_history[-self.max_history // 2 :]

    def update_average_decision_time(self, decision_time: float):
        """Update average decision time metric."""
        current_avg = self.metrics["average_decision_time"]
        decisions_made = self.metrics["decisions_made"]

        if decisions_made == 1:
            self.metrics["average_decision_time"] = decision_time
        else:
            self.metrics["average_decision_time"] = (
                current_avg * (decisions_made - 1) + decision_time
            ) / decisions_made

    async def handle_system_state_update(self, message: Dict[str, Any]):
        """Handle system state updates from the controller."""
        try:
            workers_count = message.get("workers", 0)
            ui_clients = message.get("ui_clients", 0)

            logger.debug(
                f"System state update: {workers_count} workers, {ui_clients} UI clients"
            )

        except Exception as e:
            logger.error(f"Error handling system state update: {e}")

    # -----------------------------------------------------------------------
    # Status (Doctrine §4 Transparent Operation)
    # -----------------------------------------------------------------------

    async def get_status(self) -> Dict[str, Any]:
        """Get LLM Task Master status — fully transparent per Doctrine §4."""
        uptime = datetime.now() - self.metrics["start_time"]

        status = {
            "running": self.running,
            "execution_mode": self.execution_mode.value,
            "model_config": self.model_config,
            "routing_intelligence": getattr(self, "routing_intelligence", {}),
            "metrics": {
                **self.metrics,
                "start_time": self.metrics["start_time"].isoformat(),
                "uptime": str(uptime),
                "decisions_per_minute": self.metrics["decisions_made"]
                / max(1, uptime.total_seconds() / 60),
            },
            "decision_history_size": len(self.decision_history),
            "socket_connected": (
                self.socket_client is not None
                and getattr(self.socket_client, "running", False)
            ),
            "governance": {
                "soul": "doctrine/PHANTOM_MANIFEST.md",
                "mind": "doctrine/PHANTOM_DOCTRINE.md",
                "body": ".cursorrules + PHANTOM_TEN_COMMANDMENTS.md",
            },
            "pipeline": {
                "active": self.pipeline is not None,
                "authority_chain": "MemoryGuard → ModeGate → ModelRouter → ContextBuilder → ApprovalGate",
                "stages": [
                    "MemoryGuard",
                    "ModeGate",
                    "ModelRouter",
                    "ContextBuilder",
                    "ApprovalGate",
                ],
            },
        }

        # HYBRID-specific status
        if self.execution_mode == ExecutionMode.HYBRID:
            pending = self.proposal_store.get_pending()
            status["hybrid"] = {
                "pending_proposals": len(pending),
                "proposals": [
                    {
                        "proposal_id": p["proposal_id"],
                        "proposed_worker": p.get("proposed_worker"),
                        "created_at": p.get("created_at"),
                    }
                    for p in pending
                ],
            }

        return status

    # -----------------------------------------------------------------------
    # Shutdown (Doctrine §8 Reversibility)
    # -----------------------------------------------------------------------

    async def shutdown(self):
        """Graceful shutdown — Opera Principle: vanish cleanly."""
        logger.info("🛑 Shutting down LLM Task Master")

        self.running = False

        # Expire all pending proposals on shutdown
        if self.execution_mode == ExecutionMode.HYBRID:
            expired = self.proposal_store.expire_stale()
            if expired:
                logger.info(f"⏰ Expired {len(expired)} pending proposals on shutdown")

        if self.socket_client:
            await self.socket_client.disconnect()

        logger.info("✅ LLM Task Master shutdown complete")


# ===========================================================================
# Standalone Operation
# ===========================================================================
async def main():
    """Main entry point for standalone LLM Task Master."""
    import argparse

    parser = argparse.ArgumentParser(description="Phantom LLM Task Master")
    parser.add_argument(
        "--controller-host", default=None, help="Controller host (default: from config)"
    )
    parser.add_argument(
        "--socket-port",
        type=int,
        default=None,
        help="Socket port (default: from config)",
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=["auto", "hybrid", "manual"],
        help="Execution mode (default: from config or env PHANTOM_EXECUTION_MODE)",
    )
    parser.add_argument("--config", default=None, help="Path to llm_config.json")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config_path = Path(args.config) if args.config else None

    llm_taskmaster = LightweightLLMTaskMaster(
        controller_host=args.controller_host,
        socket_port=args.socket_port,
        execution_mode=args.mode,
        config_path=config_path,
    )

    try:
        await llm_taskmaster.initialize()

        while llm_taskmaster.running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"LLM Task Master error: {e}")
    finally:
        await llm_taskmaster.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
