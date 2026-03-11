# Phantom Distributed Compute Fabric — Corrected Architecture Design

**Date:** 2026-03-10  
**Basis:** FINAL_ARCHITECTURAL_CORRECTION_MAP.md, GAP_ANALYSIS_AUDIT_REPORT.md, ROOT_CAUSE_ANALYSIS_REPORT.md, Phantom Doctrine, Deploy-flow correction map, Trust model alignment, GPU discovery audit, DARPA DevOps audit  
**Audience:** Senior engineers implementing Phantom's doctrine  
**Method:** Design only. No code. No implementation details.

---

## Table of Contents

1. [Controller Selection Ceremony](#1-controller-selection-ceremony)
2. [Worker Selection Ceremony](#2-worker-selection-ceremony)
3. [Manifest Signing Model](#3-manifest-signing-model)
4. [Corrected Deploy Flow](#4-corrected-deploy-flow)
5. [Corrected Trust Model](#5-corrected-trust-model)
6. [Corrected Port Model](#6-corrected-port-model)
7. [Corrected Readiness Model](#7-corrected-readiness-model)
8. [Corrected Config Model](#8-corrected-config-model)
9. [Corrected Installer Discovery Model](#9-corrected-installer-discovery-model)

---

## 1. Controller Selection Ceremony

### Purpose

The Controller Selection Ceremony establishes — before any deployment step executes — which machine, address, and identity will serve as the sovereign controller for this Phantom domain. It surfaces the controller's cryptographic identity to the user and requires an explicit, informed decision about placement.

Doctrine principles satisfied:
- **§2 Sovereign Domains:** The user asserts which node is sovereign. No authority is assumed.
- **§3 Authentic Trust:** The controller identity (Ed25519) is generated or loaded and displayed before trust relationships are formed.
- **§4 Transparent Operation:** The user sees exactly where the controller will run and what identity it will carry.
- **§8 Reversibility:** The user may cancel or reconfigure before any installation step commits.

---

### Problem Statement

**Root causes addressed:** RC-1 (controller selection missing), RC-12 (deploy flow assumes LAN trusted), RC-14 (deploy flow assumes controller config exists early).

The current deploy flow hardcodes the controller address to `127.0.0.1:8080` and never asks the user where the controller should run, which device should be sovereign, or what identity the controller holds. The `identity_manager` exists and produces Ed25519 keypairs but is never invoked during deployment. The WizardWelcome screen obtains general consent ("configure your system as a compute controller") but offers no placement choice. This means:

- Multi-device deployments silently fail or produce an unintended topology.
- The controller identity is invisible to the user at the moment it matters most.
- Users cannot exercise domain sovereignty because they are never asked to assert it.

---

### Design Specification

**High-level architecture:**  
A pre-deploy screen (ControllerSelectionScreen) is inserted between WizardWelcome consent and the deploy button. It drives a two-phase interaction: (1) placement selection, (2) identity confirmation.

**Required components:**
- `ControllerSelectionScreen` — UI panel presenting placement options and identity fingerprint
- `ControllerPlacementParams` — data structure capturing user's placement decision
- `IdentityRecord` — controller Ed25519 public key, fingerprint, and creation timestamp, sourced from identity_manager
- Updated `start_controller` — consumes `ControllerPlacementParams`; does not hardcode host or port

**Required data structures:**
```
ControllerPlacementParams {
  host: string          // e.g. "127.0.0.1" or a LAN IP
  port: uint16          // default 8080; user-configurable
  device_label: string  // human-readable name for this controller node
  identity_fingerprint: string  // Ed25519 pubkey hex, shown to user
  confirmed_at: timestamp
}
```

**Required ceremonies:**
1. User opens ControllerSelectionScreen before deploy.
2. System loads or generates the controller Ed25519 keypair via identity_manager.
3. Screen displays: placement options (local CPU, local GPU, specify IP), identity fingerprint, and device label.
4. User reviews and confirms or cancels.
5. On confirmation, `ControllerPlacementParams` is persisted to config layer (see §8).
6. Deploy flow Step 0 reads `ControllerPlacementParams`; all subsequent steps consume it.

**Required trust boundaries:**  
No controller starts until placement is confirmed. Identity_manager must not be bypassed. Fingerprint displayed must match the key actually used.

**Required user interactions:**  
Explicit confirmation click. Cancel must abort deploy entirely without side effects.

**Required controller/worker responsibilities:**  
Controller: bind only to the host/port from `ControllerPlacementParams`. Worker: no change at this ceremony stage.

**Required network behavior:**  
No network calls during the ceremony. Placement is local configuration only.

**Required identity behavior:**  
Ed25519 keypair is generated on first deploy if absent; loaded from storage on subsequent deploys. Fingerprint is shown as hex-encoded public key truncated to 16 bytes (human-readable). Key is never transmitted during the ceremony; it is used in manifest signing (see §3).

**Required config behavior:**  
`ControllerPlacementParams` written to `phantom_config.json` before Step 5. See §8 for config ordering rules.

**Required timing behavior:**  
Ceremony completes before any deploy step executes. No timeout on user decision.

**Required error-handling behavior:**  
If identity_manager fails to generate a keypair, the ceremony blocks and surfaces the error. Deploy cannot proceed without a confirmed placement.

**Required reversibility behavior:**  
User may return to this screen, change placement, and re-confirm before deploy. After deploy starts, placement cannot change without a full undeploy-redeploy cycle (see §8).

---

### Flow Diagram

```
[WizardWelcome — consent obtained]
        |
        v
[ControllerSelectionScreen]
        |
        |-- Load/generate Ed25519 keypair via identity_manager
        |
        |-- Display:
        |     Placement options: Local CPU | Local GPU | Custom IP
        |     Controller address: <host>:<port>
        |     Identity fingerprint: <hex>
        |     Device label: <string>
        |
        |-- User selects placement and reviews identity
        |
        |-- [CANCEL] --> Return to WizardWelcome; no state written
        |
        |-- [CONFIRM] --> Write ControllerPlacementParams to config
        |
        v
[FrontPorchDeploy — deploy button now enabled]
        |
        v
[Deploy Step 0: read ControllerPlacementParams]
        |
        v
[Deploy Step 5: start_controller(host, port from params)]

PRECONDITION:  WizardWelcome consent obtained; no prior deploy in progress
POSTCONDITION: ControllerPlacementParams persisted; identity_manager keypair on disk;
               FrontPorchDeploy enabled; controller not yet started
```

---

### Doctrine Alignment

| Principle | How Satisfied |
|-----------|--------------|
| §2 Sovereign Domains | User chooses controller placement; no implicit authority |
| §3 Authentic Trust | Identity fingerprint shown before any trust relationship forms |
| §4 Transparent Operation | Address, port, and fingerprint visible at decision point |
| §8 Reversibility | Cancel returns to pre-ceremony state with no side effects |

---

### Trust Model Alignment

- **Eliminates implicit trust:** Controller is no longer silently started at a hardcoded address. Every controller has a user-confirmed identity.
- **Restores user approval workflows:** Placement is an explicit screen, not a background step.
- **Prevents auto-registration:** Controller identity is confirmed before workers are allowed to register.
- **Enforces manifest authenticity:** The keypair confirmed here is the signing root for manifest verification (see §3).

---

### Interoperability Requirements

- `ControllerPlacementParams` is written to `phantom_config.json` (§8) before Step 5. All components reading controller address must read from this config, not hardcoded values.
- Identity keypair is the same root used by §3 Manifest Signing Model.
- §4 Corrected Deploy Flow must insert this ceremony as its first gate.
- §5 Corrected Trust Model reads confirmed identity from this ceremony.

---

### Migration Notes

- **Legacy behavior:** `start_controller` hardcodes `127.0.0.1:8080`. On first run of corrected deploy, user sees the new ceremony. Existing single-node users confirm local placement; no functional change for them.
- **Deprecated:** Hardcoded host/port in `start_controller`. Fixed controller address in WizardWelcome consent text.
- **Transitional behavior:** If `phantom_config.json` already exists with a controller address (from a prior deploy), pre-populate the ceremony fields with that address and prompt the user to review, not re-enter from scratch.

---

## 2. Worker Selection Ceremony

### Purpose

The Worker Selection Ceremony presents discovered worker manifests to the user and requires explicit per-worker approval before any worker is registered with the controller. It is the enforcement gate for the Voluntary Mesh principle: no worker joins the mesh without a human decision.

Doctrine principles satisfied:
- **§5 Voluntary Mesh Participation:** Joining is a human decision; automatic registration is prohibited.
- **§8 Reversibility:** Users may deselect workers; selection is reviewable before commit.
- **§3 Authentic Trust:** Only manifests that pass signature verification (§3) appear in the selection list.
- **§4 Transparent Operation:** Each discovered worker's identity, address, and capabilities are shown before the user decides.

---

### Problem Statement

**Root causes addressed:** RC-2 (worker selection missing), RC-10 (auto-registration violates trust model), RC-12 (LAN assumed trusted).

The current `scan_lan()` and `scan_and_register_workers()` functions discover worker manifests and immediately register every one of them without user interaction. No UI step exists between discovery and registration. The `WorkersPanel` only shows workers that are already registered. The Phantom Doctrine explicitly bans auto-approval. The installer architecture defines a `select_workers()` step (S3) but the Tauri deploy path never invokes it.

---

### Design Specification

**High-level architecture:**  
Step 9 (LAN scan) is split into three ordered sub-steps: 9a Discover, 9b User Selects, 9c Register Selected. An intermediate UI panel (`WorkerSelectionPanel`) receives the discovered-but-unregistered manifest list and gates Step 9c on explicit user confirmation.

**Required components:**
- `WorkerSelectionPanel` — UI panel displaying discovered manifests pending approval
- `DiscoveredManifest` — data structure for a manifest received from discovery, before registration
- `WorkerSelectionDecision` — records which manifests the user approved, rejected, or deferred
- Updated Step 9c — registers only approved manifests; skips rejected/deferred ones

**Required data structures:**
```
DiscoveredManifest {
  worker_id: string
  address: string         // IP:port
  capabilities: string[]  // CPU, GPU type, VRAM
  signature_verified: bool
  discovered_at: timestamp
}

WorkerSelectionDecision {
  approved: [worker_id, ...]
  rejected: [worker_id, ...]
  deferred: [worker_id, ...]
  decided_at: timestamp
}
```

**Required ceremonies:**
1. Step 9a: Discovery broadcast runs; manifests collected (not registered).
2. System emits manifest list to frontend via Tauri event.
3. `WorkerSelectionPanel` displays each manifest with: worker_id, address, capabilities, signature status.
4. User checks/unchecks each worker; confirms selection.
5. Step 9c: Only checked (approved) manifests are passed to `register_worker()`.
6. Rejected manifests are logged; never registered in this session.
7. Deferred manifests may be re-offered on next scan.

**Required trust boundaries:**  
Manifests with `signature_verified: false` must be visually flagged and should default to unchecked. The user may still approve an unverified manifest but must do so knowingly (see §3 for full enforcement).

**Required user interactions:**  
Per-manifest checkboxes. Confirm button (registers selected). Cancel button (registers none; leaves deploy in post-discovery state).

**Required controller/worker responsibilities:**  
Controller: does not call `register_worker()` until `WorkerSelectionDecision.approved` list is provided.  
Worker: no change; continues responding to discovery broadcasts.

**Required reversibility behavior:**  
A registered worker may be deregistered from the WorkersPanel at any time. The selection decision is not final beyond the current session; re-scanning presents a fresh list.

---

### Flow Diagram

```
[Deploy Step 9a: Discovery broadcast]
        |
        |-- UDP broadcast PHANTOM_DISCOVER_WORKERS to :8095
        |-- Collect WORKER_MANIFEST responses (timeout 1500ms per subnet)
        |-- Verify signatures (§3)
        |-- Emit DiscoveredManifest[] to frontend
        |
        v
[WorkerSelectionPanel]
        |
        |-- Display each DiscoveredManifest:
        |     worker_id | address | capabilities | sig: OK / UNVERIFIED
        |     [checkbox — default: checked if verified, unchecked if not]
        |
        |-- [CANCEL] --> No workers registered; deploy continues to Step 10
        |
        |-- [CONFIRM SELECTION]
        |       |
        |       v
        |   WorkerSelectionDecision written
        |
        v
[Deploy Step 9c: Register approved workers only]
        |
        |-- For each worker_id in approved list:
        |     verify signature (double-check, §3)
        |     POST /workers/register with manifest
        |
        |-- Rejected workers: logged, not registered
        |
        v
[Step 10: Load execution modes]

PRECONDITION:  Step 9a complete; manifests collected; §3 verification run
POSTCONDITION: Only user-approved workers registered; WorkersPanel reflects final list
```

---

### Doctrine Alignment

| Principle | How Satisfied |
|-----------|--------------|
| §5 Voluntary Mesh | Every registration is an explicit user act |
| §8 Reversibility | No irreversible trust without approval; deregistration always available |
| §3 Authentic Trust | Unsigned/unverified manifests flagged; user sees trust status |
| §4 Transparent Operation | Full manifest details shown before decision |

---

### Trust Model Alignment

- **Eliminates implicit trust:** No manifest is registered by discovery alone.
- **Restores user approval workflows:** Per-worker checkboxes enforce manual approval per `.cursorrules:50`.
- **Prevents auto-registration:** The loop `for m in manifests { register_worker(m) }` is replaced by a gated ceremony.
- **Enforces manifest authenticity:** Signature status visible; unverified manifests default-unchecked.

---

### Interoperability Requirements

- Depends on §3 Manifest Signing Model for `signature_verified` field.
- Feeds into §4 Corrected Deploy Flow as Steps 9a/9b/9c.
- §5 Corrected Trust Model records each approval in the trust ledger.
- `WorkerSelectionPanel` replaces the current auto-register behavior in `scan_lan()`.

---

### Migration Notes

- **Legacy behavior:** `scan_lan()` registers all. On migration, this function is split; existing single-worker deployments where the only worker is local will see a one-item selection list — one click to confirm, no regression.
- **Deprecated:** Auto-register loop in `scan_lan()` and `scan_and_register_workers()`.
- **Transitional behavior:** If running in a non-UI (CLI) deploy mode, require an explicit `--approve-all-workers` flag to replicate current behavior, with a clear trust-bypass warning logged.

---

## 3. Manifest Signing Model

### Purpose

The Manifest Signing Model ensures that every worker manifest transmitted over the network carries a cryptographic signature proving its origin. The controller verifies the signature before considering registration. This transforms discovery from a network-scoped trust assumption into a cryptographic trust assertion.

Doctrine principles satisfied:
- **§3 Authentic Trust:** Identity is cryptographic and verifiable; no peer trusted by default.
- **§2 Sovereign Domains:** Each worker's identity is self-sovereign; its signature cannot be forged.
- **§6 Consistent Behavior:** All discovery paths — Tauri, installer, future clients — verify signatures the same way.

---

### Problem Statement

**Root causes addressed:** RC-3 (manifest signing missing), RC-12 (LAN assumed trusted).

Workers currently emit plain unsigned JSON manifests. The `discovery_listener.py` docstring claims manifests are signed — they are not. The controller's `register_worker()` accepts any `WorkerInfo` without verification. Any host on the LAN can send a forged manifest claiming any `worker_id`. This enables impersonation and mesh infiltration.

---

### Design Specification

**High-level architecture:**  
Each worker generates or loads a per-worker Ed25519 keypair at startup. Before sending a discovery response, the worker signs the manifest payload. The receiver (Tauri deployer or controller) verifies the signature against the worker's public key before accepting the manifest.

**Required components:**
- `WorkerIdentity` — per-worker Ed25519 keypair stored at worker startup path
- `SignedManifest` — manifest schema extended with signature and public_key fields
- `ManifestSigner` — worker-side component that signs the payload before sending
- `ManifestVerifier` — controller/deployer-side component that verifies before registering

**Required data structures:**
```
SignedManifest {
  // Existing fields
  worker_id: string
  address: string
  capabilities: object
  msg_type: "WORKER_MANIFEST"
  // New fields
  public_key: string      // hex-encoded Ed25519 public key
  signature: string       // hex-encoded Ed25519 signature over canonical payload
  signed_at: timestamp
}

canonical_payload = JSON(worker_id, address, capabilities, msg_type, signed_at)
// deterministic: sorted keys, no whitespace
```

**Required ceremonies:**
1. Worker startup: generate Ed25519 keypair if absent; persist to worker identity store.
2. On discovery request: construct canonical payload; sign with private key; include `public_key` and `signature` in response.
3. Receiver: reconstruct canonical payload from received fields; verify `signature` using `public_key`; reject if invalid.
4. Controller `register_worker()`: requires `signature_verified: true` before persisting worker record.

**Required trust boundaries:**  
The receiver must never trust a manifest where signature verification fails. An invalid signature must result in rejection, logging, and (in the §2 Worker Selection Ceremony) the manifest appearing with `sig: INVALID` and defaulting to unchecked.

**Required identity behavior:**  
Per-worker keypairs are independent of the controller keypair (§1). A Trust-On-First-Use (TOFU) model applies: on first connection from a given `worker_id`, the public key is recorded. On subsequent connections, the recorded key is used for verification. A key change triggers a re-approval requirement.

**Required error-handling behavior:**  
Missing signature: reject manifest, log warning, do not register.  
Invalid signature: reject manifest, log security event, do not register.  
Unknown worker_id + valid signature: accept as new worker, present in selection ceremony (§2).

**Required reversibility behavior:**  
A worker's recorded public key can be removed from the trust store by the user, forcing re-approval on next discovery.

---

### Flow Diagram

```
[Worker startup]
        |
        |-- Load or generate per-worker Ed25519 keypair
        |-- Store keypair at worker identity path
        |
        v
[Discovery request received at :8095]
        |
        |-- Construct canonical payload:
        |     {worker_id, address, capabilities, msg_type, signed_at}
        |-- Sign payload with worker private key
        |-- Build SignedManifest (payload + public_key + signature)
        |-- Send UDP response to requester
        |
        v
[Tauri deployer / controller receives SignedManifest]
        |
        |-- Reconstruct canonical payload from received fields
        |-- Verify signature using received public_key
        |     |
        |     |-- [INVALID] --> Reject; log security event; do not forward to selection ceremony
        |     |
        |     |-- [VALID, known worker_id] --> Compare public_key to trust store
        |     |       |-- [KEY MISMATCH] --> Flag as suspicious; require re-approval
        |     |       |-- [KEY MATCH]    --> signature_verified = true
        |     |
        |     |-- [VALID, new worker_id] --> TOFU: record public_key; signature_verified = true
        |
        v
[Worker Selection Ceremony (§2) receives DiscoveredManifest with signature_verified flag]

PRECONDITION:  Worker has a keypair; discovery listener is active
POSTCONDITION: Controller only receives manifests that passed signature verification and user approval
```

---

### Doctrine Alignment

| Principle | How Satisfied |
|-----------|--------------|
| §3 Authentic Trust | Every manifest cryptographically attested; no implicit trust on LAN |
| §2 Sovereign Domains | Per-worker identity is self-sovereign; cannot be forged |
| §6 Consistent Behavior | Same signing/verification logic regardless of discovery path |

---

### Trust Model Alignment

- **Eliminates implicit trust:** LAN adjacency no longer grants trust. Signature is the trust primitive.
- **Restores user approval workflows:** §2 ceremony uses `signature_verified` to inform user decision.
- **Prevents impersonation:** `worker_id` cannot be claimed without the corresponding private key.
- **Enforces manifest authenticity:** The `discovery_listener.py` docstring claim ("responds with a signed manifest") is now architecturally true.

---

### Interoperability Requirements

- Depended upon by §2 Worker Selection Ceremony (provides `signature_verified` field).
- Depended upon by §4 Corrected Deploy Flow (Step 9c verifies before registering).
- §9 Corrected Installer Discovery Model must adopt the same `SignedManifest` schema.
- All three discovery paths (Rust/Tauri, Python worker, installer) must produce and consume the same schema.

---

### Migration Notes

- **Legacy behavior:** Manifests are unsigned JSON. Receivers accept all. On migration, introduce a **grace period mode** where unsigned manifests are accepted but flagged as `signature_verified: false` and shown in the selection ceremony with a visible warning.
- **Deprecated:** Unsigned manifest emission in `discovery_listener.py`; unconditional acceptance in `register_worker()`.
- **Transitional behavior:** Grace period ends after a configurable migration window. After the window, unsigned manifests are rejected outright.

---

## 4. Corrected Deploy Flow

### Purpose

The Corrected Deploy Flow is a fully-ordered, ceremony-gated sequence of steps from user consent through running mesh. It eliminates silent assumptions, inserts the two required ceremonies (controller selection §1, worker selection §2), enforces config ordering (§8), extends firewall rules (§6), replaces the fixed readiness sleep (§7), and ensures manifests are signed (§3) before any worker is registered.

Doctrine principles satisfied:
- **§4 Transparent Operation:** Each step is visible, logged, and produces a verifiable outcome.
- **§2 Sovereign Domains:** Controller placement is user-confirmed before deploy.
- **§5 Voluntary Mesh:** Worker registration is user-gated.
- **§8 Reversibility:** Each step is individually reversible; failure at any step halts forward progress.

---

### Problem Statement

**Root causes addressed:** RC-1 through RC-14 (all root causes intersect the deploy flow).

The current flow is a linear 11-step sequence (0–10) with no ceremony gates, incorrect config ordering, insufficient readiness timing, incomplete port rules, misleading logs, and auto-registration. It was designed for single-node local deployment and was never updated to reflect multi-device, doctrine-aligned behavior.

---

### Design Specification

**Corrected Step Sequence:**

| Step | Label | Change from Current |
|------|-------|---------------------|
| **Pre-0** | Controller Selection Ceremony | **NEW** — see §1 |
| 0 | Create virtual environment | Unchanged |
| 1 | Install Python runtime | Unchanged |
| 2 | Install Phantom Core | Unchanged |
| 3 | Verify GPU plugins | Unchanged (log-only; never blocking) |
| 4 | Install Phantom service | Unchanged |
| **4.5** | Bootstrap config | **NEW** — write phantom_config.json before Step 5; see §8 |
| 5 | Start controller | Consumes `ControllerPlacementParams`; reads config written at 4.5 |
| 6 | Open ports | **EXTENDED** — adds 8090/tcp, 8095/udp, 8081/tcp; see §6 |
| 7 | Initialize state | Unchanged |
| 8 | Start local worker | **READINESS PROBE** replaces 2s sleep; fix GPU log; see §7 |
| **9a** | Discover workers | Broadcast UDP to :8095; collect SignedManifests; verify signatures |
| **9b** | Worker Selection Ceremony | **NEW** — user approves/rejects; see §2 |
| **9c** | Register selected workers | Register only approved manifests; verify signature before each call |
| 10 | Load execution modes | Retain; may be a no-op if 4.5 already wrote all needed config |

**Required error-handling behavior:**  
Any step failure halts forward progress and surfaces the error to the UI. The deploy does not silently continue past a failed critical step. Non-critical steps (GPU verification, log-only) may log and continue.

**Required reversibility behavior:**  
Each step records its pre-state. Undeploy reverses steps in reverse order. No step may make an irreversible change without a confirmation gate.

---

### Flow Diagram

```
[WizardWelcome — consent]
        |
        v
[Pre-0: Controller Selection Ceremony] ──[CANCEL]──> Exit
        |
        v
[Step 0–4: Environment, deps, core, GPU, service]
        |
        v
[Step 4.5: Bootstrap config (phantom_config.json written)]
        |
        v
[Step 5: Start controller at confirmed host:port]
        |
        v
[Step 6: Open ports 8080/tcp, 8081/tcp, 8090/tcp, 8095/udp]
        |
        v
[Step 7: Initialize state marker]
        |
        v
[Step 8: Start local worker]
        |-- Spawn worker process
        |-- Readiness probe: poll :8095 until WORKER_MANIFEST received or timeout
        |-- On timeout: warn user; Step 9a will attempt discovery anyway
        |
        v
[Step 9a: Discovery broadcast → collect SignedManifests]
        |
        v
[Step 9b: Worker Selection Ceremony] ──[CANCEL/none]──> Step 10
        |
        v
[Step 9c: Verify + Register approved workers only]
        |
        v
[Step 10: Load execution modes]
        |
        v
[FrontPorchDeploy: Deployed]

PRECONDITION:  WizardWelcome consent; ControllerPlacementParams confirmed
POSTCONDITION: Controller running; selected workers registered; all ports open; config coherent
```

---

### Doctrine Alignment

| Principle | How Satisfied |
|-----------|--------------|
| §4 Transparent Operation | Every step visible; no silent failures; accurate logs |
| §2 Sovereign Domains | Controller placement confirmed at Pre-0 |
| §5 Voluntary Mesh | Worker registration gated at 9b |
| §8 Reversibility | Halt-on-failure; undeploy reversal |
| §7 Evolution Without Drift | Legacy steps updated; no stale assumptions remain |

---

### Trust Model Alignment

- Controller identity confirmed before any worker contacts it.
- Workers verified before registration (§3).
- User approves each worker (§2).
- Firewall rules match actual service ports (§6).

---

### Interoperability Requirements

- All nine domains feed into or are ordered by this flow.
- §8 Config Model governs Step 4.5.
- §6 Port Model governs Step 6.
- §7 Readiness Model governs Step 8.
- §2 and §3 govern Steps 9a–9c.
- §1 governs Pre-0.

---

### Migration Notes

- **Legacy behavior:** Steps 0–10 run linearly with no gates. Migration adds Pre-0 and 4.5 as new phases; splits 9 into 9a/9b/9c.
- **Transitional behavior:** A `--legacy-deploy` flag may bypass ceremonies during a migration window, logging a doctrine-violation warning for each bypass.
- **Deprecated:** Fixed 2s sleep in Step 8; single-port firewall in Step 6; auto-register in Step 9; config read-before-write.

---

## 5. Corrected Trust Model

### Purpose

The Corrected Trust Model defines how trust is established, recorded, and revoked across all Phantom entities — controllers, workers, and the local user. It eliminates network-topology trust (LAN = trusted) and replaces it with cryptographic attestation plus explicit user approval at every trust boundary.

Doctrine principles satisfied:
- **§3 Authentic Trust:** Trust is explicit, never implied; identity is cryptographic.
- **§2 Sovereign Domains:** Each domain's trust store is sovereign; no external authority populates it.
- **§5 Voluntary Mesh:** Mesh membership requires approval at the trust boundary.
- **§8 Reversibility:** Trust relationships can be revoked by the user.

---

### Problem Statement

**Root causes addressed:** RC-3, RC-10, RC-12 (LAN assumed trusted; auto-registration; unsigned manifests).

The current model trusts any manifest that arrives over UDP on port 8095 from any LAN host. There is no signature verification, no trust store, and no revocation mechanism. A single `register_worker()` call accepts any `WorkerInfo`. This violates §3 and §5 and contradicts `.cursorrules:50` ("Trust relationships require manual approval").

---

### Design Specification

**Trust Levels:**

| Level | Description | How Established |
|-------|-------------|-----------------|
| **Unverified** | Manifest received; signature not yet checked | Discovery arrival |
| **Signature-Valid** | Manifest signature verified; TOFU key recorded | §3 verification |
| **User-Approved** | User explicitly approved in selection ceremony | §2 ceremony |
| **Registered** | Worker record persisted in controller | Post-§2 approval |
| **Revoked** | User removed worker from trust store | Explicit user action |

**Required components:**
- `TrustStore` — per-controller ledger of worker public keys and approval records
- `TrustRecord` — immutable log entry for each trust event (approve, revoke, key-change)
- `TrustBoundary` — the verification+approval gate that all manifests must pass before registration

**Required data structures:**
```
TrustRecord {
  worker_id: string
  public_key: string
  trust_level: enum(unverified, sig_valid, approved, registered, revoked)
  decided_by: string      // "user" or "system"
  decided_at: timestamp
  reason: string          // human-readable
}
```

**Required network behavior:**  
LAN is a discovery space, not a trust space. Network adjacency grants zero trust. Trust is established only through the cryptographic and approval pipeline.

---

### Flow Diagram

```
[Manifest received from LAN]
        |
        v
[TrustBoundary: signature verification (§3)]
        |
        |-- INVALID/MISSING --> TrustRecord(unverified); blocked from §2
        |-- VALID, new key  --> TOFU record; TrustRecord(sig_valid)
        |-- VALID, known key, match --> TrustRecord(sig_valid)
        |-- VALID, key mismatch --> FLAG; TrustRecord(suspicious); blocked
        |
        v
[Worker Selection Ceremony (§2) — user approves or rejects]
        |
        |-- REJECTED --> TrustRecord(revoked); not registered
        |-- APPROVED --> TrustRecord(approved)
        |
        v
[register_worker() — TrustRecord(registered)]
        |
        v
[WorkersPanel — user may revoke at any time → TrustRecord(revoked)]

PRECONDITION:  Manifest received; TrustBoundary active
POSTCONDITION: TrustStore reflects user's decisions; only approved workers registered
```

---

### Doctrine Alignment

| Principle | How Satisfied |
|-----------|--------------|
| §3 Authentic Trust | Every trust transition requires cryptographic evidence |
| §2 Sovereign Domains | Trust store is local; no external authority |
| §5 Voluntary Mesh | Approval is the gateway to mesh membership |
| §8 Reversibility | Revocation available at any time |

---

### Trust Model Alignment

- Eliminates LAN-as-trust-boundary entirely.
- Every worker has an auditable TrustRecord chain.
- Key changes trigger re-approval — no silent substitution.
- User is the sole authority over the trust store.

---

### Interoperability Requirements

- §3 Manifest Signing Model feeds `signature_verified` and `public_key` into TrustBoundary.
- §2 Worker Selection Ceremony reads from TrustBoundary and writes TrustRecords.
- §4 Deploy Flow Step 9c queries TrustStore before calling `register_worker()`.
- §9 Installer Discovery must produce manifests compatible with this TrustBoundary.

---

### Migration Notes

- **Legacy behavior:** No trust store; all workers auto-registered. On migration, populate TrustStore with existing registered workers at `trust_level: registered` with `decided_by: "legacy-migration"`.
- **Transitional behavior:** Legacy-migrated workers are flagged in the UI; user prompted to review and explicitly re-approve or revoke.
- **Deprecated:** Unconditional `register_worker()` acceptance.

---

## 6. Corrected Port Model

### Purpose

The Corrected Port Model defines exactly which ports Phantom services use, what protocol each carries, and which must be opened by the deploy flow. It eliminates the port mismatch between what is opened (8080/tcp only) and what the system requires (8080, 8081, 8090, 8095), and corrects the UI tooltip that conflates worker HTTP and discovery UDP ports.

Doctrine principles satisfied:
- **§4 Transparent Operation:** All communication paths are documented, opened, and reachable. No silent network failures.
- **§6 Consistent Behavior:** Port roles are consistent across Rust, Python, and installer layers.

---

### Problem Statement

**Root causes addressed:** RC-5 (ports 8090/8095 not opened), RC-9 (UI tooltip wrong port).

Deploy Step 6 opens only TCP 8080. Ports 8081 (socket), 8090 (worker HTTP), and 8095 (discovery UDP) are never opened. On systems with strict host firewalls, worker traffic and discovery are silently blocked. The `WorkersPanel` tooltip says "port 8090" for discovery, but discovery uses UDP 8095. This conflation causes user confusion and misconfiguration.

---

### Design Specification

**Canonical Port Table:**

| Port | Protocol | Service | Direction | Opened by Deploy |
|------|----------|---------|-----------|-----------------|
| 8080 | TCP | Controller API (HTTP/WS) | Inbound | Yes |
| 8081 | TCP | Socket Infrastructure (WebSocket) | Inbound | Yes |
| 8090 | TCP | Worker HTTP API | Inbound (LAN) | Yes |
| 8095 | UDP | Discovery listener | Inbound (LAN, broadcast) | Yes |

**Required components:**
- `PortPolicy` — enumerated list of all required ports and protocols; single source of truth
- Updated `open_ports()` — iterates `PortPolicy`; opens all listed ports in Step 6

**Required network behavior:**  
All four ports listed above must be opened before workers are started (Step 8) and before discovery is attempted (Step 9a). Opening order must respect the corrected deploy flow sequence.

**Required config behavior:**  
`PortPolicy` is defined in `phantom_config.json` (see §8). Ports are not hardcoded in deploy logic; they are read from the config. This allows future port reassignment without code changes.

**UI correction:**  
`WorkersPanel` tooltip must read: "Discovery uses UDP port 8095 · Worker API uses TCP port 8090". Port roles must never be conflated.

---

### Flow Diagram

```
[Deploy Step 6: Open ports]
        |
        |-- Read PortPolicy from phantom_config.json
        |
        |-- For each entry in PortPolicy:
        |     Open firewall rule: <port>/<protocol>
        |     Log: "Opened <port>/<protocol> for <service>"
        |
        |-- On any rule failure:
        |     Log warning with port, protocol, and error
        |     Surface to UI (non-fatal; worker/discovery may still work)
        |
        v
[Step 7, 8, 9a proceed with all ports open]

PRECONDITION:  Step 5 (controller started); firewall management available
POSTCONDITION: Rules exist for 8080/tcp, 8081/tcp, 8090/tcp, 8095/udp
```

---

### Doctrine Alignment

| Principle | How Satisfied |
|-----------|--------------|
| §4 Transparent Operation | All service ports opened and logged; no silent firewall blocks |
| §6 Consistent Behavior | Same port policy applied on Linux and Windows |

---

### Trust Model Alignment

- Correct port opening ensures discovery reaches only the intended listener (signed manifests per §3), not arbitrary hosts.
- Firewall rules align with the actual trust perimeter.

---

### Interoperability Requirements

- `PortPolicy` is read by §8 Config Model.
- §4 Deploy Flow Step 6 consumes `PortPolicy`.
- §9 Installer Discovery Model must open 8095/udp independently if deploying via installer path.
- §7 Readiness Model depends on 8095/udp being open before the readiness probe runs.

---

### Migration Notes

- **Legacy behavior:** Only 8080/tcp opened. On migration, Step 6 is updated to iterate `PortPolicy`. Existing single-port systems gain three additional rules; no rules are removed.
- **Deprecated:** Hardcoded single-port logic in `open_ports()`.
- **Transitional behavior:** If the firewall management layer fails to open 8090 or 8095 (e.g., insufficient permissions), deploy continues but logs a clear warning: "Discovery and worker traffic may be blocked. Open ports 8090/tcp and 8095/udp manually."

---

## 7. Corrected Readiness Model

### Purpose

The Corrected Readiness Model replaces the fixed 2-second sleep after worker spawn with an active readiness probe. The probe confirms that the worker's discovery listener is bound and responsive before the deploy flow advances to discovery (Step 9a). This eliminates the race condition where discovery runs before the worker is ready.

Doctrine principles satisfied:
- **§4 Transparent Operation:** Deploy does not silently advance past an unready worker; the user is informed of readiness status.
- **§6 Consistent Behavior:** Readiness is probed the same way on all platforms and hardware configurations.

---

### Problem Statement

**Root causes addressed:** RC-4 (worker readiness timing too short), RC-13 (deploy flow assumes worker ready in 2 seconds).

The worker's startup sequence — GPU detection, plugin initialization, HTTP registration, background task spawn — can exceed 2 seconds on GPU-equipped or slow systems. The fixed sleep is a race condition. If the worker's discovery listener is not yet bound when Step 9a runs, the local worker does not appear in the discovery results and the deploy completes with zero workers.

---

### Design Specification

**Required components:**
- `ReadinessProbe` — sends a unicast UDP discovery request to `127.0.0.1:8095`; expects a `WORKER_MANIFEST` response
- `ReadinessConfig` — configurable probe parameters (interval, max_attempts, timeout_per_attempt)

**Required data structures:**
```
ReadinessConfig {
  probe_interval_ms: uint     // default 500ms
  max_attempts: uint          // default 20 (10 seconds total)
  attempt_timeout_ms: uint    // default 1000ms
  success_criterion: "WORKER_MANIFEST_received"
}
```

**Required timing behavior:**
1. After worker process is spawned, immediately begin readiness probing.
2. Send unicast `PHANTOM_DISCOVER_WORKERS` to `127.0.0.1:8095`.
3. Wait up to `attempt_timeout_ms` for a `WORKER_MANIFEST` response.
4. If received: worker is ready; advance to Step 9a.
5. If not received: wait `probe_interval_ms`; retry up to `max_attempts`.
6. If `max_attempts` exhausted: log warning "Local worker did not respond within readiness window"; advance to Step 9a anyway (non-fatal; broadcast may still find it or it may not be present).

**Required error-handling behavior:**  
Readiness timeout is non-fatal. The probe is a best-effort gate, not a hard dependency. Discovery in Step 9a is the authoritative step; if the local worker responds there, it is discovered. If not, the user sees it absent from the §2 selection list.

**GPU log correction:**  
The worker spawn failure log message must not assert GPU necessity. Correct text: `"Failed to start local worker: {e}"` (applicable on all platforms equally).

---

### Flow Diagram

```
[Deploy Step 8: Start local worker]
        |
        |-- Write local_worker_config.json
        |-- Spawn worker process
        |
        v
[ReadinessProbe loop]
        |
        |-- attempt = 0
        |-- LOOP:
        |     Send unicast PHANTOM_DISCOVER_WORKERS to 127.0.0.1:8095
        |     Wait attempt_timeout_ms for WORKER_MANIFEST response
        |     |
        |     |-- RECEIVED --> Worker ready; exit loop
        |     |-- TIMEOUT  --> attempt++
        |     |               if attempt < max_attempts: sleep probe_interval_ms; retry
        |     |               if attempt == max_attempts: log warning; exit loop
        |
        v
[Deploy Step 9a: Discovery broadcast]

PRECONDITION:  Worker process spawned
POSTCONDITION: Either worker confirmed ready, or timeout logged; Step 9a proceeds either way
```

---

### Doctrine Alignment

| Principle | How Satisfied |
|-----------|--------------|
| §4 Transparent Operation | Readiness status surfaced to user; no silent race condition |
| §6 Consistent Behavior | Same probe on all platforms; no platform-specific sleep assumptions |

---

### Trust Model Alignment

- Readiness probe uses the same UDP channel as discovery (§3 manifests). A responsive worker is already speaking the signed manifest protocol.

---

### Interoperability Requirements

- Depends on §6 Port Model having opened 8095/udp before this probe runs.
- §4 Deploy Flow Step 8 invokes `ReadinessProbe` before Step 9a.
- §3 Manifest Signing Model applies to the probe response — the local worker's manifest is verified even in the readiness probe.

---

### Migration Notes

- **Legacy behavior:** `sleep(2s)` in `start_local_worker()`. Replace with `ReadinessProbe`. On fast machines the probe completes in one or two attempts (< 1s); on slow machines it waits up to 10s instead of potentially failing silently.
- **Deprecated:** Fixed `sleep(2s)` after worker spawn; platform-inconsistent "GPU required" log text.
- **Transitional behavior:** `ReadinessConfig` values are conservative defaults; operators may tune via config (§8).

---

## 8. Corrected Config Model

### Purpose

The Corrected Config Model defines the lifecycle of `phantom_config.json` and related configuration artifacts. It enforces write-before-read ordering, establishes a bootstrap step that writes config before the controller starts, and provides a single authoritative source of truth for all runtime parameters — port policy, placement params, execution modes, and readiness config.

Doctrine principles satisfied:
- **§4 Transparent Operation:** Config state is deterministic; no silent fallbacks due to missing files.
- **§6 Consistent Behavior:** All components read from the same config; no component has its own hardcoded defaults that diverge from the config.
- **§8 Reversibility:** Config is written atomically; prior config is preserved before overwrite.

---

### Problem Statement

**Root causes addressed:** RC-7 (phantom_config ordering bug), RC-14 (deploy flow assumes config exists early).

`phantom_config.json` is written in Step 10 (`load_execution_modes`) but read in Step 5 (`start_controller`). On first deploy, the file does not exist, and the controller starts with a fallback value of `"disabled"` for security. The comment in the deployer source says "written by step 9" — both the comment and the step number are wrong. This is low-risk today because the fallback is acceptable, but it is architecturally fragile: if any future component requires a correct config value at Step 5 or earlier, read-before-write will silently produce wrong behavior.

---

### Design Specification

**Config lifecycle:**

| Phase | Action | Config state |
|-------|--------|-------------|
| Pre-0 (Controller ceremony) | `ControllerPlacementParams` available | Not yet written |
| Step 4.5 (Bootstrap config) | Write `phantom_config.json` with: placement, port policy, security level, readiness config, execution mode defaults | Written; authoritative |
| Step 5 | Read `phantom_config.json` → start controller with correct params | Read (file exists) |
| Step 10 | Verify or update execution modes; no re-write if already written at 4.5 | Idempotent update |

**Required components:**
- `ConfigBootstrap` — Step 4.5 component that collects all pre-deploy inputs and writes `phantom_config.json` atomically
- `ConfigSchema` — defines all fields of `phantom_config.json` with types and defaults
- Atomic write pattern: write to `.phantom_config.json.tmp`, then rename to `phantom_config.json`

**Required data structures:**
```
phantom_config.json {
  controller: {
    host: string,
    port: uint16,
    security: string,           // "disabled" | "basic" | "full"
    identity_fingerprint: string
  },
  ports: {
    controller_api: 8080,
    socket: 8081,
    worker_http: 8090,
    discovery_udp: 8095
  },
  worker: {
    readiness_probe_interval_ms: 500,
    readiness_max_attempts: 20,
    readiness_attempt_timeout_ms: 1000
  },
  execution_modes: {
    default_mode: string,
    ...
  },
  config_version: string,
  written_at: timestamp,
  written_by_step: "4.5"    // correct annotation
}
```

**Required reversibility behavior:**  
Before overwriting an existing `phantom_config.json`, back it up to `phantom_config.json.bak` with a timestamp. The backup is retained until the next successful deploy.

---

### Flow Diagram

```
[Pre-0: ControllerPlacementParams confirmed (§1)]
        |
        v
[Steps 0–4: environment setup]
        |
        v
[Step 4.5: ConfigBootstrap]
        |
        |-- Collect: ControllerPlacementParams, PortPolicy, ReadinessConfig, execution defaults
        |-- If phantom_config.json exists: backup to .bak
        |-- Write phantom_config.json atomically (tmp → rename)
        |-- Log: "phantom_config.json written at step 4.5"
        |
        v
[Step 5: start_controller reads phantom_config.json]
        |   (file guaranteed to exist; no fallback needed)
        |
        v
[Steps 6–9c: consume config values (ports, readiness)]
        |
        v
[Step 10: load_execution_modes — idempotent; updates only missing fields]

PRECONDITION:  Pre-0 ceremony complete; Steps 0–4 complete
POSTCONDITION: phantom_config.json exists and is coherent before Step 5 reads it
```

---

### Doctrine Alignment

| Principle | How Satisfied |
|-----------|--------------|
| §4 Transparent Operation | Config written before read; no silent fallback; step annotation correct |
| §6 Consistent Behavior | All components read the same config; no divergent hardcoded defaults |
| §8 Reversibility | Atomic write; backup before overwrite |

---

### Trust Model Alignment

- Security level in config is set by user at ceremony time (Pre-0), not silently defaulted to "disabled".
- Config is the source of truth for controller identity fingerprint, ensuring no drift between ceremony and runtime.

---

### Interoperability Requirements

- §1 Controller Selection Ceremony writes `ControllerPlacementParams` which becomes the `controller` block in config.
- §6 Port Model reads `ports` block.
- §7 Readiness Model reads `worker.readiness_*` fields.
- §4 Deploy Flow Step 4.5 is the write point.
- §5 Trust Model reads `controller.identity_fingerprint` from config.

---

### Migration Notes

- **Legacy behavior:** Config written at Step 10; read at Step 5 with `unwrap_or_else("disabled")`. On migration, Step 4.5 is inserted. For existing deployments, the first corrected deploy backs up the old config and writes a new one.
- **Deprecated:** `unwrap_or_else` fallback in `start_controller`; incorrect "written by step 9" comment.
- **Transitional behavior:** If `phantom_config.json` exists from a legacy deploy and passes schema validation, ConfigBootstrap may skip re-writing it and log "existing config retained."

---

## 9. Corrected Installer Discovery Model

### Purpose

The Corrected Installer Discovery Model aligns the installer's worker discovery mechanism with the protocol used by the Tauri deploy path and the worker's discovery listener. It replaces the incompatible TCP raw-JSON probe with a UDP broadcast-based discovery that matches the actual worker protocol, and ensures the same `SignedManifest` schema (§3) is used across all discovery paths.

Doctrine principles satisfied:
- **§6 Consistent Behavior:** Installer discovers workers the same way as Tauri — via UDP broadcast to port 8095.
- **§4 Transparent Operation:** Discovery failures are reported accurately; no silent fallback to fabricated worker info.
- **§7 Evolution Without Drift:** The legacy TCP placeholder is retired; a single canonical discovery protocol exists.

---

### Problem Statement

**Root causes addressed:** RC-8 (installer discovery TCP probing incompatible with HTTP workers).

`installer/modules/worker_discovery.py::_query_worker_info()` sends a raw JSON `{"action": "get_info"}` payload over a raw TCP connection to ports 8090–8094. Workers speak HTTP on port 8090 — they do not respond to raw JSON over TCP. The function's comment explicitly marks it as a placeholder that was never replaced. This means the installer's worker discovery always falls back to fabricated minimal info (`Worker-{ip}`) and never retrieves real `worker_id`, GPU info, or capabilities. The Tauri deploy path is unaffected (it uses `discovery.rs` UDP broadcast), but the installer path is systematically broken for worker discovery.

---

### Design Specification

**Required components:**
- `InstallerDiscoveryClient` — sends UDP broadcast `PHANTOM_DISCOVER_WORKERS` to `:8095`; collects `SignedManifest` responses; replaces `_query_worker_info()`
- `InstallerWorkerRecord` — populated from real `SignedManifest` data, not fabricated fallback

**Required protocol:**

| Property | Corrected Value |
|----------|----------------|
| Protocol | UDP |
| Discovery port | 8095 |
| Request payload | `{"msg_type": "PHANTOM_DISCOVER_WORKERS"}` |
| Response schema | `SignedManifest` (see §3) |
| Timeout | 1500ms per subnet (matches Tauri `TIMEOUT_MS`) |
| Deduplication | By `worker_id` |

**Required alignment with Tauri discovery:**  
The installer discovery must use the same timeout, request payload format, deduplication key, and response schema as `discovery.rs`. This is the canonical discovery contract. Any future discovery client must implement this contract.

**Required signature verification:**  
`InstallerDiscoveryClient` must verify `SignedManifest` signatures (§3) before surfacing workers to the installer's selection step (S3). Unsigned or invalid-signature manifests are flagged, not silently accepted.

**Required error-handling behavior:**  
If no workers respond within the timeout: report "No workers discovered" accurately. Do not fabricate minimal worker records. Do not silently substitute `Worker-{ip}`.

---

### Flow Diagram

```
[Installer Stage S2: Worker Discovery]
        |
        |-- Send UDP broadcast: PHANTOM_DISCOVER_WORKERS to <broadcast>:8095
        |-- Also unicast to 127.0.0.1:8095 (local worker)
        |-- Wait 1500ms
        |-- Collect SignedManifest responses
        |-- Deduplicate by worker_id
        |-- Verify signatures (§3):
        |     |-- VALID   --> InstallerWorkerRecord(real worker_id, capabilities, sig_verified=true)
        |     |-- INVALID --> flag; include in list with sig_verified=false
        |     |-- MISSING --> flag; include in list with sig_verified=false (grace period) or exclude
        |
        v
[Installer Stage S3: Worker Selection]
        |   (identical ceremony to §2 Worker Selection Ceremony)
        |   User approves/rejects each discovered worker
        |
        v
[Installer Stage S4: Register approved workers only]

PRECONDITION:  Port 8095/udp reachable; workers running and listening
POSTCONDITION: Real worker info (not fabricated) surfaced to S3; only approved workers registered
```

---

### Doctrine Alignment

| Principle | How Satisfied |
|-----------|--------------|
| §6 Consistent Behavior | Installer and Tauri use the same discovery protocol |
| §4 Transparent Operation | No fabricated fallback; accurate reporting of discovery results |
| §7 Evolution Without Drift | TCP placeholder retired; single canonical UDP protocol |

---

### Trust Model Alignment

- Same `SignedManifest` verification as §3 applied on installer path.
- Installer's S3 selection ceremony mirrors §2 Worker Selection Ceremony.
- No installer-specific trust bypass; trust model is uniform across deploy paths.

---

### Interoperability Requirements

- §3 Manifest Signing Model defines the `SignedManifest` schema consumed here.
- §2 Worker Selection Ceremony design is reused for installer S3.
- §5 Corrected Trust Model applies equally to installer-discovered workers.
- §6 Port Model: installer must open 8095/udp before running S2 discovery.

---

### Migration Notes

- **Legacy behavior:** `_query_worker_info()` TCP raw-JSON probe, fallback to `Worker-{ip}`. On migration, this function is replaced by `InstallerDiscoveryClient` (UDP). No data is preserved from the legacy fallback records — they were fabricated.
- **Deprecated:** `_query_worker_info()` TCP probing; fabricated worker record fallback; `discover_workers_comprehensive()` TCP connect loop.
- **Transitional behavior:** During migration, if a target host does not respond to UDP discovery, the installer reports "Worker at {ip} did not respond to UDP discovery on port 8095" with instructions for the user to verify the worker is running. No silent fallback.

---

## Summary: Cross-Domain Dependency Map

```
§1 Controller Selection ──writes──> §8 Config (ControllerPlacementParams)
                        ──identity root──> §3 Manifest Signing (controller keypair)

§3 Manifest Signing ──provides sig_verified──> §2 Worker Selection
                    ──provides sig_verified──> §9 Installer Discovery
                    ──provides signed manifests──> §5 Trust Model

§2 Worker Selection ──gates registration in──> §4 Deploy Flow (Step 9b)
                    ──writes TrustRecords to──> §5 Trust Model

§4 Deploy Flow ──consumes──> §1 (Pre-0 ceremony)
               ──consumes──> §6 Port Model (Step 6)
               ──consumes──> §7 Readiness Model (Step 8)
               ──consumes──> §8 Config Model (Step 4.5)
               ──invokes──> §2 and §3 (Steps 9a–9c)

§6 Port Model ──read by──> §4 Deploy Flow Step 6
              ──enables──> §7 Readiness Model (8095/udp must be open)
              ──enables──> §9 Installer Discovery (8095/udp)

§7 Readiness Model ──depends on──> §6 Port Model (8095/udp open)
                   ──precedes──> §4 Deploy Flow Step 9a

§8 Config Model ──provides config to──> §4, §6, §7 at Step 4.5

§9 Installer Discovery ──mirrors protocol of──> §4 Deploy Flow Steps 9a–9c
                       ──applies──> §3 Manifest Signing verification
                       ──applies──> §2 Worker Selection ceremony (S3)
                       ──subject to──> §5 Trust Model
```

---

*End of document. No code. No implementation details. Design only.*  
*Senior engineers implementing this design must treat each section as an authoritative specification.*
