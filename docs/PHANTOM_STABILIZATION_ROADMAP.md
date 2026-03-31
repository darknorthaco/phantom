# PHANTOM — Stabilization roadmap (living)

**Product:** PHANTOM only.  
**Source of truth for what to fix:** Evidence-backed stabilization audit (spawn vs health, hardcoded API URL, firewall vs config ports, Linux worker `Ok` on spawn fail, UDP/readiness silence, config/state drift, partial registration, TLS client drift, macOS parity, pre-deploy gates).

**Rules**

1. Phases are sequential — do not skip ahead.
2. Mark a task `[x]` only after completion, with diff reference or reasoning recorded (commit message / PR / note below the checklist).
3. After each completed task, update this file and record the date.
4. **No code changes without explicit human confirmation** for that task.
5. Systems-thinking (stocks, flows, boundaries, delays, loops) is for **diagnosis only** — it does not redefine PHANTOM.
6. Every fix: minimal, safe, reversible, evidence-backed, aligned with PHANTOM architecture.

**Progress log** (append a line per completed task)

| Date | Task | Evidence |
|------|------|----------|
| 2026-03-31 | 1 | `phantom_deployer.rs` `start_controller`: poll `GET /health` (scheme from `tls_enabled`) up to 90s; `phantom_api.rs` `for_local_health_check` + HTTP status check on health. |
| 2026-03-31 | 2 | `phantom_api.rs`: `controller_base_url_from_config`, `from_phantom_config`, `from_phantom_root_or_fallback`, `post_execution_mode`, shared `build_http_client`. `phantom_deployer.rs`: `scan_lan`, `complete_deployment`, `scan_and_register_workers` use config client. `lib.rs`: `phantom_api_for_app` for TOC commands. |
| 2026-03-31 | 3 | `phantom_deployer.rs` `open_ports`: `read_firewall_port_policy` reads `ports.*.port`; Linux ufw/iptables and Windows netsh use those values (defaults 8080/8090/8095/8081 if missing). |
| 2026-03-31 | 4 | `phantom_deployer.rs` Linux `start_local_worker`: `spawn` failure returns `Err` (parity with Windows). |
| 2026-03-31 | 5 | `discovery.rs` `probe_worker_readiness`: log bind/send/set_timeout/recv failures; `run_readiness_probe`: log + scan-log on `spawn_blocking` join error. |
| 2026-03-31 | 6 | `bootstrap_config`: `ports.controller_api.port` = placement `controller.port`. `read_phantom_runtime_endpoints` + local worker JSON + offline synthetic + readiness UDP use config host/ports. `probe_worker_readiness(timeout, discovery_port)`. |
| 2026-03-31 | 7 | `phantom_core/state.py`: default state dir when `PHANTOM_STATE_DIR` unset is `~/.phantom/state` (not `/var/lib/phantom/state`). |
| 2026-03-31 | 8 | `controller_api.py`: `orchestrator_init_error`, `/health` `degraded` + `orchestrator_ready` / `orchestrator_error`; `phantom_api.rs` `HealthResponse` serde defaults; `phantom_deployer.rs` health gate accepts `degraded` with warn. |
| 2026-03-31 | 9 | `phantom_deployer.rs`: `WorkerRegistrationSummary` + counted trust/register outcomes in `complete_deployment_with_selection`; scan-log + warn on partial LAN/ceremony pools; `ScanResult` adds `registration_failed` / `partial_registration`; audit + consent UI surface partial registration. |
| 2026-03-31 | 10 | `phantom_api.rs`: fallback path warns when config on disk cannot load; `new` uses `build_http_client` timeouts; `phantom_state.rs` + `lib.rs` `sync_controller_url_mutex` after TLS save / deploy / pre-scan / ceremony; mutex tracks `https` when `tls_enabled`. |
| 2026-03-31 | 11 | `discovery.rs`: `log::error/warn` on bind / `set_broadcast` / loopback+broadcast `send_to` failures; broadcast batch marks `discovery_send_broadcast` failed with per-target errors; `recv_from` errors classified + `debug` on idle slice; `log::info` summary when no `DiscoveryLogBuilder` (manual scan); invalid manifest / UTF-8 `debug` without log; signature fail `warn`; readiness probe success `info` + clearer timeout `debug`. |
| 2026-03-31 | 12 | Offline: ceremony pre-selects synthetic workers; `DiscoveryLog.discovery_mode` (`lan_udp` / `offline_synthetic`); LAN-only diagnostic hints gated; `ScanResult` + `offline_install.json` field `workers_panel_lan_udp`; Workers panel skip reason + `log::info`; UI banners; `offline_install.md` table. |
| 2026-03-31 | 13 | `phantom_deployer.rs`: macOS uses `start_local_worker` linux-worker path; explicit logs for macOS firewall / service skip / uninstall; GPU pre-check + generic-OS firewall messages; non-Linux/macOS/Windows skip worker with scan-log; `offline_install.md` platform table. |
| 2026-03-31 | 14 | `pre_deploy_validator.rs`: checklist (root, host Python, `run.py`, placement, offline bundle, `phantom_config` + port parity + TLS, engine/venv/imports, worker main, `/health`); `run_pre_deploy_validation` + audit; Front Porch **Validate prerequisites** UI. |
| 2026-03-31 | 15 | `pre_deploy_validator.rs`: `assert_ready_for_controller_start` (TLS/WAN, entrypoints, venv imports, `controller_base_url_from_config` + `for_local_health_check`); `phantom_deployer.rs` `start_controller` runs gate before spawn + scan-log on failure; TLS checklist uses same bool parsing as API client. |
| 2026-03-31 | 16 | `phantom_state.rs` `DeployFailureInfo` + `deploy-failed` event; `lib.rs`: pre-scan failure resets `AppPhase::FrontPorch` + audit; `deploy_phantom` fail-fast (no false “complete”); registration failure emits event + `log::error`; audit `pre_deploy_validation` includes failed/warn check details + paths. UI: `FrontPorchDeploy` banner + `deploy-failed` listener + controller step scan-log; pre-deploy checklist sorted + paths + hints; `DeploymentCeremony` registration error banner. |
| 2026-03-31 | 17 | `phantom_api.rs`: `get_execution_mode`, `get_task`; `lib.rs`: `get_execution_mode`, `get_controller_base_url`, `get_task_status`. TOC UI uses Tauri (`getPhantomHealth`, `getWorkers`, `getStats`, `getExecutionMode`, `setExecutionMode`, `submitTask`, `getTaskStatus`) instead of hardcoded `http://127.0.0.1:8080` fetches; `App.tsx` wizard skip accepts `degraded`; Settings shows live base URL from mutex. `RoutingPanel` surfaces mode switch errors. `DeploymentsPanel`: controller row treats `degraded` as running; comment on standalone `:8081` probe. |
| 2026-03-31 | 18 | `audit_logger.rs`: `log_event_best_effort` + `phantom_audit` target `warn` on write failure; `lib.rs` all prior `log_event`…`.ok()` → `log_event_best_effort`…`.await`; `load_llm_config` `create_dir_all` failure logged (`phantom_app`). Structured `log::info!` at `phantom_deploy`: pre-scan OK, ceremony registration OK, `deploy_phantom` all steps OK, pre-deploy validation summary. |

