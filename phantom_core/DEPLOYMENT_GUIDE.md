# 🚀 Phantom Distributed Deployment Guide

## Quick Start (5 Minutes)

### 1. Deploy on Fedora Server (Controller + Local Workers)
```bash
cd phantom-distributed

# Start the complete integrated system
./start_complete_phantom.sh

# Verify everything is running
./start_complete_phantom.sh status
```

### 2. Deploy on Windows PC (Remote Workers)
```powershell
cd windows-worker

# Start RTX 5080 worker
copy worker_config_network.json windows_worker\worker_config.json
.\run_worker.ps1

# Start RTX 5060 worker (in new terminal)
mkdir rtx5060_instance
copy worker_config_rtx5060.json rtx5060_instance\worker_config.json
cd rtx5060_instance
..\run_worker.ps1
```

### 3. Verify Complete System
```bash
# Check all workers connected
curl http://192.168.1.103:8080/workers

# View system dashboard
curl http://192.168.1.103:8080/stats
```

**🎉 Your heterogeneous GPU cluster is now ready!**

---

## Detailed Deployment

### Task lifecycle (controller ↔ workers)

Distributed tasks use **worker callbacks** for authoritative completion/failure. The controller persists state in `tasks.json` (`QUEUED` → `RUNNING` → `COMPLETED` | `FAILED`). See:

- [`deployment/worker_lifecycle.md`](../deployment/worker_lifecycle.md)
- [`controller/task_ledger.md`](../controller/task_ledger.md)

### Prerequisites

#### Fedora Server Requirements
- **OS**: Fedora 35+ or RHEL 8+
- **Python**: 3.9+ with pip
- **GPU Drivers**: NVIDIA drivers + CUDA, AMD ROCm (optional)
- **Network**: Static IP configured (192.168.1.103)
- **Ports**: 8080-8120 available

#### Windows PC Requirements
- **OS**: Windows 10/11
- **Python**: 3.9+ with pip
- **GPU Drivers**: Latest NVIDIA drivers
- **Network**: Access to Fedora server

#### Network Requirements
- **Bandwidth**: Gigabit Ethernet recommended
- **Latency**: <10ms between machines
- **Firewall**: Ports 8080-8120 open on Fedora server

### Step-by-Step Deployment

#### Phase 1: Fedora Server Setup

**1. Install Dependencies**
```bash
# Update system
sudo dnf update -y

# Install Python and development tools
sudo dnf install -y python3 python3-pip python3-devel gcc git

# Install GPU drivers (if not already installed)
# NVIDIA:
sudo dnf install -y nvidia-driver nvidia-cuda-toolkit

# AMD (optional):
sudo dnf install -y rocm-opencl rocm-smi
```

**2. Clone and Setup Phantom**
```bash
# Clone the enhanced repository
git clone <your-phantom-repo-url> phantom-distributed
cd phantom-distributed

# Install Python dependencies
pip3 install --user -r requirements.txt

# Make scripts executable
chmod +x *.sh
chmod +x linux-worker/*.sh
```

**3. Configure Network**
```bash
# Open firewall ports
sudo firewall-cmd --add-port=8080/tcp --permanent  # Controller API
sudo firewall-cmd --add-port=8081/tcp --permanent  # Socket infrastructure
sudo firewall-cmd --add-port=8090-8120/tcp --permanent  # Workers
sudo firewall-cmd --reload

# Verify network configuration
ip addr show
ping 192.168.1.103  # Should respond
```

**4. Deploy Linux Workers**
```bash
# Deploy worker instances for detected GPUs
cd linux-worker
./deploy_workers.sh

# Verify worker instances created
ls -la instances/

# Expected output:
# nvidia-gpu-0/     (GTX 1080)
# amd-gpu-0/        (FirePro W9100)
# storage-hub/      (Virtual storage worker)
```

**5. Start Integrated System**
```bash
cd ..  # Back to phantom-distributed root

# Start complete system with all features
./start_complete_phantom.sh

# Expected output:
# 🚀 Phantom Complete System Startup
# ==================================
# Controller: 0.0.0.0:8080
# Socket Infrastructure: 0.0.0.0:8081
# Security Level: disabled
# LLM Task Master: true
# 
# 🎯 Starting integrated system...
# 🔌 Starting socket infrastructure...
# 🤖 Starting LLM Task Master...
# ✅ Integrated system started successfully
```

