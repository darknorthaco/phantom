# Phantom Distributed Compute Fabric — Implementation Roadmap

**Source:** `docs/CORRECTED_ARCHITECTURE_DESIGN.md`  
**Date:** 2026-03-11  
**Status:** Ready to paste as GitHub Issues  

Each section below is a self-contained GitHub Issue. Copy the title and body verbatim.

---

## Issue 1 of 9

**Title:** `[Domain §1] Implement Controller Selection Ceremony`

**Body:**

### Summary

Insert a `ControllerSelectionScreen` between the WizardWelcome screen and the deploy trigger. This screen is the mandatory pre-deploy gate for controller placement and identity confirmation. No deploy step may execute until the user has selected a controller placement option, reviewed the controller's Ed25519 identity fingerprint, and clicked **Confirm**. Cancellation at this screen leaves zero state on disk.

This directly addresses **RC-1** from `FINAL_ARCHITECTURAL_CORRECTION_MAP.md`: controller placement is currently implicit, and the controller's identity is never shown to the user at deploy time.

---

### Doctrine Alignment

| Principle | Requirement |
|-----------|-------------|
| §2 Sovereign Domains | User explicitly asserts which node is sovereign; no placement defaults |
| §3 Authentic Trust | Controller Ed25519 identity generated and displayed before any trust relationship forms |
| §4 Transparent Operation | User sees exact address, port, and fingerprint before committing |
| §8 Reversibility | Cancel leaves the system entirely unchanged |

---

### Required Code Locations

| Layer | File(s) | Change |
|-------|---------|--------|
| **Rust / Tauri** | `phantom_app/src-tauri/src/security/identity_manager.rs` | Expose `get_fingerprint()` as a Tauri command; ensure keypair is generated on first call and reloaded on subsequent calls |
| **Rust / Tauri** | `phantom_app/src-tauri/src/lib.rs` | Register new Tauri commands: `get_controller_identity`, `confirm_controller_placement` |
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/phantom_deployer.rs` | Add guard: abort deploy sequence if `ControllerPlacementParams` is absent from config |
| **TypeScript** | `phantom_app/src/` | Create `ControllerSelectionScreen` component; wire to `get_controller_identity` and `confirm_controller_placement` commands; display placement options (Local CPU · Local GPU · Custom IP:Port), address preview, fingerprint, and device label |
| **Python / Installer** | `installer/gui/screens/` | Add `controller_selection.py` screen (mirrors Tauri screen for installer path) |
| **Python / Installer** | `installer/backend_interface/config_writer.py` | Write confirmed `ControllerPlacementParams` to `phantom_config.json` |
| **Python / Installer** | `installer/integration/phantom_installer_api.py` | Add `confirm_controller_placement()` method |

**New data structures to define** (language-agnostic schema; implement in both Rust and Python):
```
ControllerPlacementParams {
  host:                 string    // user-selected address
  port:                 uint16    // default 8080
  device_label:         string    // human-readable node name
  identity_fingerprint: string    // hex-encoded Ed25519 public key (first 16 bytes)
  confirmed_at:         timestamp
}
```

---

### Dependencies

- **Blocks** Issue §4 (Corrected Deploy Flow) — Pre-0 step cannot be sequenced until this screen exists.
- **Blocks** Issue §8 (Corrected Config Model) — `ControllerPlacementParams` must exist before Step 4.5 can write `phantom_config.json`.
- **Required before** any deploy guard referencing `ControllerPlacementParams`.
- **Uses** `identity_manager.rs`, which already exists and implements EdDSA keypair generation. Verify `get_fingerprint()` returns the first 16 bytes of the hex-encoded public key.

---

### Migration Considerations

- **Existing single-node installs:** On first corrected deploy, pre-populate the ceremony screen with `127.0.0.1:8080` and the existing keypair's fingerprint (if the keypair already exists in `identity/private.key`). The user sees the screen once; one click confirms continuity.
- **Legacy `phantom_config.json`:** If a prior config exists with a `controller.host` and `controller.port`, pre-populate the placement fields from it. Do **not** silently reuse values — require explicit re-confirmation.
- **Deprecate:** Any code path that proceeds to deploy without a confirmed `ControllerPlacementParams`.

---

### Testing Requirements

- **Unit:** `IdentityManager` generates a stable fingerprint across process restarts (load same keypair → same fingerprint).
- **Unit:** `ControllerPlacementParams` schema validation rejects missing or malformed fields.
- **Integration:** Wizard cannot advance past the selection screen without a valid `ControllerPlacementParams` in the config.
- **Integration:** Clicking Cancel on the selection screen produces no new files in `PHANTOM_STATE_DIR` or the config path.
- **UI:** Screen renders all three placement options; Custom IP:Port field validates against the `host:port` pattern; Confirm button is disabled until a placement is selected and the fingerprint section is visible.
- **Regression:** Deploy sequence still reaches Step 5 (controller start) correctly after ceremony completion.

---

### Reference

- Architecture spec: `docs/CORRECTED_ARCHITECTURE_DESIGN.md` §1
- Correction map entry: RC-1 in `FINAL_ARCHITECTURAL_CORRECTION_MAP.md`
- Existing identity implementation: `phantom_app/src-tauri/src/security/identity_manager.rs`

---

## Issue 2 of 9

**Title:** `[Domain §2] Implement Worker Selection Ceremony`

**Body:**

### Summary

Decompose the current Step 9 (LAN scan + auto-register) into three ordered sub-steps — **9a Discover**, **9b Worker Selection Ceremony**, **9c Register Selected** — and gate Step 9c on an explicit per-worker user approval. No worker may be registered in the mesh without appearing in the `WorkerSelectionPanel` and receiving a user checkbox selection.

This addresses **RC-2** and **RC-10**: the deploy flow currently auto-registers every discovered worker without user interaction, violating §5 (Voluntary Mesh) and §8 (Reversibility).

---

### Doctrine Alignment

| Principle | Requirement |
|-----------|-------------|
| §5 Voluntary Mesh Participation | Every registration is an explicit human act; automatic enrollment is prohibited |
| §8 Reversibility | Selection is reviewable before commit; registered workers can be deregistered at any time |
| §3 Authentic Trust | Signature verification precedes the user decision; unsigned manifests are flagged |
| §4 Transparent Operation | Full manifest details (identity, address, capabilities, trust status) shown at decision point |

---

### Required Code Locations

| Layer | File(s) | Change |
|-------|---------|--------|
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/phantom_deployer.rs` | Replace single Step 9 with sub-steps 9a/9b/9c; emit `DiscoveredManifest[]` to frontend after 9a; block 9c until `WorkerSelectionDecision` is received |
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/discovery.rs` | Return `DiscoveredManifest[]` (not raw worker records); include `signature_verified` field from §3 verifier |
| **Rust / Tauri** | `phantom_app/src-tauri/src/lib.rs` | Register Tauri commands: `get_discovered_workers`, `submit_worker_selection` |
| **TypeScript** | `phantom_app/src/` | Create `WorkerSelectionPanel` component: renders per-worker checkboxes with worker_id, address, capabilities, and signature badge (VERIFIED · UNVERIFIED · INVALID); `UNVERIFIED`/`INVALID` manifests default to unchecked |
| **Python / Installer** | `installer/gui/screens/worker_selection.py` | Rebuild existing `WorkerSelectionScreen` to mirror ceremony semantics: per-worker checkboxes, signature badges, Confirm gate |
| **Python / Installer** | `installer/backend_interface/worker_discovery_adapter.py` | Add `get_discovered_manifests()` returning `DiscoveredManifest[]` with `signature_verified`; remove auto-register logic |

**New data structures:**
```
DiscoveredManifest {
  worker_id:          string
  address:            string        // IP:port
  capabilities:       string[]
  signature_verified: bool
  discovered_at:      timestamp
}