---

## PHASE 1 — HIGH-LEVERAGE FIXES _(complete)_

- [x] **1.** Replace spawn+sleep with real controller health gate  
  _Audit:_ `phantom_deployer.rs` `start_controller` spawns then fixed `sleep(3s)`; no `/health` or TCP gate.
- [x] **2.** Create unified controller API base URL (TLS + port)  
  _Audit:_ `PhantomApiClient::new("http://127.0.0.1:8080")` in `scan_lan`, `complete_deployment`; ignores TLS and config port.
- [x] **3.** Align firewall rules with config ports  
  _Audit:_ `open_ports` uses fixed 8080/8090/8095 (and 8081); not driven by `phantom_config.json` `ports`.
- [x] **4.** Fix Linux worker spawn semantics (return `Err` on failure)  
  _Audit:_ Linux `start_local_worker` logs warn on spawn fail but returns `Ok`; Windows returns `Err`.
- [x] **5.** Harden readiness logging (UDP bind/send/join errors)  
  _Audit:_ `probe_worker_readiness` returns false silently; `run_readiness_probe` uses `unwrap_or(false)` on blocking join.

---

## PHASE 2 — STRUCTURAL DRIFT CORRECTIONS _(complete)_

- [x] **6.** Fix config stock inconsistencies (ports, controller placement)  
  _Audit:_ `bootstrap_config` sets `controller.port` from placement but `ports.controller_api.port` hardcoded 8080 in same blob.
- [x] **7.** Correct state directory fallback behavior  
  _Audit:_ `state.py` defaults `PHANTOM_STATE_DIR` to `/var/lib/phantom/state` when unset — wrong for desktop paths.
- [x] **8.** Harden orchestrator startup (fail or degrade explicitly)  
  _Audit:_ `controller_api.py` startup catches orchestrator init failure, logs, continues without clear degraded signal.
- [x] **9.** Fix partial registration semantics  
  _Audit:_ `scan_lan` / `complete_deployment` warn and continue on per-worker failure — ambiguous pool state.
- [x] **10.** Correct TLS drift (Rust client must respect TLS mode)  
  _Audit:_ Same as item 2 if not fully absorbed there; ensure all Rust→controller paths match `tls_enabled` / HTTPS.

---

## PHASE 3 — DISCOVERY & ENVIRONMENT STABILIZATION _(complete)_

- [x] **11.** Fix discovery silent failures  
  _Audit:_ UDP readiness and related paths lack explicit diagnostics beyond high-level logs.
- [x] **12.** Normalize offline/online mode behavior  
  _Audit:_ Offline synthetic worker vs online discovery — document and align UX/telemetry so operators are not surprised.
- [x] **13.** Ensure cross-OS parity (Windows / Linux / macOS)  
  _Audit:_ macOS skips local worker; asymmetric behaviors across platforms.

---

## PHASE 4 — PRE-DEPLOY VALIDATION SYSTEM _(complete)_

- [x] **14.** Implement deterministic pre-deploy validator  
  _Audit:_ Checklist gates (placement, config, venv imports, entrypoint, health, firewall parity, worker spawn, TLS consistency).
- [x] **15.** Enforce readiness gates before Step 6+  
  _Audit:_ Tie deploy progression to validated controller (and worker where required), not only spawn.
- [x] **16.** Add explicit user-facing diagnostics for failed gates  
  _Audit:_ Reduce silent/partial success; surface actionable messages in UI and logs.

---

## PHASE 5 — OPTIONAL AUTO-PATCHES _(complete)_

- [x] **17.** Apply safe PR-sized patches identified in audit  
  _Audit:_ Small, surgical diffs (e.g. Linux spawn `Err`, health poll loop, shared API client factory).
- [x] **18.** Add structured logging for all critical boundaries  
  _Audit:_ e.g. audit `log_event` `.ok()` swallowing — log failures; critical path structured events.

---

## Next recommended step (when starting work)

Stabilization roadmap phases 1–5 are complete. Further work: new audit items, product features, or tighten filters (`RUST_LOG=phantom_audit=warn,phantom_deploy=info,phantom_app=info`).
