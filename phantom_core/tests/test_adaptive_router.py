"""Tests for the adaptive routing module (Thompson Sampling over routing strategies)."""

import asyncio
import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from phantom_core.adaptive_router import (
    AdaptiveRouter,
    ArmState,
    TaskTypeRouter,
    ROUTING_PRESETS,
)
from phantom_core.orchestrator import (
    PhantomOrchestrator,
    GPUInfo,
    WorkerInfo,
    WorkerStatus,
    Task,
    TaskStatus,
)


# ── Unit Tests: ArmState ──────────────────────────────────────────────


class TestArmState:
    def test_default_priors(self):
        arm = ArmState(arm_id="test")
        assert arm.alpha == 1.0
        assert arm.beta == 1.0
        assert arm.mean == 0.5
        assert arm.pulls == 0

    def test_mean_after_updates(self):
        arm = ArmState(arm_id="test", alpha=8.0, beta=2.0)
        assert arm.mean == pytest.approx(0.8)

    def test_variance_decreases_with_evidence(self):
        weak = ArmState(arm_id="a", alpha=2.0, beta=2.0)
        strong = ArmState(arm_id="b", alpha=20.0, beta=20.0)
        assert strong.variance < weak.variance


# ── Unit Tests: AdaptiveRouter ─────────────────────────────────────────


class TestAdaptiveRouter:
    def test_init_creates_all_arms(self):
        router = AdaptiveRouter(seed=42)
        assert len(router.arms) == len(ROUTING_PRESETS)
        for name in ROUTING_PRESETS:
            assert name in router.arms

    def test_select_returns_valid_strategy(self):
        router = AdaptiveRouter(seed=42)
        strategy = router.select_strategy()
        assert strategy in ROUTING_PRESETS

    def test_update_modifies_posterior(self):
        router = AdaptiveRouter(seed=42)
        arm_before = router.arms["balanced"]
        alpha_before = arm_before.alpha

        router.update("balanced", reward=1.0)

        assert router.arms["balanced"].alpha > alpha_before
        assert router.arms["balanced"].pulls == 1

    def test_update_clamps_reward(self):
        router = AdaptiveRouter(seed=42)
        router.update("balanced", reward=5.0)  # Should clamp to 1.0
        assert router.arms["balanced"].alpha == 2.0  # 1.0 prior + 1.0 reward

        router.update("balanced", reward=-3.0)  # Should clamp to 0.0
        assert router.arms["balanced"].beta == pytest.approx(2.0)  # 1.0 prior + 1.0

    def test_update_unknown_strategy_warns(self, caplog):
        router = AdaptiveRouter(seed=42)
        router.update("nonexistent_strategy", reward=0.5)
        assert "Unknown strategy" in caplog.text

    def test_discount_decays_all_arms(self):
        router = AdaptiveRouter(seed=42, discount=0.9)
        # Give one arm some history
        router.arms["balanced"].alpha = 10.0
        router.arms["balanced"].beta = 5.0

        router.update("gpu_affinity", reward=1.0)

        # balanced should have decayed
        assert router.arms["balanced"].alpha < 10.0
        assert router.arms["balanced"].beta < 5.0


class TestScoring:
    def test_score_worker_uses_weights(self):
        router = AdaptiveRouter(seed=42)
        factors = {"gpu": 1.0, "load": 0.0, "perf": 0.0, "memory": 0.0, "util": 0.0}

        # gpu_affinity weights gpu at 0.50
        score_gpu = router.score_worker("gpu_affinity", factors)
        # load_balanced weights gpu at 0.10
        score_load = router.score_worker("load_balanced", factors)

        assert score_gpu > score_load

    def test_score_balanced_is_average(self):
        router = AdaptiveRouter(seed=42)
        factors = {"gpu": 0.8, "load": 0.6, "perf": 0.4, "memory": 0.2, "util": 1.0}

        score = router.score_worker("balanced", factors)
        expected = 0.2 * (0.8 + 0.6 + 0.4 + 0.2 + 1.0)
        assert score == pytest.approx(expected)

    def test_missing_factor_treated_as_zero(self):
        router = AdaptiveRouter(seed=42)
        factors = {"gpu": 1.0}  # Missing load, perf, memory, util

        score = router.score_worker("balanced", factors)
        assert score == pytest.approx(0.2 * 1.0)  # Only gpu contributes