WorkerSelectionDecision {
  approved:   [worker_id, ...]
  rejected:   [worker_id, ...]
  deferred:   [worker_id, ...]
  decided_at: timestamp
}
```

---

### Dependencies

- **Requires** Issue §3 (Manifest Signing Model) — `signature_verified` field in `DiscoveredManifest` is set by the manifest verifier from §3.
- **Requires** Issue §6 (Port Model) — 8090/tcp and 8095/udp must be open before Step 9a discovery runs.
- **Requires** Issue §8 (Config Model) — discovery parameters may be read from `phantom_config.json`.
- **Feeds** Issue §5 (Trust Model) — each user approval in Step 9b writes a `TrustRecord(approved)`.
- **Feeds** Issue §4 (Deploy Flow) — Steps 9a–9c are positioned by §4.

---

### Migration Considerations

- **Existing single-worker installs:** On first corrected deploy, the panel shows one item (the local worker). One checkbox confirmation; end state is identical.
- **CLI / headless deploys:** Must require an explicit `--approve-all-workers` flag. Every invocation must log a doctrine-bypass warning to `installation_audit.log`.
- **Deprecate:** Any code path in `phantom_deployer.rs`, `worker_discovery_adapter.py`, or the installer that registers workers without a preceding `WorkerSelectionDecision`.

---

### Testing Requirements

- **Unit:** `WorkerSelectionDecision` with an empty `approved` list results in zero POST calls to the worker registration endpoint.
- **Unit:** Manifests with `signature_verified: false` default to unchecked in the panel.
- **Integration:** Step 9c re-verifies signatures for each approved worker before the registration call.
- **Integration:** Rejected and deferred worker IDs appear in the audit log and are absent from the controller's worker list.
- **UI:** Panel renders all discovered manifests; Confirm is disabled until the user has interacted with at least one checkbox (or explicitly chosen to proceed with zero approvals).
- **Regression:** Deregistration from WorkersPanel after the ceremony leaves the controller in a consistent state.

---

### Reference

- Architecture spec: `docs/CORRECTED_ARCHITECTURE_DESIGN.md` §2
- Correction map entries: RC-2, RC-10 in `FINAL_ARCHITECTURAL_CORRECTION_MAP.md`
- Existing discovery: `phantom_app/src-tauri/src/backend/discovery.rs`
- Existing installer screen: `installer/gui/screens/worker_selection.py`

---

## Issue 3 of 9

**Title:** `[Domain §3] Implement Manifest Signing Model`

**Body:**

### Summary

Add Ed25519 signing to every worker manifest emitted during discovery, and add signature verification to every receiver of those manifests. Replace the current unsigned JSON discovery responses with `SignedManifest` objects that include `public_key`, `signature`, and `signed_at` fields. Implement TOFU (Trust On First Use) key recording and key-change detection at the verification layer.

This addresses **RC-3**: worker manifests are currently transmitted as unsigned JSON. Any host on the LAN can claim any worker identity and be registered without challenge.

---

### Doctrine Alignment

| Principle | Requirement |
|-----------|-------------|
| §3 Authentic Trust | Every manifest carries cryptographic proof of origin; no implicit LAN trust |
| §2 Sovereign Domains | Each worker's identity is self-sovereign; keypair cannot be transferred or forged |
| §6 Consistent Behavior | Same `SignedManifest` schema and verification logic applies on all discovery paths |

---

### Required Code Locations

| Layer | File(s) | Change |
|-------|---------|--------|
| **Rust / Worker (Linux)** | `phantom_core/linux-worker/linux_worker/` | Add `manifest_signer.py` module: loads or generates per-worker Ed25519 keypair at startup; constructs canonical payload; signs and emits `SignedManifest` |
| **Rust / Worker (Linux)** | `phantom_core/linux-worker/linux_worker/discovery_listener.py` | Update response format from raw JSON to `SignedManifest` schema |
| **Rust / Tauri** | `phantom_app/src-tauri/src/security/signature_verifier.rs` | Extend (or create) `ManifestVerifier`: reconstructs canonical payload; verifies Ed25519 signature; applies TOFU rules against `TrustStore`; returns `signature_verified: bool` |
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/discovery.rs` | Parse `SignedManifest` instead of raw JSON; pass each received manifest through `ManifestVerifier` before emitting `DiscoveredManifest[]` |
| **Python / Installer** | `installer/backend_interface/worker_discovery_adapter.py` | Add `InstallerManifestVerifier`: same verification logic as Rust layer (or delegate to a shared Python module) |
| **Python / Worker** | `phantom_core/linux-worker/linux_worker/main.py` | Trigger keypair generation at startup via `ManifestSigner.init()` before the discovery listener binds |

