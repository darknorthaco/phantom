# Phantom Deploy Flow — Gap Analysis Audit Report

**Date:** 2025-03-10  
**Scope:** Intended behavior vs actual codebase behavior after user clicks "Deploy"  
**Method:** Inspection only. No code changes. No proposed fixes.

---

## 1. EXECUTION TRACE

### Entry Point
- **File:** `phantom_app/src-tauri/src/lib.rs`
- **Function:** `deploy_phantom()` (tauri command, lines 272–344)
- **Flow:** Sets `AppPhase::Deploying`, creates `PhantomDeployer`, iterates `PhantomDeployer::steps()` (0–10), calls `deployer.run_step(i)` for each, emits `deploy-progress`, sets `AppPhase::Deployed` on success.

### Step-by-Step Trace (Cursor Deploy Flow 0–10)

| Step | Label | File + Function | What Actually Happens |
|------|-------|----------------|------------------------|
| 0 | "Creating Phantom virtual environment" | `phantom_deployer.rs` `create_venv()` | Creates `~/.phantom/venv` via `python -m venv`. Fails on pip/venv error. |
| 1 | "Installing Python runtime" | `phantom_deployer.rs` `install_python_deps()` | Runs pip install for fastapi, uvicorn, pydantic, httpx, requests, websockets, psutil, numpy, pyyaml, cryptography, pyjwt. Uses `requirements.txt` from engine_source only for existence check; packages hardcoded. |
| 2 | "Installing Phantom Core" | `phantom_deployer.rs` `install_phantom_core()` | Copies `engine_source` → `~/.phantom/engine` via `copy_dir_all()`. Skips if `run.py` exists. |
| 3 | "Verifying GPU plugins" | `phantom_deployer.rs` `verify_gpu_plugins()` | Linux: `gpu_detection::detect_nvidia_gpus()`. Windows: `gpu_detection::detect_gpus()`. Logs only; **never returns Err**. |
| 4 | "Installing Phantom service" | `phantom_deployer.rs` `install_service()` | Linux: writes systemd user unit `~/.config/systemd/user/phantom.service`, `systemctl --user daemon-reload`. Windows: calls `service_installer::install_service()`. Unit hardcodes `--security basic` (line 11 of `systemd_installer.rs`). |
| 5 | "Starting controller" | `phantom_deployer.rs` `start_controller()` | Spawns `python run.py --host 127.0.0.1 --port 8080 --security <level>`. Security level from `phantom_config.json` via `read_controller_config()`. **phantom_config.json does not exist yet** (written in step 10) → **defaults to "disabled"**. Sleep 3s. |
| 6 | "Opening ports" | `phantom_deployer.rs` `open_ports()` | **Opens TCP 8080 only** (ufw/iptables on Linux, netsh on Windows). No 8081, 8090, or 8095. |
| 7 | "Initializing state" | `phantom_deployer.rs` `initialize_state()` | Writes `~/.phantom/deployed.marker` with content "deployed". |
| 8 | "Starting local worker" | `phantom_deployer.rs` `start_local_worker()` | Writes `local_worker_config.json`, spawns `python -m linux_worker.main --config <path>`. Linux: log on spawn failure says "GPU required" (line 413); Windows: does not (line 349). Sleep 2s. |
| 9 | "Scanning LAN" | `phantom_deployer.rs` `scan_lan()` | Calls `discovery::discover_workers(&broadcast_addrs)`, registers each manifest via `PhantomApiClient::register_worker()`, writes `lan_scan.json`. |
| 10 | "Loading execution modes" | `phantom_deployer.rs` `load_execution_modes()` | Writes `llm_config.json` and `phantom_config.json` if missing. |

### Comparison to Cursor's Deploy-Flow Report
- Cursor's report lists steps 0–9; step 10 (loading execution modes) is present in code.
- Step order matches: 0=venv, 1=python deps, 2=core, 3=GPU verify, 4=service, 5=controller, 6=ports, 7=state, 8=worker, 9=scan, 10=modes.
- **Correction:** `phantom_config.json` is written in step 10, not step 9. Comment at `phantom_deployer.rs:259` ("written by step 9") is **incorrect**.

