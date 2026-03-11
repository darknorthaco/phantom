# Phantom Worker Implementation — Multi-Layer Audit Report

**Date:** 2025-03-11  
**Scope:** Full repository audit — worker implementations, deployer paths, OS support, packaging, discovery, and silent failures  
**Method:** Inspection only. No code changes. No modifications to any files.

---

## 1. Executive Summary

| Finding | Severity | Status |
|---------|----------|--------|
| Windows worker has no executable runtime | **CRITICAL** | `windows-worker/` contains only JSON configs; no `main.py`, `run_worker.ps1`, or entrypoint |
| Deployer uses `linux-worker` on Windows | **INFO** | Windows deploy path correctly uses `linux-worker` (Python is cross-platform) |
| `run_worker.ps1` referenced in docs but missing | **HIGH** | DEPLOYMENT_GUIDE.md, README.md, TOPOLOGY_SETUP.md instruct `.\run_worker.ps1` — file does not exist |
| macOS worker not implemented | **KNOWN** | PHASE_1_PLATFORM_ARCHITECTURE_REPORT documents "Worker Support: Not supported" |
| Deployer silently succeeds when worker fails | **MEDIUM** | `main_py` missing or `cmd.spawn()` failure returns `Ok(())` with log-only |
| Discovery pipeline assumes linux-worker | **INFO** | Correct — linux-worker has discovery_listener on UDP 8095 |

---

## 2. Worker Implementations Found

### 2.1 Directory and Entrypoint Summary

| Directory | Entrypoint | OS Target | Status |
|-----------|------------|-----------|--------|
| `phantom_core/linux-worker/` | `linux_worker/main.py` | Linux (Python — runs on Windows too) | **COMPLETE** |
| `phantom_core/windows-worker/` | **NONE** | Windows | **CONFIG ONLY** |
| `phantom_core/` (macos-worker) | N/A | macOS | **DOES NOT EXIST** |

### 2.2 Linux Worker — Full Implementation

**Location:** `phantom_core/linux-worker/`

**Entrypoint:** `phantom_core/linux-worker/linux_worker/main.py`

**Structure:**
```
phantom_core/linux-worker/
├── linux_worker/
│   ├── __init__.py
│   ├── main.py              ← Entrypoint
│   ├── worker.py            ← PhantomLinuxWorker, FastAPI, registration, heartbeat
│   ├── discovery_listener.py ← UDP 8095, PHANTOM_DISCOVER_WORKERS
│   └── gpu/
│       ├── __init__.py
│       └── gpu_info_linux.py ← NVIDIA nvidia-smi, AMD rocm-smi (Linux-focused)
├── plugins/
│   ├── __init__.py
│   ├── plugin_manager.py
│   ├── nvidia_cuda_plugin.py
│   ├── amd_rocm_plugin.py
│   ├── firepro_plugin.py
│   ├── rtx50_plugin.py
│   ├── gtx1080_plugin.py
│   └── general_plugin.py
├── deploy_workers.sh
├── worker_config_*.json     (if any)
```

**Notes:**
- `main.py` invokes `python -m linux_worker.main --config <path>`
- Uses `gpu_info_linux.py` — `nvidia-smi` works on Windows; AMD `rocm-smi` is Linux-only
- Worker supports CPU-only fallback when no GPU detected
- Discovery listener runs on UDP port 8095

### 2.3 Windows Worker — Config Only, No Runtime

**Location:** `phantom_core/windows-worker/`

**Contents:**
- `worker_config_network.json` — template (RTX 5080, port 8091)
- `worker_config_rtx5060.json` — template (RTX 5060, port 8092)

**Missing:**
- No `main.py`, `worker_main.py`, `run_worker.py`, or any Python entrypoint
- No `run_worker.ps1` (documented but absent)
- No `windows_worker/` package, no GPU detection, no plugin loader

**References in docs:**
- `DEPLOYMENT_GUIDE.md`, `README.md`, `TOPOLOGY_SETUP.md` instruct: `cd windows-worker`, `.\run_worker.ps1`
- `CHANGELOG.md` v1.0.0 claims "Windows worker implementation" — no such code exists in current tree
- `PHASE_1_PLATFORM_ARCHITECTURE_REPORT.md` (ARCH-008): "Windows worker is config-only — no Python runtime code"

### 2.4 macOS Worker — Not Implemented

**Status:** No `macos-worker` or `darwin-worker` directory.  
**Documentation:** `phantom_core/PHASE_1_PLATFORM_ARCHITECTURE_REPORT.md` §5.3: "Worker Support | Not supported — no macOS worker implementation"

### 2.5 Rust / Tauri Worker

**Status:** No Rust-based or Tauri-based worker implementation found. All worker logic is Python (`linux-worker`).

---

## 3. Expected Worker Paths in Deployer

### 3.1 Code References

**File:** `phantom_app/src-tauri/src/backend/phantom_deployer.rs`