**Canonical manifest schema (implement in both Python and Rust):**
```
SignedManifest {
  // existing discovery fields
  worker_id:    string
  address:      string
  capabilities: object
  msg_type:     "WORKER_MANIFEST"
  // new signing fields
  public_key:   string     // hex-encoded Ed25519 public key
  signature:    string     // hex-encoded Ed25519 signature over canonical_payload
  signed_at:    timestamp
}
// canonical_payload = deterministic JSON of:
// { worker_id, address, capabilities, msg_type, signed_at } — sorted keys, no extra whitespace
```

**Worker identity persistence:**
- Private key: `<worker_state_dir>/identity/worker_private.key`
- Public key: `<worker_state_dir>/identity/worker_public.key`

---

### Dependencies

- **Blocks** Issue §2 (Worker Selection Ceremony) — `signature_verified` field required.
- **Blocks** Issue §5 (Trust Model) — TOFU public-key records written here populate the TrustStore.
- **Blocks** Issue §9 (Installer Discovery Model) — installer verifier must use the same `SignedManifest` schema.
- **No hard upstream dependencies** — this is a foundational primitive. Can be developed and tested in isolation using mock discovery responses.

---

### Migration Considerations

- **Grace period:** During the initial migration window (duration configurable in `phantom_config.json`), manifests without a signature are accepted but surfaced in §2 with badge `UNSIGNED` and default to unchecked. Workers are given time to adopt the signing model.
- **End of grace period:** Unsigned manifests are rejected at the receiver before reaching the selection ceremony.
- **Schema compatibility:** The `SignedManifest` is a strict superset of the current discovery response. Existing receivers that only read `worker_id`, `address`, etc., continue to work during the grace period.
- **Deprecate:** Unsigned manifest emission from `discovery_listener.py`; unconditional manifest acceptance at the registration endpoint.

---

### Testing Requirements

- **Unit (Python):** `ManifestSigner.sign()` produces a deterministic signature for the same canonical payload; changing any field produces a different signature.
- **Unit (Python):** `ManifestVerifier.verify()` returns `True` for a correctly signed manifest and `False` for a tampered payload.
- **Unit (Rust):** Same cases for `ManifestVerifier` in `signature_verifier.rs`.
- **Unit:** TOFU path: first manifest from a new `worker_id` records the public key and returns `signature_verified = true`.
- **Unit:** Key-change path: second manifest from the same `worker_id` with a different `public_key` returns `signature_verified = false` and writes a `key_change_detected` TrustRecord.
- **Integration:** Discovery listener emits a `SignedManifest`; Tauri receiver parses and verifies it end-to-end.
- **Security:** A manifest with a forged signature (payload modified after signing) must never reach the registration pipeline.

---

### Reference

- Architecture spec: `docs/CORRECTED_ARCHITECTURE_DESIGN.md` §3
- Correction map entry: RC-3 in `FINAL_ARCHITECTURAL_CORRECTION_MAP.md`
- Existing signature infrastructure: `phantom_app/src-tauri/src/security/signature_verifier.rs`, `identity_manager.rs`
- Existing discovery listener: `phantom_core/linux-worker/linux_worker/discovery_listener.py`

---

## Issue 4 of 9

**Title:** `[Domain §4] Implement Corrected Deploy Flow`

**Body:**

### Summary

Refactor the deploy sequence in `phantom_deployer.rs` and the parallel installer pipeline to enforce the fully-ordered, ceremony-gated step sequence defined in `docs/CORRECTED_ARCHITECTURE_DESIGN.md` §4. Add Pre-0 (Controller Selection Ceremony), Step 4.5 (Config Bootstrap), expand Step 6 to the three-port model, replace the Step 8 sleep with the readiness probe, and decompose Step 9 into sub-steps 9a/9b/9c. Apply the correct halt-on-failure / log-and-continue policy to each step.

This is the **integration issue** — it sequences all other domain implementations. Addresses RC-1, RC-2, RC-4, RC-5, RC-6, RC-7, RC-8, RC-10, and RC-12 in aggregate.

---

### Doctrine Alignment

| Principle | Requirement |
|-----------|-------------|
| §4 Transparent Operation | Each step visible, logged, and produces a verifiable outcome |
| §2 Sovereign Domains | Controller placement is user-confirmed at Pre-0, not an assumption |
| §5 Voluntary Mesh | Worker registration gated by user selection at Step 9b |
| §8 Reversibility | Step failures halt forward progress; undeploy reverses steps in reverse order |

---

### Required Code Locations

