# Phantom UI Framework

> Interface contract, reference implementations, and custom UI development guide.

---

## Overview

Phantom uses a **swappable UI architecture** — any frontend (web, terminal, mobile, desktop) can connect to the Phantom backend through a standardized protocol adapter. The core system is completely UI-agnostic.

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Custom UI       │     │  Matrix Web UI   │     │  Android UI      │
│  (your impl)     │     │  (reference)     │     │  (reference)     │
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │
         └────────────┬───────────┴────────────┬───────────┘
                      │                        │
              ┌───────┴────────┐       ┌───────┴────────┐
              │ Protocol       │       │ UI Manager     │
              │ Adapter        │       │ (discovery,    │
              │ (WS/HTTP)      │       │  lifecycle)    │
              └───────┬────────┘       └───────┬────────┘
                      │                        │
              ┌───────┴────────────────────────┴───────┐
              │         Phantom Core (:8765 / :8082)    │
              └─────────────────────────────────────────┘
```

---

## Architecture Components

### Base UI Interface (`ui/ui_framework/base_ui.py`)

Abstract base class `PhantomUI` that all UI implementations must extend:

```python
from ui.ui_framework.base_ui import PhantomUI

class MyCustomUI(PhantomUI):
    def start(self) -> bool: ...
    def stop(self) -> bool: ...
    def connect_to_phantom(self) -> bool: ...
    def disconnect_from_phantom(self) -> bool: ...
    def display_system_status(self, status: dict) -> None: ...
    def display_task_result(self, result: dict) -> None: ...
    def submit_task(self, task: dict) -> str: ...
    def set_execution_mode(self, mode: str) -> bool: ...
```

**Required abstract methods:**

| Method | Purpose |
|--------|---------|
| `start()` | Initialize and launch the UI |
| `stop()` | Gracefully shut down the UI |
| `connect_to_phantom()` | Establish backend connection |
| `disconnect_from_phantom()` | Close backend connection |
| `display_system_status(status)` | Render system status to user |
| `display_task_result(result)` | Render task result to user |
| `submit_task(task)` | Submit a task to the backend |
| `set_execution_mode(mode)` | Switch execution mode |

**Configuration dict** passed to `__init__`:

```python
phantom_config = {
    "socket_host": "localhost",
    "socket_port": 8082,
    "controller_host": "localhost",
    "controller_port": 8765,
    "protocol": "websocket",         # websocket | http
    "execution_mode": "AUTO"          # AUTO | HYBRID | MANUAL
}
```

### Protocol Adapter (`ui/ui_framework/protocol_adapter.py`)

Handles all communication between the UI and Phantom core:

- **WebSocket** — Real-time bidirectional (default, port 8082)
- **HTTP REST** — Request/response (port 8765)
- **Custom** — Extensible via protocol plugins

Key capabilities:
- Automatic reconnection
- Message routing by type
- Request/response correlation via message IDs
- Thread-safe operation

### UI Manager (`ui/ui_framework/ui_manager.py`)

Discovers, loads, and manages UI implementations at runtime:

- Auto-discovers UIs in `ui/redblue_matrix/` and `ui/examples/`
- Dynamic class loading from Python modules
- Supports multiple concurrent UIs
- Configuration management per UI instance

---

## Reference Implementations

### Matrix Web UI (`ui/redblue_matrix/matrix-web-ui/`)
- Web-based dashboard
- Real-time worker status and task monitoring
- Served on port 8080

### Matrix Android UI (`ui/redblue_matrix/phantom-matrix-android/`)
- Native Android application
- Remote monitoring and control
- WebSocket connection to controller

---

## Building a Custom UI

### Step 1: Create your UI directory

```
ui/examples/my_custom_ui/
├── __init__.py
├── my_ui.py
└── templates/        # (optional, for web UIs)
```

### Step 2: Implement the interface

```python
# ui/examples/my_custom_ui/my_ui.py

from ui.ui_framework.base_ui import PhantomUI
from ui.ui_framework.protocol_adapter import ProtocolAdapter
from typing import Dict, Any

class MyCustomUI(PhantomUI):
    def __init__(self, phantom_config: Dict[str, Any]):
        super().__init__(phantom_config)
        self.adapter = ProtocolAdapter(phantom_config)

    def start(self) -> bool:
        self.logger.info("Starting custom UI...")
        return self.connect_to_phantom()

    def stop(self) -> bool:
        self.disconnect_from_phantom()
        self.logger.info("Custom UI stopped")
        return True

    def connect_to_phantom(self) -> bool:
        self.connected = self.adapter.connect()
        return self.connected

    def disconnect_from_phantom(self) -> bool:
        result = self.adapter.disconnect()
        self.connected = False
        return result

    def display_system_status(self, status: dict) -> None:
        print(f"System: {status}")

    def display_task_result(self, result: dict) -> None:
        print(f"Result: {result}")

    def submit_task(self, task: dict) -> str:
        return self.adapter.submit_task(task)

    def set_execution_mode(self, mode: str) -> bool:
        self.execution_mode = mode
        return self.adapter.set_execution_mode(mode)
```

### Step 3: Register and launch

```python
from ui.ui_framework.ui_manager import UIManager

manager = UIManager()
manager.discover_uis()

# Load your UI
config = {
    "socket_host": "localhost",
    "socket_port": 8082,
    "controller_host": "localhost",
    "controller_port": 8765,
    "protocol": "websocket",
    "execution_mode": "AUTO"
}

ui = manager.load_ui("my_custom_ui", config)
ui.start()
```

---

## Execution Modes

UIs must respect the current execution mode:

| Mode | Behavior |
|------|----------|
| **AUTO** | System executes tasks automatically; UI displays status |
| **HYBRID** | System proposes actions; UI presents for human approval |
| **MANUAL** | Human initiates all actions via UI; system awaits commands |

The execution mode is set via `set_execution_mode()` and enforced by the core, not the UI.

---

## Protocol Messages

All messages between UI and core use JSON over WebSocket or HTTP:

### Task Submission
```json
{
    "type": "task_submit",
    "id": "msg-001",
    "payload": {
        "task_type": "compute",
        "data": { ... },
        "priority": "normal"
    }
}
```

### System Status
```json
{
    "type": "system_status",
    "payload": {
        "workers": 3,
        "tasks_queued": 12,
        "tasks_running": 2,
        "execution_mode": "AUTO"
    }
}
```

### Task Result
```json
{
    "type": "task_result",
    "payload": {
        "task_id": "task-abc123",
        "status": "completed",
        "result": { ... }
    }
}
```

---

## Cross-References

- [ARCHITECTURE.md](./ARCHITECTURE.md) — Full system architecture
- [README.md](../README.md) — Project overview
- [INSTALLATION.md](../INSTALLATION.md) — Installation guide
