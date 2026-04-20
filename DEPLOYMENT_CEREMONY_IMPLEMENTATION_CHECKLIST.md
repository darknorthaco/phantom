# Deployment Ceremony Implementation Checklist

**Plan Approved.** Use this checklist to track implementation progress.

> Phase 13 note: items that reference legacy commands (`runDeploymentPreScan`,
> `completeDeploymentWithSelection`, `deployPhantom`) are historical migration
> artifacts. Canonical builds now run ceremony-only A→F and no longer expose
> those commands.

---

## Phase 1: Backend — Discovery Log & Infrastructure ✅

- [x] **1.1** Create `phantom_app/src-tauri/src/backend/discovery_log.rs`
  - [x] Define `DiscoveryLog` struct with: timestamp, interfaces_scanned, broadcast_port, packets_sent, responses_received, signature_failures, manifest_errors, worker_count, raw_entries
  - [x] Implement `Serialize` for JSON output
  - [x] Add `to_sanitized_string()` for copy/paste
  - [x] Export from `backend/mod.rs`

- [x] **1.2** Modify `phantom_app/src-tauri/src/backend/discovery.rs`
  - [x] Add log-building capability (callback or `discover_workers_with_log()`)
  - [x] Track: interfaces scanned, packets sent, responses received, signature failures, manifest errors
  - [x] Return manifests + optional `DiscoveryLog`

- [x] **1.3** Modify `phantom_app/src-tauri/src/backend/phantom_deployer.rs`
  - [x] Add `run_pre_scan_deployment()`: steps 0–9 + discovery **without** registration
  - [x] Build `DiscoveryLog` during step 10 (scan)
  - [x] Return `DeploymentPreScanResult { discovered_workers, discovery_log, discovery_failed }`
  - [x] Add `complete_deployment_with_selection(controller_host, worker_pool, run_controller_llm)`
  - [x] In completion: register only selected workers, run step 11, persist controller/LLM config

---

## Phase 2: Backend — Tauri Commands ✅

- [x] **2.1** Add commands in `phantom_app/src-tauri/src/lib.rs`
  - [x] `run_deployment_pre_scan` → returns `{ discovered_workers, discovery_log }`
  - [x] `complete_deployment_with_selection` → accepts controller, workers, LLM toggle
  - [ ] Optional: `run_diagnostic_command(cmd: String)` for phantomctl-style calls

- [x] **2.2** Wire deploy flow
  - [x] New commands support phased flow (`deploy_phantom` retained for legacy)
  - [x] Emit `deploy-discovery-result` event with discovery data when pre-scan completes

---

## Phase 3: Frontend — State & Types ✅

- [x] **3.1** Create `phantom_app/src/state/deploymentState.ts`
  - [x] Define `DiscoveredWorker`, `DiscoveryLog`, `ControllerConfig` types
  - [x] Define state: discoveredWorkers, discoveryLog, discoveryFailed, controllerConfig, workerPool
  - [x] Add React context (`DeploymentCeremonyProvider`, `useDeploymentCeremony`) for ceremony state

---

## Phase 4: Frontend — Tauri Bindings ✅

- [x] **4.1** Update `phantom_app/src/utils/tauri.ts`
  - [x] Add `runDeploymentPreScan()` binding
  - [x] Add `completeDeploymentWithSelection(...)` binding
  - [x] Discovery log from pre-scan result (no separate getDiscoveryLog needed)

---

## Phase 5: Frontend — Screen 4 Components ✅

- [x] **5.1** Create `phantom_app/src/components/Screen4ControllerSelect.tsx`
  - [x] List all discovered workers (including local)
  - [x] Show hardware summary: CPU, GPU, RAM, OS
  - [x] Show signature_verified and trust status
  - [x] Radio group for exactly one controller host
  - [x] Toggle: "Run Controller LLM (Phi-Lite) on selected hardware"
  - [x] Save to deploymentState.controllerConfig

- [x] **5.2** Create `phantom_app/src/components/Screen4WorkerSelect.tsx`
  - [x] List workers with "Include in worker pool" checkboxes
  - [x] Enforce at least one selected
  - [x] Save to deploymentState.workerPool

- [x] **5.3** Create `phantom_app/src/components/Screen4Diagnostics.tsx`
  - [x] Show only when worker_count === 0
  - [x] Message: "No workers detected. Phantom cannot proceed."
  - [x] "Open Diagnostic Tools" button
  - [x] Scrollable raw discovery log
  - [x] "Copy Log to Clipboard" button
  - [x] Buttons/instructions for phantomctl commands (copyable text)

- [x] **5.4** Create `phantom_app/src/components/DeploymentCeremony.tsx`
  - [x] Tab/section layout: [ Controller | Workers | Diagnostics ]
  - [x] Diagnostics tab only visible when worker_count === 0
  - [x] "Continue" enabled only when controller chosen + >=1 worker + !discovery_failed
  - [x] Uses Phantom sovereign styling (dark, minimal)

---

## Phase 6: Frontend — Flow Integration ✅

- [x] **6.1** Modify `phantom_app/src/components/FrontPorchDeploy.tsx`
  - [x] Remove auto-transition on `fraction >= 1.0`
  - [x] Call `runDeploymentPreScan()` instead of `deployPhantom()`
  - [x] Transition to `deployment_ceremony` via `onPreScanComplete(result)`

- [x] **6.2** Modify `phantom_app/src/App.tsx`
  - [x] Add `deployment_ceremony` phase and `preScanResult` state
  - [x] Render `DeploymentCeremony` wrapped in `DeploymentCeremonyProvider`
  - [x] Block TOC until ceremony complete (controller + ≥1 worker)
  - [x] On ceremony "Continue": `completeDeploymentWithSelection` → `consent_toc`
  - [x] Add "Back" to retry or return to front porch

---

## Phase 7: Styling & UX ✅

- [x] **7.1** Update `phantom_app/src/styles/deploy.css`
  - [x] Ceremony tab styles
  - [x] Worker card styles
  - [x] Diagnostic panel styles
  - [x] Ensure sovereign design (dark, minimal)

---

## Phase 8: Acceptance Verification ✅

- [x] **8.1** Discovery log is always generated on scan (discover_workers_with_log)
- [x] **8.2** Diagnostic Tools only visible when worker_count === 0 (discoveryFailed)
- [x] **8.3** Cannot enter TOC unless at least one worker selected (canContinue gate)
- [x] **8.4** Controller hardware must be explicitly chosen (controllerConfig required)
- [x] **8.5** Controller LLM toggle persists to config (llm_config.json, fixed: run load_execution_modes first)
- [x] **8.6** Worker pool selection persists to config (register_worker API)
- [x] **8.7** Auto mode cannot bypass Screen 4 (FrontPorchDeploy uses runDeploymentPreScan only)
- [x] **8.8** UI matches Phantom sovereign design language (deploy.css, theme vars)

---

## Notes

- `phantomctl` may not exist in repo — use copyable instructions or optional shell invocation.
- Bootstrap config (`phantom_config.json`) may need to be updated at completion with chosen controller host.