class TestReward:
    def test_success_fast_task(self):
        reward = AdaptiveRouter.compute_reward(
            success=True, duration_seconds=30.0, baseline_duration=60.0,
        )
        assert reward == pytest.approx(1.0)  # Capped at 1.0

    def test_success_slow_task(self):
        reward = AdaptiveRouter.compute_reward(
            success=True, duration_seconds=120.0, baseline_duration=60.0,
        )
        assert reward == pytest.approx(0.5)

    def test_failure_always_zero(self):
        reward = AdaptiveRouter.compute_reward(
            success=False, duration_seconds=10.0,
        )
        assert reward == 0.0

    def test_cost_aware_penalizes_waste(self):
        raw = 0.8
        # Using 2x resources → half reward
        adjusted = AdaptiveRouter.cost_aware_reward(raw, resource_cost=2.0, baseline_cost=1.0)
        assert adjusted == pytest.approx(0.4)


# ── Integration Tests: Convergence ─────────────────────────────────────


class TestConvergence:
    def test_bandit_converges_to_best_arm(self):
        """Simulate a scenario where gpu_affinity is clearly best.

        After enough episodes, the bandit's posterior should favor it.
        """
        router = AdaptiveRouter(seed=123)

        # Simulate: gpu_affinity gets reward 0.9, others get 0.3
        rng = np.random.default_rng(456)

        for _ in range(200):
            strategy = router.select_strategy()
            if strategy == "gpu_affinity":
                reward = 0.7 + rng.uniform(0, 0.3)
            else:
                reward = 0.1 + rng.uniform(0, 0.3)
            router.update(strategy, reward)

        summary = router.get_summary()
        assert summary["best_strategy"] == "gpu_affinity"
        assert summary["total_pulls"] == 200

    def test_all_arms_explored(self):
        """Over enough episodes, every arm should be pulled at least once."""
        router = AdaptiveRouter(seed=789)

        for _ in range(100):
            strategy = router.select_strategy()
            router.update(strategy, reward=0.5)

        for arm in router.arms.values():
            assert arm.pulls > 0, f"Arm {arm.arm_id} was never explored"


# ── Persistence Tests ──────────────────────────────────────────────────


class TestPersistence:
    def test_save_and_load_state(self, tmp_path):
        # Create and train a router
        router1 = AdaptiveRouter(state_dir=str(tmp_path), seed=42)
        router1.update("balanced", reward=0.9)
        router1.update("gpu_affinity", reward=0.3)
        router1.update("gpu_affinity", reward=0.7)

        # Create a new router from the same state dir
        router2 = AdaptiveRouter(state_dir=str(tmp_path), seed=42)

        # Should have loaded the persisted state
        assert router2.arms["balanced"].pulls == 1
        assert router2.arms["gpu_affinity"].pulls == 2
        assert router2.arms["balanced"].alpha == router1.arms["balanced"].alpha

    def test_state_file_is_valid_json(self, tmp_path):
        router = AdaptiveRouter(state_dir=str(tmp_path), seed=42)
        router.update("balanced", reward=0.5)

        state_file = tmp_path / "adaptive_router_state.json"
        assert state_file.exists()

        data = json.loads(state_file.read_text())
        assert "arms" in data
        assert "saved_at" in data

    def test_no_state_dir_works_fine(self):
        router = AdaptiveRouter(seed=42)
        router.update("balanced", reward=0.5)
        # Should not raise — just skips persistence


# ── Decision Logging Tests ─────────────────────────────────────────────


class TestDecisionLogging:
    def test_log_and_retrieve_decisions(self):
        router = AdaptiveRouter(seed=42)
        router.log_decision(
            task_id="t1",
            strategy="balanced",
            worker_id="w1",
            worker_scores={"w1": 0.8, "w2": 0.3},
        )

        recent = router.get_recent_decisions(10)
        assert len(recent) == 1
        assert recent[0]["task_id"] == "t1"
        assert recent[0]["strategy"] == "balanced"

    def test_record_outcome_attaches_reward(self):
        router = AdaptiveRouter(seed=42)
        router.log_decision("t1", "balanced", "w1", {})
        router.record_outcome("t1", reward=0.75)

        assert router.decisions[0].reward == 0.75

    def test_decision_log_bounded(self):
        router = AdaptiveRouter(seed=42)
        router._max_decisions = 5

        for i in range(10):
            router.log_decision(f"t{i}", "balanced", "w1", {})

        assert len(router.decisions) == 5


# ── Summary Tests ──────────────────────────────────────────────────────


class TestSummary:
    def test_summary_structure(self):
        router = AdaptiveRouter(seed=42)
        summary = router.get_summary()

        assert "total_pulls" in summary
        assert "best_strategy" in summary
        assert "arms" in summary
        assert len(summary["arms"]) == len(ROUTING_PRESETS)

    def test_summary_sorted_by_mean(self):
        router = AdaptiveRouter(seed=42)
        # Make gpu_affinity clearly best
        for _ in range(10):
            router.update("gpu_affinity", reward=0.95)

        summary = router.get_summary()
        means = [arm["mean"] for arm in summary["arms"]]
        assert means == sorted(means, reverse=True)