---

## 2. GAP ANALYSIS

### 2.1 Intended vs Actual Behavior

| Intended Step | Status | Evidence |
|---------------|--------|----------|
| **1. Controller Selection Ceremony** | **MISSING** | No UI to choose where controller runs (local CPU, local GPU, another device). Controller always started at `127.0.0.1:8080` (`phantom_deployer.rs:276`). Identity (Ed25519) exists in `identity_manager.rs` and is exposed via `get_identity` Tauri command and ExperimentalAOL panel; **not used in deploy flow**. |
| **2. Worker Discovery (broadcast-only)** | **PARTIALLY MET** | `discovery.rs` uses UDP broadcast to port 8095 and unicast to 127.0.0.1. No ARP, no port scanning. **Doctrine-aligned**. Installer `worker_discovery.py` uses ping + TCP probing (8090–8094); **not used by Tauri deploy**. |
| **3. Worker Selection Ceremony** | **MISSING** | No UI to select/deselect discovered workers. `scan_lan()` and `scan_and_register_workers()` register **all** discovered manifests. WorkersPanel shows workers but no pre-registration selection. |
| **4. Local Worker Startup** | **PRESENT** | Worker spawned in step 8. GPU detection optional; `worker.py` has CPU fallback (lines 148–158). Discovery listener started in `start_background_tasks()` after `register_with_controller()`. |
| **5. Registration (selected only)** | **VIOLATED** | All manifests are registered. No selection step. Manifest is plain JSON; no signing. |
| **6. Execution Modes** | **PRESENT** | `load_execution_modes()` writes `llm_config.json` and `phantom_config.json`. |

### 2.2 Missing Ceremonies
- **Controller selection:** No UI to choose controller host/port or identity display during deploy.
- **Worker selection:** No UI to approve or reject discovered workers before registration.

### 2.3 Missing Logic
- Manifest signing/verification per Doctrine ("All cross-controller messages must be signed").
- Controller identity generation or display during deploy.
- Port 8095 (discovery UDP) opened by deploy.
- Port 8090 (worker HTTP) opened by deploy.
- Port 8081 (socket) opened by deploy.

### 2.4 Broken or Misleading Logic
- **phantom_config comment:** Line 259 says "written by step 9"; actual writer is step 10.
- **GPU required log:** Linux `start_local_worker()` line 413: `"Failed to start local worker (GPU required): {e}"` — misleading; worker has CPU fallback.
- **WorkersPanel tooltip:** Line 72: "Scan LAN for Phantom workers on port 8090" — discovery uses UDP 8095; 8090 is worker HTTP.
- **discovery_listener.py docstring:** "Responds with a signed manifest" — manifest has no signature field; it is unsigned JSON.

### 2.5 Dead Code
- `installer/modules/worker_discovery.py` — TCP probing, `_query_worker_info()` sends raw JSON over TCP; workers speak HTTP. Used only by standalone installer, not Tauri deploy.
- `emit_scan_log_opt()` in `phantom_deployer.rs` (lines 416–420) — defined but `emit_scan_log()` is used instead for `PhantomDeployer`; `emit_scan_log_opt()` used only by `scan_and_register_workers()`.

### 2.6 Contradictions with Doctrine
- **Manifest signing:** Doctrine requires signed messages; manifests are unsigned.
- **Worker selection:** "Trust relationships require manual approval" — workers auto-registered without selection.
- **Controller identity:** Identity exists but not shown or used in deploy.

### 2.7 Contradictions with DARPA Audit
- **Worker discovery failures:** Installer `discover_workers_comprehensive()` uses TCP probing incompatible with worker HTTP API; Tauri uses broadcast, so not directly affected. If port 8095 is blocked, discovery still fails.
- **GPU hard dependencies:** Tauri `verify_gpu_plugins()` never blocks; worker has CPU fallback. Log message "GPU required" is misleading.
- **Port conflicts:** Deploy opens only 8080; 8090, 8095, 8081 not opened; firewall may block discovery or worker traffic on some systems.

