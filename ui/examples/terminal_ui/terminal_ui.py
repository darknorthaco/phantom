#!/usr/bin/env python3
"""
Terminal UI Example
Command-line interface demonstrating the Phantom UI Framework
"""

import cmd
import json
import time
from typing import Dict, Any, Optional
from ui.ui_framework.base_ui import PhantomUI


class TerminalUI(PhantomUI, cmd.Cmd):
    """
    Terminal-based UI for Phantom using the cmd module.

    Demonstrates:
    - Framework integration
    - Command-line interface
    - Interactive task management
    """

    UI_NAME = 'terminal_ui'
    VERSION = '1.0.0'

    intro = """
╔══════════════════════════════════════════════════════════╗
║              Phantom Terminal UI                        ║
║              Command-Line Interface                     ║
╚══════════════════════════════════════════════════════════╝

Type 'help' or '?' for commands.
Type 'connect' to connect to Phantom backend.
"""

    prompt = 'phantom> '

    def __init__(self, phantom_config: Dict[str, Any]):
        # Initialize base UI first
        PhantomUI.__init__(self, phantom_config)

        # Initialize cmd after base UI
        cmd.Cmd.__init__(self)

        # UI state
        self.tasks = {}
        self.workers = []

        # Set up callbacks
        self.set_callback('task_received', self._on_task_received)
        self.set_callback('task_completed', self._on_task_completed)
        self.set_callback('system_status', self._on_system_status)
        self.set_callback('error', self._on_error)

    def start(self) -> bool:
        """Start the terminal UI."""
        print("Starting Phantom Terminal UI...")
        if not self.connect_to_phantom():
            print("Warning: Could not connect to Phantom backend. Running in offline mode.")
        else:
            print("Connected to Phantom backend.")

        # Start the command loop
        try:
            self.cmdloop()
        except KeyboardInterrupt:
            print("\nShutting down...")
            return self.stop()

        return True

    def stop(self) -> bool:
        """Stop the terminal UI."""
        print("Stopping Phantom Terminal UI...")
        self.disconnect_from_phantom()
        return True

    def connect_to_phantom(self) -> bool:
        """Connect to phantom backend."""
        print(f"Connecting to Phantom at {self.config['controller_host']}:{self.config['controller_port']}...")

        # In a real implementation, this would establish actual connection
        # For demo purposes, we'll simulate connection
        try:
            # Simulate connection delay
            time.sleep(1)
            self.connected = True
            print("✅ Connected to Phantom backend")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def disconnect_from_phantom(self) -> bool:
        """Disconnect from phantom backend."""
        if self.connected:
            print("Disconnecting from Phantom...")
            self.connected = False
            print("✅ Disconnected")
        return True

    def submit_task(self, task_data: Dict[str, Any]) -> str:
        """Submit a task for execution."""
        task_id = f"task_{int(time.time())}_{len(self.tasks)}"

        task = {
            'id': task_id,
            'name': task_data.get('name', 'Unnamed Task'),
            'command': task_data.get('command', ''),
            'status': 'submitted',
            'submitted_at': time.time()
        }

        self.tasks[task_id] = task

        if self.connected:
            print(f"📤 Task '{task['name']}' submitted to Phantom")
        else:
            print(f"📝 Task '{task['name']}' queued (offline mode)")

        return task_id

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        return {
            'connected': self.connected,
            'execution_mode': self.execution_mode,
            'active_tasks': len([t for t in self.tasks.values() if t['status'] == 'running']),
            'total_tasks': len(self.tasks),
            'workers_online': len([w for w in self.workers if w.get('status') == 'online'])
        }

    def set_execution_mode(self, mode: str) -> bool:
        """Set execution mode."""
        if mode not in ['AUTO', 'HYBRID', 'MANUAL']:
            print(f"❌ Invalid mode: {mode}")
            return False

        old_mode = self.execution_mode
        self.execution_mode = mode

        if self.connected:
            print(f"🔄 Execution mode changed: {old_mode} → {mode}")
        else:
            print(f"📝 Mode set to {mode} (will apply when connected)")

        return True

    def get_available_workers(self) -> list:
        """Get list of available workers."""
        # Simulate worker data
        if not self.workers:
            self.workers = [
                {'id': 'worker-1', 'name': 'GPU Worker 1', 'status': 'online', 'gpu': 'RTX 3080'},
                {'id': 'worker-2', 'name': 'CPU Worker 1', 'status': 'online', 'gpu': 'None'},
                {'id': 'worker-3', 'name': 'GPU Worker 2', 'status': 'offline', 'gpu': 'RTX 4070'}
            ]

        return self.workers

    def approve_task(self, task_id: str, approved: bool, worker_id: Optional[str] = None) -> bool:
        """Approve or reject a task."""
        if task_id not in self.tasks:
            print(f"❌ Task {task_id} not found")
            return False

        task = self.tasks[task_id]
        if task['status'] != 'pending_approval':
            print(f"❌ Task {task_id} is not pending approval")
            return False

        task['status'] = 'approved' if approved else 'rejected'
        task['approved_at'] = time.time()
        if worker_id:
            task['assigned_worker'] = worker_id

        action = "approved" if approved else "rejected"
        print(f"✅ Task '{task['name']}' {action}")

        return True

    # Command handlers
    def do_connect(self, arg):
        """Connect to Phantom backend: connect"""
        if self.connect_to_phantom():
            print("Successfully connected!")
        else:
            print("Connection failed.")

    def do_disconnect(self, arg):
        """Disconnect from Phantom backend: disconnect"""
        if self.disconnect_from_phantom():
            print("Successfully disconnected!")
        else:
            print("Disconnect failed.")

    def do_status(self, arg):
        """Show system status: status"""
        status = self.get_system_status()
        print("\n📊 System Status:")
        print(f"  Connected: {'✅' if status['connected'] else '❌'}")
        print(f"  Execution Mode: {status['execution_mode']}")
        print(f"  Active Tasks: {status['active_tasks']}")
        print(f"  Total Tasks: {status['total_tasks']}")
        print(f"  Workers Online: {status['workers_online']}")

    def do_mode(self, arg):
        """Set execution mode: mode <AUTO|HYBRID|MANUAL>"""
        if not arg:
            print(f"Current mode: {self.execution_mode}")
            print("Usage: mode <AUTO|HYBRID|MANUAL>")
            return

        mode = arg.upper()
        if self.set_execution_mode(mode):
            print(f"Mode set to: {mode}")
        else:
            print(f"Invalid mode: {mode}")

    def do_submit(self, arg):
        """Submit a task: submit <name> <command>"""
        parts = arg.split(' ', 1)
        if len(parts) < 2:
            print("Usage: submit <name> <command>")
            return

        name, command = parts
        task_data = {
            'name': name,
            'command': command
        }

        task_id = self.submit_task(task_data)
        print(f"Task submitted with ID: {task_id}")

    def do_tasks(self, arg):
        """List tasks: tasks [task_id]"""
        if arg:
            # Show specific task
            task_id = arg
            if task_id in self.tasks:
                task = self.tasks[task_id]
                print(f"\n📋 Task {task_id}:")
                print(f"  Name: {task['name']}")
                print(f"  Command: {task['command']}")
                print(f"  Status: {task['status']}")
                print(f"  Submitted: {time.ctime(task['submitted_at'])}")
                if 'approved_at' in task:
                    print(f"  Approved: {time.ctime(task['approved_at'])}")
                if 'assigned_worker' in task:
                    print(f"  Worker: {task['assigned_worker']}")
            else:
                print(f"Task {task_id} not found")
        else:
            # List all tasks
            if not self.tasks:
                print("No tasks submitted yet")
                return

            print(f"\n📋 Tasks ({len(self.tasks)} total):")
            for task_id, task in self.tasks.items():
                status_icon = {
                    'submitted': '📤',
                    'running': '⚙️',
                    'completed': '✅',
                    'failed': '❌',
                    'pending_approval': '⏳',
                    'approved': '👍',
                    'rejected': '👎'
                }.get(task['status'], '❓')

                print(f"  {status_icon} {task_id}: {task['name']} ({task['status']})")

    def do_workers(self, arg):
        """List workers: workers"""
        workers = self.get_available_workers()

        if not workers:
            print("No workers available")
            return

        print(f"\n👷 Workers ({len(workers)} total):")
        for worker in workers:
            status_icon = '🟢' if worker['status'] == 'online' else '🔴'
            gpu_info = f" | GPU: {worker['gpu']}" if worker.get('gpu') != 'None' else ""
            print(f"  {status_icon} {worker['id']}: {worker['name']} ({worker['status']}){gpu_info}")

    def do_approve(self, arg):
        """Approve a task: approve <task_id> [worker_id]"""
        parts = arg.split()
        if not parts:
            print("Usage: approve <task_id> [worker_id]")
            return

        task_id = parts[0]
        worker_id = parts[1] if len(parts) > 1 else None

        if self.approve_task(task_id, True, worker_id):
            worker_msg = f" (assigned to {worker_id})" if worker_id else ""
            print(f"Task {task_id} approved{worker_msg}")
        else:
            print(f"Failed to approve task {task_id}")

    def do_reject(self, arg):
        """Reject a task: reject <task_id>"""
        if not arg:
            print("Usage: reject <task_id>")
            return

        if self.approve_task(arg, False):
            print(f"Task {arg} rejected")
        else:
            print(f"Failed to reject task {arg}")

    def do_quit(self, arg):
        """Exit the terminal UI: quit"""
        print("Goodbye!")
        return True

    def do_exit(self, arg):
        """Exit the terminal UI: exit"""
        return self.do_quit(arg)

    # Callback handlers
    def _on_task_received(self, task_data):
        """Handle task received event."""
        task_id = task_data.get('id')
        if task_id:
            self.tasks[task_id] = {
                'id': task_id,
                'name': task_data.get('name', 'Unknown'),
                'command': task_data.get('command', ''),
                'status': 'received',
                'received_at': time.time()
            }

            if self.execution_mode == 'HYBRID':
                self.tasks[task_id]['status'] = 'pending_approval'
                print(f"\n⏳ Task '{self.tasks[task_id]['name']}' requires approval")
                print(f"   Use 'approve {task_id}' or 'reject {task_id}'")
            else:
                print(f"\n📥 Task '{self.tasks[task_id]['name']}' received")

    def _on_task_completed(self, result_data):
        """Handle task completed event."""
        task_id = result_data.get('task_id')
        if task_id and task_id in self.tasks:
            task = self.tasks[task_id]
            task['status'] = 'completed' if result_data.get('success') else 'failed'
            task['completed_at'] = time.time()
            task['result'] = result_data.get('result')

            status_icon = '✅' if result_data.get('success') else '❌'
            print(f"\n{status_icon} Task '{task['name']}' completed")

    def _on_system_status(self, status_data):
        """Handle system status update."""
        # Update internal state if needed
        pass

    def _on_error(self, error_data):
        """Handle error event."""
        print(f"\n❌ Error: {error_data.get('message', 'Unknown error')}")

    # Help commands
    def help_connect(self):
        print("Connect to Phantom backend")

    def help_disconnect(self):
        print("Disconnect from Phantom backend")

    def help_status(self):
        print("Show current system status")

    def help_mode(self):
        print("Set execution mode: AUTO, HYBRID, or MANUAL")

    def help_submit(self):
        print("Submit a task: submit <name> <command>")

    def help_tasks(self):
        print("List all tasks or show details of a specific task")

    def help_workers(self):
        print("List available workers")

    def help_approve(self):
        print("Approve a pending task: approve <task_id> [worker_id]")

    def help_reject(self):
        print("Reject a pending task: reject <task_id>")


if __name__ == '__main__':
    # Example usage
    config = {
        'socket_host': 'localhost',
        'socket_port': 8082,
        'controller_host': 'localhost',
        'controller_port': 8765,
        'execution_mode': 'AUTO'
    }

    ui = TerminalUI(config)
    ui.start()