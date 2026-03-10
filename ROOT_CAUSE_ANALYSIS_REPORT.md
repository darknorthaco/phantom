# Phantom Deploy Flow — Root-Cause Analysis Report

**Date:** 2025-03-10  
**Basis:** GAP_ANALYSIS_AUDIT_REPORT.md  
**Method:** Inspection only. No code changes. No proposed solutions.

---

## 1. ROOT-CAUSE ANALYSIS (Per Gap)

### 1.1 Controller Selection Ceremony — MISSING

| Field | Finding |
|-------|---------|
| **Exact file/function** | `phantom_deployer.rs::start_controller()` lines 250–287. No ceremony in `App.tsx`, `WizardWelcome.tsx`, `FrontPorchDeploy.tsx`. `identity_manager.rs` exists but is never invoked during deploy. |
| **Architectural assumption** | Single-node, local-first deployment. Controller location is fixed and implicit: `127.0.0.1:8080`. The deploy flow was designed as a linear "install and run locally" sequence with no branching or user choice. |
| **Missing logic** | No UI step to choose controller host, port, or device. No call to `get_identity` or identity display during deploy. No controller placement selection. |
| **Incorrect logic** | None. Logic assumes fixed local controller. |
| **Contradictions** | **Doctrine:** Controller selection ceremony is intended. **UX:** WizardWelcome asks consent for "configure your system as a compute controller" but offers no placement choice. **Deploy flow:** Step 5 hardcodes host/port. |
| **Gap type** | Architectural, UX/UI. |
| **Severity** | Medium-risk. Deployment works for local-only; multi-device or custom placement scenarios fail. |

**Why it was never implemented:** The Tauri Stone-Home app was built as a streamlined "one-click" deploy. Identity was implemented for WAN/trust (ExperimentalAOL) and was never wired into the deploy path. The installer architecture spec (S0–S7) does not define a controller selection stage; it assumes a central node.

**Where it should have been inserted:** Between WizardWelcome consent and FrontPorchDeploy, or as a pre–Step 5 screen. Would require: a new React phase/screen, a Tauri command to load identity or accept placement params, and `start_controller()` to consume host/port from config or args.

**Files that would need to support it:** `App.tsx`, new `ControllerSelectionScreen.tsx`, `phantom_deployer.rs` (accept placement), `phantom_state.rs` (controller_url), `identity_manager.rs` (invocation on first deploy).

---

### 1.2 Worker Selection Ceremony — MISSING

| Field | Finding |
|-------|---------|
| **Exact file/function** | `phantom_deployer.rs::scan_lan()` lines 466–527; `scan_and_register_workers()` lines 434–477. Both register every manifest. `WorkersPanel.tsx` shows workers post-registration only. |
| **Architectural assumption** | "Discover and register" in one shot. No intermediate step between discovery and registration. The flow assumes all discovered workers are trusted. |
| **Missing logic** | No UI to display discovered-but-unregistered workers. No `select_workers` or approval step. No filtering before `controller.register_worker()`. |
| **Incorrect logic** | `for m in manifests { ... controller.register_worker(&req).await }` registers all. No selection gate. |
| **Contradictions** | **Doctrine:** "Trust relationships require manual approval" (.cursorrules:50). **Installer:** Has S2 Worker Discovery → S3 Worker Selection (INSTALLER_ARCHITECTURE_SPEC) with `select_workers()`. **Deploy flow:** Tauri path skips selection. |
| **Gap type** | Architectural, UX/UI, Doctrine violation. |
| **Severity** | High-risk. Auto-registration bypasses trust model; any reachable worker is trusted. |

**Why scan_lan() auto-registers:** The deployer was designed for a linear step sequence. Step 9 was implemented as "scan then register" without an intervening ceremony. The installer's `WorkerDiscovery.select_workers()` exists but is never used by the Tauri deploy path.

**Why no UI exists:** WorkersPanel displays workers from `GET /workers` (already registered). Discovery results are never shown before registration. Scan runs, manifests are collected, then immediately registered. No React component receives "discovered, not yet registered" list.

**Where selection logic should live:** Between `discovery::discover_workers()` and `controller.register_worker()`. Would require: (a) emit discovered manifests to frontend, (b) new UI to select/deselect, (c) Tauri command or deploy step that registers only selected workers. Files: `phantom_deployer.rs`, `lib.rs` (new command or step), `WorkersPanel.tsx` or new `WorkerSelectionScreen.tsx`.

---

### 1.3 Manifest Signing — MISSING

