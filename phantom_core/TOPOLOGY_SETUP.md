# 🏗️ Phantom Distributed Topology Setup

## Your Specific Hardware Configuration

### 🖥️ Fedora Server (192.168.1.103) - Controller + Local Workers
- **Hardware**: Intel i7-2700K, 32GB DDR3, GTX 1080, AMD FirePro W9100
- **Role**: Primary controller, storage hub, legacy compute, LLM Task Master
- **Network**: Gigabit Ethernet, Static IP 192.168.1.103
- **Storage**: HDD array for models, datasets, and cache

**Local Workers Deployed:**
- `nvidia-gpu-0` (GTX 1080) - Port 8090 - LLM Task Master + Stable Inference
- `amd-gpu-0` (FirePro W9100) - Port 8100 - Large Dataset Processing
- `storage-hub` (Virtual) - Port 8110 - Model/Dataset Serving

### 💻 Windows Main PC - High-Performance Compute Cluster
- **Hardware**: Intel i9-13900K, 64GB DDR5, RTX 5080, RTX 5060
- **Role**: Primary ML/AI compute cluster
- **Network**: Gigabit Ethernet, connects to Fedora server
- **Optimization**: Latest GPU features, high-speed processing

**Remote Workers:**
- `windows-rtx5080-primary` - Port 8091 - Flagship Performance
- `windows-rtx5060-secondary` - Port 8092 - Mainstream Performance

## 🎯 Performance Hierarchy

| GPU | Performance | Memory | Role | Specialization |
|-----|-------------|--------|------|----------------|
| **RTX 5080** | ~165 TFLOPS | 24GB | Primary ML Powerhouse | Large models, real-time AI, training |
| **RTX 5060** | ~85 TFLOPS | 16GB | Secondary Modern Compute | Batch processing, medium models |
| **GTX 1080** | ~9 TFLOPS | 8GB | Legacy + LLM Task Master | Stable inference, compatibility, routing |
| **FirePro W9100** | ~5.2 TFLOPS | 16GB | Memory Specialist | Large datasets, professional compute |

## 🌐 Network Architecture

```
Internet
    │
    ├── Router/Switch (192.168.1.1)
    │
    ├── Fedora Server (192.168.1.103)
    │   ├── Controller API (Port 8080)
    │   ├── Socket Infrastructure (Port 8081)
    │   ├── GTX 1080 Worker (Port 8090)
    │   ├── FirePro Worker (Port 8100)
    │   └── Storage Hub (Port 8110)
    │
    └── Windows PC (192.168.1.xxx)
        ├── RTX 5080 Worker (Port 8091)
        └── RTX 5060 Worker (Port 8092)
```

## 🔄 Task Routing Strategy

### Intelligent Routing (LLM Task Master on GTX 1080)
The GTX 1080 hosts a lightweight LLM that makes intelligent routing decisions:

**Task Type → Preferred GPU:**
- **Large Model Inference** → RTX 5080 (flagship performance)
- **Real-time AI** → RTX 5080 (4th gen Tensor cores)
- **Medium ML Tasks** → RTX 5060 (modern efficiency)
- **Batch Processing** → RTX 5060 (good throughput)
- **Data Processing** → FirePro W9100 (16GB memory specialist)
- **Legacy Models** → GTX 1080 (proven compatibility)
- **Stable Inference** → GTX 1080 (maximum reliability)

### Fallback Routing (Smart Programming)
When LLM Task Master is unavailable, rule-based routing:

1. **Memory Requirements** → FirePro W9100 for >12GB tasks
2. **Performance Requirements** → RTX 5080 for demanding tasks
3. **Compatibility Requirements** → GTX 1080 for legacy support
4. **Load Balancing** → Distribute across available workers

## 🚀 Deployment Sequence

### 1. Fedora Server Setup (Controller)
```bash
# On Fedora Server (192.168.1.103)
cd phantom-distributed

# Start integrated system with all features
./start_complete_phantom.sh

# Verify controller is running
curl http://localhost:8080/health
```

### 2. Linux Workers Deployment
```bash
# Deploy and start local workers
cd linux-worker
./deploy_workers.sh
./start_all_workers.sh

# Monitor worker status
./monitor_workers.sh
```

