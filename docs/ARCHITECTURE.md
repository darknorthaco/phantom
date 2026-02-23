# Phantom Architecture

> System architecture overview for the Phantom Distributed Compute Fabric.

---

## High-Level Overview

Phantom is a distributed compute platform that orchestrates workloads across heterogeneous nodes (Linux, Windows, macOS) with optional GPU acceleration, governed by a strict ethical and operational framework.

```
┌─────────────────────────────────────────────────────────┐
│                     Phantom Controller                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Controller    │  │ Orchestrator │  │ Execution    │  │
│  │ API (HTTP/WS) │  │              │  │ Modes        │  │
│  │ :8765         │  │              │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                  │          │
│  ┌──────┴─────────────────┴──────────────────┴───────┐  │
│  │              State Management Layer               │  │
│  └───────────────────────┬───────────────────────────┘  │
│                          │                              │
│  ┌───────────────────────┴───────────────────────────┐  │
│  │           Socket Infrastructure (:8082)            │  │
│  │           (Hybrid WebSocket Server)                │  │
│  └───────────────────────┬───────────────────────────┘  │
│                          │                              │
│  ┌──────────────┐  ┌─────┴────────┐  ┌──────────────┐  │
│  │ LLM          │  │ Security     │  │ UI Framework │  │
│  │ Taskmaster   │  │ Framework    │  │ :8080        │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────┬───────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        ┌─────┴─────┐  ┌─────┴─────┐  ┌──────┴────┐
        │ Linux     │  │ Windows   │  │ macOS     │
        │ Worker    │  │ Worker    │  │ Worker    │
        │ (GPU)     │  │           │  │           │
        └───────────┘  └───────────┘  └───────────┘
```

---

## Repository Structure

```
phantom/
├── phantom_core/                    # Core application (assimilated from phantom_ptr)
│   ├── phantom_core/                # Python package
│   │   ├── controller_api.py        # HTTP/WebSocket API server
│   │   ├── orchestrator.py          # Task distribution and scheduling
│   │   ├── execution_modes.py       # Mode management (safe/moderate/full)
│   │   ├── socket_integration.py    # Socket layer integration
│   │   └── state.py                 # System state management
│   ├── socket_infrastructure/
│   │   └── hybrid_socket_server.py  # WebSocket server for worker communication
│   ├── llm_taskmaster/
│   │   └── lightweight_llm_setup.py # AI-powered task routing
│   ├── security_framework/
│   │   └── integrated_security.py   # Authentication and authorization
│   ├── linux-worker/                # Linux worker implementation
│   ├── windows-worker/              # Windows worker configuration
│   ├── installer/                   # Platform installers
│   ├── scripts/                     # Utility scripts
│   ├── selinux/                     # SELinux policies
│   └── tests/                       # Test suite
├── ui/                              # UI layer (assimilated from redblue-private)
│   ├── ui_framework/                # Abstract UI framework
│   │   ├── base_ui.py               # Base UI interface
│   │   ├── protocol_adapter.py      # Protocol adapter for UI ↔ core
│   │   ├── ui_manager.py            # UI lifecycle management
│   │   └── __init__.py
│   ├── redblue_matrix/              # Reference Matrix UI implementation
│   │   ├── matrix-web-ui/           # Web-based Matrix UI
│   │   └── phantom-matrix-android/  # Android Matrix UI
│   └── examples/                    # Custom UI examples
├── installer/                       # Top-level installer (assimilated from rm-phantom)
│   ├── windows_gui_installer.py     # Windows GUI installer
│   ├── phantom_uninstaller.py       # Cross-platform uninstaller
│   └── modules/                     # Installer modules
├── package/                         # Distribution packaging
│   ├── build_complete.{sh,bat}      # Build scripts
│   ├── install.{sh,bat}             # Install scripts
│   └── uninstall.{sh,bat}           # Uninstall scripts
├── governance/                      # Governance subdirectory
├── docs/                            # Extended documentation
└── [root governance files]          # LICENSE, README, ETHOS, etc.
```