| Layer | File(s) | Change |
|-------|---------|--------|
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/phantom_deployer.rs` | Reorder steps per corrected sequence table (see below); add Pre-0 guard; add Step 4.5 config write; expand Step 6 to three ports; replace sleep with readiness probe in Step 8; decompose Step 9 into 9a/9b/9c |
| **Rust / Tauri** | `phantom_app/src-tauri/src/lib.rs` | Update deploy Tauri commands to reflect new step structure and state transitions |
| **Python / Installer** | `installer/backend_interface/installer_driver.py` | Mirror corrected step sequence; apply same halt/continue policy |
| **Python / Installer** | `installer/integration/phantom_installer_api.py` | Add `run_deploy_flow()` method that enforces ceremony gates |
| **Python / Installer** | `installer/gui/wizard.py` | Add Pre-0 and 9b screens to the wizard screen ordering |

**Corrected step sequence:**

| Step | Label | Critical (halt on failure) |
|------|-------|---------------------------|
| Pre-0 | Controller Selection Ceremony (§1) | Yes |
| 0 | Create virtual environment | Yes |
| 1 | Install Python runtime | Yes |
| 2 | Install Phantom Core | Yes |
| 3 | Verify GPU plugins | No (log and continue) |
| 4 | Install Phantom service | Yes |
| 4.5 | Bootstrap `phantom_config.json` (§8) | Yes |
| 5 | Start controller | Yes |
| 6 | Open ports — 8080/tcp, 8090/tcp, 8095/udp (§6) | No (warn and continue) |
| 7 | Initialize state | No (log and continue) |
| 8 | Start local worker + readiness probe (§7) | No (warn and continue) |
| 9a | Discover workers — UDP broadcast + verify (§3) | No (empty list is valid) |
| 9b | Worker Selection Ceremony (§2) | No (cancel = empty mesh, continue to 10) |
| 9c | Register selected workers | No (partial failure logged) |
| 10 | Load execution modes | No (idempotent) |

**Step pre-state recording:** Every step that writes persistent state (4.5, 5, 6, 9c) must record the pre-state to enable undeploy reversal.

---

### Dependencies

- **Requires** Issue §1 (Controller Selection Ceremony) — Pre-0 screen must exist.
- **Requires** Issue §8 (Config Model) — Step 4.5 `ConfigBootstrap` must be implemented.
- **Requires** Issue §6 (Port Model) — Step 6 multi-port opening must be implemented.
- **Requires** Issue §7 (Readiness Model) — Step 8 readiness probe must replace the sleep.
- **Requires** Issue §3 (Manifest Signing Model) — Step 9a manifest verification.
- **Requires** Issue §2 (Worker Selection Ceremony) — Step 9b panel must exist.
- This issue **integrates** all other domain implementations into a coherent sequence.

---

### Migration Considerations

- **Existing deploys:** Steps 0–7 and 10 behave identically for existing single-node users. Pre-0 adds one confirmation screen; Step 4.5 is automatic; Step 6 adds two additional firewall rules; Step 8 replaces the sleep (transparent to users); Steps 9a/9b/9c replace the auto-register loop.
- **Transitional flag:** A `--legacy-deploy` CLI mode may be provided for automated environments during a migration window. Every invocation must write a `DOCTRINE_BYPASS` warning to `installation_audit.log`.
- **Deprecate:** Fixed `sleep(2)` after worker spawn; single-port firewall logic in Step 6; the auto-register loop in Step 9; controller start before `phantom_config.json` is written.

---

### Testing Requirements

- **Integration:** Full deploy sequence completes end-to-end with all nine corrected steps in order, against a local test controller and worker.
- **Integration:** Step failure at any critical step halts the sequence and surfaces an error to the UI / CLI; no subsequent steps run.
- **Integration:** Cancel at Pre-0 leaves the filesystem identical to its pre-run state.
- **Integration:** `--legacy-deploy` flag writes `DOCTRINE_BYPASS` to `installation_audit.log`.
- **Regression:** Existing single-node deploy still reaches a running controller with the local worker registered.
- **Undeploy:** Undeploy reverses steps in reverse order and returns the system to a clean state.

---

### Reference

- Architecture spec: `docs/CORRECTED_ARCHITECTURE_DESIGN.md` §4
- Correction map entries: RC-1, RC-2, RC-4, RC-5, RC-6, RC-7, RC-8, RC-10, RC-12
- Existing deployer: `phantom_app/src-tauri/src/backend/phantom_deployer.rs`
- Existing installer driver: `installer/backend_interface/installer_driver.py`

---

## Issue 5 of 9

**Title:** `[Domain §5] Implement Corrected Trust Model`

**Body:**

### Summary

Create a `TrustStore` — a persistent, append-only ledger local to the controller — that records every trust-level transition for every worker. Define the five trust levels (`unverified`, `sig_valid`, `approved`, `registered`, `revoked`) and the `TrustRecord` schema. Enforce the `TrustBoundary` rule: no manifest enters the approval pipeline without passing §3 verification, and no worker is registered without a `TrustRecord(approved)` written by a human user decision.

This addresses RC-3, RC-10, and RC-12: the current system has no trust store and no revocation mechanism.

---

### Doctrine Alignment

| Principle | Requirement |
|-----------|-------------|
| §3 Authentic Trust | Every trust transition backed by cryptographic evidence |
| §2 Sovereign Domains | Trust store is entirely local; user is the sole authority |
| §5 Voluntary Mesh | A `TrustRecord(approved)` written by the user is the gateway to mesh membership |
| §8 Reversibility | Trust can be revoked at any time without side effects on other workers |

---

### Required Code Locations

| Layer | File(s) | Change |
|-------|---------|--------|
| **Python** | `phantom_core/phantom_core/state.py` | Add `TrustStore` class: append-only JSON ledger at `<PHANTOM_STATE_DIR>/trust_store.json`; methods: `write_record()`, `get_current_level()`, `get_history()`, `revoke()` |
| **Python** | `phantom_core/phantom_core/` | Add `trust_model.py`: define `TrustLevel` enum, `TrustRecord` dataclass, `TrustBoundary` enforcement function |
| **Python** | `phantom_core/phantom_core/controller_api.py` | Registration endpoint must query `TrustStore` and reject any `WorkerInfo` not accompanied by a `TrustRecord(approved)` |
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/phantom_deployer.rs` | Step 9c: query TrustStore for `TrustRecord(approved)` before each registration POST call |
| **Rust / Tauri** | `phantom_app/src-tauri/src/` | Add Tauri command `get_trust_store()` for display in WorkersPanel; add `revoke_worker()` command that writes `TrustRecord(revoked)` |
| **Python / Installer** | `installer/backend_interface/worker_discovery_adapter.py` | Installer discovery path must write to the same TrustStore (no installer-specific bypass) |

**TrustRecord schema:**
```
TrustRecord {
  worker_id:   string
  public_key:  string
  trust_level: "unverified" | "sig_valid" | "approved" | "registered" | "revoked"
  decided_by:  "user" | "system"
  decided_at:  timestamp
  reason:      string
}
```

**TrustStore rules:**
- Append-only: records are never modified or deleted.
- Current trust level = trust level of the most recent record for a given `worker_id`.
- On key-change detection (§3): set trust level back to `unverified`, reason = `"key_change_detected"`.

---

### Dependencies

- **Requires** Issue §3 (Manifest Signing Model) — signature verification results feed the `TrustBoundary`.
- **Requires** Issue §2 (Worker Selection Ceremony) — user approval decisions write `TrustRecord(approved/revoked)`.
- **Feeds** Issue §4 (Deploy Flow) — Step 9c reads `TrustRecord(approved)` before registration.
- **Feeds** Issue §9 (Installer Discovery) — installer-discovered workers use the same TrustStore.

---

### Migration Considerations

- **Existing registered workers:** On first corrected deploy, seed the TrustStore with a `TrustRecord(registered, decided_by: "legacy-migration")` for each worker currently in `workers.json`. Flag these records in the WorkersPanel UI and prompt the user to explicitly re-approve or revoke each one.
- **Deprecate:** Any registration pathway that calls the controller registration endpoint without a preceding `TrustRecord(approved)`.

---

### Testing Requirements

