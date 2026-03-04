"""
Phantom LLM Task Master — Constitutional Pipeline
===================================================

Five discrete pipeline stages, each a constitutional office with a single
responsibility.  Every stage is auditable, independently overridable, and
composable through a shared PipelineContext.

Authority Chain (ADR-0010):
  MemoryGuard → Mode Gate → Model Router → Context Builder → Approval Gate

Governance Alignment (Soul–Mind–Body):
  Soul  → doctrine/PHANTOM_MANIFEST.md   (Identity Contract)
  Mind  → doctrine/PHANTOM_DOCTRINE.md   (11 Principles)
  Body  → .cursorrules + TEN_COMMANDMENTS (Operational Rules)

Design Principles:
  - Doctrine §9  (Modularity): Each stage is a swappable module.
  - Doctrine §4  (Transparent Operation): Every decision is logged.
  - Doctrine §8  (Reversibility): Every action can be undone.
  - Doctrine §10 (Minimalism): Each stage does one thing well.
  - Commandment IV (Show Thy Reasoning): Audit trail on every step.
"""

import asyncio
import logging
import platform
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared Enumerations
# ---------------------------------------------------------------------------


class ExecutionMode(str, Enum):
    """Phantom execution modes — human-selectable, always changeable (§8)."""

    AUTO = "auto"
    HYBRID = "hybrid"
    MANUAL = "manual"


class PipelineVerdict(str, Enum):
    """Outcome of any pipeline stage."""

    PROCEED = "proceed"  # Continue to next stage
    BYPASS = "bypass"  # Skip remaining stages (MANUAL mode)
    PROPOSE = "propose"  # Generate proposal, await human (HYBRID)
    EXECUTE = "execute"  # Execute immediately (AUTO)
    REJECT = "reject"  # Hard stop — unsafe or forbidden
    WITHDRAW = "withdraw"  # Human priority withdrawal (§1)
    PAUSE = "pause"  # Temporary hold (HYBRID + human active)
    DOWNGRADE = "downgrade"  # Memory pressure — use smaller model


class LLMBackend(str, Enum):
    """Supported LLM inference backends (ADR-0010)."""

    LLAMA_CPP = "llama.cpp"  # Primary — native GGUF, lowest overhead
    OLLAMA = "ollama"  # Fallback — easy local inference
    VLLM = "vllm"  # High-throughput serving
    RULE_ENGINE = "rule_engine"  # Scaffold — no real LLM, rule-based routing


# ---------------------------------------------------------------------------
# Pipeline Context — flows through every stage
# ---------------------------------------------------------------------------


@dataclass
class AuditEntry:
    """Single audit trail entry — one per pipeline stage decision."""

    stage: str
    verdict: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    """Shared state that flows through all five pipeline stages.

    Every stage reads from and writes to this context.  The audit_trail
    list provides a complete, traceable log of every decision made
    (Doctrine §4 Transparent Operation, Commandment IV Show Thy Reasoning).
    """

    # --- Request identity ---
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # --- Input (set by caller) ---
    task: Dict[str, Any] = field(default_factory=dict)
    available_workers: Dict[str, Any] = field(default_factory=dict)
    requested_mode: Optional[str] = None  # per-task override

    # --- MemoryGuard output ---
    memory_safe: bool = False
    memory_verdict: str = ""
    system_ram_mb: float = 0.0
    system_ram_available_mb: float = 0.0
    gpu_vram_mb: float = 0.0
    gpu_vram_available_mb: float = 0.0
    swap_used_mb: float = 0.0
    model_footprint_mb: float = 0.0

    # --- ModeGate output ---
    effective_mode: Optional[ExecutionMode] = None
    human_active: bool = False
    human_priority_reason: str = ""

    # --- ModelRouter output ---
    selected_backend: Optional[LLMBackend] = None
    selected_model: str = ""
    selected_worker: Optional[str] = None
    worker_scores: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    routing_reasoning: str = ""

    # --- ContextBuilder output ---
    governance_preamble: str = ""
    system_prompt: str = ""
    user_prompt: str = ""

    # --- ApprovalGate output ---
    proposal_id: Optional[str] = None
    final_verdict: PipelineVerdict = PipelineVerdict.REJECT
    approval_status: str = "pending"

    # --- Audit trail (Doctrine §4, Commandment IV) ---
    audit_trail: List[AuditEntry] = field(default_factory=list)

    # --- Timing ---
    pipeline_start: Optional[datetime] = None
    pipeline_end: Optional[datetime] = None

    def audit(self, stage: str, verdict: str, reason: str, **details: Any) -> None:
        """Append an audit entry.  Every stage MUST call this."""
        self.audit_trail.append(
            AuditEntry(stage=stage, verdict=verdict, reason=reason, details=details)
        )
        logger.info(f"[AUDIT] {stage}: {verdict} — {reason}")

    @property
    def elapsed_ms(self) -> float:
        if self.pipeline_start and self.pipeline_end:
            return (self.pipeline_end - self.pipeline_start).total_seconds() * 1000
        return 0.0

    def to_response(self) -> Dict[str, Any]:
        """Serialize context into a socket-ready response dict."""
        return {
            "type": "llm_routing_response",
            "request_id": self.request_id,
            "status": self.final_verdict.value,
            "mode": self.effective_mode.value if self.effective_mode else "unknown",
            "selected_worker": self.selected_worker,
            "selected_backend": (
                self.selected_backend.value if self.selected_backend else None
            ),
            "confidence": self.confidence,
            "reasoning": self.routing_reasoning,
            "proposal_id": self.proposal_id,
            "memory_safe": self.memory_safe,
            "elapsed_ms": self.elapsed_ms,
            "audit_trail": [
                {
                    "stage": e.stage,
                    "verdict": e.verdict,
                    "reason": e.reason,
                    "timestamp": e.timestamp,
                    "details": e.details,
                }
                for e in self.audit_trail
            ],
            "timestamp": datetime.now().isoformat(),
        }