# ── TaskTypeRouter Tests ───────────────────────────────────────────────


class TestTaskTypeRouter:
    def test_creates_separate_bandits_per_type(self):
        router = TaskTypeRouter(seed=42)

        router.select_strategy("ml_inference")
        router.select_strategy("data_processing")
        router.select_strategy("training")

        assert "ml_inference" in router._routers
        assert "data_processing" in router._routers
        assert "training" in router._routers

    def test_types_learn_independently(self):
        router = TaskTypeRouter(seed=42)

        # ml_inference: gpu_affinity is best
        for _ in range(50):
            router.update("ml_inference", "gpu_affinity", reward=0.9)
            router.update("ml_inference", "balanced", reward=0.3)

        # data_processing: load_balanced is best
        for _ in range(50):
            router.update("data_processing", "load_balanced", reward=0.9)
            router.update("data_processing", "balanced", reward=0.3)

        ml_summary = router._get_router("ml_inference").get_summary()
        dp_summary = router._get_router("data_processing").get_summary()

        assert ml_summary["best_strategy"] == "gpu_affinity"
        assert dp_summary["best_strategy"] == "load_balanced"

    def test_unknown_type_gets_own_bandit(self):
        router = TaskTypeRouter(seed=42)
        strategy = router.select_strategy("never_seen_before")
        assert strategy in ROUTING_PRESETS
        assert "never_seen_before" in router._routers

    def test_summary_shows_all_types(self):
        router = TaskTypeRouter(seed=42)
        router.update("ml_inference", "balanced", reward=0.5)
        router.update("training", "gpu_affinity", reward=0.8)

        summary = router.get_summary()
        assert summary["active_task_types"] >= 3  # default + 2 types
        assert "ml_inference" in summary["task_types"]
        assert "training" in summary["task_types"]

    def test_persistence_per_type(self, tmp_path):
        router1 = TaskTypeRouter(state_dir=str(tmp_path), seed=42)
        router1.update("ml_inference", "gpu_affinity", reward=0.9)
        router1.update("training", "load_balanced", reward=0.7)

        # New router from same state dir
        router2 = TaskTypeRouter(state_dir=str(tmp_path), seed=42)
        # Force loading by accessing the task types
        router2.select_strategy("ml_inference")
        router2.select_strategy("training")

        ml_arm = router2._get_router("ml_inference").arms["gpu_affinity"]
        assert ml_arm.pulls == 1

    def test_recent_decisions_aggregated(self):
        router = TaskTypeRouter(seed=42)
        router.log_decision("t1", "ml_inference", "balanced", "w1", {})
        router.log_decision("t2", "training", "gpu_affinity", "w2", {})

        recent = router.get_recent_decisions(10)
        assert len(recent) == 2
        task_types = {d["task_type"] for d in recent}
        assert task_types == {"ml_inference", "training"}


# ── Orchestrator Integration Tests ─────────────────────────────────────


def _make_worker(worker_id, gpu_name, mem_total, mem_free, util=10.0):
    """Helper to build a WorkerInfo with realistic GPU data."""
    gpu = GPUInfo(
        name=gpu_name,
        memory_total=mem_total,
        memory_free=mem_free,
        compute_capability="9.0",
        driver_version="560.0",
        utilization=util,
    )
    return WorkerInfo(
        worker_id=worker_id,
        host="localhost",
        port=8090,
        gpu_info=gpu,
        status=WorkerStatus.ACTIVE,
        performance_score=1.0,
    )