### 2.8 Contradictions with GPU Discovery Audit
- Tauri GPU detection: optional, log-only.
- Linux worker: CPU fallback in `worker.py`.
- Misleading "GPU required" log in deployer.

### 2.9 Contradictions with UI
- **WizardWelcome:** Explicit consent for "create local environment, install engine, configure as controller" — no controller/worker selection.
- **FrontPorchDeploy:** Single "Deploy Phantom" button; no pre-deploy controller or worker ceremonies.
- **WorkersPanel:** "Scan LAN" runs discovery; tooltip mentions port 8090 (should be 8095 for discovery).

---

## 3. DISCOVERY DIAGNOSTIC

### 3.1 Tauri Discovery (`discovery.rs`)
- **Mechanism:** UDP broadcast `PHANTOM_DISCOVER_WORKERS` to `{broadcast_addr}:8095`, unicast to `127.0.0.1:8095`.
- **Timeout:** 1500 ms per subnet (`TIMEOUT_MS`).
- **Deduplication:** By `worker_id` via `HashSet`.
- **Manifest validation:** `msg_type == "WORKER_MANIFEST"`, non-empty `worker_id`.
- **Doctrine:** No probing, ARP, or port scanning. **Aligned.**

### 3.2 Worker Listener (`discovery_listener.py`)
- **Port:** 8095.
- **Start order:** Called from `worker.start_background_tasks()` which runs **after** `register_with_controller()` and **before** `uvicorn.serve()`. So discovery listener is up before HTTP server. Worker init (~GPU detect, plugins, socket) runs first; then HTTP register; then background tasks (discovery + heartbeat + monitoring); then uvicorn.
- **Latency:** Worker needs `initialize()` + `register_with_controller()` before discovery listener starts. Deploy sleeps 2s after spawning worker. If init takes >2s, discovery may run before listener is ready.

### 3.3 Why `discover_workers_comprehensive()` Fails (Installer)
- **File:** `installer/modules/worker_discovery.py`
- **Mechanism:** TCP connect to 8090–8094; sends `{"action": "get_info"}` as raw bytes; expects JSON response.
- **Worker API:** HTTP on 8090; expects HTTP requests, not raw JSON.
- **Result:** `_query_worker_info()` fails; fallback returns minimal info (`Worker-{ip}`) without real worker_id/gpu.
- **Usage:** Called by installer GUI/CLI; **not used by Tauri deploy**.

### 3.4 Tauri Discovery Failure Modes
1. **Port 8095 not opened:** Deploy `open_ports()` opens only 8080. Firewall may block 8095.
2. **Worker readiness:** 2s sleep may be insufficient if GPU detection or plugin init is slow.
3. **Broadcast filtering:** Some networks filter broadcast; unicast to 127.0.0.1 should still find local worker.
4. **Listener bind failure:** `discovery_listener.py` binds `0.0.0.0:8095`; if port in use, logs warning and returns early.

### 3.5 Deduplication
- Rust `discover_workers()` deduplicates by `worker_id`. Worker may self-register via HTTP and also respond to discovery; both paths can register same worker. Controller `/workers/register` may deduplicate or overwrite; not audited here.

---

## 4. GPU DIAGNOSTIC

### 4.1 Tauri GPU Detection
- **File:** `phantom_app/src-tauri/src/backend/linux/gpu_detection.rs`, `.../windows/gpu_detection.rs`
- **Usage:** `verify_gpu_plugins()` in deploy step 3.
- **Behavior:** Logs GPU count or "CPU-only mode"; **never returns Err**.
- **Blocking:** None.

