# PHASE 4 — Full Deployment Initialization Log

## Design Proposal (Pre-Implementation)

**Goal:** Ultra-verbose, chronological diagnostic log capturing every internal action from "Deploy" click until discovery completes.

---

## 1. Schema: Full Deployment Log Entry

```rust
/// Single entry in the Full Deployment Initialization Log.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FullDeployLogEntry {
    /// RFC3339 timestamp when the step completed.
    pub timestamp: String,
    /// Step index (1-based, chronological order).
    pub step_index: u32,
    /// Human-readable step name.
    pub step_name: String,
    /// Whether the step succeeded.
    pub success: bool,
    /// Duration in milliseconds.
    pub duration_ms: u64,
    /// Optional metadata (JSON-serializable: paths, counts, targets, etc.).
    pub metadata: Option<serde_json::Value>,
    /// Error message if success == false.
    pub error_message: Option<String>,
}
```

---

## 2. Integration Points

| Location | Responsibility |
|----------|-----------------|
| `discovery_log.rs` | Define `FullDeployLogEntry`, add `full_deploy_log: Vec<FullDeployLogEntry>` to `DiscoveryLog` and `DiscoveryLogBuilder` |
| `phantom_deployer.rs` | Emit entries for each deploy step (0–10), subprocess spawns, config reads, filesystem checks |
| `discovery.rs` | Emit entries for socket ops, send targets, recv/parse, signature validation |
| `to_sanitized_string()` | Render "--- Full Deployment Initialization Log ---" section before Discovery Timing Breakdown |

---

## 3. Entry Taxonomy (Chronological)

Entries are emitted in strict order. Step index increments for each entry.

### 3.1 Deploy Flow (phantom_deployer)

| Step Index | Step Name | When | Metadata | Error Handling |
|-------------|-----------|------|----------|----------------|
| 1 | deploy_clicked | Entry to run_pre_scan_deployment | `{}` | N/A |
| 2 | step_0_create_venv | Before/after create_venv | venv_path, status exit code | stderr on failure |
| 3 | step_1_install_python_deps | Before/after pip install | req_path, packages | stderr on failure |
| 4 | step_2_install_phantom_core | Before/after copy engine | src, dest, skipped | N/A |
| 5 | step_3_verify_gpu_plugins | Before/after GPU detect | gpu_count, gpu_names | N/A |
| 6 | step_4_install_service | Before/after systemd/netsh | platform, paths | stderr on failure |
| 7 | step_5_bootstrap_config | Before/after config write | config_path, placement_path | parse error |
| 8 | step_6_start_controller | Before/after controller spawn | python_path, run_py, host, port | spawn error |
| 9 | step_7_open_ports | Before/after firewall rules | rules_applied, platform | per-rule failures |
| 10 | step_8_initialize_state | Before/after marker write | marker_path | write error |
| 11 | step_9_start_local_worker | Before/after worker spawn | main_py_path, config_path, spawn_args | spawn error |
| 12 | subprocess_controller | On controller spawn | cmd, args, env_keys, creation_flags | N/A |
| 13 | subprocess_worker | On worker spawn | cmd, args, cwd, creation_flags | N/A |
| 14 | config_load_phantom_config | read_discovery_config | total_timeout_ms, early_exit | parse fail → defaults |
| 15 | config_load_placement | If bootstrap reads placement | host, port | read/parse error |
| 16 | filesystem_check_phantom_root | create_dir_all phantom_root | path, exists | mkdir error |
| 17 | filesystem_check_state_dir | create_dir_all state | path | mkdir error |
| 18 | env_var_phantom_state_dir | When spawning controller | value | N/A |

### 3.2 Pre-Discovery (phantom_deployer, run_pre_scan_deployment)

| Step Index | Step Name | When | Metadata | Error Handling |
|-------------|-----------|------|----------|----------------|
| 19 | network_interface_enumeration | local_ip_bases() | bases[], count | N/A |
| 20 | broadcast_address_calculation | base_to_broadcast for each | broadcast_addrs[] | N/A |
| 21 | readiness_probe_start | Before probe loop | max_attempts, interval_ms, timeout_ms | N/A |
| 22 | readiness_probe_result | After probe loop | attempts, success | N/A |

### 3.3 Discovery (discovery.rs, discover_single_window)

| Step Index | Step Name | When | Metadata | Error Handling |
|-------------|-----------|------|----------|----------------|
| 23 | socket_create | UdpSocket::bind | bind_addr | bind error |
| 24 | socket_set_broadcast | set_broadcast(true) | success | log failure |
| 25 | discovery_send_loopback | send_to 127.0.0.1:8095 | target, bytes_sent | send error |
| 26 | discovery_send_broadcast | send_to each broadcast | target, bytes_sent | send error (per target) |
| 27 | discovery_listen_loop_start | Before recv loop | total_timeout_ms, early_exit | N/A |
| 28 | discovery_recv | Each successful recv | source_ip, bytes, worker_id, sig_ok | parse/sig errors |
| 29 | discovery_manifest_parse | parse_manifest | worker_id, port, msg_type | invalid JSON, wrong type |
| 30 | discovery_signature_validation | verify_signature | worker_id, verified | verification fail |
| 31 | discovery_listen_loop_end | After loop | duration_ms, poll_cycles, worker_count | N/A |

### 3.4 Out-of-Scope (Tauri Cannot Observe)

Per .cursorrules: *"Do not modify Phantom controller, worker, or protocol code."*