- **Unit:** `TrustStore.write_record()` is append-only; calling it twice for the same worker produces two records.
- **Unit:** `TrustStore.get_current_level()` returns the level of the most recent record.
- **Unit:** `TrustBoundary` blocks a manifest with `signature_verified = false` from advancing to the approval pipeline.
- **Unit:** Key-change path: second manifest with different `public_key` sets trust level to `unverified` and adds a `key_change_detected` reason record.
- **Integration:** Controller registration endpoint returns HTTP 403 for a `WorkerInfo` with no `TrustRecord(approved)` in the store.
- **Integration:** WorkersPanel revocation writes `TrustRecord(revoked)` and the worker no longer appears in the active mesh.
- **Regression:** Legacy-migration seed produces valid `TrustRecord(registered)` entries readable by the WorkersPanel.

---

### Reference

- Architecture spec: `docs/CORRECTED_ARCHITECTURE_DESIGN.md` §5
- Correction map entries: RC-3, RC-10, RC-12
- Existing state manager: `phantom_core/phantom_core/state.py`
- Existing controller API: `phantom_core/phantom_core/controller_api.py`

---

## Issue 6 of 9

**Title:** `[Domain §6] Implement Corrected Port Model`

**Body:**

### Summary

Replace the current single-port (8080/tcp) firewall rule with a config-driven `PortPolicy` that opens all three required ports — **8080/tcp** (Controller API), **8090/tcp** (Worker HTTP API), and **8095/udp** (Discovery listener) — at Deploy Step 6. Store the `PortPolicy` in `phantom_config.json`. Remove all hardcoded port values from deploy logic. Correct the WorkersPanel tooltip to distinguish the worker API port (8090) from the discovery port (8095).

This addresses RC-5 and RC-9: currently only 8080/tcp is opened, silently leaving worker communication and discovery unreachable on firewalled systems.

---

### Doctrine Alignment

| Principle | Requirement |
|-----------|-------------|
| §4 Transparent Operation | Every port opened or attempted is logged; failures surface to the user |
| §6 Consistent Behavior | One PortPolicy; identical port assignments on Linux and Windows; UI matches config |

---

### Required Code Locations

| Layer | File(s) | Change |
|-------|---------|--------|
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/phantom_deployer.rs` | Replace single-port `open_port(8080)` call with a loop over `PortPolicy` entries from config; log each port opened; surface failures as warnings (non-fatal) |
| **Rust / Tauri — Linux** | `phantom_app/src-tauri/src/backend/linux/systemd_installer.rs` | Replace hardcoded 8080 UFW/iptables calls with the three required ports |
| **Rust / Tauri — Windows** | `phantom_app/src-tauri/src/backend/windows/` | Replace hardcoded 8080 netsh call with three required ports |
| **Python / Installer** | `installer/backend_interface/installer_driver.py` | Add port-opening step that iterates `PortPolicy` from `phantom_config.json`; log each result; surface failures as non-fatal warnings |
| **Config** | `phantom_config.json` (written by §8 ConfigBootstrap) | Add `ports` block (see schema below) |
| **TypeScript / UI** | `phantom_app/src/` (WorkersPanel component) | Update discovery tooltip from conflated "port 8090" to: "Workers are discovered via UDP broadcast on port **8095** · The Worker HTTP API is available on TCP port **8090**" |

**PortPolicy schema (in `phantom_config.json`):**
```json
"ports": {
  "controller_api": { "port": 8080, "protocol": "tcp", "required": true  },
  "worker_http":    { "port": 8090, "protocol": "tcp", "required": true  },
  "discovery_udp":  { "port": 8095, "protocol": "udp", "required": true  },
  "socket_infra":   { "port": 8081, "protocol": "tcp", "required": false }
}
```

**Operational rules:**
- Port 8081/tcp is opened only if `socket_infra.required` is `true` in the config.
- Port-opening failure for a required port is a non-fatal warning; the deploy continues but the user is informed.
- No port number may be hardcoded in deploy logic — read from `PortPolicy` only.

---

### Dependencies

- **Requires** Issue §8 (Config Model) — `phantom_config.json` must exist (Step 4.5) before Step 6 reads `PortPolicy`.
- **Blocks** Issue §7 (Readiness Model) — 8095/udp must be open before the readiness probe runs at Step 8.
- **Blocks** Issue §9 (Installer Discovery) — 8095/udp must be open on the installer host before Stage S2.
- **Feeds** Issue §4 (Deploy Flow) — Step 6 is positioned between Step 5 and Step 7 in the corrected sequence.

---

### Migration Considerations

- **Existing installs:** Only 8080/tcp is currently opened. First corrected deploy adds 8090/tcp and 8095/udp rules. No existing rules are removed.
- **Permission failures:** On systems where the deploy user lacks firewall management permissions, all three required ports must appear in the post-deploy output with manual opening instructions.
- **Deprecate:** Hardcoded single-port logic; any UI label that conflates 8090 and 8095.

---

### Testing Requirements

- **Unit:** `PortPolicy` loader raises an error if a required port entry is missing from `phantom_config.json`.
- **Integration (Linux):** After Step 6, `ufw status` or `iptables -L` shows allow rules for all three required ports.
- **Integration (Windows):** After Step 6, `netsh advfirewall` shows rules for all three required ports.
- **Integration:** Port-opening failure for a required port emits a warning log entry and does not halt the deploy.
- **UI:** WorkersPanel tooltip renders the correct port labels for 8090 and 8095 without conflation.
- **Regression:** Opening 8090/tcp and 8095/udp does not disrupt the existing 8080/tcp controller API.

---

### Reference

- Architecture spec: `docs/CORRECTED_ARCHITECTURE_DESIGN.md` §6
- Correction map entries: RC-5, RC-9
- Existing port logic: `phantom_app/src-tauri/src/backend/phantom_deployer.rs`, `linux/systemd_installer.rs`

---

## Issue 7 of 9

**Title:** `[Domain §7] Implement Corrected Readiness Model`

**Body:**

### Summary

Replace the fixed `sleep(2)` after worker spawn with an active `ReadinessProbe` loop that sends unicast `PHANTOM_DISCOVER_WORKERS` UDP packets to `127.0.0.1:8095` and waits for a `WORKER_MANIFEST` response. Read probe parameters (`probe_interval_ms`, `max_attempts`, `attempt_timeout_ms`) from `phantom_config.json`. Correct the worker spawn failure log message to remove any GPU-presence assertion — the worker supports CPU-only mode.

This addresses RC-4 and RC-13: the fixed sleep is an unreliable readiness gate and the spawn failure message incorrectly implies a GPU requirement.

---

### Doctrine Alignment

| Principle | Requirement |
|-----------|-------------|
| §4 Transparent Operation | Deploy status accurately reflects whether the local worker is ready; no silent race condition |
| §6 Consistent Behavior | One probe mechanism; same behavior on all platforms; no platform-specific timing |

---

### Required Code Locations

| Layer | File(s) | Change |
|-------|---------|--------|
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/phantom_deployer.rs` | Remove `sleep(Duration::from_secs(2))` after worker spawn; replace with `ReadinessProbe::wait_for_worker()` |
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/` | Add `readiness_probe.rs`: implements the probe loop (send unicast to 127.0.0.1:8095, wait for WORKER_MANIFEST, retry up to `max_attempts`, log timeout warning) |
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/phantom_deployer.rs` | Fix worker spawn failure log: replace GPU-assertion wording with `"Failed to start local worker: <reason>"` |
| **Python / Installer** | `installer/backend_interface/installer_driver.py` | Mirror readiness probe logic for installer deploy path; read parameters from `phantom_config.json` |
| **Config** | `phantom_config.json` (written by §8 ConfigBootstrap) | Add `worker` block with `readiness_probe_interval_ms`, `readiness_max_attempts`, `readiness_attempt_timeout_ms` |