### 4.2 Linux Worker GPU Detection
- **File:** `phantom_core/linux-worker/linux_worker/gpu/gpu_info_linux.py`
- **Usage:** `worker.py` line 147: `self.gpu_info = await self.gpu_detector.detect_gpu()`.
- **Fallback:** If `detect_gpu()` returns None, sets `gpu_info` to CPU placeholder (lines 149–158). **Does not block.**
- **Blocking:** None.

### 4.3 LLM Pipeline VRAM Checks
- **File:** `phantom_core/llm_taskmaster/pipeline.py`
- **Class:** `MemoryGuard`
- **Behavior:** `_read_gpu_vram()` via nvidia-smi/rocm-smi; fallback to config-based estimates. If model footprint > available VRAM, sets `reject_insufficient_vram` and `final_verdict = REJECT`. Does not block worker startup.
- **Blocking:** Rejects routing/model load; does not block worker process.

### 4.4 Installer GPU Logic
- **File:** `installer/backend_interface/system_scan_adapter.py`
- **Function:** `_detect_gpu()` — best-effort nvidia-smi/rocm-smi; returns "ok", "warning", or "unknown". Not blocking.
- **Message:** "No GPU detected — CPU mode will be used" when no GPU found.

### 4.5 Misleading Log
- **File:** `phantom_deployer.rs` line 413 (Linux only)
- **Text:** `"Failed to start local worker (GPU required): {e}"`
- **Reality:** Worker supports CPU fallback. Error reflects spawn failure (e.g. module not found, Python crash), not GPU requirement.

### 4.6 GPU Detection Consistency
- Tauri: NVIDIA (Linux), NVIDIA + WMI (Windows); log-only.
- Worker: NVIDIA, AMD ROCm, lspci fallback; CPU fallback.
- LLM pipeline: nvidia-smi, rocm-smi, config fallback; rejects insufficient VRAM at routing time.
- Overall: GPU is optional for worker startup; CPU fallback present. Log message contradicts this.

---

## 5. PORT + SERVICE DIAGNOSTIC

### 5.1 Ports Used

| Port | Role | Opened by Deploy | Health Check |
|------|------|------------------|--------------|
| 8080 | Controller API | Yes (TCP) | `/health` used by app |
| 8081 | Socket (WebSocket) | No | DeploymentsPanel checks `http://127.0.0.1:8081/health` |
| 8090 | Worker HTTP | No | None in deploy |
| 8095 | Discovery UDP | No | None |

### 5.2 Port Conflicts
- Deploy opens only 8080. If 8090 or 8095 are blocked by firewall, local worker discovery may fail.
- No check for port 8090 or 8095 availability before worker spawn.

### 5.3 Missing Firewall Rules
- 8081 (socket): not opened.
- 8090 (worker): not opened.
- 8095 (discovery): not opened. UDP rarely blocked by host firewall but may be blocked on some setups.

### 5.4 Health Checks
- Controller: `get_phantom_health`, `get_workers`, etc. hit `http://127.0.0.1:8080`.
- Socket: DeploymentsPanel checks 8081; no deploy-time verification.
- Worker: No deploy-time health check.
- Discovery listener: No health check.

### 5.5 Systemd Service Port
- Unit runs `run.py --host 127.0.0.1 --port 8080`. Controller only; no worker or discovery started by systemd.

---

## 6. SUMMARY TABLE

| Category | Finding |
|----------|---------|
| Controller selection | Missing; fixed at 127.0.0.1:8080 |
| Worker selection | Missing; all discovered workers auto-registered |
| Manifest signing | Missing; manifests unsigned |
| Discovery mechanism | Broadcast/unicast UDP 8095; doctrine-aligned |
| Installer discovery | TCP probing; incompatible with workers; not used by Tauri |
| GPU blocking | None; CPU fallback present |
| Misleading logs | "GPU required", "port 8090" in tooltip |
| Ports opened | 8080 only; 8081, 8090, 8095 not opened |
| phantom_config | Written in step 10; comment says step 9 |
| Identity in deploy | Not used |

---

*End of report. No code changes proposed.*