| Item | Where It Happens | Mitigation |
|------|------------------|------------|
| trust store initialization | Controller (Python) | Log "controller_started" with note; trust store init is internal to subprocess |
| cryptographic key loading | Worker (Python) | Log "worker_started"; key load is internal |
| manifest loading | Worker (Python) | Same as above |
| manifest signing | Worker discovery_listener | We observe result via recv (sig_ok); no internal visibility |

We add a single placeholder entry after controller/worker spawn:

```
step_name: "subprocess_controller_started" / "subprocess_worker_started"
metadata: { "note": "Trust store, crypto, manifest init occur inside subprocess. See controller/worker logs." }
```

---

## 4. Subprocess Creation Flags (Windows)

**Requirement:** *"If a subprocess would normally flash a command window, correct the creation flags."*

| Platform | Current | Proposed |
|----------|---------|----------|
| Windows | `Command::new().spawn()` | Add `CREATE_NO_WINDOW` (0x08000000) when creating the process |
| Unix | N/A | No console window by default |

Rust `tokio::process::Command` does not expose creation flags directly. Options:

- **Option A:** Use `std::process::Command` with `creation_flags` on Windows (via `creation_flags(0x08000000)`) — requires synchronous spawn or wrapping.
- **Option B:** Use `CommandExt` trait (windows only) — `cmd.creation_flags(0x08000000)`.
- **Option C:** Keep `tokio::process::Command`; on Windows, use `CommandExt` if available in tokio.

**Recommendation:** Use `#[cfg(windows)]` and `std::os::windows::process::CommandExt` with `creation_flags(0x08000000)` for `Command::new().spawn()` in the deployer. For `tokio::process::Command`, check if tokio re-exports or supports creation_flags; if not, use `std::process::Command` for spawn where we need no-window (controller, worker) and keep the flow simple.

---

## 5. Data Flow

```
run_pre_scan_deployment()
  │
  ├─► FullDeployLogCollector (new) or pass &mut Vec<FullDeployLogEntry> through call chain
  │   - Deployer steps 0–9 each push 1–2 entries
  │   - Pre-discovery steps push entries
  │
  └─► discover_workers_with_log(..., dependency_init_entries, full_deploy_entries?)
        │
        └─► discover_single_window(..., log: &mut DiscoveryLogBuilder)
              - log has full_deploy_log: Vec<FullDeployLogEntry>
              - discovery.rs pushes entries for socket/send/recv/parse/sig
```

**Design choice:** `DiscoveryLogBuilder` owns `full_deploy_log`. The deployer creates the builder (or a pre-builder) and passes it down. Alternatively, we build the full log in the deployer and pass `Vec<FullDeployLogEntry>` into `discover_workers_with_log`, which merges it into the builder.

**Recommended:** Deployer maintains `full_deploy_log: Vec<FullDeployLogEntry>` and passes it to `discover_workers_with_log` together with `dependency_init_entries`. Discovery adds its entries inside `discover_single_window` when `log` is `Some`. Final merge: `full_deploy_log = deployer_entries + discovery_entries`, ordered by step_index.

---

## 6. Ordering and Determinism

- Each entry gets `step_index` at emit time from a running counter.
- Deployer emits 1–22; discovery emits 23–31.
- Merge preserves order.
- No async races; deployer is sequential, discovery runs in `spawn_blocking` and receives the builder.

---

## 7. to_sanitized_string() Output Order

1. Phantom Discovery Log — {timestamp}
2. Summary (interfaces, port, packets, responses, etc.)
3. **--- Full Deployment Initialization Log ---** *(NEW)*
4. --- Discovery Timing Breakdown ---
5. --- Dependency Initialization Log ---
6. --- Raw entries ---
7. --- Possible causes --- (if worker_count == 0)

---

## 8. Files to Modify

| File | Changes |
|------|---------|
| `discovery_log.rs` | Add `FullDeployLogEntry`, add `full_deploy_log` to structs, add `add_full_deploy_entry()`, render in `to_sanitized_string()` |
| `phantom_deployer.rs` | Add `emit_full_deploy_entry()` helper; instrument steps 0–9, config loads, filesystem, env, subprocess spawns; pass entries to discovery |
| `discovery.rs` | Add `add_full_deploy_entry()` calls in `discover_single_window` for socket, send, recv, parse, sig; extend `discover_workers_with_log` to accept/merge full deploy entries |
| `discovery_log.rs` (builder) | Add `step_index_counter`, `add_full_deploy_entry(step_name, success, duration_ms, metadata, error)` |

---

## 9. API Changes (Non-Breaking)

- `discover_workers_with_log(..., dependency_init_entries, full_deploy_entries: Vec<FullDeployLogEntry>)` — append discovery entries, merge into builder.
- New public type: `FullDeployLogEntry`.
- Existing `DiscoveryLog` gains field `full_deploy_log: Vec<FullDeployLogEntry>` (default `vec![]` for backward compat if any consumers exist).

---

## 10. Windows CREATE_NO_WINDOW

- Constant: `CREATE_NO_WINDOW = 0x08000000`
- Apply to: controller spawn (step 6), worker spawn (step 9).
- Use `#[cfg(windows)]` and `std::os::windows::process::CommandExt`.

---

## 11. Open Questions

1. **Step 0–9 granularity:** Emit one entry per step (e.g. `step_0_create_venv`) or split into "before" and "after"? Proposal: one entry per step on completion, with duration = whole step.
2. **Metadata size:** Keep metadata minimal (paths, counts) to avoid huge logs; truncate long paths if needed.
3. **Error propagation:** On step failure, deployer returns `Err`. We still emit a `success: false` entry with `error_message` before returning.

---

*End of Design Proposal. Awaiting approval before implementation.*