# ===========================================================================
# Stage 1: MEMORY GUARD
# Constitutional pre-check — no pipeline stage may proceed if memory is unsafe.
# Authority: Memory Guard → Mode Gate → Model Router → Context Builder → Approval Gate
# ===========================================================================


class MemoryGuard:
    """First constitutional authority — protects the node from OOM.

    Before any routing, model loading, or prompt construction may begin,
    MemoryGuard verifies system RAM, GPU VRAM, swap pressure, and the
    model's declared footprint.

    If memory is unsafe or borderline:
      - Reject the request, OR
      - Downgrade to a smaller model, OR
      - Force HYBRID or MANUAL mode, OR
      - Return a proposal instead of executing.

    Never proceeds silently.  Never truncates silently.
    Always logs the memory decision in the audit trail.

    Governance: Doctrine §1 (Human Priority — protect the node),
                Doctrine §4 (Transparent Operation — log everything),
                Doctrine §10 (Minimalism — smallest viable solution).
    """

    # Safe thresholds (percentage of total)
    RAM_SAFE_PERCENT = 30  # Must have ≥30% RAM free
    VRAM_SAFE_PERCENT = 25  # Must have ≥25% VRAM free
    SWAP_DANGER_PERCENT = 50  # Swap usage >50% is dangerous
    # Borderline: between safe and dangerous
    RAM_BORDERLINE_PERCENT = 20
    VRAM_BORDERLINE_PERCENT = 15

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        res = config.get("resource_limits", {})
        self.max_memory_mb = res.get("max_memory_mb", 2048)
        self.max_vram_mb = res.get("max_vram_mb", 2048)
        model_cfg = config.get("model", {})
        # Declared footprint from config — overrideable by real model metadata
        self.model_footprint_mb = self._estimate_model_footprint(model_cfg)

    @staticmethod
    def _estimate_model_footprint(model_cfg: Dict[str, Any]) -> float:
        """Estimate model memory footprint from config declarations.

        For GGUF Q4_K_M quants, rule of thumb:
          footprint ≈ model_params_B × 0.6 GB  (for 4-bit quant)
        Phi-3.5 Mini (3.8B params, Q4_K_M) ≈ ~2.3 GB ≈ 2350 MB.
        """
        # If explicitly declared, use that
        declared = model_cfg.get("footprint_mb")
        if declared:
            return float(declared)

        # Heuristic based on model name
        model_name = model_cfg.get("default_model", "phi-3.5-mini").lower()
        quant = model_cfg.get("default_quant", "Q4_K_M").upper()

        # Known model sizes (approximate, conservative)
        known_models = {
            "phi-3.5-mini": 2400,  # 3.8B params, Q4_K_M ≈ 2.3GB
            "phi-3-mini": 2200,  # 3.8B params
            "llama-3.2-1b": 800,  # 1B params
            "llama-3.2-3b": 2000,  # 3B params
            "mistral-7b": 4500,  # 7B params
            "gemma-2b": 1500,  # 2B params
        }

        for name, footprint in known_models.items():
            if name in model_name:
                return float(footprint)

        # Unknown model — conservative 2GB estimate
        return 2048.0

    def _read_system_memory(self) -> Dict[str, float]:
        """Read current system RAM and swap usage.

        Uses psutil if available; falls back to conservative estimates.
        """
        try:
            import psutil

            vm = psutil.virtual_memory()
            swap = psutil.swap_memory()
            return {
                "ram_total_mb": vm.total / (1024 * 1024),
                "ram_available_mb": vm.available / (1024 * 1024),
                "ram_percent_used": vm.percent,
                "swap_total_mb": swap.total / (1024 * 1024),
                "swap_used_mb": swap.used / (1024 * 1024),
                "swap_percent_used": swap.percent,
            }
        except ImportError:
            logger.warning("psutil not available — using conservative memory estimates")
            return {
                "ram_total_mb": 8192.0,
                "ram_available_mb": 4096.0,
                "ram_percent_used": 50.0,
                "swap_total_mb": 4096.0,
                "swap_used_mb": 0.0,
                "swap_percent_used": 0.0,
            }

    def _read_gpu_vram(self) -> Dict[str, float]:
        """Read current GPU VRAM usage.

        Tries nvidia-smi (NVIDIA), then ROCm (AMD), then falls back.
        Hardware-agnostic: works with whatever GPU is discovered.
        """
        # Try NVIDIA (pynvml/nvidia-smi)
        try:
            import subprocess

            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total,memory.used,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    total = float(parts[0].strip())
                    used = float(parts[1].strip())
                    free = float(parts[2].strip())
                    return {
                        "vram_total_mb": total,
                        "vram_available_mb": free,
                        "vram_used_mb": used,
                        "vram_percent_used": (used / total * 100) if total > 0 else 0,
                    }
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

        # Try AMD ROCm
        try:
            import subprocess

            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram", "--csv"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse ROCm CSV output
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    # Simplified parsing — real impl would be more robust
                    return {
                        "vram_total_mb": 4096.0,
                        "vram_available_mb": 2048.0,
                        "vram_used_mb": 2048.0,
                        "vram_percent_used": 50.0,
                    }
        except (FileNotFoundError, Exception):
            pass

        # Fallback — conservative estimates based on config target
        target_vram_gb = self.config.get("resource_limits", {}).get("target_vram_gb", 4)
        total_mb = target_vram_gb * 1024
        return {
            "vram_total_mb": total_mb,
            "vram_available_mb": total_mb * 0.7,  # Assume 30% used
            "vram_used_mb": total_mb * 0.3,
            "vram_percent_used": 30.0,
        }

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        """Run the memory guard pre-check.

        Populates ctx with memory readings and sets memory_safe.
        If unsafe: sets final_verdict to REJECT or DOWNGRADE.
        If borderline: forces HYBRID mode (no silent AUTO execution).
        """
        ram = self._read_system_memory()
        vram = self._read_gpu_vram()

        ctx.system_ram_mb = ram["ram_total_mb"]
        ctx.system_ram_available_mb = ram["ram_available_mb"]
        ctx.gpu_vram_mb = vram["vram_total_mb"]
        ctx.gpu_vram_available_mb = vram["vram_available_mb"]
        ctx.swap_used_mb = ram["swap_used_mb"]
        ctx.model_footprint_mb = self.model_footprint_mb

        ram_free_pct = (
            (ram["ram_available_mb"] / ram["ram_total_mb"] * 100)
            if ram["ram_total_mb"] > 0
            else 0
        )
        vram_free_pct = (
            (vram["vram_available_mb"] / vram["vram_total_mb"] * 100)
            if vram["vram_total_mb"] > 0
            else 0
        )
        swap_pct = ram["swap_percent_used"]

        # Check 1: Can the model even fit in available VRAM?
        if self.model_footprint_mb > vram["vram_available_mb"]:
            ctx.memory_safe = False
            ctx.memory_verdict = "reject_insufficient_vram"
            ctx.final_verdict = PipelineVerdict.REJECT
            ctx.audit(
                "MemoryGuard",
                "REJECT",
                f"Model footprint ({self.model_footprint_mb:.0f}MB) exceeds "
                f"available VRAM ({vram['vram_available_mb']:.0f}MB). "
                f"Cannot proceed — OOM risk.",
                ram_free_pct=ram_free_pct,
                vram_free_pct=vram_free_pct,
                model_footprint_mb=self.model_footprint_mb,
            )
            return ctx

        # Check 2: RAM critically low
        if ram_free_pct < self.RAM_BORDERLINE_PERCENT:
            ctx.memory_safe = False
            ctx.memory_verdict = "reject_ram_critical"
            ctx.final_verdict = PipelineVerdict.REJECT
            ctx.audit(
                "MemoryGuard",
                "REJECT",
                f"System RAM critically low ({ram_free_pct:.1f}% free, "
                f"threshold {self.RAM_BORDERLINE_PERCENT}%). "
                f"Node stability at risk.",
                ram_available_mb=ram["ram_available_mb"],
            )
            return ctx

        # Check 3: Swap thrashing
        if swap_pct > self.SWAP_DANGER_PERCENT:
            ctx.memory_safe = False
            ctx.memory_verdict = "reject_swap_pressure"
            ctx.final_verdict = PipelineVerdict.REJECT
            ctx.audit(
                "MemoryGuard",
                "REJECT",
                f"Swap usage dangerously high ({swap_pct:.1f}%, "
                f"threshold {self.SWAP_DANGER_PERCENT}%). "
                f"System is thrashing.",
                swap_used_mb=ram["swap_used_mb"],
            )
            return ctx

        # Check 4: VRAM borderline — model fits but tight
        if vram_free_pct < self.VRAM_SAFE_PERCENT:
            # Not an outright reject, but force HYBRID (no silent AUTO)
            ctx.memory_safe = True  # Can technically proceed
            ctx.memory_verdict = "borderline_force_hybrid"
            ctx.audit(
                "MemoryGuard",
                "DOWNGRADE",
                f"VRAM borderline ({vram_free_pct:.1f}% free). "
                f"Model fits but margin is thin. "
                f"Forcing HYBRID mode — no silent AUTO execution.",
                vram_available_mb=vram["vram_available_mb"],
                model_footprint_mb=self.model_footprint_mb,
            )
            # ModeGate will read this and cap at HYBRID
            return ctx

        # Check 5: RAM borderline — similar treatment
        if ram_free_pct < self.RAM_SAFE_PERCENT:
            ctx.memory_safe = True
            ctx.memory_verdict = "borderline_ram"
            ctx.audit(
                "MemoryGuard",
                "PROCEED_WITH_CAUTION",
                f"RAM somewhat low ({ram_free_pct:.1f}% free). "
                f"Proceeding but flagged for monitoring.",
                ram_available_mb=ram["ram_available_mb"],
            )
            return ctx

        # All clear
        ctx.memory_safe = True
        ctx.memory_verdict = "safe"
        ctx.audit(
            "MemoryGuard",
            "SAFE",
            f"Memory check passed. RAM {ram_free_pct:.1f}% free, "
            f"VRAM {vram_free_pct:.1f}% free, "
            f"model footprint {self.model_footprint_mb:.0f}MB. "
            f"Pipeline may proceed.",
            ram_free_pct=ram_free_pct,
            vram_free_pct=vram_free_pct,
            swap_pct=swap_pct,
            model_footprint_mb=self.model_footprint_mb,
        )
        return ctx


