# Phase 6 — Windows Worker Implementation: Full Diffs

**Status:** Implementation applied. Awaiting your approval.  
**Date:** 2025-03-11

---

## Summary of Changes

| Category | Files | Action |
|----------|-------|--------|
| New | `phantom_core/windows-worker/windows_worker/__init__.py` | Created |
| New | `phantom_core/windows-worker/windows_worker/main.py` | Created |
| New | `phantom_core/windows-worker/windows_worker/worker.py` | Created |
| New | `phantom_core/windows-worker/windows_worker/discovery_listener.py` | Created |
| New | `phantom_core/windows-worker/windows_worker/utils/__init__.py` | Created |
| New | `phantom_core/windows-worker/windows_worker/utils/config_loader.py` | Created |
| New | `phantom_core/windows-worker/windows_worker/utils/logging_utils.py` | Created |
| New | `phantom_core/windows-worker/windows_worker/gpu/__init__.py` | Created |
| New | `phantom_core/windows-worker/windows_worker/gpu/gpu_info_windows.py` | Created |
| New | `phantom_core/windows-worker/run_worker.ps1` | Created |
| Modified | `phantom_app/src-tauri/src/backend/phantom_deployer.rs` | Windows `start_local_worker` |
| Unchanged | `phantom_app/scripts/prepare-resources.mjs` | Already includes `windows-worker` |

---

## 1. phantom_deployer.rs — Windows start_local_worker

**Location:** `phantom_app/src-tauri/src/backend/phantom_deployer.rs` (lines 644–698)

**Changes:**
- Use `windows-worker` path instead of `linux-worker`
- Use `windows_worker.main` module instead of `linux_worker.main`
- **No silent failures:** If `main_py` missing → return `Err(...)` with `worker_runtime_missing`
- **No silent failures:** If `cmd.spawn()` fails → return `Err(...)` with `worker_spawn_failed`

```diff
     #[cfg(target_os = "windows")]
     async fn start_local_worker(&self) -> Result<(), String> {
         let engine = self.phantom_root.join("engine");
-        let linux_worker_dir = engine.join("linux-worker");
-        let main_py = linux_worker_dir.join("linux_worker").join("main.py");
-        if !main_py.exists() {
-            log::info!("Local worker main.py not found, skipping");
-            return Ok(());
+        let windows_worker_dir = engine.join("windows-worker");
+        let main_py = windows_worker_dir.join("windows_worker").join("main.py");
+
+        if !main_py.exists() {
+            let msg = "Windows worker runtime missing. Expected engine/windows-worker/windows_worker/main.py";
+            log::error!("worker_runtime_missing: {msg}");
+            return Err(format!(
+                "Windows worker runtime missing or failed to start. {}",
+                msg
+            ));
         }

         let config_path = self.phantom_root.join("local_worker_config.json");
         ...
-        cmd.args(["-m", "linux_worker.main", "--config"])
+        cmd.args(["-m", "windows_worker.main", "--config"])
             .arg(config_path.to_string_lossy().as_ref())
-            .current_dir(&linux_worker_dir)
-            .env("PYTHONPATH", linux_worker_dir.to_string_lossy().as_ref());
+            .current_dir(&windows_worker_dir)
+            .env("PYTHONPATH", windows_worker_dir.to_string_lossy().as_ref());

         match cmd.spawn() {
-            Ok(_) => log::info!("Local worker started on 0.0.0.0:8090"),
-            Err(e) => log::warn!("Failed to start local worker: {e}"),
+            Ok(_) => {
+                log::info!("Local Windows worker started on 0.0.0.0:8090");
+            }
+            Err(e) => {
+                let msg = format!("worker_spawn_failed: {e}");
+                log::error!("{}", msg);
+                return Err(format!(
+                    "Windows worker runtime missing or failed to start. {}",
+                    msg
+                ));
+            }
         }
```

---

## 2. New File: phantom_core/windows-worker/windows_worker/__init__.py

```python
# Windows Worker Package
"""Phantom Windows worker — mirrors Linux worker protocol with Windows-native APIs."""
```