| Lines | Logic | Path Used |
|-------|-------|-----------|
| 604–606 (Linux) | `start_local_worker` | `engine.join("linux-worker")` → `main_py = linux_worker_dir.join("linux_worker").join("main.py")` |
| 646–648 (Windows) | `start_local_worker` | **Identical:** `engine.join("linux-worker")` → same `main_py` path |
| 604, 646 | `engine` | `self.phantom_root.join("engine")` |

**Engine source resolution:** `find_engine_source()` in `lib.rs:540–567`
1. Bundled: `app.path().resource_dir().join("phantom_core")`
2. Dev: `/workspace/phantom_core` or `../phantom_core`
3. Fallback: `~/.phantom/engine` (or `%USERPROFILE%\.phantom\engine` on Windows)

**Install step:** `install_phantom_core()` copies `engine_source` → `phantom_root/engine` via `copy_dir_all()`. So `~/.phantom/engine/` contains `run.py`, `linux-worker/`, `windows-worker/`, etc.

### 3.2 Expected Absolute Path on Windows

- `%USERPROFILE%\.phantom\engine\linux-worker\linux_worker\main.py`
- This path **exists** after a successful deploy (copy from `phantom_core`).

### 3.3 Run Command (Both Linux and Windows)

```rust
python -m linux_worker.main --config <local_worker_config_path>
```

- `current_dir`: `engine/linux-worker`
- `PYTHONPATH`: `engine/linux-worker`
- Config: `phantom_root/local_worker_config.json`

---

## 4. Path Mismatches or Missing Workers

### 4.1 Deployer Never References `windows-worker`

| Expected by User / Docs | Actual Deployer |
|------------------------|-----------------|
| Windows-specific worker in `windows-worker/` | Deployer uses `linux-worker` on both Linux and Windows |
| `run_worker.ps1` in `windows-worker/` | File does not exist |

**Interpretation:** The Tauri deployer intentionally uses the Linux worker (Python) on Windows. The `windows-worker/` folder is **unused by the deployer**; it is a placeholder for future native Windows worker or for manual/installer-based deployment that was never completed.

### 4.2 Documentation vs Reality

| Document | Instruction | Exists? |
|----------|-------------|---------|
| `DEPLOYMENT_GUIDE.md` | `cd windows-worker`, `.\run_worker.ps1` | No — `run_worker.ps1` missing |
| `README.md` | Same | No |
| `TOPOLOGY_SETUP.md` | Same | No |
| `UNINSTALL_WIZARD_PROPOSALS.md` | "Windows workers require PowerShell scripts (see windows-worker/README.md)" | No `windows-worker/README.md` |

### 4.3 prepare-resources.mjs

**File:** `phantom_app/scripts/prepare-resources.mjs`

- Includes `windows-worker` in `INCLUDE_DIRS` (line 30)
- Bundles `phantom_core/windows-worker/` (config JSONs only) into Tauri resources
- No runtime benefit — only config files are bundled

---

## 5. Impact on Windows Deployment

### 5.1 Tauri Deploy on Windows

| Step | Behavior |
|------|----------|
| 2. Install Phantom Core | Copies `phantom_core` (including `linux-worker`) to `~/.phantom/engine` |
| 9. Start local worker | Looks for `engine/linux-worker/linux_worker/main.py` — **present** |
| | Runs `python -m linux_worker.main --config ...` |

**Conclusion:** Windows deployment via Tauri **can** start a local worker if:
- `engine_source` resolves correctly (bundled or dev path)
- Python venv is created and deps installed
- `linux-worker` is copied into `engine`
- `gpu_info_linux.py` uses `nvidia-smi` (available on Windows with NVIDIA drivers) — AMD GPUs may not be detected (rocm-smi is Linux-only)

### 5.2 Risks on Windows

1. **GPU detection:** `gpu_info_linux.py` is Linux-biased. NVIDIA works; AMD ROCm does not. CPU-only mode is supported.
2. **Signal handling:** `main.py` uses `signal.signal(signal.SIGTERM, ...)` — Windows has limited SIGTERM support; shutdown may differ.
3. **Paths:** Deployer uses `venv\Scripts\python.exe` — correct for Windows.

### 5.3 Standalone Windows Worker (Docs)

Users following `DEPLOYMENT_GUIDE.md` or `README.md` for **manual** Windows worker setup will fail:
- No `run_worker.ps1`
- No Python entrypoint in `windows-worker/`
- Config templates alone cannot start a worker

---

## 6. Logic Bombs and Silent Failures

### 6.1 `main_py` Not Found

**Location:** `phantom_deployer.rs` lines 607–609 (Linux), 649–651 (Windows)

```rust
if !main_py.exists() {
    log::info!("Local worker main.py not found, skipping");
    return Ok(());  // ← Silent success
}
```

**Effect:** Deployment reports success; no local worker is started. No error surfaced to the user.

### 6.2 Worker Spawn Failure

**Location:** `phantom_deployer.rs` lines 634–637 (Linux), 676–679 (Windows)

```rust
match cmd.spawn() {
    Ok(_) => log::info!("Local worker started on 0.0.0.0:8090"),
    Err(e) => log::warn!("Failed to start local worker: {e}"),  // ← Log only
}
// ... continues to run_readiness_probe()
```