**ReadinessConfig defaults (in `phantom_config.json`):**
```json
"worker": {
  "readiness_probe_interval_ms":  500,
  "readiness_max_attempts":       20,
  "readiness_attempt_timeout_ms": 1000
}
```

**Probe algorithm:**
1. Spawn worker process.
2. Send unicast `PHANTOM_DISCOVER_WORKERS` → `127.0.0.1:8095`.
3. Wait `attempt_timeout_ms` for a `WORKER_MANIFEST` response.
4. On response: advance to Step 9a immediately.
5. On timeout: increment attempt counter; if `attempt < max_attempts`, wait `probe_interval_ms` and retry from step 2.
6. On `max_attempts` exhausted: log `"Local worker did not respond within the readiness window. Discovery will proceed."` Advance to Step 9a.

---

### Dependencies

- **Requires** Issue §6 (Port Model) — 8095/udp must be open before the probe loop runs.
- **Requires** Issue §8 (Config Model) — `ReadinessConfig` parameters are read from `phantom_config.json`.
- **Requires** Issue §3 (Manifest Signing Model) — the probe response is a `SignedManifest`; the verifier should verify it even during the readiness phase.
- **Feeds** Issue §4 (Deploy Flow) — the probe is the gate between Step 8 (worker spawn) and Step 9a (discovery).

---

### Migration Considerations

- **Existing behavior:** Fixed `sleep(2s)` after spawn. On fast machines, the probe typically resolves in under one second — faster than the sleep. On slow machines (GPU initialization), the probe waits up to 10 seconds (default) instead of silently missing the worker after 2 seconds.
- **Config tuning:** Default parameters are conservative. Operators on fast hardware may reduce `max_attempts`; GPU-heavy systems may increase it.
- **Deprecate:** Any `sleep`/`time.sleep` call inserted between worker spawn and Step 9a; the GPU-assertion wording in the spawn failure log.

---

### Testing Requirements

- **Unit:** `ReadinessProbe` exits the loop immediately upon receiving a valid `WORKER_MANIFEST` UDP response.
- **Unit:** After `max_attempts` exhausted with no response, the probe logs the timeout warning and returns without error.
- **Unit:** Probe reads `probe_interval_ms`, `max_attempts`, `attempt_timeout_ms` from `phantom_config.json`, not from hardcoded constants.
- **Integration:** Worker spawn followed by readiness probe: probe resolves before Step 9a broadcast on a running local worker.
- **Regression:** Removing the sleep does not introduce a race condition — if the worker is slower to start than `max_attempts × (probe_interval_ms + attempt_timeout_ms)`, the deploy continues and the worker appears in the Step 9a broadcast result.
- **Log correctness:** Spawn failure log contains `"Failed to start local worker: <reason>"` with no mention of GPU presence.

---

### Reference

- Architecture spec: `docs/CORRECTED_ARCHITECTURE_DESIGN.md` §7
- Correction map entries: RC-4, RC-13
- Existing deployer (contains sleep): `phantom_app/src-tauri/src/backend/phantom_deployer.rs`
- Existing discovery (contains unicast): `phantom_app/src-tauri/src/backend/discovery.rs`

---

## Issue 8 of 9

**Title:** `[Domain §8] Implement Corrected Config Model`

**Body:**

### Summary

Establish `phantom_config.json` as the single config source of truth for all runtime parameters — controller host/port/security/identity, port policy, readiness probe settings, and execution modes. Insert a **Step 4.5 `ConfigBootstrap`** into the deploy sequence that writes this file atomically before the controller (Step 5) ever reads it. Implement atomic-write semantics (write to `.tmp`, rename) and timestamped backups of any pre-existing config. Enforce no-fallback semantics: Step 5 fails explicitly if `phantom_config.json` is absent.

This addresses RC-7 and RC-14: `phantom_config.json` is currently written after Step 5 reads it, causing the controller to silently fall back to default values for security level and other parameters.

---

### Doctrine Alignment

| Principle | Requirement |
|-----------|-------------|
| §4 Transparent Operation | Config is written before it is read; no silent fallbacks; write-step annotation is correct |
| §6 Consistent Behavior | All components read from one file; no component has divergent hardcoded values |
| §8 Reversibility | Atomic write prevents partial state; timestamped backup enables manual rollback |

---

### Required Code Locations