---

## 3. New File: phantom_core/windows-worker/windows_worker/main.py

- Parse `--config`, load config, initialize worker
- Windows-safe: `signal.SIGINT`, `signal.SIGTERM` (if available), `KeyboardInterrupt`
- Starts HTTP server (uvicorn) and discovery listener
- Graceful shutdown in `finally`

(See full file in repo.)

---

## 4. New File: phantom_core/windows-worker/windows_worker/worker.py

- `PhantomWindowsWorker` class (mirrors `PhantomLinuxWorker`)
- `os` field in manifest and registration = `"windows"`
- Reuses `plugins` from `engine/linux-worker` via `sys.path`
- HTTP endpoints: `/`, `/health`, `/tasks/execute`, `/tasks/{id}`, `/metrics`, `/manifest`
- Windows-safe `get_system_metrics()` (disk path for Windows)
- Imports `phantom_core` and `plugins` from engine root

(See full file in repo.)

---

## 5. New File: phantom_core/windows-worker/windows_worker/discovery_listener.py

- UDP bind `0.0.0.0:8095`, same payload format as Linux
- Signed manifest via `phantom_core.discovery.ManifestSigner` / `SignedManifest`
- Windows-safe socket options (`SO_REUSEADDR`)
- Adds `os: "windows"` to manifest

(See full file in repo.)

---

## 6. New File: phantom_core/windows-worker/windows_worker/utils/config_loader.py

- `load_config(path)` — load JSON, normalize with Windows-friendly defaults

---

## 7. New File: phantom_core/windows-worker/windows_worker/utils/logging_utils.py

- Structured JSON logging (timestamp, event, success, duration_ms, metadata, error_message)
- `StructuredLogHandler`, `setup_structured_logging()`

---

## 8. New File: phantom_core/windows-worker/windows_worker/gpu/gpu_info_windows.py

- `GPUDetector` using `pynvml`
- Enumerates NVIDIA GPUs: name, memory total/free/used, driver version, temperature, compute capability
- If `pynvml` unavailable: logs `gpu_detection_unavailable`, returns empty list (non-fatal)

---

## 9. New File: phantom_core/windows-worker/run_worker.ps1

- Activates venv from `%USERPROFILE%\.phantom\venv\Scripts\python.exe` if present
- Runs `python -m windows_worker.main --config <path>`
- Validates `windows_worker/main.py` and config file exist
- Sets `PYTHONPATH` to windows-worker dir

---

## 10. prepare-resources.mjs

**No changes.** `windows-worker` is already in `INCLUDE_DIRS` (line 30). `copyDirRecursive` will bundle the new `windows_worker/` directory and all Python files.

---

## Directory Structure Created

```
phantom_core/windows-worker/
├── windows_worker/
│   ├── __init__.py
│   ├── main.py
│   ├── worker.py
│   ├── discovery_listener.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logging_utils.py
│   │   └── config_loader.py
│   └── gpu/
│       ├── __init__.py
│       └── gpu_info_windows.py
├── run_worker.ps1
├── worker_config_network.json   (pre-existing)
└── worker_config_rtx5060.json  (pre-existing)
```

---

## Deployment Flow (Windows)

1. `install_phantom_core()` copies `phantom_core` → `~/.phantom/engine`
2. `start_local_worker()` looks for `engine/windows-worker/windows_worker/main.py`
3. If missing → **Err** (no silent skip)
4. Writes `local_worker_config.json`, spawns `python -m windows_worker.main --config ...`
5. If spawn fails → **Err** (no silent warn)
6. Runs readiness probe (UDP 8095)

---

## Verification Commands

```powershell
# Manual run (from phantom_core):
cd phantom_core\windows-worker
.\run_worker.ps1 -ConfigPath worker_config_rtx5060.json

# Or with venv:
$env:PYTHONPATH = "D:\path\to\phantom_core\windows-worker"
python -m windows_worker.main --config local_worker_config.json
```

---

**Implementation complete. Awaiting your approval. Reply to confirm or request changes.**
