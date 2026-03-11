# PHASE 2 — Discovery and Deployment Pipeline Audit Report

**Date:** 2025-03-11  
**Scope:** Full audit of discovery and worker-deployment pipeline. No modifications made.

---

## 1. DISCOVER_WORKERS PACKET FLOW

### 1.1 Sending

| Location | Behavior | Notes |
|----------|----------|-------|
| `discovery.rs` `discover_single_window` | Sends to 127.0.0.1:8095 and each broadcast addr:8095 | All targets probed up front |
| `discovery.rs` `probe_worker_readiness` | Sends to 127.0.0.1:8095 only | Used by readiness probe loop |

**Payload:** `b"PHANTOM_DISCOVER_WORKERS"` — matches worker expectation.

**Silent failures when `log` is `None`:**
- `socket.send_to()` failures for loopback or broadcast are not logged when using `discover_workers()` (no log builder)
- Only `discover_workers_with_log` path records send success/failure

### 1.2 Receiving Worker Responses

| Location | Behavior | Notes |
|----------|----------|-------|
| `discovery.rs` `discover_single_window` | Single loop, `recv_from` with shrinking timeout | Collects until window expires or early exit |
| `parse_manifest` | Parses JSON, requires `WORKER_MANIFEST` + non-empty `worker_id` | Legacy + signed format supported |

**Suppressed behavior:**
- `recv_from` `Err(_)` → loop breaks. Any error (timeout, connection reset, etc.) treated the same; no distinction when `log` is `None`

---

## 2. SOCKET SETUP

| Component | Finding |
|-----------|---------|
| `UdpSocket::bind("0.0.0.0:0")` | Ephemeral port; correct |
| `socket.set_broadcast(true).ok()` | **Silent:** broadcast enable failure is ignored; no log |
| `set_read_timeout` | Per-iteration shrinking timeout; correct for total-window model |

**Logic bomb (low):** On some systems, `set_broadcast(true)` can fail. Failure is ignored; broadcasts may not reach LAN.

---

## 3. EVENT LOOP / POLLING

- **Discovery:** Single blocking loop; no async. Runs in `spawn_blocking`. Deterministic.
- **Readiness probe:** Sequential probe → sleep → probe in `run_readiness_probe`. Blocking probe in `spawn_blocking`.
- **Worker Python:** Discovery listener runs in daemon thread; 1s socket timeout, `recvfrom` loop. Correct.

---

## 4. WORKER BOOTSTRAP AND INITIALIZATION

### 4.1 Worker Startup Sequence (`main.py`)

```
1. load_config()
2. worker.initialize()     — GPU, plugins, socket client
3. worker.register_with_controller()  — HTTP POST /workers/register
4. if not success: return 1  ← EXIT
5. worker.start_background_tasks()  — discovery listener + heartbeat
6. uvicorn.serve()
```

### 4.2 **CRITICAL LOGIC BOMB — Worker Exits Before Discovery Listener Starts**

**Observation:** The worker calls `register_with_controller()` **before** `start_background_tasks()`. The discovery listener is started inside `start_background_tasks()`.

**Controller behavior (§5):** `/workers/register` requires `TrustRecord(approved)`. Unapproved workers receive **403**.

**Ceremony flow:**
1. Steps 0–9 run (including `start_local_worker`)
2. Discovery runs (step 10)
3. User sees discovered workers and approves
4. `complete_deployment_with_selection` registers approved workers

**At step 9:** No workers are approved yet. When the worker starts:
1. It calls `register_with_controller()` → 403
2. `main.py` returns `1` and **exits**
3. `start_background_tasks()` is never called
4. **Discovery listener never binds to 8095**
5. Readiness probe times out
6. Discovery finds 0 workers

**Impact:** Fresh deployments with the ceremony flow will always report 0 workers, because the worker process exits before exposing the discovery listener.

**Recommendation:** Worker must not exit on registration failure during initial bootstrap. It should start the discovery listener and HTTP server regardless, so it can be discovered and later registered after user approval.

---

### 4.3 Worker Discovery Listener (`discovery_listener.py`)

| Aspect | Finding |
|--------|---------|
| Bind | `0.0.0.0:8095`; 3 retries with 1s sleep on failure |
| Payload check | `data == DISCOVER_PAYLOAD` (byte equality) |
| Response | Signed or legacy manifest JSON |
| Identity | `_init_signer()` — can return None if `cryptography` missing; falls back to unsigned |

**Potential issue:** If `discovery_listener` bind fails after 3 attempts, listener thread returns; worker continues but will not respond to discovery. Error is logged.

---

## 5. SILENT EXCEPTIONS AND SUPPRESSED ERRORS

| Location | Behavior | Surfaces in diagnostics? |
|----------|----------|---------------------------|
| `probe_worker_readiness` | Bind/send/recv failures → `false`; no log | No |
| `discover_single_window` (log=None) | Bind error → `vec![]`; no log | No |
| `discover_single_window` (log=None) | Send failures → silent | No |
| `discover_single_window` (log=None) | `recv_from` Err → break; no log | No |
| `socket.set_broadcast(true).ok()` | Broadcast enable failure ignored | No |
| `start_local_worker` | `cmd.spawn()` Err → `log::warn!` only; step still Ok(()) | Partial |
| Port opening (ufw/iptables/netsh) | Failures → `log::warn!` only; step Ok(()) | Partial |

---

## 6. LOGIC BOMBS SUMMARY

| Severity | Location | Description |
|----------|----------|-------------|
| **CRITICAL** | `linux_worker/main.py` | Worker exits on registration failure before starting discovery listener; blocks discovery in ceremony flow |
| Medium | `discovery.rs` | No logging when `log` is `None`; bind/send/recv failures invisible |
| Low | `set_broadcast(true).ok()` | Broadcast enable failure ignored |
| Low | `start_local_worker` | Worker spawn failure does not fail step; deployment appears successful |

---

## 7. DEPENDENCY AND ORDERING

| Dependency | When Used | Potential Failure |
|------------|-----------|-------------------|
| `local_ip_bases()` | Before discovery | Can return empty; fallbacks to 192.168.1.1, 192.168.0.1, etc. |
| `phantom_config.json` | Read by `read_discovery_config` | Missing → defaults (10000 ms, early_exit true) |
| Controller running | Worker `register_with_controller` | If controller not ready, worker may fail to connect; still exits |
| Port 8095/udp open | Discovery, worker listener | Firewall can block; open_ports step warns but does not fail |

---

## 8. INSTALLER DISCOVERY (Out of Scope, Noted)

`installer/modules/worker_discovery.py` uses:
- `DISCOVERY_PORT = 8090` (incorrect; should be 8095)
- TCP `connect_ex` for port check
- No UDP broadcast, no `PHANTOM_DISCOVER_WORKERS`

Per docs, installer discovery is broken and uses a different protocol. Not part of Tauri deploy path.

---

## 9. RECOMMENDATIONS (For Future Implementation)

1. **Fix worker bootstrap:** Do not exit on registration failure; start discovery listener and HTTP server regardless. Treat registration as best-effort during initial deploy.
2. **Log probe failures:** Have `probe_worker_readiness` accept optional log or emit to a shared diagnostic when bind/send fails.
3. **Log discovery failures when log is None:** When using `discover_workers`, consider at least `log::warn!` on bind/send failures.
4. **Firewall step:** Consider failing deployment if required ports cannot be opened (or document that users must open manually).
5. **Worker spawn:** Consider returning `Err` from `start_local_worker` if spawn fails on platforms where a local worker is expected.

---

*End of PHASE 2 Audit Report*
