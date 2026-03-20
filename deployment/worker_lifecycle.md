# Worker → Controller Task Lifecycle

Phantom workers execute tasks **asynchronously**. The controller is the **authoritative** source for task state; workers report outcomes via HTTP callbacks.

## Flow

1. **Submit** — Client calls `POST /tasks/submit` on the controller.
2. **Queue** — Controller records the task as `QUEUED` (or `pending_approval` in HYBRID / MANUAL flows).
3. **Dispatch** — Controller calls `POST http://{worker_host}:{worker_port}/tasks/execute` with `task_id`, `task_type`, `parameters`.
4. **Accept** — Worker returns `200` with body `{"task_id", "status": "running", ...}` and runs the task in the background.
5. **Running** — Controller sets task status to `RUNNING` and sets `started_at`.
6. **Callback (success)** — Worker calls `POST /api/worker/completion` on the controller with `task_id`, `worker_id`, `timestamp`, `result`.
7. **Callback (failure)** — Worker calls `POST /api/worker/failure` with `task_id`, `worker_id`, `timestamp`, `error`.
8. **Terminal** — Controller sets `COMPLETED` or `FAILED` and persists `tasks.json`.

## Endpoints (worker → controller)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/worker/completion` | Task finished successfully |
| `POST` | `/api/worker/failure` | Task failed on worker |

### Optional authentication

If the controller process has `PHANTOM_WORKER_CALLBACK_SECRET` set, workers must send header:

`X-Phantom-Callback-Key: <same value>`

Set the same variable on worker processes so callbacks succeed.

## Reconciliation

If a task stays `RUNNING` longer than `PHANTOM_TASK_RUNNING_TIMEOUT_SEC` (default `86400` seconds) without a callback, the controller marks it `FAILED` with `failure_reason` / `error` = `timeout/no-callback`. The scan runs every 30 seconds.

## Related

- [controller/task_ledger.md](../controller/task_ledger.md) — state machine and persistence
- `phantom_core/linux-worker/linux_worker/worker.py` — Linux implementation
- `phantom_core/windows-worker/windows_worker/worker.py` — Windows implementation