**6. Verify Fedora Server Deployment**
```bash
# Check system status
./start_complete_phantom.sh status

# Expected output:
# 📊 System Status
# ===============
# 🟢 Integrated System: RUNNING
# 🟢 Controller API: ACCESSIBLE
# 🟢 Socket Infrastructure: RUNNING
# 
# 👷 Linux Workers:
# nvidia-gpu-0         🟢 RUNNING (PID: xxxx) Port: 8090
# amd-gpu-0           🟢 RUNNING (PID: xxxx) Port: 8100
# storage-hub         🟢 RUNNING (PID: xxxx) Port: 8110

# Test API endpoints
curl http://localhost:8080/health
curl http://localhost:8080/workers
curl http://localhost:8080/socket/status
```

#### Phase 2: Windows PC Setup

**1. Install Dependencies**
```powershell
# Install Python 3.9+ from python.org
# Install Git for Windows

# Verify installations
python --version
git --version
```

**2. Setup Windows Workers**
```powershell
# Navigate to windows-worker directory
cd phantom-distributed\windows-worker

# Install Python dependencies
pip install -r requirements.txt

# Verify GPU detection
nvidia-smi
```

**3. Configure Network Connection**
```powershell
# Test connectivity to Fedora server
ping 192.168.1.103
curl http://192.168.1.103:8080/health

# If curl not available, use PowerShell:
Invoke-WebRequest -Uri "http://192.168.1.103:8080/health"
```

**4. Deploy RTX 5080 Worker (Primary)**
```powershell
# Copy network configuration
copy worker_config_network.json windows_worker\worker_config.json

# Start RTX 5080 worker
.\run_worker.ps1

# Expected output:
# 🚀 Starting Phantom Windows Worker
# Worker ID: windows-rtx5080-primary
# Controller: 192.168.1.103:8080
# GPU: RTX 5080 (24GB VRAM)
# ✅ Worker started successfully
```

**5. Deploy RTX 5060 Worker (Secondary)**
```powershell
# Open new PowerShell terminal
cd phantom-distributed\windows-worker

# Create separate instance for RTX 5060
mkdir rtx5060_instance
copy worker_config_rtx5060.json rtx5060_instance\worker_config.json
cd rtx5060_instance

# Start RTX 5060 worker
..\run_worker.ps1

# Expected output:
# 🚀 Starting Phantom Windows Worker
# Worker ID: windows-rtx5060-secondary
# Controller: 192.168.1.103:8080
# GPU: RTX 5060 (16GB VRAM)
# ✅ Worker started successfully
```

#### Phase 3: System Verification

**1. Check All Workers Connected**
```bash
# From Fedora server
curl http://localhost:8080/workers

# Expected JSON response with 5 workers:
# {
#   "workers": [
#     {"worker_id": "nvidia-gpu-0", "gpu_info": {"name": "GTX 1080"}},
#     {"worker_id": "amd-gpu-0", "gpu_info": {"name": "FirePro W9100"}},
#     {"worker_id": "storage-hub", "gpu_info": {"name": "Storage Hub"}},
#     {"worker_id": "windows-rtx5080-primary", "gpu_info": {"name": "RTX 5080"}},
#     {"worker_id": "windows-rtx5060-secondary", "gpu_info": {"name": "RTX 5060"}}
#   ]
# }
```

**2. Test Task Submission**
```bash
# Submit a test ML inference task
curl -X POST http://localhost:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "ml_inference",
    "parameters": {
      "model_path": "test_model",
      "batch_size": 4
    },
    "priority": 1
  }'

# Expected response:
# {
#   "task_id": "uuid-here",
#   "status": "queued",
#   "worker_id": "windows-rtx5080-primary"
# }
```

**3. Monitor System Performance**
```bash
# Get comprehensive system stats
curl http://localhost:8080/stats

# Monitor in real-time
watch -n 5 'curl -s http://localhost:8080/stats | jq'
```

**4. Test LLM Task Master (if enabled)**
```bash
# Check LLM Task Master status
curl http://localhost:8080/socket/status

# Submit a task that will trigger intelligent routing
curl -X POST http://localhost:8080/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "large_model_inference",
    "parameters": {
      "model_size": "70B",
      "sequence_length": 4096
    }
  }'

# Should route to RTX 5080 for large model inference
```

### Advanced Configuration

#### Security Setup

**Development Security (Basic)**
```bash
# Enable basic security
export SECURITY_LEVEL=development
./start_complete_phantom.sh restart

# Create API key for testing
curl -X POST http://localhost:8080/auth/create-key \
  -H "Content-Type: application/json" \
  -d '{"name": "test-key", "permissions": ["read", "write"]}'
```

