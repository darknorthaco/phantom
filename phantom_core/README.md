# 🚀 Phantom Distributed Compute Fabric - Enhanced Edition

## ⚠️ Important: Repository Governance

**This is Phantom_PTR** - a **public sandbox** for Phantom Distributed exploration and community contribution.

Before using or contributing to this repository, please read:
- **[PHANTOM_ETHOS.md](./PHANTOM_ETHOS.md)** - Core principles
- **[PHANTOM_COMMANDMENTS.md](./PHANTOM_COMMANDMENTS.md)** - Operational rules
- **[GOVERNANCE.md](./GOVERNANCE.md)** - Repository governance
- **[CONTRIBUTING.md](./CONTRIBUTING.md)** - How to contribute
- **[AGENT_USAGE_GUIDE.md](./AGENT_USAGE_GUIDE.md)** - 🆕 Agent usage best practices
- **[BRANCH_INVENTORY.md](./BRANCH_INVENTORY.md)** - 🆕 Branch management strategy

**Key Points:**
- 🔒 This is a **public sandbox**, NOT the production Phantom codebase
- 📝 Default mode is **ANALYSIS-ONLY** - propose changes, don't apply without authorization
- 👤 **Human authority** - Machines propose, humans decide
- 🎯 **Sovereignty, transparency, reversibility** - Core to everything we do

See [GITPRO_ANALYSIS_MODE.md](./GITPRO_ANALYSIS_MODE.md) for detailed operational guidelines.

---

## Overview

**Phantom Distributed** is a comprehensive distributed computing platform designed for heterogeneous GPU clusters. This enhanced edition provides intelligent task routing, socket-based communication, and ground-up security integration.

### ✨ New: Unified Installation Wizard

Phantom now includes a modular, cross-platform installation wizard that makes setup a breeze:
- **Single entry point** for complete ecosystem installation
- **Cross-platform support** (Linux, macOS, Windows)
- **Interactive CLI** with guided configuration
- **Automatic worker discovery** on your network
- **Modular components** - install only what you need
- **Virtual environment management** with dependency handling
- **Post-installation validation** and health checks

> **UI Source:** The RedBlue UI is maintained in the private repository:
> https://github.com/darknorthaco/redblue-private

