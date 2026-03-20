# Controller Task Ledger

## Persistence

- **File:** `{PHANTOM_STATE_DIR}/tasks.json` (see `StateManager` in `phantom_core/state.py`).
- **Format:** JSON object keyed by `task_id`, each value a task record (dict).

## Execution states (canonical)

| Status | Meaning |
|--------|---------|
| `QUEUED` | Accepted; not yet dispatched or waiting for worker accept |
| `RUNNING` | Dispatched to worker; awaiting callback |
| `COMPLETED` | Worker posted `/api/worker/completion` |
| `FAILED` | Worker posted `/api/worker/failure`, dispatch error, or reconciliation timeout |

## Workflow states (unchanged)

| Status | Meaning |
|--------|---------|
| `pending_approval` | HYBRID / MANUAL proposal awaiting human action |
| `expired` | Proposal expired |
| `cancelled` | User cancelled |
| `rejected` | Proposal rejected |

## Typical fields

- `task_id`, `task_type`, `parameters`, `priority`, `worker_id`
- `created_at`, `eta_seconds` (where applicable)
- `started_at` — set when task enters `RUNNING`
- `completed_at` — set on `COMPLETED`
- `failed_at`, `error`, `failure_reason` — set on `FAILED`
- `result` — plugin output on `COMPLETED`

## Code

- **Ledger logic:** `phantom_core/phantom_core/task_ledger.py`
- **HTTP API:** `phantom_core/phantom_core/controller_api.py` (`/api/worker/completion`, `/api/worker/failure`, `execute_task`, reconciliation loop)

## Legacy migration

On controller startup, legacy lowercase statuses (`queued`, `running`, `completed`, `failed`) in `tasks.json` are normalized to the canonical uppercase values.