| Field | Finding |
|-------|---------|
| **Exact file/function** | `discovery_listener.py::run_discovery_listener()` lines 36–42 (emits unsigned manifest). `controller_api.py::register_worker()` lines 477–519 (accepts `WorkerInfo` with no signature). `discovery.rs` parses `RawManifest` with no signature field. |
| **Architectural assumption** | LAN discovery is implicitly trusted. Signing reserved for WAN/cross-controller (identity_manager used in ExperimentalAOL). Worker manifests treated as self-attested, not cryptographically verified. |
| **Missing logic** | Worker does not sign manifest. Controller does not verify signature. `WorkerInfo` has no `signature` field. `identity_manager.rs::sign_message` / `verify_signature` never invoked for manifests. |
| **Incorrect logic** | `discovery_listener.py` docstring (line 2): "Responds with a signed manifest" — manifest has no signature. Docstring is aspirational, not accurate. |
| **Contradictions** | **Doctrine:** "All cross-controller messages must be signed" (.cursorrules). Manifest is cross-entity (worker→controller) but unsigned. **Discovery docstring:** Claims signing; code does not implement it. |
| **Gap type** | Architectural, Doctrine violation. |
| **Severity** | High-risk. Unsigned manifests allow impersonation; any host can claim any worker_id. |

**Where signing should occur:** In `discovery_listener.py`, before `sock.sendto(payload, addr)`. Worker would need access to a signing key (per-worker identity not present today; worker has no Ed25519). Manifest would need `signature` and optionally `public_key` or `worker_id`→key mapping.

**Where verification should occur:** In `phantom_deployer.rs` or in controller before `orchestrator.register_worker()`. Tauri could verify before calling `register_worker`; alternatively controller API would need to accept and verify signature. `controller_api.py` `register_worker` currently trusts all incoming `WorkerInfo`.

---

### 1.4 Worker Readiness Timing — RISK

| Field | Finding |
|-------|---------|
| **Exact file/function** | `phantom_deployer.rs::start_local_worker()` line 417: `tokio::time::sleep(2s)`. `main.py` lines 54–59: `initialize()` → `register_with_controller()` → `start_background_tasks()` (discovery listener). |
| **Architectural assumption** | Worker is ready within 2 seconds. Init (GPU, plugins, socket) and HTTP register complete quickly. |
| **Missing logic** | No readiness probe. No retry or backoff. Fixed 2s sleep regardless of machine speed or GPU presence. |
| **Incorrect logic** | None. Timing may simply be insufficient on slow systems. |
| **Contradictions** | **DARPA audit:** Discovery failures. **Gap report:** Worker may not be listening when discovery runs. **Deploy flow:** Step 8 spawns, sleeps 2s, Step 9 runs discovery. |
| **Gap type** | Timing-related, worker readiness–related. |
| **Severity** | Medium-risk. Discovery may miss local worker on slow machines; deploy still completes. |

**Discovery listener start order:** `main.py`: `initialize()` (GPU detect, plugins, optional socket) → `register_with_controller()` (HTTP POST) → `start_background_tasks()` (spawns discovery listener thread) → `uvicorn.serve()`. Listener starts only after init and HTTP register. If init takes >2s, discovery in step 9 may run before listener binds to 8095.

**Does register_with_controller() block readiness?** Yes. If controller is not yet up, register fails and `main()` returns 1 (worker exits). So worker either never starts listening, or it completes register and then starts listener. The 2s includes controller startup (3s) + worker spawn, so controller should be up. Risk: worker init > 2s on GPU detection or plugin load.

---

### 1.5 Port Alignment — 8080 Only Opened; UI Port Mismatch

| Field | Finding |
|-------|---------|
| **Exact file/function** | `phantom_deployer.rs::open_ports()` lines 289–372: only `8080/tcp`. `WorkersPanel.tsx` line 72: tooltip "port 8090". `discovery.rs`: uses port 8095. |
| **Architectural assumption** | Controller is the only service that needs firewall rules. Worker (8090) and discovery (8095) are on localhost or trusted LAN; host firewall does not block them. Socket (8081) not considered part of deploy. |
| **Missing logic** | No rules for 8081, 8090, 8095. `open_ports()` has no loop or parameterization; single hardcoded port. |
| **Incorrect logic** | None. Port-8090 tooltip is incorrect for discovery (which uses 8095). |
| **Contradictions** | **DARPA audit:** Port conflicts, discovery failures. **UI:** Tooltip says 8090; discovery uses 8095. **Port roles:** 8090 = worker HTTP; 8095 = discovery UDP. Tooltip conflates them. |
| **Gap type** | Port/firewall-related, cosmetic (tooltip). |
| **Severity** | Medium-risk (firewall); Cosmetic (tooltip). |

**Why deploy opens only 8080:** `open_ports()` was written to open the controller port. Design focus was "make controller reachable"; worker and discovery were assumed local or on trusted networks. DARPA/SELinux notes mention 8081, 8090–8092; deploy was never updated to match.