See [Quick Start](#-quick-start) for installation instructions.

## 🎯 Your Specific Setup

This package is optimized for your dual-machine topology:

### 🖥️ Fedora Server (192.168.1.103)
- **Hardware**: i7-2700K, 32GB DDR3, GTX 1080, AMD FirePro W9100
- **Role**: Controller + Storage Hub + Legacy Compute + LLM Task Master
- **Workers**: 3 local workers (GTX 1080, FirePro W9100, Storage Hub)

### 💻 Windows Main PC
- **Hardware**: i9-13900K, 64GB DDR5, RTX 5080, RTX 5060  
- **Role**: High-Performance Compute Cluster
- **Workers**: 2 remote workers (RTX 5080 primary, RTX 5060 secondary)

## ✨ Key Features

### 🧠 Intelligent Task Routing
- **LLM Task Master** running on GTX 1080 for AI-powered routing decisions
- **Smart Programming** fallback with GPU-aware algorithms
- **Performance Hierarchy** optimization for heterogeneous hardware

### 🔌 Socket Infrastructure
- **WebSocket Communication** for real-time coordination
- **Hybrid Mode** supporting both AI and programmatic routing
- **Multi-client Support** (UI, workers, task master, controller)

### 🔒 Ground-up Security
- **Multiple Security Levels**: Disabled → Basic → Enhanced → Enterprise
- **Authentication Methods**: API Keys, JWT Tokens, Certificates
- **Rate Limiting & IP Filtering** with audit logging
- **Easy Enable/Disable** without breaking socket architecture

### 🎮 GPU-Specific Optimizations
- **RTX 50-Series Plugin**: 4th gen Tensor cores, DLSS 3+, AV1 encoding
- **GTX 1080 Plugin**: Proven stability, LLM Task Master capability
- **FirePro Plugin**: 16GB memory specialist for large datasets
- **General Plugin**: Universal fallback support

## 🚀 Quick Start

### Option 1: Unified Installation Wizard (Recommended)

The easiest way to install Phantom is using our unified installation wizard:

**Linux/Mac:**
```bash
cd installer
./phantom_installer.sh
```

**Windows:**
```powershell
cd installer
.\phantom_installer.ps1
```

The wizard will guide you through:
- System requirements check
- Component selection (Core, Workers, UI, etc.)
- Network configuration
- Worker discovery
- Virtual environment setup
- Post-installation configuration

See [installer/README.md](installer/README.md) for detailed documentation.

### Uninstalling Phantom

To uninstall Phantom, use the unified uninstallation wizard:

**Linux/Mac:**
```bash
cd installer
./phantom_uninstaller.sh          # Safe mode (preserves configs)
./phantom_uninstaller.sh --mode full   # Complete removal
```

**Windows:**
```powershell
cd installer
.\phantom_uninstaller.ps1          # Safe mode (preserves configs)
.\phantom_uninstaller.ps1 -Mode full   # Complete removal
```

See [installer/UNINSTALLER.md](installer/UNINSTALLER.md) for detailed uninstallation documentation.

### Option 2: Manual Setup (5 Minutes)

### 1. Start Fedora Server (Controller + Local Workers)
```bash
cd phantom-distributed

# Complete system startup
./start_complete_phantom.sh

# Verify status
./start_complete_phantom.sh status
```

### 2. Start Windows Workers
```powershell
# RTX 5080 Worker
cd windows-worker
copy worker_config_network.json windows_worker\worker_config.json
.\run_worker.ps1

# RTX 5060 Worker (new terminal)
mkdir rtx5060_instance
copy worker_config_rtx5060.json rtx5060_instance\worker_config.json
cd rtx5060_instance
..\run_worker.ps1
```

### 3. Verify Complete System
```bash
# Check all 5 workers connected
curl http://192.168.1.103:8080/workers

# View system dashboard
curl http://192.168.1.103:8080/stats
```

**🎉 Your heterogeneous GPU cluster is ready!**

## 📊 Performance Hierarchy

| GPU | Performance | Memory | Specialization |
|-----|-------------|--------|----------------|
| **RTX 5080** | ~165 TFLOPS | 24GB | Large models, real-time AI, training |
| **RTX 5060** | ~85 TFLOPS | 16GB | Batch processing, medium models |
| **GTX 1080** | ~9 TFLOPS | 8GB | Stable inference, LLM Task Master |
| **FirePro W9100** | ~5.2 TFLOPS | 16GB | Large datasets, memory-intensive tasks |

## 🌐 Access Points

- **Controller API**: http://192.168.1.103:8080
- **Health Check**: http://192.168.1.103:8080/health
- **Worker Status**: http://192.168.1.103:8080/workers
- **System Stats**: http://192.168.1.103:8080/stats
- **Socket Status**: http://192.168.1.103:8080/socket/status

## 🛠️ Management Commands

```bash
# System Control
./start_complete_phantom.sh start     # Start complete system
./start_complete_phantom.sh stop      # Stop complete system
./start_complete_phantom.sh restart   # Restart complete system
./start_complete_phantom.sh status    # Show system status
./start_complete_phantom.sh health    # Run health check
./start_complete_phantom.sh logs      # Show recent logs

# Monitoring
./monitor_system.sh                   # One-time status check
./monitor_system.sh --continuous      # Continuous monitoring

# Development
./dev_tools.sh test-task             # Submit test task
./dev_tools.sh stress-test           # Run stress test
./dev_tools.sh benchmark             # Performance benchmark

# Maintenance
./backup_system.sh                   # Create system backup
./update_system.sh                   # Update system
```

## 📁 Repository Structure

```
phantom-distributed/
├── 📁 ORIGINAL CODE (Preserved)
│   ├── phantom_core/              # Enhanced FastAPI controller
│   ├── windows-worker/            # Windows worker (with network configs)
│   ├── run.py                     # Original entry point (still works)
│   └── scripts/                   # Utility scripts
│
├── 📁 LINUX WORKERS
│   ├── linux-worker/              # Complete Linux worker system
│   │   ├── linux_worker/          # Core worker implementation
│   │   ├── plugins/               # GPU-specific plugins
│   │   ├── instances/             # Worker instances (auto-created)
│   │   └── deploy_workers.sh      # Deployment automation
│
├── 📁 SOCKET INFRASTRUCTURE
│   ├── socket_infrastructure/      # WebSocket server and clients
│   └── start_hybrid_mode.sh       # Hybrid mode startup
│
├── 📁 LLM TASK MASTER
│   └── llm_taskmaster/            # AI-powered task routing
│
├── 📁 SECURITY FRAMEWORK
│   ├── security_framework/        # Ground-up security integration
│   └── security_config.json       # Security configuration
│
├── 📁 INTEGRATION & DEPLOYMENT
│   ├── run_integrated_phantom.py  # Complete integrated system
│   ├── start_complete_phantom.sh  # Full system startup
│   ├── complete_integration.sh    # Integration setup
│   ├── TOPOLOGY_SETUP.md          # Your hardware topology
│   ├── DEPLOYMENT_GUIDE.md        # Step-by-step deployment
│   └── README_COMPLETE.md          # Comprehensive documentation
│
└── 📁 MONITORING & TOOLS
    ├── monitor_system.sh          # System monitoring
    ├── backup_system.sh           # Backup utilities
    ├── update_system.sh           # Update management
    └── dev_tools.sh               # Development tools
```

## 🔧 Configuration Options

### Security Levels
```bash
# Development (default)
export SECURITY_LEVEL=disabled
./start_complete_phantom.sh

# Basic security
export SECURITY_LEVEL=development
./start_complete_phantom.sh

# Production security
export SECURITY_LEVEL=production
./start_complete_phantom.sh
```

### LLM Task Master
```bash
# Enable AI-powered routing
export ENABLE_LLM_TASKMASTER=true
./start_complete_phantom.sh

# Disable (use smart programming only)
export ENABLE_LLM_TASKMASTER=false
./start_complete_phantom.sh
```

### Execution Modes

Phantom supports **three execution modes** that determine how task routing decisions are made:

#### AUTO Mode (Default)
Fully automated task routing with AI-powered or algorithmic worker selection.
```bash
export PHANTOM_EXECUTION_MODE=auto
./start_complete_phantom.sh
```

**Features:**
- Zero-latency task execution
- LLM Task Master integration (optional)
- Smart programming fallback
- Optimal for production workloads

#### HYBRID Mode
Human-governed workflow where system proposes workers but requires approval.
```bash
export PHANTOM_EXECUTION_MODE=hybrid
export HYBRID_PROPOSAL_TIMEOUT=300  # 5 minutes
./start_complete_phantom.sh
```

**Features:**
- System generates worker recommendations
- Human approval required before execution
- Override capability for human selection
- Batch approval support
- Ideal for development and testing

**API Workflow:**
```python
# 1. Submit task
response = requests.post("/tasks/submit", json={
    "task_type": "ml_inference",
    "parameters": {...},
    "execution_mode": "hybrid"
})
task_id = response.json()["task_id"]

# 2. Review proposal
proposals = requests.get("/tasks/proposals").json()

# 3. Approve
requests.post(f"/tasks/{task_id}/approve", json={
    "approver": "operator-1",
    "approval_reason": "Verified optimal for workload"
})
```

#### MANUAL Mode
Full human control where users directly specify which worker executes each task.
```bash
export PHANTOM_EXECUTION_MODE=manual
./start_complete_phantom.sh
```

**Features:**
- Direct worker selection by human
- Validation and warnings for suboptimal choices
- Override safeguards available
- Perfect for debugging and experimentation

**API Usage:**
```python
# Submit task with explicit worker
response = requests.post("/tasks/submit", json={
    "task_type": "training",
    "parameters": {...},
    "execution_mode": "manual",
    "target_worker": "worker-rtx-5080"
})
```

**Mode Comparison:**
| Mode | Human Involvement | Latency | Best For |
|------|------------------|---------|----------|
| AUTO | None (monitoring only) | Lowest | Production |
| HYBRID | Approval required | Medium | Development, Testing |
| MANUAL | Direct selection | Low | Debugging, Training |

For complete specification, see [PHANTOM_EXECUTION_MODES_AND_API_SPEC.md](./PHANTOM_EXECUTION_MODES_AND_API_SPEC.md).

## 🎯 Task Routing Examples

### Automatic Intelligent Routing
```bash
# Large model inference → RTX 5080
curl -X POST http://192.168.1.103:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "large_model_inference",
    "parameters": {"model_size": "70B"}
  }'

# Data processing → FirePro W9100
curl -X POST http://192.168.1.103:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "data_processing",
    "parameters": {"dataset_size_gb": 12}
  }'

# Stable inference → GTX 1080
curl -X POST http://192.168.1.103:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "stable_inference",
    "parameters": {"model_path": "production_model"}
  }'
```

## 📈 Expected Performance

### Throughput
- **ML Inference**: 100-500 samples/second
- **Training**: 2-10x faster than single GPU
- **Data Processing**: 50-200 GB/hour
- **Image Processing**: 1000-5000 images/minute

### Latency
- **Task Routing**: <100ms (LLM Task Master)
- **Worker Assignment**: <50ms (smart programming)
- **Cross-machine Communication**: <10ms
- **Task Startup**: <1s

## 🐛 Troubleshooting

### Quick Diagnostics
```bash
# System health check
./start_complete_phantom.sh health

# Check connectivity
ping 192.168.1.103
curl http://192.168.1.103:8080/health

# Monitor resources
./monitor_system.sh --continuous
```

### Common Issues

**Workers not connecting:**
```bash
# Check firewall
sudo firewall-cmd --add-port=8080-8120/tcp --permanent
sudo firewall-cmd --reload
```

**GPU not detected:**
```bash
# NVIDIA
nvidia-smi

# AMD
rocm-smi --showid
lspci | grep VGA
```

**Socket issues:**
```bash
# Check socket status
curl http://192.168.1.103:8080/socket/status
```

## 📚 Documentation

### Core Documentation
- **[TOPOLOGY_SETUP.md](TOPOLOGY_SETUP.md)** - Your specific hardware configuration
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Step-by-step deployment instructions
- **[README_COMPLETE.md](README_COMPLETE.md)** - Comprehensive feature documentation

### Governance & Philosophy
- **[PHANTOM_ETHOS.md](PHANTOM_ETHOS.md)** - Foundational principles (sovereignty, transparency, human control)
- **[PHANTOM_COMMANDMENTS.md](PHANTOM_COMMANDMENTS.md)** - Ten operational rules
- **[PHANTOM_SOUL.md](PHANTOM_SOUL.md)** - Philosophical foundation
- **[GOVERNANCE.md](GOVERNANCE.md)** - Repository governance model
- **[GITPRO_ANALYSIS_MODE.md](GITPRO_ANALYSIS_MODE.md)** - Analysis-only operational guidelines

### Contributing
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute to this project
- **[PROPOSAL_TEMPLATE.md](PROPOSAL_TEMPLATE.md)** - Template for proposing changes
- **[adr/](./adr/)** - Architecture Decision Records

## 🔄 Migration from Original

### Zero-Risk Migration
1. **Test in parallel** - Run enhanced version alongside original
2. **Gradual adoption** - Start with Linux workers only
3. **Feature toggle** - Enable advanced features when ready
4. **Fallback ready** - Original code always available

### Compatibility
- ✅ **100% API compatible** with your existing code
- ✅ **Same endpoints** and response formats
- ✅ **Existing Windows workers** continue to work
- ✅ **No breaking changes** to your current setup

## 🚀 What's New in Enhanced Edition

### Core Enhancements
- **Complete Linux Worker Implementation** - Full GPU detection and plugin system
- **Socket Infrastructure** - WebSocket communication for hybrid AI/programmatic routing
- **LLM Task Master** - Lightweight AI running on GTX 1080 for intelligent routing
- **Ground-up Security** - Multi-level security framework with easy enable/disable
- **GPU-Specific Plugins** - Optimized plugins for each GPU type in your cluster

### Operational Improvements
- **One-Command Deployment** - Complete system startup with single script
- **Comprehensive Monitoring** - Real-time system monitoring and health checks
- **Automated Backup/Restore** - System state management and recovery
- **Development Tools** - Testing, benchmarking, and debugging utilities
- **Docker Support** - Containerized deployment option

### Performance Optimizations
- **Heterogeneous GPU Optimization** - Specialized handling for each GPU type
- **Network Topology Awareness** - Cross-machine communication optimization
- **Memory Management** - GPU-specific memory optimization strategies
- **Task Routing Intelligence** - AI-powered and rule-based routing algorithms

## 💰 Licensing

### 🆓 Open Source (MIT License)
**Perfect for:**
- Personal projects and learning
- Academic research and education
- Non-commercial experimentation
- Community contributions

### 💼 Commercial License Available
**Required for:**
- Business and enterprise use
- Commercial products and services
- White-label redistribution
- Custom branding and support

**[📄 View Licensing Details](README-LICENSING.md)**

### 🧠 Framework IP
Phantom's distinctive component names — "Phantom Distributed Compute Fabric",
"LLM Task Master", and "Phantom Core" — are proprietary trademarks of Dark
North Co. The specific source code implementations in this repository are
also protected by copyright. Commercial use of those implementations requires
a commercial license.
See [README-LICENSING.md](README-LICENSING.md#-framework-ip-protection) for details.

### Commercial License Tiers
- **Professional**: $300/year - Small business use
- **Enterprise**: $1,500/year - Large organizations
- **OEM/White-label**: Custom pricing - Redistribution rights

**[📋 View Full Commercial License](LICENSE-COMMERCIAL.md)**

For licensing inquiries: licensing@darknorthco.com

## 🎉 Ready to Deploy!

Your enhanced Phantom Distributed Compute Fabric provides:

- ✅ **Preserved Original Functionality** - All existing features work unchanged
- ✅ **Enhanced Capabilities** - Linux workers, socket infrastructure, AI routing
- ✅ **Production Ready** - Security, monitoring, backup/restore
- ✅ **Future Proof** - Socket infrastructure for advanced features

**Start with what you know works, then enhance as you're ready!** 🚀

---

**Your heterogeneous compute cluster awaits!** 🎮🖥️💻
