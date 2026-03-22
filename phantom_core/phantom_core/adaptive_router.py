"""
Adaptive Task Router — Thompson Sampling over routing strategies.

Learns which worker-scoring strategy produces the best task outcomes.
Instead of fixed multiplicative scoring, the system explores different
weight presets (arms) and converges on the best one for the workload.

Based on the Thompson Sampling approach from:
  DiRocco, A. (2026). "Learning Retrieval Weights Online via
  Dimension-Specific Self-Assessment." arXiv preprint.

Adapted from retrieval weight optimization to compute task routing.
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np

logger = logging.getLogger(__name__)

# ── Routing Strategy Presets ───────────────────────────────────────────
#
# Each arm is a named weight vector over five worker-scoring dimensions:
#   gpu      — base GPU capability score (from hardware profile)
#   load     — how idle the worker is (1 - tasks/capacity)
#   perf     — historical performance score (moving average)
#   memory   — memory availability relative to task requirement
#   util     — GPU utilization headroom (1 - utilization%)
#
# Weights are normalized to sum to 1.0 at scoring time.

ROUTING_PRESETS: Dict[str, Dict[str, float]] = {
    "balanced": {
        "gpu": 0.20, "load": 0.20, "perf": 0.20, "memory": 0.20, "util": 0.20,
    },
    "gpu_affinity": {
        "gpu": 0.50, "load": 0.10, "perf": 0.15, "memory": 0.15, "util": 0.10,
    },
    "load_balanced": {
        "gpu": 0.10, "load": 0.40, "perf": 0.10, "memory": 0.20, "util": 0.20,
    },
    "memory_optimized": {
        "gpu": 0.10, "load": 0.10, "perf": 0.10, "memory": 0.50, "util": 0.20,
    },
    "performance_first": {
        "gpu": 0.15, "load": 0.10, "perf": 0.45, "memory": 0.15, "util": 0.15,
    },
    "utilization_aware": {
        "gpu": 0.10, "load": 0.20, "perf": 0.10, "memory": 0.20, "util": 0.40,
    },
}


@dataclass
class ArmState:
    """Beta distribution parameters for one routing strategy arm."""
    arm_id: str
    alpha: float = 1.0
    beta: float = 1.0
    pulls: int = 0
    total_reward: float = 0.0
    last_updated: str = ""

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))


@dataclass
class RoutingDecision:
    """Record of a single routing decision for audit trail."""
    task_id: str
    strategy: str
    worker_id: str
    worker_scores: Dict[str, float]
    timestamp: str
    reward: Optional[float] = None


class AdaptiveRouter:
    """Thompson Sampling bandit over routing strategy presets.

    Usage:
        router = AdaptiveRouter(state_dir="/var/lib/phantom/state")
        strategy = router.select_strategy()
        score = router.score_worker(strategy, factor_scores)
        # ... assign task, await completion ...
        router.update(strategy, reward=0.85)
    """

    def __init__(
        self,
        state_dir: Optional[str] = None,
        presets: Optional[Dict[str, Dict[str, float]]] = None,
        discount: Optional[float] = None,
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0,
        seed: Optional[int] = None,
    ):
        self.presets = presets or ROUTING_PRESETS
        self.discount = discount
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self._rng = np.random.default_rng(seed)

        # State directory for persistence
        if state_dir:
            self._state_path = Path(state_dir) / "adaptive_router_state.json"
        else:
            self._state_path = None

        # Initialize arms
        self.arms: Dict[str, ArmState] = {}
        self._init_arms()

        # Decision log (recent, for debugging)
        self.decisions: List[RoutingDecision] = []
        self._max_decisions = 500

        # Try loading persisted state
        if self._state_path:
            self._load_state()

        logger.info(
            "Adaptive router initialized: %d strategies, discount=%s",
            len(self.arms), self.discount,
        )

    def _init_arms(self):
        """Initialize Beta posteriors for each routing strategy."""
        for name in self.presets:
            if name not in self.arms:
                self.arms[name] = ArmState(
                    arm_id=name,
                    alpha=self.prior_alpha,
                    beta=self.prior_beta,
                )

    # ── Core Bandit Operations ─────────────────────────────────────────

    def select_strategy(self) -> str:
        """Sample from Beta posteriors, return the strategy with highest sample.

        This is the Thompson Sampling selection rule: each arm's probability
        of being selected equals its posterior probability of being optimal.
        """
        best_arm = None
        best_sample = -1.0

        for arm_id, arm in self.arms.items():
            sample = self._rng.beta(arm.alpha, arm.beta)
            if sample > best_sample:
                best_sample = sample
                best_arm = arm_id

        logger.debug(
            "TS selected strategy '%s' (sample=%.4f, mean=%.4f)",
            best_arm, best_sample, self.arms[best_arm].mean,
        )
        return best_arm

    def update(self, strategy: str, reward: float):
        """Update the Beta posterior for the chosen strategy.

        Args:
            strategy: Name of the routing strategy that was used.
            reward: Outcome signal in [0, 1]. Higher = better task result.
        """
        if strategy not in self.arms:
            logger.warning("Unknown strategy '%s', skipping update", strategy)
            return

        reward = max(0.0, min(1.0, reward))
        arm = self.arms[strategy]

        # Optional discounting for non-stationary environments.
        # As the worker pool changes, old observations become less relevant.
        if self.discount is not None:
            for a in self.arms.values():
                a.alpha *= self.discount
                a.beta *= self.discount
                # Floor to prevent posterior collapse
                a.alpha = max(a.alpha, 0.01)
                a.beta = max(a.beta, 0.01)

        arm.alpha += reward
        arm.beta += (1.0 - reward)
        arm.pulls += 1
        arm.total_reward += reward
        arm.last_updated = datetime.now().isoformat()

        logger.debug(
            "Updated arm '%s': reward=%.3f, alpha=%.2f, beta=%.2f, pulls=%d",
            strategy, reward, arm.alpha, arm.beta, arm.pulls,
        )

        # Auto-persist
        if self._state_path:
            self._save_state()

    # ── Worker Scoring ─────────────────────────────────────────────────

    def score_worker(
        self,
        strategy: str,
        factor_scores: Dict[str, float],
    ) -> float:
        """Score a worker using the selected strategy's weights.

        Args:
            strategy: Name of the active routing strategy.
            factor_scores: Dict with keys {gpu, load, perf, memory, util},
                           each a float in [0, 1] or similar normalized range.

        Returns:
            Weighted score (higher = better candidate).
        """
        weights = self.presets.get(strategy, self.presets["balanced"])

        score = 0.0
        for dimension, weight in weights.items():
            score += weight * factor_scores.get(dimension, 0.0)

        return score

    # ── Reward Computation ─────────────────────────────────────────────

    @staticmethod
    def compute_reward(
        success: bool,
        duration_seconds: float,
        baseline_duration: float = 60.0,
    ) -> float:
        """Map a task outcome to a [0, 1] reward signal.

        Reward formula:
            - Failed tasks: 0.0
            - Successful tasks: speed_bonus in (0, 1]
              speed_bonus = min(1.0, baseline / max(1, actual_duration))

        This incentivizes both reliability (success) and efficiency (speed).
        """
        if not success:
            return 0.0

        speed_bonus = min(1.0, baseline_duration / max(1.0, duration_seconds))
        return speed_bonus

    @staticmethod
    def cost_aware_reward(
        raw_reward: float,
        resource_cost: float,
        baseline_cost: float = 1.0,
    ) -> float:
        """Adjust reward by resource cost ratio.

        Penalizes routing to overpowered workers for simple tasks.
        E.g., sending a data_processing task to an RTX 5080 when a
        GTX 1080 would have sufficed.
        """
        if resource_cost <= 0:
            return raw_reward
        adjusted = raw_reward * (baseline_cost / resource_cost)
        return max(0.0, min(1.0, adjusted))

    # ── Decision Logging ───────────────────────────────────────────────

    def log_decision(
        self,
        task_id: str,
        strategy: str,
        worker_id: str,
        worker_scores: Dict[str, float],
    ):
        """Record a routing decision for audit/debugging."""
        decision = RoutingDecision(
            task_id=task_id,
            strategy=strategy,
            worker_id=worker_id,
            worker_scores=worker_scores,
            timestamp=datetime.now().isoformat(),
        )
        self.decisions.append(decision)
        if len(self.decisions) > self._max_decisions:
            self.decisions = self.decisions[-self._max_decisions:]

    def record_outcome(self, task_id: str, reward: float):
        """Attach the reward to a logged decision (retroactive)."""
        for decision in reversed(self.decisions):
            if decision.task_id == task_id:
                decision.reward = reward
                break

    # ── Persistence ────────────────────────────────────────────────────

    def _save_state(self):
        """Persist bandit state to JSON file."""
        if not self._state_path:
            return
        try:
            state = {
                "arms": {k: asdict(v) for k, v in self.arms.items()},
                "discount": self.discount,
                "saved_at": datetime.now().isoformat(),
            }
            # Atomic write via temp file
            tmp_path = self._state_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(state, indent=2))
            tmp_path.rename(self._state_path)
        except Exception as e:
            logger.error("Failed to save adaptive router state: %s", e)

    def _load_state(self):
        """Load bandit state from JSON file if it exists."""
        if not self._state_path or not self._state_path.exists():
            return
        try:
            state = json.loads(self._state_path.read_text())
            for arm_id, arm_data in state.get("arms", {}).items():
                if arm_id in self.arms:
                    self.arms[arm_id] = ArmState(**arm_data)
            logger.info(
                "Loaded adaptive router state: %d arms, total pulls=%d",
                len(self.arms),
                sum(a.pulls for a in self.arms.values()),
            )
        except Exception as e:
            logger.warning("Failed to load adaptive router state: %s", e)

    # ── Reporting ──────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Return a serializable summary of the bandit state."""
        arms_sorted = sorted(
            self.arms.values(), key=lambda a: a.mean, reverse=True,
        )
        total_pulls = sum(a.pulls for a in self.arms.values())

        best_arm = arms_sorted[0] if arms_sorted else None

        return {
            "total_pulls": total_pulls,
            "best_strategy": best_arm.arm_id if best_arm else None,
            "best_mean": round(best_arm.mean, 4) if best_arm else None,
            "discount": self.discount,
            "arms": [
                {
                    "strategy": a.arm_id,
                    "alpha": round(a.alpha, 3),
                    "beta": round(a.beta, 3),
                    "mean": round(a.mean, 4),
                    "pulls": a.pulls,
                    "total_reward": round(a.total_reward, 3),
                }
                for a in arms_sorted
            ],
        }

    def get_recent_decisions(self, limit: int = 20) -> List[Dict]:
        """Return recent routing decisions for the UI/API."""
        recent = self.decisions[-limit:]
        return [
            {
                "task_id": d.task_id,
                "strategy": d.strategy,
                "worker_id": d.worker_id,
                "reward": d.reward,
                "timestamp": d.timestamp,
            }
            for d in reversed(recent)
        ]