| Layer | File(s) | Change |
|-------|---------|--------|
| **Python / Installer** | `installer/backend_interface/config_writer.py` | Implement `ConfigBootstrap.write()`: collect `ControllerPlacementParams`, `PortPolicy`, `ReadinessConfig`; write to `.tmp`; rename to `phantom_config.json`; back up any existing file to `phantom_config.json.bak.<timestamp>`; add `written_by_step: "4.5"` annotation |
| **Python / Installer** | `installer/integration/phantom_installer_api.py` | Add `bootstrap_config()` method that calls `ConfigBootstrap.write()` |
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/phantom_deployer.rs` | Add Step 4.5 invocation; ensure Step 5 reads `phantom_config.json` with no fallback — fail with a clear error if absent |
| **Python** | `phantom_core/phantom_core/` | Add `config_schema.py`: defines `ConfigSchema` dataclass with all fields, types, and defaults; single contract for the config file |
| **Python** | `phantom_core/phantom_core/controller_api.py` | On startup, read `security` level from `phantom_config.json["controller"]["security"]`; do not fallback to hardcoded default |
| **Rust / Tauri** | `phantom_app/src-tauri/src/backend/phantom_deployer.rs` | Steps 6, 8, 9a: read port assignments and readiness config from `phantom_config.json` rather than from constants |

**`phantom_config.json` schema (full):**
```json
{
  "controller": {
    "host":                 "string",
    "port":                 8080,
    "security":             "disabled | basic | full",
    "identity_fingerprint": "string"
  },
  "ports": {
    "controller_api": { "port": 8080, "protocol": "tcp", "required": true  },
    "worker_http":    { "port": 8090, "protocol": "tcp", "required": true  },
    "discovery_udp":  { "port": 8095, "protocol": "udp", "required": true  },
    "socket_infra":   { "port": 8081, "protocol": "tcp", "required": false }
  },
  "worker": {
    "readiness_probe_interval_ms":  500,
    "readiness_max_attempts":       20,
    "readiness_attempt_timeout_ms": 1000
  },
  "execution_modes": {
    "default_mode": "string"
  },
  "config_version":  "string",
  "written_at":      "timestamp",
  "written_by_step": "4.5"
}
```

---

### Dependencies

- **Requires** Issue §1 (Controller Selection Ceremony) — `ControllerPlacementParams` supplies the `controller` block.
- **Blocks** Issue §6 (Port Model) — `ports` block must exist before Step 6.
- **Blocks** Issue §7 (Readiness Model) — `worker` block must exist before Step 8.
- **Feeds** Issue §4 (Deploy Flow) — Step 4.5 is positioned by §4 between Steps 4 and 5.
- **Feeds** Issue §5 (Trust Model) — `controller.identity_fingerprint` confirms controller identity continuity.

---

### Migration Considerations

- **Legacy read-before-write:** On first corrected deploy, Step 4.5 is inserted and writes the config before Step 5 reads it. For existing single-node installs, the written values match prior behavior (local address, existing security level), so there is no functional change.
- **Existing config files:** Any pre-existing `phantom_config.json` (or `llm_config.json`) is backed up before `ConfigBootstrap` writes the new one. The user is informed via the deploy log.
- **`llm_config.json`:** The existing `phantom_core/llm_taskmaster/llm_config.json` is a separate file for LLM routing. It is not superseded by `phantom_config.json`; the two files serve different domains. Document the distinction clearly in `ConfigSchema`.
- **Deprecate:** Any mechanism that reads `phantom_config.json` with a silent fallback value when the file is absent; any annotation claiming a step other than 4.5 owns the initial config write.

---

### Testing Requirements

- **Unit:** `ConfigBootstrap.write()` produces a valid `phantom_config.json` that passes `ConfigSchema` validation.
- **Unit:** Atomic write: if the process is interrupted after `.tmp` is written but before rename, the original `phantom_config.json` is untouched.
- **Unit:** A pre-existing `phantom_config.json` is backed up to `phantom_config.json.bak.<timestamp>` before overwrite.
- **Integration:** Controller startup (Step 5) fails with a clear error if `phantom_config.json` is absent — no silent fallback.
- **Integration:** Step 6 reads `ports` from config (not hardcoded); Step 8 reads `worker.readiness_*` from config (not hardcoded).
- **Regression:** Existing `llm_config.json` is not overwritten or moved by `ConfigBootstrap`.

---

### Reference

- Architecture spec: `docs/CORRECTED_ARCHITECTURE_DESIGN.md` §8
- Correction map entries: RC-7, RC-14
- Existing config writer: `installer/backend_interface/config_writer.py`
- Existing config: `phantom_core/llm_taskmaster/llm_config.json`
- Existing state defaults: `phantom_core/phantom_core/state.py`

---

## Issue 9 of 9

**Title:** `[Domain §9] Implement Corrected Installer Discovery Model`

**Body:**

### Summary

Rebuild the installer's worker discovery stage (Stage S2) around an `InstallerDiscoveryClient` that implements the canonical discovery protocol: UDP broadcast + unicast to **port 8095**, `PHANTOM_DISCOVER_WORKERS` request format, 1500ms timeout, `SignedManifest` response schema (§3), deduplication by `worker_id`. Remove and permanently delete the broken TCP raw-JSON probe. Add an `InstallerManifestVerifier` that applies §3 signature verification. Implement Stage S3 as a full worker selection ceremony (mirroring §2) before any registration call. Prohibit fabricated fallback worker records.

This addresses RC-8: the installer's current TCP-based discovery sends a raw JSON payload that workers do not understand, producing fabricated `Worker-{ip}` placeholder records with no real identity or capabilities.

---

### Doctrine Alignment

| Principle | Requirement |
|-----------|-------------|
| §6 Consistent Behavior | One discovery protocol across Tauri and installer paths; same schema, timeout, dedup |
| §4 Transparent Operation | Actual worker data surfaced, not fabricated; empty results reported accurately |
| §7 Evolution Without Drift | TCP placeholder retired permanently; canonical protocol owned by this spec |

---

### Required Code Locations

| Layer | File(s) | Change |
|-------|---------|--------|
| **Python / Installer** | `installer/backend_interface/worker_discovery_adapter.py` | Replace TCP discovery implementation with `InstallerDiscoveryClient`: UDP broadcast + unicast to 8095; 1500ms timeout; collect and deduplicate `SignedManifest` responses; apply `InstallerManifestVerifier` (§3 verification); return `DiscoveredManifest[]` |
| **Python / Installer** | `installer/backend_interface/worker_discovery_adapter.py` | Add `InstallerManifestVerifier`: applies §3 canonical payload verification; sets `signature_verified`; records TOFU keys in TrustStore (§5) |
| **Python / Installer** | `installer/gui/screens/worker_selection.py` | Rebuild Stage S3 to mirror §2 Worker Selection Ceremony: per-worker checkboxes, signature badges (VERIFIED · UNVERIFIED · INVALID), Confirm gate; no fabricated records rendered |
| **Python / Installer** | `installer/integration/phantom_installer_api.py` | Update `discover_workers()` to use `InstallerDiscoveryClient`; remove TCP probe call |
| **Python / Installer** | `installer/backend_interface/` | Delete or clearly quarantine any function that generates `Worker-{ip}` placeholder records |
| **Python / Installer** | `installer/modules/component_manager.py` | Ensure 8095/udp is open on the installer host before Stage S2 runs (coordinate with §6 PortPolicy) |

**Canonical discovery contract (must match `phantom_app/src-tauri/src/backend/discovery.rs`):**

| Property | Value |
|----------|-------|
| Protocol | UDP |
| Port | 8095 |
| Request type | `PHANTOM_DISCOVER_WORKERS` |
| Response schema | `SignedManifest` (§3) |
| Timeout | 1500 ms |
| Deduplication key | `worker_id` |
| Empty result | Valid; display "No workers discovered" message |

**No fabricated records:** If no workers respond within 1500ms, the installer reports "No workers discovered on this subnet" with an empty `DiscoveredManifest[]`. It must not construct any `Worker-*` placeholder entry.

---

### Dependencies

- **Requires** Issue §3 (Manifest Signing Model) — `SignedManifest` schema and `InstallerManifestVerifier` logic.
- **Requires** Issue §2 (Worker Selection Ceremony) — Stage S3 mirrors the §2 ceremony; UX and approval semantics must be identical.
- **Requires** Issue §5 (Trust Model) — installer-discovered and approved workers write to the same TrustStore; no installer-specific trust bypass.
- **Requires** Issue §6 (Port Model) — 8095/udp must be open before Stage S2.
- Both `discovery.rs` (Tauri) and `InstallerDiscoveryClient` (Python) implement the **same canonical contract**. Any schema change to `SignedManifest` must propagate to both simultaneously.

---

### Migration Considerations

- **Legacy TCP probe:** Remove entirely. There is no transitional mode; the TCP probe was always incompatible with the worker protocol and produced no usable data.
- **Fabricated records:** Any `Worker-{ip}` placeholder records in installer-generated data stores are invalid. Do not migrate them forward. Users must be informed that prior installer discovery results are unreliable.
- **Schema sync:** Maintain a shared `discovery_contract.md` or equivalent specification document that both the Rust and Python implementations must pass. Any PR that modifies the schema must update both implementations.
- **Deprecate:** The TCP discovery function; the fabricated-fallback path; any installer stage that registers workers without a preceding selection ceremony; `Worker-{ip}` placeholder IDs.

---

### Testing Requirements

- **Unit:** `InstallerDiscoveryClient.discover()` sends a UDP broadcast to `<subnet>:8095` and a unicast to `127.0.0.1:8095` within 1500ms.
- **Unit:** Deduplication: two responses with the same `worker_id` produce one `DiscoveredManifest`.
- **Unit:** Timeout with no responses returns an empty list (not a fabricated record).
- **Unit:** `InstallerManifestVerifier` produces the same `signature_verified` values as the Rust `ManifestVerifier` for identical inputs (cross-language parity test).
- **Integration:** Full installer discovery flow: UDP broadcast → `SignedManifest` response → `InstallerManifestVerifier` → Stage S3 panel → user approval → registration with `TrustRecord(registered)`.
- **Integration (parity):** The same running worker, discovered by both the Tauri deploy path and the installer path, produces identical `DiscoveredManifest` records (same `worker_id`, `capabilities`, `signature_verified`).
- **Regression:** No `Worker-{ip}` string appears anywhere in the `TrustStore`, `workers.json`, or any log after a corrected installer discovery run.

---

### Reference

- Architecture spec: `docs/CORRECTED_ARCHITECTURE_DESIGN.md` §9
- Correction map entry: RC-8
- Existing (broken) TCP discovery: `installer/backend_interface/worker_discovery_adapter.py`
- Canonical UDP discovery: `phantom_app/src-tauri/src/backend/discovery.rs`
- Existing installer screen: `installer/gui/screens/worker_selection.py`

---

## Cross-Domain Dependency Graph

```
§8 Config Model
  └── must be implemented first; provides phantom_config.json written at Step 4.5

