# Simple Web UI Example

A minimal HTML/JavaScript implementation demonstrating the Phantom UI Framework.

## Features

- Clean, simple web interface
- Task submission and monitoring
- Execution mode selection (AUTO/HYBRID/MANUAL)
- Worker status display
- Task approval/rejection for HYBRID mode

## Usage

1. Open `index.html` in a web browser
2. The interface will attempt to connect to the Phantom backend
3. Submit tasks using the form
4. Monitor task status and worker availability

## Implementation Notes

This example demonstrates:
- Basic UI framework integration
- Simulated backend communication (in a real implementation, this would use WebSocket/HTTP)
- Event handling and state management
- Responsive design

## Development

To extend this UI:
1. Replace the simulated backend calls with real API calls
2. Add more sophisticated state management
3. Implement real-time updates using WebSocket
4. Add authentication and security features

## Framework Integration

This UI can be loaded by the UIManager:

```python
from ui.ui_framework import UIManager

manager = UIManager()
manager.discover_uis()
ui = manager.load_ui('simple_web_ui', config)
ui.start()
```