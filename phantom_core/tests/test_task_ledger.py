"""Unit tests for phantom_core.task_ledger.

Loads task_ledger directly so this suite runs without FastAPI/controller deps.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

_tl_path = Path(__file__).resolve().parent.parent / "phantom_core" / "task_ledger.py"
_spec = importlib.util.spec_from_file_location("phantom_task_ledger", _tl_path)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
sys.modules["phantom_task_ledger"] = _mod

TASK_QUEUED = _mod.TASK_QUEUED
TASK_RUNNING = _mod.TASK_RUNNING
TASK_COMPLETED = _mod.TASK_COMPLETED
TASK_FAILED = _mod.TASK_FAILED
normalize_task_status = _mod.normalize_task_status
apply_worker_completion = _mod.apply_worker_completion
apply_worker_failure = _mod.apply_worker_failure
reconcile_stale_running_tasks = _mod.reconcile_stale_running_tasks


class TestTaskLedger(unittest.TestCase):
    def test_normalize_legacy(self):
        self.assertEqual(normalize_task_status("queued"), TASK_QUEUED)
        self.assertEqual(normalize_task_status("RUNNING"), TASK_RUNNING)
        self.assertEqual(normalize_task_status("completed"), TASK_COMPLETED)
        self.assertEqual(normalize_task_status("pending_approval"), "pending_approval")

    def test_completion_happy_path(self):
        tasks = {
            "t1": {
                "task_id": "t1",
                "worker_id": "w1",
                "status": TASK_RUNNING,
            }
        }
        ok, reason = apply_worker_completion(
            tasks, "t1", "w1", {"ok": True}, "2025-01-01T00:00:00"
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")
        self.assertEqual(tasks["t1"]["status"], TASK_COMPLETED)
        self.assertEqual(tasks["t1"]["result"], {"ok": True})

    def test_completion_worker_mismatch(self):
        tasks = {"t1": {"task_id": "t1", "worker_id": "w1", "status": TASK_RUNNING}}
        ok, reason = apply_worker_completion(tasks, "t1", "w2", {}, "2025-01-01T00:00:00")
        self.assertFalse(ok)
        self.assertEqual(reason, "worker_mismatch")

    def test_failure_from_running(self):
        tasks = {"t1": {"task_id": "t1", "worker_id": "w1", "status": TASK_RUNNING}}
        ok, _ = apply_worker_failure(tasks, "t1", "w1", "boom", "2025-01-01T00:00:01")
        self.assertTrue(ok)
        self.assertEqual(tasks["t1"]["status"], TASK_FAILED)
        self.assertEqual(tasks["t1"]["error"], "boom")

    def test_reconcile_timeout(self):
        old = (datetime.now() - timedelta(seconds=7200)).isoformat()
        tasks = {
            "t1": {
                "task_id": "t1",
                "status": TASK_RUNNING,
                "started_at": old,
            }
        }
        updated = reconcile_stale_running_tasks(tasks, timeout_sec=3600)
        self.assertIn("t1", updated)
        self.assertEqual(tasks["t1"]["status"], TASK_FAILED)
        self.assertIn("timeout", tasks["t1"]["error"])


if __name__ == "__main__":
    unittest.main()
