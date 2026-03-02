# Terminal UI Example

A command-line interface implementation demonstrating the Phantom UI Framework.

## Features

- Interactive command-line interface using Python's `cmd` module
- Task submission and monitoring
- Execution mode management
- Worker status display
- Task approval/rejection for HYBRID mode
- Comprehensive help system

## Usage

Run the terminal UI:

```bash
python terminal_ui.py
```

Available commands:
- `connect` - Connect to Phantom backend
- `disconnect` - Disconnect from Phantom backend
- `status` - Show system status
- `mode <AUTO|HYBRID|MANUAL>` - Set execution mode
- `submit <name> <command>` - Submit a task
- `tasks [task_id]` - List tasks or show task details
- `workers` - List available workers
- `approve <task_id> [worker_id]` - Approve a pending task
- `reject <task_id>` - Reject a pending task
- `help` - Show help
- `quit` - Exit the interface

## Example Session

```
phantom> connect
Connecting to Phantom at localhost:8080...
✅ Connected to Phantom backend

phantom> mode HYBRID
🔄 Execution mode changed: AUTO → HYBRID

phantom> submit "test_task" "echo Hello World"
📤 Task 'test_task' submitted to Phantom

phantom> tasks
📋 Tasks (1 total):
  📤 task_1640995200_0: test_task (submitted)

phantom> workers
👷 Workers (3 total):
  🟢 worker-1: GPU Worker 1 (online) | GPU: (auto-detected)
  🟢 worker-2: CPU Worker 1 (online)
  🔴 worker-3: GPU Worker 2 (offline) | GPU: (auto-detected)

phantom> quit
Goodbye!
```

## Implementation Notes

This example demonstrates:
- Integration with the Phantom UI Framework
- Command-line interface design
- State management
- Event handling
- Simulated backend communication

## Framework Integration

This UI can be loaded by the UIManager:

```python
from ui.ui_framework import UIManager

manager = UIManager()
manager.discover_uis()
ui = manager.load_ui('terminal_ui', config)
ui.start()
```

## Extending the Terminal UI

To add new commands:
1. Add a `do_<command>` method
2. Optionally add a `help_<command>` method
3. Use the framework methods for backend communication

The UI automatically handles callbacks for task events, system status updates, and errors.