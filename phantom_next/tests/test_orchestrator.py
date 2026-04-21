import unittest

from phantom_next import (
    GPUInfo,
    TaskRequest,
    WorkerInfo,
    WorkerStatus,
    smart_worker_selection,
)


class SmartWorkerSelectionTests(unittest.TestCase):
    def test_selects_best_ml_worker_by_memory_and_load(self) -> None:
        workers = [
            WorkerInfo(
                worker_id="w1",
                status=WorkerStatus.ACTIVE,
                current_tasks=0,
                max_concurrent_tasks=2,
                gpu_info=GPUInfo(
                    name="RTX 5060", memory_total=16384, memory_free=14000, utilization=10.0
                ),
            ),
            WorkerInfo(
                worker_id="w2",
                status=WorkerStatus.ACTIVE,
                current_tasks=1,
                max_concurrent_tasks=1,
                gpu_info=GPUInfo(
                    name="RTX 5080", memory_total=24576, memory_free=20000, utilization=20.0
                ),
            ),
        ]
        task = TaskRequest(task_id="t1", task_type="ml_inference", min_memory_mb=8000)

        selected = smart_worker_selection(task, workers)
        self.assertEqual(selected, "w1")

    def test_returns_none_when_no_capacity(self) -> None:
        workers = [
            WorkerInfo(
                worker_id="w1",
                status=WorkerStatus.BUSY,
                current_tasks=1,
                max_concurrent_tasks=1,
                gpu_info=GPUInfo(name="GTX 1080", memory_total=8192, memory_free=1024),
            )
        ]
        task = TaskRequest(task_id="t2", task_type="training", min_memory_mb=4096)

        selected = smart_worker_selection(task, workers)
        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()