# ===========================================================================
# Stage 2: MODE GATE
# First authority — decides whether routing is even allowed.
# ===========================================================================


class ModeGate:
    """Second constitutional authority — enforces execution mode boundaries.

    MANUAL → Bypass the entire pipeline. Human routes directly.
    AUTO   → Proceed through all remaining stages.
    HYBRID → Proceed through stages, but ApprovalGate will block for human.

    Also enforces Human Priority (Doctrine §1, Opera Principle §11):
    if the human is active, AUTO withdraws and HYBRID pauses.

    MemoryGuard borderline verdicts can force HYBRID — ModeGate honors that.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        system_mode: ExecutionMode,
        human_priority_checker=None,
    ):
        self.config = config
        self.system_mode = system_mode
        self.human_priority_checker = human_priority_checker
        self.allow_per_task_override = config.get("execution_mode", {}).get(
            "allow_per_task_override", True
        )

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        """Determine effective mode and gate accordingly."""

        # Resolve effective mode: per-task override → system mode
        effective_mode = self.system_mode
        if ctx.requested_mode and self.allow_per_task_override:
            try:
                effective_mode = ExecutionMode(ctx.requested_mode.lower())
            except ValueError:
                ctx.audit(
                    "ModeGate",
                    "WARN",
                    f"Invalid per-task mode '{ctx.requested_mode}' — "
                    f"falling back to system mode {self.system_mode.value}",
                )

        # MemoryGuard borderline → cap at HYBRID (never allow silent AUTO)
        if ctx.memory_verdict == "borderline_force_hybrid":
            if effective_mode == ExecutionMode.AUTO:
                effective_mode = ExecutionMode.HYBRID
                ctx.audit(
                    "ModeGate",
                    "DOWNGRADE",
                    "MemoryGuard flagged borderline VRAM. "
                    "AUTO downgraded to HYBRID — no silent execution under memory pressure.",
                )

        ctx.effective_mode = effective_mode

        # ----- MANUAL: bypass entire pipeline -----
        if effective_mode == ExecutionMode.MANUAL:
            ctx.final_verdict = PipelineVerdict.BYPASS
            ctx.audit(
                "ModeGate",
                "BYPASS",
                "MANUAL mode — LLM routing bypassed. "
                "Human selects worker directly. (Commandment I)",
            )
            return ctx

        # ----- Human Priority Check (Doctrine §1) -----
        if self.human_priority_checker:
            hp_status = await self.human_priority_checker.check()
            ctx.human_active = hp_status.get("human_active", False)
            ctx.human_priority_reason = hp_status.get("reason", "")

            if ctx.human_active:
                hp_cfg = self.config.get("human_priority", {})

                if effective_mode == ExecutionMode.AUTO:
                    action = hp_cfg.get("auto_mode_action", "withdraw")
                    if action == "withdraw":
                        ctx.final_verdict = PipelineVerdict.WITHDRAW
                        ctx.audit(
                            "ModeGate",
                            "WITHDRAW",
                            f"Human activity detected: {ctx.human_priority_reason}. "
                            f"AUTO mode withdrawing. (Doctrine §1 Human Priority, "
                            f"Opera Principle §11)",
                        )
                        return ctx

                elif effective_mode == ExecutionMode.HYBRID:
                    action = hp_cfg.get("hybrid_mode_action", "pause")
                    if action == "pause":
                        ctx.final_verdict = PipelineVerdict.PAUSE
                        ctx.audit(
                            "ModeGate",
                            "PAUSE",
                            f"Human activity detected: {ctx.human_priority_reason}. "
                            f"HYBRID mode paused — proposal deferred. (Doctrine §1)",
                        )
                        return ctx

        # Mode is valid and human is not blocking — proceed
        ctx.audit(
            "ModeGate",
            "PROCEED",
            f"Mode={effective_mode.value}, human_active={ctx.human_active}. "
            f"Pipeline may proceed to ModelRouter.",
        )
        return ctx


# ===========================================================================
# Stage 3: MODEL ROUTER
# Second authority — selects backend and worker based on capability scoring.
# ===========================================================================


class ModelRouter:
    """Third constitutional authority — selects the LLM backend and target worker.

    Routing is hardware-agnostic: workers report their GPU capabilities via
    auto-discovery during installation. The router scores workers against
    the task requirements and selects the best fit.

    Backend selection (ADR-0010):
      - llama.cpp  → Primary for GGUF models, lowest overhead
      - ollama     → Fallback for easy local inference
      - vllm       → High-throughput serving (multi-worker)
      - rule_engine → Scaffold when no real LLM is loaded

    Governance: Doctrine §4 (Transparent Operation — log all scoring),
                Doctrine §9 (Modularity — swappable backends),
                Doctrine §6 (Consistent Behavior — same logic everywhere).
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.gpu_profiles = config.get("gpu_profiles", {})
        self.task_preferences = config.get("task_preferences", {})
        self.confidence_threshold = config.get("routing", {}).get(
            "confidence_threshold", 0.5
        )
        self.decision_history: List[Dict[str, Any]] = []
        self.max_history = config.get("routing", {}).get("max_decision_history", 100)

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        """Score workers, select backend, pick the best worker."""

        if ctx.final_verdict in (
            PipelineVerdict.REJECT,
            PipelineVerdict.BYPASS,
            PipelineVerdict.WITHDRAW,
            PipelineVerdict.PAUSE,
        ):
            return ctx  # Pipeline already terminated by earlier stage

        if not ctx.available_workers:
            ctx.final_verdict = PipelineVerdict.REJECT
            ctx.audit(
                "ModelRouter", "REJECT", "No workers available. Cannot route task."
            )
            return ctx

        task_type = ctx.task.get("task_type", "unknown")
        task_params = ctx.task.get("parameters", {})

        # Score every available worker
        for worker_id, worker_info in ctx.available_workers.items():
            score = self._score_worker(worker_info, task_type, task_params)
            ctx.worker_scores[worker_id] = score

        # Select best worker
        if ctx.worker_scores:
            best_id = max(ctx.worker_scores, key=ctx.worker_scores.get)
            ctx.selected_worker = best_id
        else:
            ctx.final_verdict = PipelineVerdict.REJECT
            ctx.audit("ModelRouter", "REJECT", "Worker scoring produced no results.")
            return ctx

        # Select backend based on model config
        ctx.selected_backend = self._select_backend()
        ctx.selected_model = self.config.get("model", {}).get(
            "default_model", "phi-3.5-mini"
        )

        # Calculate confidence
        ctx.confidence = self._calculate_confidence(
            ctx.worker_scores, ctx.selected_worker, task_type
        )

        # Generate human-readable reasoning (Commandment IV)
        ctx.routing_reasoning = self._generate_reasoning(
            ctx.task, ctx.available_workers, ctx.selected_worker, ctx.worker_scores
        )

        ctx.audit(
            "ModelRouter",
            "ROUTED",
            f"Selected worker={ctx.selected_worker}, "
            f"backend={ctx.selected_backend.value}, "
            f"confidence={ctx.confidence:.2f}. "
            f"Scores: {ctx.worker_scores}",
            selected_worker=ctx.selected_worker,
            confidence=ctx.confidence,
            backend=ctx.selected_backend.value,
        )

        return ctx

    def _score_worker(
        self, worker_info: Dict[str, Any], task_type: str, task_params: Dict[str, Any]
    ) -> float:
        """Score a worker for a specific task using capability matching."""
        gpu_info = worker_info.get("gpu_info", {})
        gpu_name = gpu_info.get("name", "Unknown")

        base_score = 1.0
        gpu_profile = None

        for profile_name, profile in self.gpu_profiles.items():
            if profile_name.startswith("_"):
                continue  # Skip _comment, _example
            if profile_name in gpu_name:
                gpu_profile = profile
                base_score = profile.get("score_multiplier", 1.0)
                break

        if not gpu_profile:
            # Unknown GPU — fair base score, no penalty
            return max(0.1, base_score)

        # Task preference matching
        task_prefs = self.task_preferences.get(task_type, {})

        # Memory adequacy
        memory_score = self._memory_score(gpu_profile, task_prefs, task_params)

        # Feature compatibility
        feature_score = self._feature_score(gpu_profile, task_prefs)

        # Load penalty
        current_tasks = worker_info.get("current_tasks", 0)
        max_tasks = worker_info.get("max_concurrent_tasks", 1)
        load_penalty = (current_tasks / max_tasks) * 2.0 if max_tasks > 0 else 0.0

        # Historical bonus
        history_bonus = self._history_bonus(worker_info, task_type)

        final_score = (
            base_score * memory_score * feature_score * (1 + history_bonus)
            - load_penalty
        )
        return max(0.1, final_score)

    def _memory_score(
        self,
        gpu_profile: Dict[str, Any],
        task_prefs: Dict[str, Any],
        task_params: Dict[str, Any],
    ) -> float:
        """Score memory adequacy."""
        gpu_memory = gpu_profile.get("memory_gb", 4)
        memory_reqs = {"low": 2, "medium": 6, "high": 12, "very_high": 20}
        required = memory_reqs.get(task_prefs.get("memory_requirement", "medium"), 4)
        if "memory_required_gb" in task_params:
            required = task_params["memory_required_gb"]
        if gpu_memory >= required:
            return 1.0 + min(0.5, (gpu_memory - required) / required)
        return max(0.1, gpu_memory / required)

    def _feature_score(
        self, gpu_profile: Dict[str, Any], task_prefs: Dict[str, Any]
    ) -> float:
        """Score feature compatibility."""
        score = 1.0
        for feat in task_prefs.get("preferred_features", []):
            if feat == "tensor_cores" and gpu_profile.get("tensor_cores") not in (
                "none",
                None,
            ):
                score *= 1.5
            elif feat == "high_memory" and gpu_profile.get("memory_gb", 0) >= 16:
                score *= 1.3
            elif (
                feat == "proven_stability"
                and gpu_profile.get("performance_tier") == "legacy"
            ):
                score *= 1.2
        for feat in task_prefs.get("avoid_features", []):
            if feat == "legacy" and gpu_profile.get("performance_tier") == "legacy":
                score *= 0.8
        return score

    def _history_bonus(self, worker_info: Dict[str, Any], task_type: str) -> float:
        """Bonus from historical performance on similar tasks."""
        worker_id = worker_info.get("worker_id", "")
        similar = [
            d
            for d in self.decision_history
            if d.get("worker_id") == worker_id and d.get("task_type") == task_type
        ]
        return min(0.2, len(similar) * 0.05) if similar else 0.0

    def _select_backend(self) -> LLMBackend:
        """Select the LLM inference backend based on configuration.

        ADR-0010 priority: llama.cpp (native GGUF) → ollama → vllm → rule_engine.
        """
        model_cfg = self.config.get("model", {})
        model_type = model_cfg.get("model_type", "rule_based_with_learning")
        model_format = model_cfg.get("default_format", "GGUF").upper()

        # If still on rule-based scaffold, use rule engine
        if "rule_based" in model_type:
            return LLMBackend.RULE_ENGINE

        # GGUF models → llama.cpp
        if model_format == "GGUF":
            return LLMBackend.LLAMA_CPP

        # Fallback priority
        return LLMBackend.OLLAMA

    def _calculate_confidence(
        self, scores: Dict[str, float], selected: str, task_type: str
    ) -> float:
        """Calculate confidence in the routing decision."""
        confidence = 0.7

        if len(scores) > 1:
            sorted_vals = sorted(scores.values(), reverse=True)
            if len(sorted_vals) >= 2 and sorted_vals[0] > 0:
                gap = sorted_vals[0] - sorted_vals[1]
                confidence += min(0.25, gap / sorted_vals[0])

        if task_type in self.task_preferences:
            confidence += 0.1
        if task_type == "unknown":
            confidence -= 0.2

        return min(0.95, max(0.1, confidence))

    def _generate_reasoning(
        self,
        task: Dict[str, Any],
        workers: Dict[str, Any],
        selected: str,
        scores: Dict[str, float],
    ) -> str:
        """Generate human-readable reasoning (Commandment IV: Show Thy Reasoning)."""
        if not selected or selected not in workers:
            return "No suitable worker available for this task."

        worker_info = workers[selected]
        gpu_name = worker_info.get("gpu_info", {}).get("name", "Unknown GPU")
        task_type = task.get("task_type", "unknown")
        score = scores.get(selected, 0)

        reasons = []

        # Find GPU profile for reasoning
        for profile_name, profile in self.gpu_profiles.items():
            if profile_name.startswith("_"):
                continue
            if profile_name in gpu_name:
                tier = profile.get("performance_tier", "unknown")
                tier_labels = {
                    "flagship": "flagship GPU performance",
                    "mainstream": "modern GPU capabilities",
                    "legacy": "proven stability and compatibility",
                    "professional": "professional-grade memory capacity",
                }
                reasons.append(tier_labels.get(tier, f"{tier} tier"))
                if task_type in profile.get("best_for", []):
                    reasons.append(f"optimized for {task_type}")
                mem_gb = profile.get("memory_gb", 0)
                if mem_gb >= 16:
                    reasons.append("abundant memory available")
                elif mem_gb >= 8:
                    reasons.append("sufficient memory capacity")
                break

        load = worker_info.get("current_tasks", 0)
        if load == 0:
            reasons.append("no current load")
        elif load == 1:
            reasons.append("light current load")

        total_workers = len(workers)
        reasons.append(f"scored {score:.2f} across {total_workers} candidate(s)")

        return (
            f"Selected {gpu_name}: {', '.join(reasons)}"
            if reasons
            else f"Selected {gpu_name} as best available option"
        )

    def store_decision(
        self, task: Dict[str, Any], selected_worker: str, reasoning: str
    ) -> None:
        """Store decision for historical learning (Doctrine §4)."""
        self.decision_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "task_type": task.get("task_type"),
                "worker_id": selected_worker,
                "reasoning": reasoning,
            }
        )
        if len(self.decision_history) > self.max_history:
            self.decision_history = self.decision_history[-self.max_history // 2 :]


# ===========================================================================
# Stage 4: CONTEXT BUILDER
# Third authority — shapes the prompt and injects doctrine governance.
# ===========================================================================


class ContextBuilder:
    """Fourth constitutional authority — constructs the governed LLM prompt.

    Injects the Soul–Mind–Body governance preamble into every LLM
    interaction.  The preamble is immutable at runtime (per ADR-0010).

    The governance preamble ensures the LLM operates within Phantom's
    constitutional framework even at the inference level.

    Governance: Doctrine §4 (Transparent Operation — prompt is auditable),
                Doctrine §7 (Evolution Without Drift — preamble is fixed),
                Doctrine §9 (Modularity — prompt assembly is a separate concern).
    """

    # Governance preamble — derived from the three governance documents.
    # This is the constitutional oath injected into every LLM context.
    # It is immutable at runtime.  Changes require a governance review.
    GOVERNANCE_PREAMBLE = """You are the Phantom LLM Task Master — a sovereign, \
human-first routing intelligence operating within the Phantom Intelligence Fabric.

CONSTITUTIONAL AUTHORITY (Soul — PHANTOM_MANIFEST.md):
- You are a presence that appears when invited and withdraws when the human steps forward.
- Sovereignty: Every controller is its own domain.
- Humility: You yield instantly to human activity.
- Authenticity: All decisions are signed and verifiable.
- Transparency: No hidden state or silent calls.

GOVERNING PRINCIPLES (Mind — PHANTOM_DOCTRINE.md):
- §1 Human Priority: Yield immediately when the human is active.
- §4 Transparent Operation: Reveal what you are doing and why.
- §8 Reversibility: No irreversible action without explicit human authorization.
- §9 Modularity: Components are swappable and independently functional.
- §10 Minimalism: Simplicity is sovereign. Smallest viable solution.
- §11 Opera Principle: Powerful but quiet. Orchestrate when invited, vanish when the human takes the stage.

OPERATIONAL RULES (Body — .cursorrules + Ten Commandments):
- Commandment I: No execution without human authorization (HYBRID mode).
- Commandment IV: Show your reasoning — all decisions must be explained.
- Commandment VIII: Every change must be reversible.
- Commandment IX: The human architect's decision is final.

You must route tasks to the best available worker based on GPU capabilities, \
task requirements, current load, and historical performance. You must explain \
every routing decision with explicit reasoning."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.context_length = config.get("model", {}).get("context_length", 1024)

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        """Build the governed LLM context/prompt."""

        if ctx.final_verdict in (
            PipelineVerdict.REJECT,
            PipelineVerdict.BYPASS,
            PipelineVerdict.WITHDRAW,
            PipelineVerdict.PAUSE,
        ):
            return ctx  # Pipeline already terminated

        ctx.governance_preamble = self.GOVERNANCE_PREAMBLE

        # Build system prompt: governance + task context
        ctx.system_prompt = self.GOVERNANCE_PREAMBLE

        # Build user prompt from task details
        task_type = ctx.task.get("task_type", "unknown")
        task_desc = ctx.task.get("description", "")
        task_params = ctx.task.get("parameters", {})

        worker_summary = []
        for wid, winfo in ctx.available_workers.items():
            gpu = winfo.get("gpu_info", {}).get("name", "Unknown")
            load = winfo.get("current_tasks", 0)
            score = ctx.worker_scores.get(wid, 0)
            worker_summary.append(
                f"  - {wid}: GPU={gpu}, load={load}, score={score:.2f}"
            )

        workers_text = "\n".join(worker_summary) if worker_summary else "  (none)"

        ctx.user_prompt = (
            f"Route the following task to the best available worker.\n\n"
            f"Task Type: {task_type}\n"
            f"Description: {task_desc}\n"
            f"Parameters: {task_params}\n\n"
            f"Available Workers:\n{workers_text}\n\n"
            f"Execution Mode: {ctx.effective_mode.value if ctx.effective_mode else 'unknown'}\n"
            f"Memory Safe: {ctx.memory_safe}\n\n"
            f"Provide your routing decision with explicit reasoning."
        )

        # Validate prompt size against context length
        total_tokens_est = self._estimate_tokens(ctx.system_prompt + ctx.user_prompt)
        if total_tokens_est > self.context_length:
            # Truncate worker list if needed — but NEVER silently
            ctx.audit(
                "ContextBuilder",
                "WARN",
                f"Prompt estimated at {total_tokens_est} tokens, "
                f"context limit is {self.context_length}. "
                f"Worker list may be trimmed. This is logged explicitly.",
                estimated_tokens=total_tokens_est,
                context_length=self.context_length,
            )

        ctx.audit(
            "ContextBuilder",
            "BUILT",
            f"Governance preamble injected. "
            f"System prompt: {len(ctx.system_prompt)} chars, "
            f"User prompt: {len(ctx.user_prompt)} chars, "
            f"Estimated tokens: {total_tokens_est}.",
            system_prompt_len=len(ctx.system_prompt),
            user_prompt_len=len(ctx.user_prompt),
            estimated_tokens=total_tokens_est,
        )

        return ctx

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate — ~4 chars per token for English text."""
        return len(text) // 4


# ===========================================================================
# Stage 5: APPROVAL GATE
# Final authority — enforces HYBRID/MANUAL human oversight.
# ===========================================================================


class ApprovalGate:
    """Fifth constitutional authority — the final gate before execution.

    AUTO:   Log the decision and mark for immediate execution.
    HYBRID: Create a proposal and block until the human approves or rejects.
            "Hey, I have N workers available to work that job you just input —
             would you like me to proceed using all available workers,
             or select yourself?"
    MANUAL: Should never reach here (ModeGate bypasses), but rejects if it does.

    Governance: Commandment I (No execution without authorization),
                Doctrine §8 (Reversibility — proposals are cancellable),
                Commandment IX (The human architect's decision is final).
    """

    def __init__(self, config: Dict[str, Any], proposal_store=None):
        self.config = config
        self.proposal_store = proposal_store

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        """Apply the final approval gate."""

        if ctx.final_verdict in (
            PipelineVerdict.REJECT,
            PipelineVerdict.BYPASS,
            PipelineVerdict.WITHDRAW,
            PipelineVerdict.PAUSE,
        ):
            return ctx  # Pipeline already terminated

        mode = ctx.effective_mode

        # ----- AUTO: Execute immediately, log transparently -----
        if mode == ExecutionMode.AUTO:
            ctx.final_verdict = PipelineVerdict.EXECUTE
            ctx.approval_status = "auto_approved"
            ctx.audit(
                "ApprovalGate",
                "EXECUTE",
                f"AUTO mode — executing immediately. "
                f"Worker={ctx.selected_worker}, "
                f"confidence={ctx.confidence:.2f}. "
                f"Decision logged for audit trail (Doctrine §4).",
            )
            return ctx

        # ----- HYBRID: Propose and block for human approval -----
        if mode == ExecutionMode.HYBRID:
            ctx.final_verdict = PipelineVerdict.PROPOSE

            # Build the proposal with alternatives
            alternatives = self._build_alternatives(ctx)

            proposal_data = {
                "request_id": ctx.request_id,
                "task": ctx.task,
                "proposed_worker": ctx.selected_worker,
                "confidence": ctx.confidence,
                "reasoning": ctx.routing_reasoning,
                "alternatives": alternatives,
                "available_workers": list(ctx.available_workers.keys()),
                "memory_safe": ctx.memory_safe,
                "memory_verdict": ctx.memory_verdict,
                "governance_preamble_injected": True,
                "audit_trail": [
                    {"stage": e.stage, "verdict": e.verdict, "reason": e.reason}
                    for e in ctx.audit_trail
                ],
            }

            # Store proposal if store is available
            if self.proposal_store:
                ctx.proposal_id = self.proposal_store.add(proposal_data)
            else:
                ctx.proposal_id = str(uuid.uuid4())

            ctx.approval_status = "pending_approval"

            # Build the human-facing message
            worker_count = len(ctx.available_workers)
            worker_names = ", ".join(
                f"{wid} ({winfo.get('gpu_info', {}).get('name', '?')})"
                for wid, winfo in ctx.available_workers.items()
            )
            human_message = (
                f"I have {worker_count} worker(s) available for this "
                f"{ctx.task.get('task_type', 'unknown')} task: {worker_names}. "
                f"My recommendation is {ctx.selected_worker} "
                f"(confidence: {ctx.confidence:.0%}). "
                f"Would you like me to proceed with this worker, "
                f"use all available workers, or select yourself?"
            )

            ctx.audit(
                "ApprovalGate",
                "PROPOSE",
                f"HYBRID mode — proposal generated [{ctx.proposal_id[:8] if ctx.proposal_id else '?'}]. "
                f"Awaiting human approval. "
                f"(Commandment I: No execution without authorization). "
                f"Message: {human_message}",
                proposal_id=ctx.proposal_id,
                alternatives=alternatives,
                worker_count=worker_count,
            )
            return ctx

        # ----- MANUAL: Should not reach here — reject as safety net -----
        ctx.final_verdict = PipelineVerdict.BYPASS
        ctx.audit(
            "ApprovalGate",
            "BYPASS",
            "MANUAL mode reached ApprovalGate unexpectedly — bypassing. "
            "Human routes directly. (Commandment I)",
        )
        return ctx

    def _build_alternatives(self, ctx: PipelineContext) -> List[Dict[str, Any]]:
        """Build ordered list of alternative workers for the proposal."""
        alternatives = []
        for wid, score in sorted(
            ctx.worker_scores.items(), key=lambda x: x[1], reverse=True
        ):
            if wid == ctx.selected_worker:
                continue
            worker_info = ctx.available_workers.get(wid, {})
            gpu_name = worker_info.get("gpu_info", {}).get("name", "Unknown")
            alternatives.append(
                {
                    "worker_id": wid,
                    "gpu": gpu_name,
                    "score": round(score, 3),
                    "reason": f"{gpu_name} — score {score:.2f}",
                }
            )
        return alternatives


# ===========================================================================
# Pipeline Orchestrator — runs the five stages in constitutional order
# ===========================================================================


class TaskMasterPipeline:
    """Orchestrates the five constitutional pipeline stages in order.

    Authority chain:
      MemoryGuard → Mode Gate → Model Router → Context Builder → Approval Gate

    Each stage receives the shared PipelineContext, makes its decision,
    logs to the audit trail, and passes the context forward.  If any
    stage issues a terminal verdict (REJECT, BYPASS, WITHDRAW, PAUSE),
    subsequent stages are skipped — the pipeline short-circuits cleanly.

    Governance: Doctrine §9 (Modularity — stages are independent),
                Doctrine §4 (Transparent Operation — full audit trail),
                Doctrine §10 (Minimalism — pipeline does one thing: orchestrate).
    """

    def __init__(
        self,
        config: Dict[str, Any],
        system_mode: ExecutionMode,
        human_priority_checker=None,
        proposal_store=None,
    ):
        self.config = config
        self.system_mode = system_mode

        # Instantiate the five constitutional offices
        self.memory_guard = MemoryGuard(config)
        self.mode_gate = ModeGate(config, system_mode, human_priority_checker)
        self.model_router = ModelRouter(config)
        self.context_builder = ContextBuilder(config)
        self.approval_gate = ApprovalGate(config, proposal_store)

        logger.info(
            "🏛️ TaskMasterPipeline initialized — "
            "MemoryGuard → ModeGate → ModelRouter → ContextBuilder → ApprovalGate"
        )

    def update_mode(self, new_mode: ExecutionMode) -> None:
        """Update system execution mode at runtime (Doctrine §8)."""
        self.system_mode = new_mode
        self.mode_gate.system_mode = new_mode
        logger.info(f"🔄 Pipeline mode updated to {new_mode.value}")

    async def run(
        self,
        task: Dict[str, Any],
        available_workers: Dict[str, Any],
        requested_mode: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> PipelineContext:
        """Execute the full pipeline for a routing request.

        Returns the PipelineContext with all decisions, audit trail,
        and the final verdict.
        """
        ctx = PipelineContext(
            request_id=request_id or str(uuid.uuid4()),
            task=task,
            available_workers=available_workers,
            requested_mode=requested_mode,
        )
        ctx.pipeline_start = datetime.now()

        # Execute each constitutional office in order.
        # Each stage checks for terminal verdicts from previous stages
        # and short-circuits if the pipeline is already resolved.
        stages = [
            ("MemoryGuard", self.memory_guard),
            ("ModeGate", self.mode_gate),
            ("ModelRouter", self.model_router),
            ("ContextBuilder", self.context_builder),
            ("ApprovalGate", self.approval_gate),
        ]

        for stage_name, stage in stages:
            try:
                ctx = await stage.execute(ctx)

                # Short-circuit: if a terminal verdict was issued, stop
                if ctx.final_verdict in (
                    PipelineVerdict.REJECT,
                    PipelineVerdict.BYPASS,
                    PipelineVerdict.WITHDRAW,
                    PipelineVerdict.PAUSE,
                ):
                    logger.info(
                        f"⛔ Pipeline short-circuited at {stage_name}: "
                        f"{ctx.final_verdict.value}"
                    )
                    break

            except Exception as exc:
                ctx.final_verdict = PipelineVerdict.REJECT
                ctx.audit(
                    stage_name,
                    "ERROR",
                    f"Stage raised exception: {exc}. "
                    f"Pipeline halted for safety. (Doctrine §8 Reversibility)",
                )
                logger.error(f"❌ Pipeline error in {stage_name}: {exc}")
                break

        ctx.pipeline_end = datetime.now()

        logger.info(
            f"🏛️ Pipeline complete: verdict={ctx.final_verdict.value}, "
            f"elapsed={ctx.elapsed_ms:.0f}ms, "
            f"stages={len(ctx.audit_trail)}"
        )

        # Store routing decision for learning (if we got that far)
        if ctx.selected_worker and ctx.final_verdict in (
            PipelineVerdict.EXECUTE,
            PipelineVerdict.PROPOSE,
        ):
            self.model_router.store_decision(
                ctx.task, ctx.selected_worker, ctx.routing_reasoning
            )

        return ctx