**Production Security (Enhanced)**
```bash
# Enable enhanced security
export SECURITY_LEVEL=production
./start_complete_phantom.sh restart

# Configure IP filtering, rate limiting, JWT tokens
# See security_framework/integrated_security.py for details
```

#### Performance Tuning

**GPU Memory Optimization**
```bash
# Edit worker configurations for optimal memory usage
# GTX 1080: Conservative 90% memory usage
# FirePro W9100: Aggressive 95% memory usage for large datasets
# RTX 50-series: Balanced 85% memory usage with headroom for features
```

**Network Optimization**
```bash
# Increase network buffers for high-throughput workloads
echo 'net.core.rmem_max = 134217728' | sudo tee -a /etc/sysctl.conf
echo 'net.core.wmem_max = 134217728' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

**Storage Optimization**
```bash
# Configure storage hub for optimal model serving
# Create dedicated directories for models, datasets, cache
sudo mkdir -p /var/lib/phantom/{models,datasets,cache}
sudo chown -R $USER:$USER /var/lib/phantom
```

### Monitoring and Maintenance

#### Health Monitoring
```bash
# Automated health checks
./start_complete_phantom.sh health

# Continuous monitoring
watch -n 30 './start_complete_phantom.sh health'
```

#### Log Management
```bash
# View recent logs
./start_complete_phantom.sh logs

# Monitor live logs
tail -f linux-worker/instances/*/worker.log
```

#### Performance Monitoring
```bash
# GPU utilization monitoring
watch -n 2 'nvidia-smi; echo "---"; rocm-smi --showuse'

# System resource monitoring
htop
iotop
```

### Troubleshooting

#### Common Issues and Solutions

**Issue: Workers not connecting to controller**
```bash
# Check network connectivity
ping 192.168.1.103
telnet 192.168.1.103 8080

# Check firewall
sudo firewall-cmd --list-ports
sudo firewall-cmd --add-port=8080/tcp --permanent

# Check controller logs
./start_complete_phantom.sh logs
```

**Issue: GPU not detected**
```bash
# NVIDIA GPUs
nvidia-smi
sudo systemctl status nvidia-persistenced

# AMD GPUs
rocm-smi --showid
lspci | grep -i amd
```

**Issue: Socket infrastructure not working**
```bash
# Check socket server status
curl http://localhost:8080/socket/status

# Test WebSocket connection
# Use browser dev tools or wscat:
npm install -g wscat
wscat -c ws://192.168.1.103:8081
```

**Issue: High memory usage**
```bash
# Monitor memory usage
free -h
nvidia-smi

# Adjust worker memory limits in config files
# Restart workers with new configuration
```

**Issue: Poor performance**
```bash
# Check GPU utilization
nvidia-smi -l 1

# Check network latency
ping -c 10 192.168.1.103

# Monitor task queue
curl http://localhost:8080/tasks | jq '.tasks[] | select(.status=="queued")'
```

### Scaling and Expansion

#### Adding More Workers
```bash
# Add workers on additional machines
# Copy linux-worker directory to new machine
# Update CONTROLLER_HOST in configuration
# Deploy and start workers
```

#### Upgrading Components
```bash
# Upgrade to newer GPU drivers
# Update Python dependencies
# Deploy new worker configurations
# Rolling restart of workers
```

#### Performance Optimization
```bash
# Profile task execution times
# Optimize task routing algorithms
# Implement custom plugins for specific workloads
# Add caching layers for frequently used models
```

---

## 🎉 Deployment Complete!

Your Phantom Distributed Compute Fabric is now fully deployed with:

- ✅ **Fedora Server**: Controller + 3 local workers (GTX 1080, FirePro W9100, Storage Hub)
- ✅ **Windows PC**: 2 remote workers (RTX 5080, RTX 5060)
- ✅ **Socket Infrastructure**: Real-time communication and hybrid routing
- ✅ **LLM Task Master**: Intelligent task routing on GTX 1080
- ✅ **Security Framework**: Ground-up security integration (configurable)

**Access Points:**
- **Controller API**: http://192.168.1.103:8080
- **System Dashboard**: http://192.168.1.103:8080/stats
- **Worker Status**: http://192.168.1.103:8080/workers
- **Socket Status**: http://192.168.1.103:8080/socket/status

**Management Commands:**
```bash
./start_complete_phantom.sh status    # Check system status
./start_complete_phantom.sh health    # Run health check
./start_complete_phantom.sh logs      # View recent logs
./start_complete_phantom.sh restart   # Restart entire system
```

Your heterogeneous GPU cluster is ready for production workloads! 🚀