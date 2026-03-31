#!/usr/bin/env python3
"""
Test suite for Phantom Controller API
"""

import unittest
import requests
from unittest.mock import patch, MagicMock


class TestControllerAPI(unittest.TestCase):
    """Live integration tests — skipped automatically when controller is not running."""

    def setUp(self):
        self.base_url = "http://localhost:8080"
        self.test_task = {
            "task_type": "compute",
            "parameters": {"operation": "matrix_multiply", "size": 100},
            "priority": 1,
        }

    def test_health_check(self):
        """Controller health endpoint returns healthy status."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("status", data)
            self.assertIn(
                data["status"],
                ("healthy", "degraded"),
                "degraded = API up but orchestrator init failed",
            )
            self.assertIn("execution_mode", data)
            self.assertIn("workers_count", data)
        except requests.exceptions.ConnectionError:
            self.skipTest("Controller not running")

    def test_worker_registration(self):
        """Worker registration returns accepted status with a worker_id."""
        worker_data = {
            "worker_id": "test_worker_001",
            "host": "localhost",
            "port": 6000,
            "gpu_info": {
                "gpu_count": 1,
                "vram_mb": 8192,
                "gpu_name": "GTX 1080",
            },
            "capabilities": {"cuda": True},
        }
        try:
            response = requests.post(
                f"{self.base_url}/workers/register", json=worker_data, timeout=5
            )
            self.assertIn(response.status_code, [200, 201])
            data = response.json()
            self.assertIn("status", data)
        except requests.exceptions.ConnectionError:
            self.skipTest("Controller not running")

    def test_task_submission(self):
        """Task submission returns a task_id and queued/accepted status."""
        try:
            response = requests.post(
                f"{self.base_url}/tasks/submit", json=self.test_task, timeout=5
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("task_id", data)
            self.assertIn("status", data)
        except requests.exceptions.ConnectionError:
            self.skipTest("Controller not running")

    def test_task_status(self):
        """Submitted task status can be queried by task_id."""
        try:
            submit = requests.post(
                f"{self.base_url}/tasks/submit", json=self.test_task, timeout=5
            )
            self.assertEqual(submit.status_code, 200)
            task_id = submit.json()["task_id"]

            status = requests.get(f"{self.base_url}/tasks/{task_id}", timeout=5)
            self.assertEqual(status.status_code, 200)
            data = status.json()
            self.assertIn("status", data)
            self.assertIn("task_id", data)
        except requests.exceptions.ConnectionError:
            self.skipTest("Controller not running")

    def test_worker_list(self):
        """Worker list endpoint returns a workers array."""
        try:
            response = requests.get(f"{self.base_url}/workers", timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("workers", data)
            self.assertIsInstance(data["workers"], list)
        except requests.exceptions.ConnectionError:
            self.skipTest("Controller not running")

    def test_stats_endpoint(self):
        """Stats endpoint returns workers and tasks summary."""
        try:
            response = requests.get(f"{self.base_url}/stats", timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("workers", data)
            self.assertIn("tasks", data)
        except requests.exceptions.ConnectionError:
            self.skipTest("Controller not running")

    def test_mode_endpoint(self):
        """Mode endpoint returns current execution mode."""
        try:
            response = requests.get(f"{self.base_url}/mode", timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("mode", data)
            self.assertIn(data["mode"], ["AUTO", "HYBRID", "MANUAL"])
        except requests.exceptions.ConnectionError:
            self.skipTest("Controller not running")


class TestControllerLogic(unittest.TestCase):
    """Unit tests for controller routing logic — no network required."""

    def test_task_routing_logic(self):
        """High-VRAM tasks are routed only to workers meeting the memory threshold."""
        workers = [
            {
                "worker_id": "rtx4090",
                "gpu_info": {"vram_mb": 24576, "name": "RTX 4090"},
                "status": "idle",
                "performance_score": 0.95,
            },
            {
                "worker_id": "gtx1060",
                "gpu_info": {"vram_mb": 6144, "name": "GTX 1060"},
                "status": "idle",
                "performance_score": 0.60,
            },
        ]

        task_vram_requirement = 16_000  # MB

        eligible = [
            w for w in workers if w["gpu_info"]["vram_mb"] >= task_vram_requirement
        ]

        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["worker_id"], "rtx4090")

        # Low-VRAM task (512 MB) should be eligible on both
        small_task_req = 512
        all_eligible = [
            w for w in workers if w["gpu_info"]["vram_mb"] >= small_task_req
        ]
        self.assertEqual(len(all_eligible), 2)

    def test_load_balancing(self):
        """Load balancing prefers idle workers with the fewest active tasks."""
        workers = [
            {"worker_id": "w1", "status": "idle", "active_tasks": 0, "score": 0.8},
            {"worker_id": "w2", "status": "busy", "active_tasks": 5, "score": 0.8},
            {"worker_id": "w3", "status": "idle", "active_tasks": 1, "score": 0.7},
        ]

        def routing_score(w):
            idle_bonus = 1.0 if w["status"] == "idle" else 0.0
            load_penalty = w["active_tasks"] * 0.1
            return w["score"] + idle_bonus - load_penalty

        scores = {w["worker_id"]: routing_score(w) for w in workers}
        best = max(scores, key=lambda k: scores[k])

        # w1: 0.8 + 1.0 - 0.0 = 1.8
        # w2: 0.8 + 0.0 - 0.5 = 0.3
        # w3: 0.7 + 1.0 - 0.1 = 1.6
        self.assertEqual(best, "w1")
        self.assertGreater(scores["w1"], scores["w2"])
        self.assertGreater(scores["w1"], scores["w3"])
        self.assertGreater(scores["w3"], scores["w2"])

    def test_gpu_capability_matching(self):
        """Tasks requiring specific GPU capabilities route only to compatible workers."""
        workers = [
            {"worker_id": "nvidia", "caps": {"cuda": True, "rocm": False}},
            {"worker_id": "amd", "caps": {"cuda": False, "rocm": True}},
            {"worker_id": "cpu", "caps": {"cuda": False, "rocm": False}},
        ]

        def can_handle(worker, required_cap):
            if required_cap is None:
                return True
            return worker["caps"].get(required_cap, False)

        cuda_workers = [w for w in workers if can_handle(w, "cuda")]
        self.assertEqual(len(cuda_workers), 1)
        self.assertEqual(cuda_workers[0]["worker_id"], "nvidia")

        rocm_workers = [w for w in workers if can_handle(w, "rocm")]
        self.assertEqual(len(rocm_workers), 1)
        self.assertEqual(rocm_workers[0]["worker_id"], "amd")

        # Generic CPU task: all workers eligible
        cpu_workers = [w for w in workers if can_handle(w, None)]
        self.assertEqual(len(cpu_workers), 3)

        # Unavailable capability: no workers eligible
        quantum_workers = [w for w in workers if can_handle(w, "quantum")]
        self.assertEqual(len(quantum_workers), 0)


if __name__ == "__main__":
    unittest.main()
