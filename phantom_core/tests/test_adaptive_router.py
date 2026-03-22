"""Tests for the adaptive routing module (Thompson Sampling over routing strategies)."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from phantom_core.adaptive_router import (
    AdaptiveRouter,
    ArmState,
    ROUTING_PRESETS,
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