### 3. Windows Workers Setup
```powershell
# On Windows PC
cd windows-worker

# Configure RTX 5080 worker
copy worker_config_network.json windows_worker\worker_config.json
.\run_worker.ps1

# Configure RTX 5060 worker (separate instance)
mkdir rtx5060_instance
copy worker_config_rtx5060.json rtx5060_instance\worker_config.json
cd rtx5060_instance
..\run_worker.ps1
```

### 4. Verification
```bash
# Check all workers connected
curl http://192.168.1.103:8080/workers

# Check system statistics
curl http://192.168.1.103:8080/stats

# Test socket infrastructure
curl http://192.168.1.103:8080/socket/status
```

## 🔧 Configuration Optimizations

### Network Optimizations
- **Firewall Rules**: Open ports 8080-8120 on Fedora server
- **Network Buffers**: Optimized for cross-machine communication
- **Connection Pooling**: Efficient worker-controller communication

### GPU Optimizations
- **RTX 50-Series**: 4th gen Tensor cores, DLSS 3+, AV1 encoding
- **GTX 1080**: Conservative memory management, proven stability
- **FirePro W9100**: Large memory pool optimization, professional drivers

### Storage Optimizations
- **Centralized Storage**: Models and datasets served from Fedora HDD array
- **Caching Strategy**: Intelligent caching on high-speed storage
- **Network Serving**: Efficient model distribution to workers

## 📊 Expected Performance

### Throughput Estimates
- **ML Inference**: 100-500 samples/second (depending on model size)
- **Training**: 2-10x faster than single GPU (distributed across cluster)
- **Data Processing**: 50-200 GB/hour (leveraging FirePro memory)
- **Image Processing**: 1000-5000 images/minute (GPU-accelerated)

### Latency Targets
- **Task Routing**: <100ms (LLM Task Master)
- **Worker Assignment**: <50ms (smart programming)
- **Cross-machine Communication**: <10ms (gigabit network)
- **Task Startup**: <1s (optimized worker initialization)

## 🔒 Security Configuration

### Development Mode (Default)
- Security level: `disabled`
- All connections allowed
- No authentication required
- Suitable for trusted network

### Production Mode (Optional)
```bash
# Enable enhanced security
export SECURITY_LEVEL=enhanced
./start_complete_phantom.sh
```

Features:
- API key authentication
- JWT token support
- Rate limiting
- IP filtering
- Audit logging

## 🐛 Troubleshooting

### Common Issues

**Workers Not Connecting:**
```bash
# Check firewall
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --add-port=8081/tcp --permanent
sudo firewall-cmd --reload

# Test connectivity from Windows PC
curl http://192.168.1.103:8080/health
```

**GPU Not Detected:**
```bash
# NVIDIA GPUs
nvidia-smi

# AMD GPUs
rocm-smi --showid
lspci | grep VGA
```

**Socket Connection Issues:**
```bash
# Check socket server
curl http://192.168.1.103:8080/socket/status

# Check WebSocket connectivity
# Use browser dev tools or WebSocket client
```

**Performance Issues:**
```bash
# Monitor system resources
htop
nvidia-smi -l 1
rocm-smi --showuse

# Check network latency
ping 192.168.1.103
```

## 📈 Scaling Options

### Horizontal Scaling
- Add more Windows workers on additional machines
- Deploy workers on other Linux machines
- Increase worker instances per GPU

### Vertical Scaling
- Upgrade to higher-end GPUs
- Increase system memory
- Improve network infrastructure

### Advanced Features
- Multi-region deployment
- Load balancing across multiple controllers
- Advanced scheduling algorithms
- Custom plugin development

## 🎯 Optimization Tips

### For Maximum Performance
1. **Use RTX 5080** for large models and real-time applications
2. **Use FirePro W9100** for memory-intensive data processing
3. **Enable LLM Task Master** for intelligent routing
4. **Monitor GPU utilization** and adjust task distribution

### For Maximum Stability
1. **Use GTX 1080** for critical production workloads
2. **Enable conservative memory management**
3. **Use proven model configurations**
4. **Implement comprehensive monitoring**

### For Development
1. **Start with security disabled** for easy testing
2. **Use local workers first** before adding remote workers
3. **Monitor logs** for debugging information
4. **Test with simple tasks** before complex workloads

---

This topology provides a powerful, flexible, and scalable distributed computing platform that leverages the strengths of each GPU while providing intelligent task routing and comprehensive management capabilities.