**Effect:** If `spawn()` fails (e.g., Python not found, module import error), the deployer logs a warning and continues. Step still returns `Ok(())`. User sees "Deploy complete" but no worker.

### 6.3 Readiness Probe

**Location:** `phantom_deployer.rs` `run_readiness_probe()` (lines 699+)

- Sends UDP `PHANTOM_DISCOVER_WORKERS` to `127.0.0.1:8095`
- Waits for response or timeout
- Stores `(attempts, success)` in `readiness_result` for discovery log
- Does **not** fail the deploy step

**Effect:** If the worker fails to start, the probe times out. Deployment still succeeds.

---

## 7. Discovery Pipeline Assumptions

### 7.1 Expected Worker Behavior

- Worker runs `discovery_listener.run_discovery_listener()` on UDP 8095
- Listener responds to `PHANTOM_DISCOVER_WORKERS` with a manifest

### 7.2 OS Assumptions

| Assumption | Valid? |
|------------|--------|
| Worker listens on 8095 | Yes — `linux_worker` does this |
| Worker runs on this OS | Yes — deployer uses `linux-worker` on Windows and Linux |
| Worker is `linux_worker` | Yes — no other worker type is launched |

**Conclusion:** The discovery pipeline does **not** assume a worker that is missing on Windows. It assumes the same `linux-worker` that the deployer starts. If that worker fails to start, discovery finds no local worker — by design, not by wrong path.

---

## 8. Build Artifacts and Packaging for Windows Worker

### 8.1 Searched For

- `*.spec` (PyInstaller)
- `*.ps1` in `windows-worker` or `installer`
- `build.*`, `package.*` scripts mentioning Windows worker

### 8.2 Found

| Artifact | Purpose |
|----------|---------|
| `installer/phantom_installer.ps1` | Installer wrapper — not worker packaging |
| `phantom_app/build.ps1` | Tauri app build — not worker |
| `prepare-resources.mjs` | Bundles `windows-worker` configs only |

**Conclusion:** No build artifacts or scripts for packaging a standalone Windows worker binary or executable. `windows-worker` is not packaged as a runnable component.

---

## 9. Recommended Fixes

### 9.1 Critical / High

| ID | Recommendation | Effort |
|----|----------------|--------|
| R1 | Implement `run_worker.ps1` that invokes `python -m linux_worker.main --config <path>` (or equivalent) from `windows-worker/`, using the venv Python from `~/.phantom/venv/Scripts/python.exe` when available | Low |
| R2 | Update `DEPLOYMENT_GUIDE.md`, `README.md`, `TOPOLOGY_SETUP.md` to either: (a) document that Windows uses `linux-worker` and provide correct commands, or (b) remove references to `run_worker.ps1` until it exists | Low |
| R3 | Add `windows-worker/README.md` explaining that Windows currently runs the Linux worker and how to invoke it | Low |

### 9.2 Medium

| ID | Recommendation | Effort |
|----|----------------|--------|
| R4 | When `main_py` is missing: emit a deploy-progress warning or include in discovery log; consider `discovery_failed: true` when no workers discovered and worker was expected | Medium |
| R5 | When `cmd.spawn()` fails: surface the error (e.g., via `scan-log` or discovery log) so the user knows the worker did not start | Low |
| R6 | Add `gpu_info_windows.py` or refactor `gpu_info_linux.py` into a shared module with OS-specific backends for proper NVIDIA/AMD detection on Windows | Medium |

### 9.3 Low / Future

| ID | Recommendation | Effort |
|----|----------------|--------|
| R7 | Implement native `windows-worker` Python package (mirroring `linux_worker` structure) if Windows-specific behavior is required | High |
| R8 | Document macOS as "no worker support" in user-facing docs to avoid confusion | Low |

---

## 10. Appendix: File and Path Cross-Reference

### Worker-Related Files

| Path | Type |
|------|------|
| `phantom_core/linux-worker/linux_worker/main.py` | Entrypoint |
| `phantom_core/linux-worker/linux_worker/worker.py` | Worker logic |
| `phantom_core/linux-worker/linux_worker/discovery_listener.py` | Discovery responder |
| `phantom_core/linux-worker/linux_worker/gpu/gpu_info_linux.py` | GPU detection |
| `phantom_core/windows-worker/worker_config_network.json` | Config template |
| `phantom_core/windows-worker/worker_config_rtx5060.json` | Config template |

### Deployer References

| Symbol | File:Line |
|--------|-----------|
| `start_local_worker` (Linux) | phantom_deployer.rs:603–641 |
| `start_local_worker` (Windows) | phantom_deployer.rs:645–684 |
| `start_local_worker` (other OS) | phantom_deployer.rs:687–689 |
| `engine.join("linux-worker")` | phantom_deployer.rs:605, 647 |
| `venv_python` (Windows) | phantom_deployer.rs:1341–1343 |

---

**Report complete. Awaiting approval before any changes.**