**Why UI references 8090:** WorkersPanel tooltip likely copied from installer or docs where 8090 is the worker port. Discovery uses 8095; tooltip was not updated when discovery protocol changed.

---

### 1.6 GPU "Required" Misleading Log

| Field | Finding |
|-------|---------|
| **Exact file/function** | `phantom_deployer.rs::start_local_worker()` line 413 (Linux cfg only): `"Failed to start local worker (GPU required): {e}"` |
| **Architectural assumption** | Unclear. Log implies GPU is required. Worker code has CPU fallback. |
| **Missing logic** | None. |
| **Incorrect logic** | Log text. Spawn failure can be for any reason (module import, Python path, config, etc.). "GPU required" is wrong when failure is non-GPU. |
| **Contradictions** | **GPU audit:** Worker has CPU fallback. **DARPA:** GPU dependency issues. Log reinforces incorrect belief that GPU is required. **Windows variant:** Line 354 does not say "GPU required"; platform inconsistency. |
| **Gap type** | Cosmetic (log message). |
| **Severity** | Cosmetic. Misleading; may cause unnecessary debugging or incorrect user belief. |

**Root cause:** Log string appears to date from when worker was GPU-centric. CPU fallback was added in `worker.py` (lines 148–158); log was never updated. Linux has the bad message; Windows does not — suggests different authors or copy-paste with platform-specific edits.

---

### 1.7 Config Ordering Bug — phantom_config Read Before Write

| Field | Finding |
|-------|---------|
| **Exact file/function** | `phantom_deployer.rs::start_controller()` lines 259–263: reads `phantom_config.json`. `load_execution_modes()` lines 423–435: writes `phantom_config.json`. Step order: 5 (read) before 10 (write). Comment line 259: "written by step 9" — wrong. |
| **Architectural assumption** | Config exists before controller start, or fallback is acceptable. `unwrap_or_else(|| "disabled")` handles missing file. |
| **Missing logic** | Correct step order (write before read) or bootstrap of config before step 5. |
| **Incorrect logic** | Comment says "step 9"; actual write is step 10. Step order: config read in 5, written in 10. |
| **Contradictions** | **Deploy flow:** Read-before-write. **Comment:** Wrong step number. |
| **Gap type** | Config ordering–related. |
| **Severity** | Low-risk. Fallback "disabled" works; comment is wrong; ordering is fragile if config ever becomes required for correctness. |

**Root cause:** `load_execution_modes` was added as step 10. `start_controller` predates it and was written to read config. Either (a) config used to be written earlier and steps changed, or (b) config was always written late and the fallback was intentional. Comment "step 9" is simply wrong (step 9 is scan_lan).

---

### 1.8 Installer Discovery — TCP Probing Incompatible with HTTP

| Field | Finding |
|-------|---------|
| **Exact file/function** | `installer/modules/worker_discovery.py::_query_worker_info()` lines 156–191. Sends raw `{"action":"get_info"}` over TCP; expects JSON. Worker listens for HTTP on 8090. |
| **Architectural assumption** | Worker speaks a custom TCP protocol. Comment line 158: "This is a placeholder - actual implementation would use the Phantom protocol." Never updated when worker standardized on HTTP. |
| **Missing logic** | HTTP request (e.g. GET / or GET /health) instead of raw JSON. |
| **Incorrect logic** | TCP send of JSON; worker expects HTTP. `connect` succeeds; `recv` gets nothing or malformed; `json.loads` fails; fallback returns minimal info. |
| **Contradictions** | **DARPA audit:** Discovery failures. **Installer vs Tauri:** Installer uses this path; Tauri uses `discovery.rs` (UDP). Installer discovery broken for HTTP workers. |
| **Gap type** | Legacy code, incorrect protocol assumption. |
| **Severity** | High-risk for installer path. Tauri deploy unaffected (uses discovery.rs). |

**Root cause:** `worker_discovery.py` predates or was developed in parallel with worker HTTP API. "Placeholder" was never replaced. Installer and Tauri deploy diverged; installer never adopted UDP discovery.

---

### 1.9 Deploy Step Failure Handling — Non-Blocking

| Field | Finding |
|-------|---------|
| **Exact file/function** | `lib.rs::deploy_phantom()` lines 313–321: `if let Err(e) = deployer.run_step(i).await { log::warn!(...); /* audit */ }` — does not return or abort. |
| **Architectural assumption** | Deployment is best-effort. Failures are logged; flow continues. |
| **Missing logic** | Abort on critical step failure. User notification of failure. Rollback or retry. |
| **Incorrect logic** | None. Behavior is per design; may conflict with user expectation that deploy either fully succeeds or clearly fails. |
| **Contradictions** | **UX:** User sees "Deployment complete" even if steps failed. Progress bar reaches 100%. |
| **Gap type** | UX/UI, architectural. |
| **Severity** | Medium-risk. Silent failures; user may believe deploy succeeded when it did not. |

