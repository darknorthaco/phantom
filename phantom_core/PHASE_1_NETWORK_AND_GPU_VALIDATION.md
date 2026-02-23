# PHASE 1 — Network & GPU Validation Report

**Audit Classification:** DARPA-Grade Technical Assessment  
**Date:** 2025-02-18  
**Scope:** Phantom PTR — GPU Detection, Plugin System, Network Discovery, Worker Communication  
**Auditor:** Automated Phase 1 Compliance Engine  
**Status:** DRAFT — Findings Require Remediation  

---

## Table of Contents

1. [GPU Detection](#1-gpu-detection)
2. [Plugin System](#2-plugin-system)
3. [Network Discovery](#3-network-discovery)
4. [Worker Communication](#4-worker-communication)
5. [Hardcoded Values Table](#5-hardcoded-values-table)
6. [Critical Findings](#6-critical-findings)

---

## 1. GPU Detection

### 1.1 Detection Architecture

GPU detection is implemented in `linux-worker/linux_worker/gpu/gpu_info_linux.py` (455 lines). The detection chain follows a strict priority order:

```
NVIDIA (nvidia-smi) → AMD (rocm-smi) → AMD (lspci fallback) → None (Exception)
```

| Step | Tool | Location | Fallback |
|------|------|----------|----------|
| 1 | `nvidia-smi` (subprocess) | Lines 48–96 | → Step 2 |
| 2 | `rocm-smi` (subprocess) | Lines 113–186 | → Step 3 |
| 3 | `lspci` (subprocess, grep) | Lines 188–239 | → Step 4 |
| 4 | Return `None` | Line 42 | Worker raises Exception |

### 1.2 NVIDIA Detection (nvidia-smi)

**Location:** `gpu_info_linux.py`, lines 48–96

The NVIDIA path queries `nvidia-smi` with CSV output:

```
nvidia-smi --query-gpu=index,name,memory.total,memory.free,memory.used,
            utilization.gpu,driver_version,compute_cap --format=csv,noheader,nounits
```

**Fields extracted per GPU:**
- Index, name, total/free/used memory (MB), utilization (%), driver version, compute capability

**Limitation (Line 32):** Only the **first GPU** (index 0) is returned as the primary GPU. Multi-GPU configurations are detected but only one GPU is used per worker instance.

### 1.3 AMD Detection

**ROCm path** (`rocm-smi`): Lines 113–186  
- Queries device name, temperature, memory usage, utilization
- Falls back to hardcoded defaults if parsing fails (lines 170–172)

**lspci fallback**: Lines 188–239  
- Executes `lspci | grep -i 'vga\|3d\|display'` to find AMD GPUs
- Special handling for FirePro W9100 (lines 221–227):
  - Default memory: **16,000 MB** (line 210)
  - Estimated free: **15,000 MB** (line 211)
  - Estimated used: **1,000 MB** (line 212)

### 1.4 Supported GPU Hardware Profiles

| GPU | Memory | Compute Units | Peak Performance | Plugin |
|-----|--------|---------------|-----------------|--------|
| **FirePro W9100** | 16 GB (16,384 MB) | 2,816 stream processors | Professional compute/CAD | `firepro_plugin.py` |
| **RTX 5080** | 24 GB | — | ~165 TFLOPS (estimated) | `rtx50_plugin.py` |
| **RTX 5060** | 14 GB | — | ~85 TFLOPS (estimated) | `rtx50_plugin.py` |
| **GTX 1080** | 8 GB (8,192 MB) | 2,560 CUDA cores | Legacy gaming/compute | `gtx1080_plugin.py` |
| **NVIDIA (general)** | GPU-dependent | GPU-dependent | Varies | `nvidia_cuda_plugin.py` |
| **AMD (general)** | GPU-dependent | GPU-dependent | Varies | `amd_rocm_plugin.py` |

### 1.5 Multi-GPU Limitation

**Severity:** MEDIUM  
**Location:** `gpu_info_linux.py`, line 32

Only the first detected GPU is used per worker. The `detect_nvidia_gpus()` function can return multiple GPUs but the worker class (`worker.py`) only processes index 0. To use multiple GPUs, multiple worker instances must be launched on the same host with different `gpu_index` configurations.

### 1.6 No-GPU Behavior

**Severity:** HIGH  
**Location:** `gpu_info_linux.py`, line 42; `worker.py`, line 148

If no GPU is detected by any method, `detect_gpu()` returns `None`. The worker's `__init__()` raises an `Exception` — there is **no CPU-only fallback** unless:
- The `GeneralPlugin` (`general_plugin.py`) is manually loaded
- A future code path bypasses GPU detection

**Recommendation:** Implement graceful degradation to CPU-only mode via `GeneralPlugin` when no GPU is detected.

---

## 2. Plugin System

### 2.1 Plugin Architecture

**Manager:** `linux-worker/plugins/plugin_manager.py` (348 lines)

The plugin system uses a score-based selection model:

1. **Discovery:** Plugins loaded based on detected GPU vendor/model (lines 88–165)
2. **Capability check:** `plugin.can_handle_task(task_type)` filters eligible plugins (line 173)
3. **Selection:** `max(capable_plugins, key=lambda p: p.get_performance_score(task_type))` picks the best (line 182–184)

### 2.2 Plugin Inventory

| # | Plugin | File | Lines | GPU Target | Task Types |
|---|--------|------|-------|------------|------------|
| 1 | `NVIDIACudaPlugin` | `nvidia_cuda_plugin.py` | 460 | Any NVIDIA GPU | matrix_multiply, neural_network, image_processing, data_analytics, crypto_mining |
| 2 | `RTX50Plugin` | `rtx50_plugin.py` | 467 | RTX 5080, RTX 5060 | ray_tracing, ai_inference, video_encode, neural_network, general_compute |
| 3 | `GTX1080Plugin` | `gtx1080_plugin.py` | 474 | GTX 1080 | neural_network, image_processing, crypto_mining, video_encode, general_compute |
| 4 | `FireProPlugin` | `firepro_plugin.py` | 577 | FirePro W9100 | cad_rendering, scientific_compute, large_dataset, double_precision, opencl_compute, visualization |
| 5 | `AMDRocmPlugin` | `amd_rocm_plugin.py` | 557 | Any AMD GPU | matrix_multiply, neural_network, image_processing, scientific_compute, opencl_compute |
| 6 | `GeneralPlugin` | `general_plugin.py` | 401 | Any (fallback) | All types (lower scores) |

### 2.3 Plugin Loading Logic

**Location:** `plugin_manager.py`, lines 88–165

```
GPU Detected → NVIDIA?
  ├── RTX 50xx name match (line 109) → Load RTX50Plugin
  ├── GTX 1080 name match (line 117) → Load GTX1080Plugin
  └── Always load NVIDIACudaPlugin (line 125)
GPU Detected → AMD?
  ├── FirePro W9100 name match (line 138) → Load FireProPlugin
  └── Always load AMDRocmPlugin (line 146)
Always → Load GeneralPlugin (line 155)
```

**Key behavior:** Multiple plugins can be loaded simultaneously. For NVIDIA GPUs, both the specific plugin (e.g., RTX50Plugin) AND the general NVIDIACudaPlugin are loaded. Selection happens at task time via `performance_score`.

### 2.4 Performance Scores

Scores determine which plugin handles a given task type when multiple plugins claim capability:

| Task Type | NVIDIA CUDA | RTX 50 | GTX 1080 | FirePro | AMD ROCm | General |
|-----------|-------------|--------|----------|---------|----------|---------|
| neural_network | 9.5 | 9.8* | 7.0 | — | 7.5 | 5.0 |
| matrix_multiply | 9.0 | — | — | — | 7.0 | 4.5 |
| image_processing | 8.5 | — | 8.0 | — | 7.0 | 4.0 |
| ray_tracing | — | 9.9* | — | — | — | 3.0 |
| cad_rendering | — | — | — | 10.0* | — | 3.0 |
| scientific_compute | — | — | — | 9.0 | 8.0 | 4.0 |
| video_encode | — | 9.0 | 6.5 | — | — | 3.5 |
| crypto_mining | 7.0 | — | 9.0* | — | — | 3.0 |
| general_compute | 7.0 | 8.0 | 5.5 | — | 4.5 | 5.0 |

*\* = Highest scorer for that task type*

**Note:** RTX 50 series applies a 20–50% bonus multiplier for optimized workloads (lines 407–439).

### 2.5 Task Execution — All Simulated

**Severity:** MEDIUM (expected for current development phase)

**Every plugin uses `asyncio.sleep()` to simulate GPU work.** No actual CUDA kernels, ROCm compute, or OpenCL operations are executed.

| Plugin | Sleep Range | Example |
|--------|-------------|---------|
| NVIDIA CUDA | 0.5–2.0s | `asyncio.sleep(1.0)` for matrix_multiply |
| RTX 50 | 0.016–10.0s | `asyncio.sleep(0.016)` for ray_tracing (60fps simulation) |
| GTX 1080 | 0.1–1.0s | `asyncio.sleep(0.5)` for neural_network |
| FirePro | 0.1–20.0s | `asyncio.sleep(15.0)` for large_dataset |
| AMD ROCm | 0.15–15.0s | `asyncio.sleep(2.0)` for matrix_multiply |
| General | 0.2–30.0s | `asyncio.sleep(5.0)` for general_compute |

**Task results are synthetic:** Each plugin returns fabricated metrics (e.g., `{"gflops": 120.5, "efficiency": 0.92}`) that do not correspond to any real computation.

### 2.6 Plugin Overlap Concerns

Multiple plugins can claim the same task type with different scores. This is by design (best-score wins), but creates potential issues:

| Concern | Detail | Severity |
|---------|--------|----------|
| Score ties | No tiebreaker defined; `max()` picks arbitrarily | LOW |
| Score inflation | RTX50 applies bonus multipliers, skewing selection | LOW |
| No plugin versioning | Plugins can't be upgraded independently | MEDIUM |
| No plugin sandboxing | Plugin code runs in worker process; a crash kills the worker | HIGH |

---

## 3. Network Discovery

### 3.1 Discovery Modes

**Location:** `installer/modules/worker_discovery.py` (239 lines)

Three discovery modes are available during installation:

| Mode | Trigger | Method | Lines |
|------|---------|--------|-------|
| **skip** | User selects "configure later" | Returns empty worker list | Line 231–232, 239 |
| **manual** | User selects "basic scan" | Ping sweep on local /24 subnet | Lines 80–114 |
| **comprehensive** | User selects "detailed scan" | Port scan on 8090–8094 per host | Lines 116–146 |

### 3.2 Local IP Detection

**Location:** `worker_discovery.py`, line 31  
**Method:** Opens a UDP socket to `8.8.8.8:80` (Google DNS) and reads the local interface IP

```python
s.connect(("8.8.8.8", 80))
local_ip = s.getsockname()[0]
```

**Issues:**

| Issue | Severity | Detail |
|-------|----------|--------|
| Requires internet connectivity | HIGH | Fails in air-gapped environments (common for DARPA/DoD) |
| Hardcoded DNS server | MEDIUM | 8.8.8.8 may be blocked by enterprise firewalls |
| Single interface assumption | MEDIUM | Multi-homed hosts may report wrong interface |

### 3.3 /24 Subnet Assumption

**Location:** `worker_discovery.py`, line 36

```python
network = IPv4Network(f"{local_ip}/24", strict=False)
```

The discovery system assumes a /24 subnet mask regardless of actual network configuration. This means:
- Scans 254 hosts (valid for small lab networks)
- Misses hosts on larger subnets (/16, /8)
- Over-scans on smaller subnets (/28, /30)
- **No CIDR detection** from system network configuration

### 3.4 Port Scanning

**Comprehensive mode** scans ports 8090–8094 (line 130):

```python
worker_ports = [8090, 8091, 8092, 8093, 8094]
```

For each host found via ping sweep, a TCP connection is attempted on each port with a 2-second timeout (line 19). If a connection succeeds, the host:port is recorded as a potential worker.

**Worker validation protocol:** After port detection, the discovery system sends a JSON identification request:

```json
{"type": "identify", "source": "installer"}
```

**Critical issue:** No actual Phantom worker implements this protocol. The Linux worker (`worker.py`) registers via HTTP POST to the controller — it does not listen for JSON identification requests on its worker port. The discovery protocol is an **undefined placeholder**.

### 3.5 IPv6 Support

**Not implemented.** All network operations use `IPv4Network`, `socket.AF_INET`, and IPv4 address strings. No IPv6 code paths exist anywhere in the codebase.

### 3.6 Network Discovery Flow

```
Installer Start
  │
  ├── Detect local IP (8.8.8.8 UDP trick)
  │     └── line 31: s.connect(("8.8.8.8", 80))
  │
  ├── Calculate /24 network
  │     └── line 36: IPv4Network(f"{local_ip}/24")
  │
  ├── Mode: manual?
  │     └── Ping sweep 254 hosts (1s timeout each)
  │           └── line 42: subprocess ping
  │
  ├── Mode: comprehensive?
  │     └── For each pingable host:
  │           └── TCP connect to ports 8090-8094 (2s timeout)
  │                 └── line 130: worker_ports = [8090...8094]
  │
  └── Return discovered workers list
```

---

## 4. Worker Communication

### 4.1 Registration

**Location:** `linux-worker/linux_worker/worker.py`, lines 209–238

Workers register with the controller via HTTP POST:

```
POST http://{controller_host}:{controller_port}/workers/register
Content-Type: application/json

{
  "worker_id": "linux-gpu-{hostname}-{uuid}",
  "hostname": "...",
  "ip_address": "...",
  "port": 8090,
  "gpu_info": { ... },
  "capabilities": [ ... ],
  "max_concurrent_tasks": 4
}
```

| Parameter | Default | Location |
|-----------|---------|----------|
| Controller host | `localhost` | `worker.py:60` |
| Controller port | `8080` | `worker.py:61` |
| Worker port | `8090` | `worker.py:62` |
| HTTP timeout | `30.0s` | `worker.py:221` |

### 4.2 Heartbeat

**Location:** `worker.py`, lines 258–294

Workers send heartbeats every 5 seconds:

```
POST http://{controller_host}:{controller_port}/workers/{worker_id}/heartbeat
Content-Type: application/json

{
  "worker_id": "...",
  "status": "active",
  "gpu_utilization": 45.2,
  "gpu_memory_used": 4096,
  "gpu_memory_free": 4096,
  "current_tasks": 2,
  "uptime": 3600
}
```

| Parameter | Value | Location |
|-----------|-------|----------|
| Interval | `5 seconds` | `worker.py:290` |
| HTTP timeout | `5.0 seconds` | `worker.py:274` |
| Retry on failure | `5 seconds` | `worker.py:294` |

### 4.3 Task Completion Notification — STUBS

**Severity:** HIGH  
**Location:** `worker.py`, lines 424–440

```python
# Lines 424-431
async def notify_controller_completion(self, task_id, result):
    """Notify controller that task completed."""
    # For now, we'll just log it
    logger.debug(f"Task {task_id} completed: {result}")

# Lines 433-440
async def notify_controller_failure(self, task_id, error):
    """Notify controller that task failed."""
    # For now, we'll just log it
    logger.debug(f"Task {task_id} failed: {error}")
```

**Both methods are stubs.** They log the event but do NOT send an HTTP POST to the controller. The controller never learns that a task has completed or failed.

**Impact:** Task state in the controller remains `RUNNING` indefinitely after assignment (if the orchestrator were functional). There is no mechanism for task state reconciliation.

### 4.4 Socket Client (Optional)

**Location:** `worker.py`, line 163

Workers optionally connect to the WebSocket server on port 8081 for real-time events. This is a supplementary channel — registration and heartbeat still use HTTP.

### 4.5 Communication Diagram

```
                    ┌─────────────────────┐
                    │   Controller (8080)  │
                    │   FastAPI + uvicorn  │
                    └──────┬──────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        HTTP POST     HTTP POST    HTTP POST
        /register     /heartbeat   (STUB: /tasks/complete)
              │            │            │
        ┌─────┴───┐  ┌────┴────┐  ┌───┴─────┐
        │Worker:   │  │Worker:  │  │Worker:  │
        │8090      │  │8091     │  │8092     │
        └──────────┘  └─────────┘  └─────────┘
              │
        (Optional) WebSocket to Socket Server (8081)
```

---

## 5. Hardcoded Values Table

### 5.1 Ports

| Port | Usage | Location | Configurable? |
|------|-------|----------|--------------|
| `8080` | Controller API | `worker.py:61`, `controller_api.py` | Yes (env/arg) |
| `8081` | WebSocket server | `socket_integration.py:32`, `hybrid_socket_server.py:34` | Yes (constructor) |
| `8090` | Worker default port | `worker.py:62` | Yes (config) |
| `8091` | Worker secondary | `windows-worker/worker_config_network.json` | Config only |
| `8092` | Worker tertiary | `windows-worker/worker_config_rtx5060.json` | Config only |
| `8093` | Worker discovery scan | `worker_discovery.py:130` | No |
| `8094` | Worker discovery scan | `worker_discovery.py:130` | No |
| `3000` | UI (RedBlue) | `system_check.py` | Installer config |
| `5000` | Health check | `system_check.py` | Installer config |

### 5.2 Timeouts

| Timeout | Value | Location | Purpose |
|---------|-------|----------|---------|
| Discovery socket | `2 seconds` | `worker_discovery.py:19` | TCP port probe |
| Discovery ping | `1 second` | `worker_discovery.py:42` | ICMP ping |
| HTTP registration | `30.0 seconds` | `worker.py:221` | Worker → Controller |
| HTTP heartbeat | `5.0 seconds` | `worker.py:274` | Worker → Controller |
| Heartbeat interval | `5 seconds` | `worker.py:290` | Between heartbeats |
| Worker health check | `5 minutes` | `orchestrator.py:470` | Mark worker OFFLINE |
| Health monitor loop | `30 seconds` | `orchestrator.py:460` | Check interval |
| Performance analysis | `5 minutes` | `orchestrator.py:540` | Analysis interval |
| Task scheduler loop | `1 second` | `orchestrator.py:182` | Queue processing |
| Task execution max | `300.0 seconds` | `phantom_protocol/config.py:56` | Task distribution channel |
| LLM routing | `10.0 seconds` | `phantom_protocol/config.py:73` | LLM routing channel |
| Worker registration channel | `30.0 seconds` | `phantom_protocol/config.py:78` | Registration channel |
| Heartbeat channel | `5.0 seconds` | `phantom_protocol/config.py:62` | Heartbeat channel |
| HTTP transport default | `30.0 seconds` | `http_transport.py:19` | Default HTTP timeout |
| HTTP connection test | `5.0 seconds` | `http_transport.py:61` | Connection validation |
| GPU monitoring loop | `10 seconds` | `worker.py:314` | GPU stats refresh |
| Task record cleanup | `60 seconds` | `worker.py:402` | Retention period |
| Unregister timeout | `10.0 seconds` | `worker.py:506` | Shutdown deregistration |
| Session timeout | `30 minutes` | `integrated_security.py` | Auth session expiry |
| Failure retry | `5 seconds` | `worker.py:294` | Heartbeat retry delay |
| systemd restart backoff | `10 seconds` | `post_install.sh` | RestartSec |

### 5.3 Memory Values

| Value | GPU | Location | Context |
|-------|-----|----------|---------|
| `16,384 MB` (16 GB) | FirePro W9100 | `firepro_plugin.py:33` | Total memory |
| `16,000 MB` | FirePro W9100 | `gpu_info_linux.py:210` | lspci default |
| `15,000 MB` | FirePro W9100 | `gpu_info_linux.py:211` | Estimated free |
| `1,000 MB` | FirePro W9100 | `gpu_info_linux.py:212` | Estimated used |
| `8,192 MB` (8 GB) | GTX 1080 | `gtx1080_plugin.py:31` | Total memory |
| `14 GB` | RTX 5060 | `windows-worker/worker_config_rtx5060.json` | Memory limit |
| `20 GB` | RTX 5080 | `windows-worker/worker_config_network.json` | Memory limit |
| `14 GB` | FirePro W9100 | `firepro_plugin.py:42` | Max dataset size |

### 5.4 Network Assumptions

| Assumption | Value | Location | Impact |
|------------|-------|----------|--------|
| Subnet mask | `/24` (255.255.255.0) | `worker_discovery.py:36` | Misses hosts on larger/smaller subnets |
| DNS server for IP detection | `8.8.8.8` | `worker_discovery.py:31` | Fails in air-gapped/firewall environments |
| IP version | IPv4 only | All network code | No IPv6 support |
| Socket bind (default) | `127.0.0.1` | `socket_integration.py:45` | Localhost only |
| Socket bind (installer config) | `0.0.0.0` | Config generator | All interfaces (security risk) |

### 5.5 File Paths

| Path | Location | Purpose | Issue |
|------|----------|---------|-------|
| `/tmp/cuda_cache` | `nvidia_cuda_plugin.py:125` | CUDA compilation cache | Linux-only, cleared on reboot |
| `/tmp/cuda_cache` | `nvidia_cuda_plugin.py:433` | CUDA cleanup on shutdown | Shared temp directory |
| `/tmp/phantom.service` | `post_install.sh:47` | systemd service file | **Deleted on reboot** — should be `/etc/systemd/system/` |
| `~/phantom` | Installer defaults | macOS install directory | User home directory |

---

## 6. Critical Findings

### 6.1 Findings Table

| ID | Finding | Severity | Component | Cross-Ref |
|----|---------|----------|-----------|-----------|
| **NET-001** | Windows worker is config-only — no Python runtime, no registration, no heartbeat, no task execution | **CRITICAL** | `windows-worker/` | ARCH-008 |
| **NET-002** | `notify_controller_completion()` and `notify_controller_failure()` are stubs — controller never receives task outcomes | **CRITICAL** | `worker.py:424-440` | ARCH-013 |
| **NET-003** | Worker discovery protocol is undefined — installer sends JSON identification requests that no worker implements | **HIGH** | `worker_discovery.py:130+` | — |
| **NET-004** | No multi-GPU support per worker — only GPU index 0 used | **MEDIUM** | `gpu_info_linux.py:32` | — |
| **NET-005** | Race condition on GPU utilization updates — heartbeat reads GPU stats while monitoring loop writes them concurrently | **HIGH** | `worker.py:258-314` | ARCH-005 |
| **NET-006** | Linux-only paths (`/tmp/cuda_cache`) hardcoded in NVIDIA plugin | **MEDIUM** | `nvidia_cuda_plugin.py:125,433` | — |
| **NET-007** | systemd service file written to `/tmp/` — deleted on system reboot | **HIGH** | `post_install.sh:47` | INS-006 |
| **NET-008** | Network discovery assumes /24 subnet — misses hosts on other subnet sizes | **MEDIUM** | `worker_discovery.py:36` | — |
| **NET-009** | Local IP detection requires connectivity to 8.8.8.8 — fails air-gapped | **HIGH** | `worker_discovery.py:31` | — |
| **NET-010** | No IPv6 support anywhere in codebase | **LOW** | All network code | — |
| **NET-011** | All GPU task execution is simulated (asyncio.sleep) — zero real compute | **MEDIUM** | All 6 plugins | ARCH-007 |
| **NET-012** | No plugin sandboxing — plugin crash kills entire worker process | **HIGH** | `plugin_manager.py` | — |
| **NET-013** | No CPU-only fallback when GPU detection fails (unless GeneralPlugin manually loaded) | **HIGH** | `worker.py:148`, `gpu_info_linux.py:42` | — |
| **NET-014** | Socket server binds to `0.0.0.0` in installer config — exposes to all interfaces | **MEDIUM** | Config generator | INS-004 |

### 6.2 Severity Distribution

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 2 | NET-001, NET-002 |
| HIGH | 5 | NET-003, NET-005, NET-007, NET-009, NET-012, NET-013 |
| MEDIUM | 5 | NET-004, NET-006, NET-008, NET-011, NET-014 |
| LOW | 1 | NET-010 |
| **Total** | **14** | — |

### 6.3 Recommendations

| Priority | Action | Addresses |
|----------|--------|-----------|
| **P0** | Implement `notify_controller_completion()` with HTTP POST to `/tasks/{task_id}/complete` | NET-002 |
| **P0** | Implement Windows worker Python runtime or formally mark Windows as unsupported | NET-001 |
| **P1** | Define and implement a proper worker discovery protocol (e.g., mDNS, or extend HTTP health endpoint) | NET-003 |
| **P1** | Add `asyncio.Lock` to GPU stats shared between heartbeat and monitoring loops | NET-005 |
| **P1** | Move systemd service to `/etc/systemd/system/phantom.service` | NET-007 |
| **P1** | Implement air-gapped IP detection fallback (e.g., `netifaces`, parse `ip addr`) | NET-009 |
| **P1** | Add try/except around plugin task execution to prevent worker crash | NET-012 |
| **P1** | Auto-load GeneralPlugin as CPU fallback when no GPU detected | NET-013 |
| **P2** | Add multi-GPU support via `gpu_index` parameter in worker config | NET-004 |
| **P2** | Use `tempfile.gettempdir()` instead of hardcoded `/tmp/` | NET-006 |
| **P2** | Detect actual subnet mask from system network configuration | NET-008 |
| **P2** | Bind socket server to `127.0.0.1` by default; require explicit opt-in for `0.0.0.0` | NET-014 |
| **P3** | Replace simulated GPU execution with real CUDA/ROCm/OpenCL bindings | NET-011 |
| **P3** | Add IPv6 support for all network operations | NET-010 |

---

*Cross-references: See [PHASE_1_PLATFORM_ARCHITECTURE_REPORT.md](PHASE_1_PLATFORM_ARCHITECTURE_REPORT.md) for architecture bugs (ARCH-*), [PHASE_1_INSTALLER_UNINSTALLER_AUDIT.md](PHASE_1_INSTALLER_UNINSTALLER_AUDIT.md) for installer issues (INS-*).*

**END OF REPORT**