---

## Core Components

### Controller API (`phantom_core/controller_api.py`)
- **Port:** 8765 (HTTP + WebSocket)
- **Role:** Primary API endpoint for clients and management
- Exposes REST endpoints for task submission, status, and control
- WebSocket channel for real-time updates
- Routes requests to the Orchestrator

### Orchestrator (`phantom_core/orchestrator.py`)
- **Role:** Task distribution and scheduling engine
- Manages worker pool and capability discovery
- Distributes workloads based on worker capabilities (CPU, GPU, platform)
- Handles task lifecycle: queued → running → complete/failed

### Execution Modes (`phantom_core/execution_modes.py`)
- **Safe Mode** — Read-only analysis, no system modifications
- **Moderate Mode** — Limited execution with guardrails
- **Full Mode** — Production execution with human authorization
- Mode selection enforces governance compliance at runtime

### State Management (`phantom_core/state.py`)
- Centralized system state tracking
- Worker registration and health monitoring
- Task queue and completion tracking
- Persistence for crash recovery

### Socket Infrastructure (`socket_infrastructure/hybrid_socket_server.py`)
- **Port:** 8082 (WebSocket)
- **Role:** Worker communication backbone
- Bidirectional WebSocket connections to all worker nodes
- Heartbeat/health monitoring
- Task dispatch and result collection

### LLM Taskmaster (`llm_taskmaster/lightweight_llm_setup.py`)
- AI-powered intelligent task routing
- Natural language task decomposition
- Capability matching between tasks and workers
- Lightweight local LLM integration

### Security Framework (`security_framework/integrated_security.py`)
- Token-based authentication
- Role-based access control
- Encrypted worker communication
- Audit logging for all operations

### UI Framework (`ui/ui_framework/`)
- Abstract base UI interface (`base_ui.py`)
- Protocol adapter for core ↔ UI communication (`protocol_adapter.py`)
- UI lifecycle management (`ui_manager.py`)
- Pluggable: swap UI implementations without changing core

---

## Network Topology

| Port | Protocol | Component | Purpose |
|------|----------|-----------|---------|
| 8765 | HTTP/WS | Controller API | Client access, management |
| 8082 | WebSocket | Socket Infrastructure | Worker ↔ controller communication |
| 8080 | HTTP | UI Framework | Web UI serving |

### Default Bind Behavior
- All services bind to `localhost` by default
- Production deployment should use reverse proxy (nginx/caddy)
- TLS termination at the proxy layer

---

## Data Flow

```
Client Request → Controller API (:8765)
                    │
                    ▼
              Orchestrator
              (capability matching, scheduling)
                    │
                    ▼
           Socket Infrastructure (:8082)
              (dispatch to worker)
                    │
                    ▼
              Worker Node
              (execute task, return result)
                    │
                    ▼
           Socket Infrastructure
              (collect result)
                    │
                    ▼
              Orchestrator
              (update state, notify)
                    │
                    ▼
           Controller API → Client
              (result delivery via HTTP/WS)
```

---

## Deployment Models

### Single-Node (Development)
- Controller + worker on one machine
- All ports on localhost
- No TLS required

### Multi-Node (Production)
- Controller on dedicated node
- Workers on separate machines (heterogeneous OS)
- Reverse proxy with TLS
- Firewall rules per port table above

### Containerized
- `Dockerfile` and `docker-compose.yml` in `phantom_core/`
- Controller and workers as separate containers
- Network isolation via Docker networking

---

## Cross-References

- [README.md](../README.md) — Project overview and quick start
- [INSTALLATION.md](../INSTALLATION.md) — Installation guide
- [SECURITY.md](../SECURITY.md) — Security policy
- [UI_FRAMEWORK.md](./UI_FRAMEWORK.md) — UI framework details
- [GOVERNANCE.md](../GOVERNANCE.md) — Project governance