class TestOrchestratorIntegration:
    """Test the full cycle: submit → adaptive select → complete → bandit update."""

    def test_adaptive_orchestrator_selects_worker(self):
        """With adaptive routing on, select_optimal_worker uses the bandit."""
        orch = PhantomOrchestrator(adaptive_routing=True)
        orch.register_worker(_make_worker("w1", "RTX 5080", 24000, 20000))
        orch.register_worker(_make_worker("w2", "GTX 1080", 8000, 6000))

        task = Task("t1", "ml_inference", {}, 5, TaskStatus.PENDING)

        selected = asyncio.run(orch.select_optimal_worker(task))
        assert selected in ("w1", "w2")
        # Strategy should be tracked for this task
        assert "t1" in orch._active_strategies

    def test_completion_updates_bandit(self):
        """Task completion feeds reward back to the bandit."""
        orch = PhantomOrchestrator(adaptive_routing=True)
        orch.register_worker(_make_worker("w1", "RTX 5080", 24000, 20000))

        task = Task("t1", "ml_inference", {}, 5, TaskStatus.PENDING)
        # Register task with orchestrator so handle_task_completion can find it
        orch.tasks[task.task_id] = task

        # Select worker (sets up strategy tracking)
        asyncio.run(orch.select_optimal_worker(task))
        strategy_used = orch._active_strategies.get("t1")
        assert strategy_used is not None

        # Simulate task lifecycle
        from datetime import datetime, timedelta
        task.status = TaskStatus.RUNNING
        task.worker_id = "w1"
        task.started_at = datetime.now() - timedelta(seconds=30)

        asyncio.run(orch.handle_task_completion("t1", {"output": "done"}))

        # Strategy should be consumed
        assert "t1" not in orch._active_strategies
        # Bandit should have 1 pull on ml_inference
        ml_router = orch.adaptive_router._get_router("ml_inference")
        assert ml_router.arms[strategy_used].pulls == 1

    def test_failure_gives_zero_reward(self):
        """Task failure feeds reward=0.0 to the bandit."""
        orch = PhantomOrchestrator(adaptive_routing=True)
        orch.register_worker(_make_worker("w1", "RTX 5080", 24000, 20000))

        task = Task("t1", "training", {}, 5, TaskStatus.PENDING)
        orch.tasks[task.task_id] = task

        asyncio.run(orch.select_optimal_worker(task))
        strategy_used = orch._active_strategies.get("t1")

        from datetime import datetime, timedelta
        task.status = TaskStatus.RUNNING
        task.worker_id = "w1"
        task.started_at = datetime.now() - timedelta(seconds=10)

        asyncio.run(orch.handle_task_failure("t1", "OOM killed"))

        training_router = orch.adaptive_router._get_router("training")
        arm = training_router.arms[strategy_used]
        assert arm.pulls == 1
        assert arm.total_reward == 0.0  # Failure = 0 reward

    def test_different_task_types_use_different_bandits(self):
        """ml_inference and data_processing get separate bandits."""
        orch = PhantomOrchestrator(adaptive_routing=True)
        orch.register_worker(_make_worker("w1", "RTX 5080", 24000, 20000))

        for task_type in ("ml_inference", "data_processing", "training"):
            task = Task(f"t_{task_type}", task_type, {}, 5, TaskStatus.PENDING)
            asyncio.run(orch.select_optimal_worker(task))

        summary = orch.adaptive_router.get_summary()
        assert summary["active_task_types"] >= 3

    def test_legacy_scoring_when_adaptive_off(self):
        """Default orchestrator (no adaptive) uses legacy multiplicative scoring."""
        orch = PhantomOrchestrator(adaptive_routing=False)
        orch.register_worker(_make_worker("w1", "RTX 5080", 24000, 20000))

        task = Task("t1", "ml_inference", {}, 5, TaskStatus.PENDING)
        selected = asyncio.run(orch.select_optimal_worker(task))

        assert selected == "w1"
        assert orch.adaptive_router is None
        assert len(orch._active_strategies) == 0

    def test_convergence_through_orchestrator(self):
        """Over many tasks, the bandit converges to the best strategy.

        Simulates a workload where gpu_affinity routing leads to faster
        completions for ml_inference tasks.
        """
        orch = PhantomOrchestrator(adaptive_routing=True)
        orch.register_worker(_make_worker("w1", "RTX 5080", 24000, 20000, util=10))
        orch.register_worker(_make_worker("w2", "GTX 1080", 8000, 6000, util=50))

        rng = np.random.default_rng(99)

        from datetime import datetime, timedelta

        for i in range(100):
            task = Task(f"t{i}", "ml_inference", {}, 5, TaskStatus.PENDING)
            orch.tasks[task.task_id] = task
            selected = asyncio.run(orch.select_optimal_worker(task))
            strategy = orch._active_strategies.get(f"t{i}")

            # Simulate: gpu_affinity picks RTX 5080 → fast completion
            # Other strategies sometimes pick GTX 1080 → slower
            task.status = TaskStatus.RUNNING
            task.worker_id = selected
            if strategy == "gpu_affinity":
                task.started_at = datetime.now() - timedelta(seconds=20 + rng.uniform(0, 10))
            else:
                task.started_at = datetime.now() - timedelta(seconds=50 + rng.uniform(0, 30))

            asyncio.run(orch.handle_task_completion(f"t{i}", {}))

        ml_router = orch.adaptive_router._get_router("ml_inference")
        summary = ml_router.get_summary()
        # gpu_affinity should have the highest mean (best strategy)
        assert summary["best_strategy"] == "gpu_affinity"