§1 Controller Selection Ceremony
  └── depends on: §8 (writes ControllerPlacementParams to config)
  └── enables: §4 Pre-0 gate

§3 Manifest Signing Model
  └── no hard upstream dependencies (foundational primitive)
  └── enables: §2, §5, §9

§6 Port Model
  └── depends on: §8 (reads PortPolicy from config)
  └── enables: §7, §9

§7 Readiness Model
  └── depends on: §8 (reads ReadinessConfig), §6 (8095/udp open)

§2 Worker Selection Ceremony
  └── depends on: §3 (signature_verified field), §6 (ports open)
  └── feeds: §5 (TrustRecord writes)

§5 Trust Model
  └── depends on: §3, §2
  └── feeds: §4 (registration guard), §9 (shared TrustStore)

§9 Installer Discovery Model
  └── depends on: §3, §2, §5, §6

§4 Corrected Deploy Flow
  └── depends on: §1, §8, §6, §7, §3, §2 (integration of all others)
  └── recommended implementation order: §8 → §3 → §6 → §1 → §7 → §2 → §5 → §9 → §4
```

---

## Recommended Implementation Order

| Order | Issue | Rationale |
|-------|-------|-----------|
| 1st | **§8 Config Model** | Foundation; all other issues read from `phantom_config.json` |
| 2nd | **§3 Manifest Signing Model** | Foundational primitive; no upstream dependencies |
| 3rd | **§6 Port Model** | Required before readiness probe and installer discovery |
| 4th | **§1 Controller Selection Ceremony** | Required before config write and deploy guard |
| 5th | **§7 Readiness Model** | Depends only on §8 and §6 |
| 6th | **§2 Worker Selection Ceremony** | Depends on §3 and §6 |
| 7th | **§5 Trust Model** | Depends on §3 and §2 |
| 8th | **§9 Installer Discovery Model** | Depends on §3, §2, §5, §6 |
| 9th | **§4 Corrected Deploy Flow** | Integration issue; depends on all others |