*(Not in original gap list but implied by trace; included for completeness.)*

---

## 2. CROSS-MAP TABLE

| Intended Behavior | Actual Behavior | Root Cause | File/Function | Severity |
|-------------------|-----------------|------------|--------------|----------|
| Controller selection ceremony | Fixed 127.0.0.1:8080, no choice | Linear deploy design; identity not wired to deploy | `phantom_deployer.rs::start_controller`, `App.tsx` | Medium |
| Worker selection ceremony | All discovered workers auto-registered | Discover-and-register in one step; no selection gate | `phantom_deployer.rs::scan_lan` | High |
| Manifest signing | Unsigned JSON manifests | LAN assumed trusted; signing reserved for WAN | `discovery_listener.py`, `controller_api.py::register_worker` | High |
| Worker ready for discovery | 2s sleep; may miss slow worker | Fixed sleep; no readiness probe | `phantom_deployer.rs::start_local_worker`, `main.py` | Medium |
| Ports 8081, 8090, 8095 opened | Only 8080 opened | Design assumed controller-only firewall rules | `phantom_deployer.rs::open_ports` | Medium |
| UI tooltip port accuracy | "port 8090" | Conflation of worker HTTP (8090) and discovery (8095) | `WorkersPanel.tsx` | Cosmetic |
| GPU optional, log accurate | "GPU required" on spawn failure | Legacy log; CPU fallback added later | `phantom_deployer.rs::start_local_worker` | Cosmetic |
| phantom_config before controller start | Read in step 5, written in step 10 | Config added as step 10; read left in step 5; comment wrong | `phantom_deployer.rs` | Low |
| Installer discovery works | TCP probe fails (HTTP worker) | Placeholder never updated; protocol mismatch | `installer/modules/worker_discovery.py` | High (installer) |

---

## 3. DEPLOY FLOW CORRECTION MAP

### 3.1 What Deploy Flow Assumes

| Step | Assumption | Evidence |
|------|------------|----------|
| 0–2 | venv, deps, engine exist or can be created | `create_venv`, `install_python_deps`, `install_phantom_core` |
| 3 | GPU presence optional | `verify_gpu_plugins` never returns Err |
| 4 | Service can be installed (or fails non-fatally) | `install_service` |
| 5 | phantom_config.json exists or fallback "disabled" is ok | `read_controller_config` + `unwrap_or_else` |
| 5 | Controller binds 127.0.0.1:8080 | Hardcoded args |
| 6 | Port 8080 is the only one needing firewall rule | `open_ports` single-port logic |
| 7 | Marker file indicates deployed | `initialize_state` |
| 8 | Worker starts and is ready within 2s | `sleep(2)` |
| 9 | Discovered workers are trusted | No selection; register all |
| 10 | Config files can be written after controller start | `load_execution_modes` |

### 3.2 What Deploy Flow Actually Does

| Step | Actual Behavior | Where Assumption Breaks |
|------|-----------------|-------------------------|
| 5 | Reads phantom_config; file absent on first run → "disabled" | Comment says step 9; write is step 10 |
| 8 | Spawns worker; 2s sleep | Worker init may exceed 2s; discovery may miss |
| 9 | Registers all manifests | No trust ceremony |
| 9 | Discovery uses UDP 8095 | Port not opened; may be blocked on some systems |

### 3.3 Timing / Ordering Breaks

| Break | Location | Impact |
|-------|----------|--------|
| phantom_config read before write | Step 5 vs Step 10 | Fallback saves; comment wrong; fragile |
| Worker discovery before listener ready | Step 9 vs worker `start_background_tasks` | 2s may be too short; local worker may not appear |
| Controller start before config | Step 5 vs Step 10 | Controller runs with "disabled" on first deploy; systemd unit uses "basic" (separate path) |

---

## 4. SUMMARY

- **Controller selection:** Never implemented; linear local-first deploy design.
- **Worker selection:** Skipped in Tauri path; installer has it but deployer does not.
- **Manifest signing:** Not implemented; LAN trust assumed.
- **Timing:** 2s worker sleep may be insufficient; no readiness check.
- **Ports:** Only 8080 opened; 8090/8095/8081 not considered.
- **Logs/UI:** GPU "required" and port 8090 tooltip are misleading.
- **Config:** phantom_config read before write; comment wrong.
- **Installer:** TCP discovery incompatible with HTTP workers; Tauri uses UDP.

*End of report. No code changes proposed.*
