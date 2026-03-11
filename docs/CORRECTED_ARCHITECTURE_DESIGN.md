# Phantom Distributed Compute Fabric — Corrected Architecture Design

**Date:** 2026-03-10  
**Basis:** FINAL_ARCHITECTURAL_CORRECTION_MAP.md, GAP_ANALYSIS_AUDIT_REPORT.md, ROOT_CAUSE_ANALYSIS_REPORT.md, Phantom Doctrine  
**Audience:** Senior engineers implementing Phantom's doctrine  
**Scope:** Design only. No code. No implementation details.

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

The Controller Selection Ceremony is a mandatory pre-deploy gate that requires the user to explicitly choose controller placement, confirm the controller's cryptographic identity, and authorize the start of any deployment work. No installation step may execute until the ceremony completes.

This ceremony satisfies:
- **§2 Sovereign Domains** — the user asserts which node is sovereign; no placement is assumed.
- **§3 Authentic Trust** — the controller's Ed25519 identity is generated and displayed before any trust relationship can form.
- **§4 Transparent Operation** — the user sees the exact address, port, and identity fingerprint before committing.
- **§8 Reversibility** — cancellation at this stage leaves the system entirely unchanged.

---

### Problem Statement

RC-1 (correction map): the deploy flow has no controller selection ceremony; controller placement is implicit and identity is never surfaced to the user during deployment. This prevents multi-device topologies, violates §2, and makes controller identity invisible at the moment it is most consequential.

---

### Design Specification

**Architecture:**  
A `ControllerSelectionScreen` is inserted between WizardWelcome (where general consent is obtained) and the deploy trigger. It runs a two-phase interaction — placement selection followed by identity confirmation — and produces a `ControllerPlacementParams` record that all subsequent deploy steps consume.

**Required components:**

| Component | Responsibility |
|-----------|----------------|
| `ControllerSelectionScreen` | UI panel; collects placement choice; displays identity fingerprint |
| `ControllerPlacementParams` | Immutable record of user's confirmed placement decision |
| `IdentityManager` | Generates or loads the controller Ed25519 keypair; provides fingerprint |

**ControllerPlacementParams schema:**
```
{
  host:                  string   // user-selected address (e.g. "127.0.0.1" or LAN IP)
  port:                  uint16   // default 8080; user-configurable
  device_label:          string   // human-readable name for this controller node
  identity_fingerprint:  string   // hex-encoded Ed25519 public key (first 16 bytes)
  confirmed_at:          timestamp
}
```

**Ceremony steps:**
1. ControllerSelectionScreen opens; IdentityManager loads or generates an Ed25519 keypair.
2. Screen presents: placement options (Local CPU · Local GPU · Custom IP:Port), controller address preview, identity fingerprint, and device label.
3. User selects placement, reviews identity, and either confirms or cancels.
4. On confirm: `ControllerPlacementParams` is written to the config layer (see §8) and the deploy flow is unblocked.
5. On cancel: no state is written; the system returns to WizardWelcome.

**Trust boundaries:**
- The controller must not start until `ControllerPlacementParams` is present.
- The fingerprint shown must match the keypair actually used by the controller at runtime.
- IdentityManager must not be bypassed; the keypair path must not be configurable at ceremony time.

**Network behavior:** No network calls occur during the ceremony. Placement is a local configuration decision.

**Identity behavior:** The Ed25519 keypair generated here is the controller's root identity. It is the signing authority referenced in §3 (Manifest Signing Model) and the identity recorded in §5 (Trust Model). On subsequent deploys the existing keypair is loaded and the user is shown the same fingerprint to confirm continuity.

**Error handling:** If IdentityManager cannot generate or load a keypair, the ceremony halts and surfaces the error. The deploy button remains disabled. There is no fallback to an anonymous or unsigned controller.

**Reversibility:** Before deploy begins, the user may return to this screen, change placement, and re-confirm. After deploy starts, placement changes require a full undeploy-redeploy cycle.

---

### Flow Diagram

```
[WizardWelcome — general consent obtained]
        |
        v
[ControllerSelectionScreen]
        |
        |-- IdentityManager: load or generate Ed25519 keypair
        |
        |-- Display:
        |     Placement options: Local CPU | Local GPU | Custom IP:Port
        |     Controller address: <host>:<port>
        |     Identity fingerprint: <hex-16-bytes>
        |     Device label: <string>
        |
        |-- User selects placement and reviews identity
        |
        |--[CANCEL]──> return to WizardWelcome; no state written
        |
        |--[CONFIRM]──> write ControllerPlacementParams; keypair persisted
        |
        v
[FrontPorchDeploy — deploy button enabled]
        |
        v
[Deploy Step 0: ControllerPlacementParams available to all steps]
        ...
[Deploy Step 5: controller starts at confirmed host:port with confirmed identity]

PRECONDITION:  WizardWelcome consent complete; no deploy in progress
POSTCONDITION: ControllerPlacementParams persisted; Ed25519 keypair on disk;
               deploy button enabled; controller not yet started
```

---

### Doctrine Alignment

| Principle | How This Design Satisfies It |
|-----------|------------------------------|
| §2 Sovereign Domains | User asserts placement; no controller starts without explicit authorization |
| §3 Authentic Trust | Identity is cryptographic, generated before deployment, and visible to the user |
| §4 Transparent Operation | Host, port, and fingerprint are shown at the decision point |
| §8 Reversibility | Cancel leaves zero state; placement is reviewable before and between deploys |

---

### Trust Model Alignment

This design ensures that every controller has a user-confirmed identity before any worker is permitted to contact it. The fingerprint shown in the ceremony is the same key used at runtime — there is no anonymous or defaulted controller identity. The keypair produced here is the root of the manifest verification chain in §3, so trust cannot be established unless the controller ceremony has been completed.

---

### Interoperability Requirements

- `ControllerPlacementParams` is written to `phantom_config.json` at Step 4.5 (§8) and is the authoritative source for controller host and port. No other component may hardcode these values.
- The Ed25519 keypair produced here is the root identity referenced by §3 Manifest Signing Model and §5 Trust Model.
- §4 Corrected Deploy Flow positions this ceremony at Pre-0, before any installation step.

---

### Migration Notes

- **Existing single-node installs:** On first corrected deploy, users see the ceremony, pre-populated with `127.0.0.1:8080` and their existing keypair (if present). One confirmation click; no functional change.
- **Legacy config:** If a prior `phantom_config.json` exists with a controller address, pre-populate the ceremony fields from it. Do not silently re-use the values — require the user to review and re-confirm.
- **Deprecated:** Any mechanism that starts the controller without a confirmed `ControllerPlacementParams`.

---

## 2. Worker Selection Ceremony

### Purpose

The Worker Selection Ceremony is a mandatory gate between worker discovery and worker registration. It presents the list of discovered workers to the user and requires explicit per-worker approval before any registration call is made. No worker joins the mesh without a human decision.

This ceremony satisfies:
- **§5 Voluntary Mesh Participation** — joining is an explicit human act; automatic enrollment is prohibited.
- **§8 Reversibility** — selections are reviewable before commit; registered workers can be deregistered at any time.
- **§3 Authentic Trust** — only manifests that pass signature verification appear with a trusted indicator; unsigned manifests appear with a warning.
- **§4 Transparent Operation** — every worker's identity, address, and capabilities are shown before the user decides.

---

### Problem Statement

RC-2 and RC-10 (correction map): the deploy flow auto-registers every discovered worker without user interaction, violating §5 (Voluntary Mesh) and §8 (Reversibility) and directly contradicting the doctrine requirement that trust relationships require manual approval.

---

### Design Specification

**Architecture:**  
Step 9 (LAN scan) is decomposed into three ordered sub-steps:

- **9a — Discover:** broadcast and collect; do not register.
- **9b — Worker Selection Ceremony:** present manifest list; gate on user confirmation.
- **9c — Register Selected:** register only approved manifests, with final signature verification.

A `WorkerSelectionPanel` UI component mediates Step 9b. It receives the discovered-but-unregistered manifest list via a Tauri event and gates Step 9c on an explicit user action.

**Required components:**

| Component | Responsibility |
|-----------|----------------|
| `WorkerSelectionPanel` | UI panel; displays discovered manifests; collects per-worker approval decisions |
| `DiscoveredManifest` | Data record for a manifest received from discovery, before registration |
| `WorkerSelectionDecision` | Immutable record of user approvals, rejections, and deferrals for this scan session |

**DiscoveredManifest schema:**
```
{
  worker_id:          string
  address:            string      // IP:port
  capabilities:       string[]    // e.g. ["CPU", "NVIDIA RTX 4090", "24576MB VRAM"]
  signature_verified: bool
  discovered_at:      timestamp
}
```

**WorkerSelectionDecision schema:**
```
{
  approved:   [worker_id, ...]
  rejected:   [worker_id, ...]
  deferred:   [worker_id, ...]
  decided_at: timestamp
}
```

**Ceremony steps:**
1. Step 9a completes; manifests collected and signature-verified per §3.
2. `DiscoveredManifest[]` emitted to the frontend.
3. `WorkerSelectionPanel` renders each manifest with: worker_id, address, capabilities, and a signature badge (VERIFIED · UNVERIFIED · INVALID).
4. Manifests with `signature_verified: false` default to unchecked; the user must actively check them to approve.
5. User reviews, checks/unchecks, and confirms.
6. `WorkerSelectionDecision` is written; Step 9c proceeds with the approved list.
7. Rejected and deferred manifests are logged; they are never registered in this session.

**Trust boundaries:**
- The controller must not call the worker registration endpoint until `WorkerSelectionDecision.approved` is provided.
- Manifests with an invalid or missing signature are ineligible for approval unless the user explicitly overrides with a visible warning.
- Step 9c must perform a final signature re-verification for each approved manifest before the registration call.

**Reversibility:** Registration is not final. Any registered worker can be deregistered from WorkersPanel at any time without re-deploying. Re-scanning always produces a fresh manifest list; prior decisions do not carry forward automatically.

---

### Flow Diagram

```
[Deploy Step 9a: Discovery]
        |
        |-- UDP broadcast PHANTOM_DISCOVER_WORKERS → :8095
        |-- Unicast to 127.0.0.1:8095 (local worker)
        |-- Collect SignedManifest responses (1500ms timeout per subnet)
        |-- Verify signatures per §3
        |-- Emit DiscoveredManifest[] to frontend
        |
        v
[Step 9b: WorkerSelectionPanel]
        |
        |-- Display each DiscoveredManifest:
        |     worker_id | address | capabilities | VERIFIED / UNVERIFIED / INVALID
        |     [checkbox: checked by default if VERIFIED; unchecked if UNVERIFIED/INVALID]
        |
        |--[CANCEL]──> no workers registered; flow advances to Step 10
        |
        |--[CONFIRM SELECTION]──> WorkerSelectionDecision written
        |
        v
[Step 9c: Register approved workers]
        |
        |-- For each worker_id in approved list:
        |     Re-verify signature (§3)
        |     POST worker manifest to controller registration endpoint
        |
        |-- Rejected/deferred workers: logged; not registered
        |
        v
[Step 10: Load execution modes]

PRECONDITION:  Step 9a complete; DiscoveredManifest[] available
POSTCONDITION: Only user-approved workers registered; WorkersPanel reflects final membership
```

---

### Doctrine Alignment

| Principle | How This Design Satisfies It |
|-----------|------------------------------|
| §5 Voluntary Mesh | Every registration is an explicit user decision; no background enrollment |
| §8 Reversibility | Selection is reviewable before commit; deregistration is always available |
| §3 Authentic Trust | Signature verification precedes the user decision; unsigned manifests are flagged |
| §4 Transparent Operation | Full manifest details (identity, address, capabilities, trust status) shown at decision point |

---

### Trust Model Alignment

This design ensures that the mesh boundary is defined entirely by user decisions, not by network reachability. Discovery is a candidate-collection phase, not a trust-granting phase. Every worker in the mesh has a corresponding user approval record in the TrustStore (§5). Workers that the user has never seen cannot be registered, and workers the user has rejected are excluded from the session regardless of network availability.

---

### Interoperability Requirements

- Depends on §3 Manifest Signing Model for the `signature_verified` field in `DiscoveredManifest`.
- Step 9b/9c are the registration gates defined by §4 Corrected Deploy Flow.
- Each user approval writes a `TrustRecord` to §5 Trust Model.
- The installer's S3 Worker Selection stage (§9) mirrors this ceremony for the installer deploy path.

---

### Migration Notes

- **Existing single-worker installs:** On the first corrected deploy, users see a one-item selection list (the local worker). One checkbox confirmation; no functional change to the end state.
- **CLI / headless deploys:** Must require an explicit `--approve-all-workers` flag. This flag must log a doctrine-bypass warning to the audit log on every use.
- **Deprecated:** Any code path that registers workers without a preceding `WorkerSelectionDecision`.

---

## 3. Manifest Signing Model

### Purpose

The Manifest Signing Model defines how every worker manifest is cryptographically signed by its originating worker and how that signature is verified by any receiver before the manifest is acted upon. It replaces network-location trust with cryptographic identity attestation as the foundational primitive for all worker trust decisions.

This model satisfies:
- **§3 Authentic Trust** — identity is cryptographic; no peer is trusted by default; LAN adjacency grants no privileges.
- **§2 Sovereign Domains** — each worker's identity is self-sovereign and cannot be forged or transferred.
- **§6 Consistent Behavior** — all discovery paths (Tauri, installer, future clients) sign and verify using the same schema and algorithm.

---

### Problem Statement

RC-3 (correction map): worker manifests are transmitted as unsigned JSON, making it impossible to distinguish legitimate workers from imposters; any host on the LAN can claim any worker identity and be registered without challenge.

---

### Design Specification

**Architecture:**  
Each worker holds a per-worker Ed25519 keypair generated at first startup. When responding to a discovery request, the worker constructs a deterministic canonical payload, signs it, and includes the signature and public key in the response. The receiver verifies the signature before forwarding the manifest to the selection ceremony or registration pipeline.

**Required components:**

| Component | Responsibility |
|-----------|----------------|
| `WorkerIdentity` | Per-worker Ed25519 keypair; generated on first startup; persisted to worker identity path |
| `SignedManifest` | Canonical manifest schema that includes `public_key`, `signature`, and `signed_at` |
| `ManifestSigner` | Worker-side: constructs canonical payload; signs with private key |
| `ManifestVerifier` | Receiver-side: reconstructs canonical payload; verifies signature; applies TOFU rules |

**SignedManifest schema:**
```
{
  // Discovery fields (existing)
  worker_id:    string
  address:      string
  capabilities: object
  msg_type:     "WORKER_MANIFEST"

  // Signing fields (new)
  public_key:   string     // hex-encoded Ed25519 public key
  signature:    string     // hex-encoded Ed25519 signature over canonical_payload
  signed_at:    timestamp
}

canonical_payload = deterministic JSON of:
  { worker_id, address, capabilities, msg_type, signed_at }
  // sorted keys; no extra whitespace
```

**Signing ceremony (worker-side):**
1. At startup: load Ed25519 keypair from worker identity path; generate if absent.
2. On discovery request: construct `canonical_payload` from current manifest fields.
3. Sign `canonical_payload` with the worker's private key.
4. Emit `SignedManifest` (canonical_payload fields + `public_key` + `signature`).

**Verification ceremony (receiver-side):**
1. Parse received message; check for presence of `public_key`, `signature`, `signed_at`.
2. Reconstruct `canonical_payload` from received fields.
3. Verify `signature` against `canonical_payload` using `public_key`.
4. Apply TOFU: on first contact from a given `worker_id`, record `public_key` in the TrustStore (§5). On subsequent contacts, compare received `public_key` to the recorded key.
5. Set `signature_verified = true` if verification passes and key matches (or is new TOFU). Set to `false` otherwise.
6. Forward `DiscoveredManifest` with `signature_verified` flag to §2 Worker Selection Ceremony.

**Trust boundaries:**
- A manifest with a missing, malformed, or invalid signature must never reach the registration pipeline.
- A manifest whose `public_key` differs from the recorded TrustStore key for that `worker_id` must be flagged as a key-change event and require explicit user re-approval.
- The controller registration endpoint must reject any `WorkerInfo` not accompanied by a verified trust record.

**Error handling:**

| Condition | Action |
|-----------|--------|
| Signature absent | Reject; log warning; set `signature_verified = false` |
| Signature invalid | Reject; log security event; set `signature_verified = false` |
| Key mismatch (known worker_id) | Flag as suspicious; require re-approval; do not auto-register |
| New worker_id, valid signature | TOFU: record key; `signature_verified = true`; forward to §2 |

---

### Flow Diagram

```
[Worker: startup]
        |
        |-- Load or generate per-worker Ed25519 keypair
        |-- Persist keypair to worker identity path
        |
        v
[Worker: discovery request received on :8095]
        |
        |-- Construct canonical_payload {worker_id, address, capabilities, msg_type, signed_at}
        |-- Sign canonical_payload with private key → signature
        |-- Assemble SignedManifest {canonical_payload, public_key, signature}
        |-- Send UDP SignedManifest to requester
        |
        v
[Receiver: SignedManifest received]
        |
        |-- Parse: check for public_key, signature, signed_at
        |-- Reconstruct canonical_payload
        |-- Verify signature using public_key
        |
        |--[INVALID/MISSING]──> reject; log event; signature_verified = false
        |
        |--[VALID, known worker_id]
        |       |--[KEY MATCH]──> signature_verified = true
        |       |--[KEY MISMATCH]──> flag suspicious; require re-approval
        |
        |--[VALID, new worker_id]──> TOFU: record public_key; signature_verified = true
        |
        v
[§2 Worker Selection Ceremony receives DiscoveredManifest with signature_verified flag]

PRECONDITION:  Worker has a persisted keypair; discovery listener is active on :8095
POSTCONDITION: Receiver has a verified (or flagged) DiscoveredManifest;
               controller registration endpoint is never called without a verified trust record
```

---

### Doctrine Alignment

| Principle | How This Design Satisfies It |
|-----------|------------------------------|
| §3 Authentic Trust | Every manifest carries a cryptographic proof of origin; no implicit LAN trust |
| §2 Sovereign Domains | Each worker's identity is self-sovereign; keypair cannot be transferred or forged |
| §6 Consistent Behavior | The same SignedManifest schema and verification logic applies on all discovery paths |

---

### Trust Model Alignment

This design makes the network layer transparent to trust decisions. A manifest's trustworthiness is determined entirely by its cryptographic validity and the user's approval history, not by which network it arrived on. The LAN is a transport medium, not a trust boundary. Key-change detection ensures that a worker's identity cannot be silently replaced — any such change surfaces to the user as a re-approval requirement.

---

### Interoperability Requirements

- `SignedManifest` schema is the canonical manifest format for all discovery paths: Tauri, Python worker listener, and installer (§9).
- §2 Worker Selection Ceremony consumes `DiscoveredManifest.signature_verified` as produced here.
- §5 Trust Model's TrustStore is populated with `public_key` records via the TOFU path defined here.
- §9 Installer Discovery Model must implement the same signing contract and schema on the installer path.

---

### Migration Notes

- **Grace period:** During the initial migration window, manifests without a signature are accepted but surfaced in §2 with `sig: UNSIGNED` and default to unchecked. This allows existing workers time to adopt the signing model.
- **End of grace period:** After the migration window, unsigned manifests are rejected at the receiver before reaching the selection ceremony. The window duration is configurable in `phantom_config.json` (§8).
- **Deprecated:** Unsigned manifest emission; unconditional manifest acceptance at the registration endpoint.

---

## 4. Corrected Deploy Flow

### Purpose

The Corrected Deploy Flow is a fully-ordered, ceremony-gated sequence that takes the system from user consent to a running, doctrine-compliant mesh. It integrates all nine corrected domains into a coherent, reversible, step-by-step process where every user-visible decision point is explicit and every automated step is transparent.

This flow satisfies:
- **§4 Transparent Operation** — each step is visible, logged, and produces a verifiable outcome.
- **§2 Sovereign Domains** — controller placement is user-confirmed before any installation work begins.
- **§5 Voluntary Mesh** — worker registration is gated by the user's explicit selection decision.
- **§8 Reversibility** — step failures halt forward progress; undeploy reverses steps in reverse order.

---

### Problem Statement

RC-1, RC-2, RC-4, RC-5, RC-6, RC-7, RC-8, RC-10, RC-12 (correction map): the current deploy flow has no ceremony gates, starts the controller before config is written, opens only one port, uses a fixed sleep for worker readiness, and auto-registers all discovered workers — in aggregate, a linear script that violates sovereignty, trust, and transparency at every decision point.

---

### Design Specification

**Corrected step sequence:**

| Step | Label | Status |
|------|-------|--------|
| **Pre-0** | Controller Selection Ceremony | NEW — §1; user selects placement, confirms identity |
| 0 | Create virtual environment | Unchanged |
| 1 | Install Python runtime | Unchanged |
| 2 | Install Phantom Core | Unchanged |
| 3 | Verify GPU plugins | Unchanged (log-only; never blocking; corrected log text at Step 8) |
| 4 | Install Phantom service | Unchanged |
| **4.5** | Bootstrap config | NEW — §8; write `phantom_config.json` before Step 5 reads it |
| 5 | Start controller | Updated — consumes `ControllerPlacementParams` from config; reads security level from config |
| **6** | Open ports | Updated — §6; opens 8080/tcp, 8090/tcp, 8095/udp (see Port Model) |
| 7 | Initialize state | Unchanged |
| **8** | Start local worker | Updated — §7; readiness probe replaces fixed sleep; corrected log text |
| **9a** | Discover workers | NEW sub-step — UDP broadcast; collect SignedManifests; verify per §3 |
| **9b** | Worker Selection Ceremony | NEW sub-step — §2; user approves/rejects each discovered worker |
| **9c** | Register selected workers | NEW sub-step — register only approved manifests; re-verify signature before each call |
| 10 | Load execution modes | Retained; idempotent if §8 config bootstrap already wrote the relevant fields |

**Step failure policy:**  
Critical steps (Pre-0, 0, 1, 2, 4, 4.5, 5) must halt the flow on failure and surface the error to the UI. Non-critical steps (3, 7) may log and continue. Step 8 readiness timeout is non-fatal (see §7). Step 9b cancellation skips registration and proceeds to Step 10 with an empty worker set.

**Reversibility policy:**  
Each step that writes state must record the pre-state. Undeploy reverses steps in the reverse order of their execution. No step may produce an irreversible side effect without a user confirmation gate.

---

### Flow Diagram

```
[WizardWelcome — general consent]
        |
        v
[Pre-0: Controller Selection Ceremony]──[CANCEL]──> exit; no state written
        |
        v
[Steps 0–4: venv · Python deps · Phantom Core · GPU verify · service install]
        |
        v
[Step 4.5: Config bootstrap]
        |-- Write phantom_config.json (controller params, port policy, readiness config)
        |-- Atomic write: tmp file → rename
        |
        v
[Step 5: Start controller]
        |-- Read host, port, security level from phantom_config.json
        |-- Bind controller to confirmed address
        |
        v
[Step 6: Open ports]
        |-- Open 8080/tcp  (Controller API)
        |-- Open 8090/tcp  (Worker HTTP API)
        |-- Open 8095/udp  (Discovery listener)
        |
        v
[Step 7: Initialize state marker]
        |
        v
[Step 8: Start local worker]
        |-- Spawn worker process
        |-- Readiness probe: unicast PHANTOM_DISCOVER_WORKERS → 127.0.0.1:8095
        |-- Poll until WORKER_MANIFEST received or readiness timeout
        |-- On timeout: log warning; proceed to Step 9a
        |
        v
[Step 9a: Discovery broadcast]
        |-- UDP broadcast PHANTOM_DISCOVER_WORKERS → <subnet>:8095
        |-- Unicast → 127.0.0.1:8095
        |-- Collect SignedManifests (1500ms timeout per subnet)
        |-- Verify signatures per §3
        |
        v
[Step 9b: Worker Selection Ceremony]──[CANCEL/no selection]──> Step 10
        |
        v
[Step 9c: Register approved workers]
        |-- Re-verify signature for each approved manifest
        |-- POST to controller registration endpoint
        |
        v
[Step 10: Load execution modes — idempotent]
        |
        v
[Deployed]

PRECONDITION:  WizardWelcome consent; no deploy in progress
POSTCONDITION: Controller running at user-confirmed address;
               selected workers registered;
               8080/tcp, 8090/tcp, 8095/udp open;
               phantom_config.json coherent and written before it is read
```

---

### Doctrine Alignment

| Principle | How This Design Satisfies It |
|-----------|------------------------------|
| §2 Sovereign Domains | Controller placement is a user decision made at Pre-0, not an assumption |
| §3 Authentic Trust | Manifest signing and verification enforced at Steps 9a–9c |
| §4 Transparent Operation | Every step visible; accurate logs; no silent failures or false port openings |
| §5 Voluntary Mesh | Worker registration is gated by user approval at Step 9b |
| §7 Evolution Without Drift | All legacy assumptions (fixed sleep, single port, auto-register) removed |
| §8 Reversibility | Halt-on-failure; step pre-state recorded; undeploy reverses in order |

---

### Trust Model Alignment

The deploy flow enforces the trust model at every point where a trust boundary is crossed:
- Pre-0 ensures the controller has a confirmed identity before workers can contact it.
- Steps 9a–9c ensure that no worker reaches the registration endpoint without a valid signature and explicit user approval.
- Step 6 ensures that the ports actually required by the trust-model components (discovery on 8095, worker API on 8090) are open before those components are exercised.

---

### Interoperability Requirements

All nine corrected domains are sequenced by or feed into this flow:
- §1 governs Pre-0.
- §8 governs Step 4.5.
- §6 governs Step 6.
- §7 governs Step 8.
- §3 and §2 govern Steps 9a–9c.
- §5 receives trust records written during Steps 9b–9c.

---

### Migration Notes

- **Existing deploys:** The first corrected deploy adds Pre-0 (one confirmation screen) and Step 4.5 (automatic config bootstrap). Steps 0–7 and 10 behave identically for existing single-node users.
- **Transitional flag:** A `--legacy-deploy` mode may be provided for automated environments during a migration window. Every invocation must write a doctrine-bypass warning to the audit log.
- **Deprecated:** Fixed 2-second sleep after worker spawn; single-port firewall in Step 6; auto-register loop in Step 9; controller start before config is written.

---

## 5. Corrected Trust Model

### Purpose

The Corrected Trust Model defines the lifecycle of trust between the controller and every worker: how trust is initiated, elevated through verification and user approval, recorded immutably, and revoked. It establishes the LAN as a discovery medium with zero inherent trust, and cryptographic attestation plus explicit user approval as the only paths to mesh membership.

This model satisfies:
- **§3 Authentic Trust** — trust is cryptographic and explicit; it cannot be inferred from network location.
- **§2 Sovereign Domains** — the trust store is local to the controller; no external authority populates it.
- **§5 Voluntary Mesh** — mesh membership requires a user approval record in the trust store.
- **§8 Reversibility** — trust can be revoked by the user at any time without re-deploying.

---

### Problem Statement

RC-3, RC-10, RC-12 (correction map): the current system has no trust store and no revocation mechanism; network reachability on the LAN is the de facto trust criterion, meaning any host that can send a UDP packet to port 8095 can become a registered mesh member.

---

### Design Specification

**Trust levels:**

| Level | Meaning | How Reached |
|-------|---------|-------------|
| Unverified | Manifest received; signature check not yet run | Discovery arrival |
| Sig-Valid | Signature passes verification; TOFU key recorded | §3 ManifestVerifier |
| Approved | User explicitly selected this worker in §2 ceremony | §2 WorkerSelectionDecision |
| Registered | Worker record persisted in the controller | Post-approval registration call |
| Revoked | User removed this worker from the trust store | Explicit user action in WorkersPanel |

**Required components:**

| Component | Responsibility |
|-----------|----------------|
| `TrustStore` | Per-controller persistent ledger of worker public keys and their current trust level |
| `TrustRecord` | Immutable log entry written at every trust-level transition |
| `TrustBoundary` | Gate that enforces: no manifest enters the approval pipeline without passing §3 verification; no worker is registered without a `TrustRecord(Approved)` |

**TrustRecord schema:**
```
{
  worker_id:   string
  public_key:  string
  trust_level: enum { unverified, sig_valid, approved, registered, revoked }
  decided_by:  string     // "user" | "system"
  decided_at:  timestamp
  reason:      string     // human-readable note
}
```

**Trust store behavior:**
- The TrustStore is local to the controller and initialized empty on first deploy.
- Every signature verification result writes a TrustRecord.
- Every user approval decision (approve, reject, defer) writes a TrustRecord.
- Every deregistration writes a TrustRecord with `trust_level: revoked`.
- TrustRecords are append-only; the store maintains a full history per `worker_id`.
- The current trust level for a worker is the level of its most recent TrustRecord.

**Key-change handling:**  
If a manifest arrives with a valid signature but a `public_key` that differs from the recorded key for that `worker_id`, the manifest is flagged as a key-change event. The worker's trust level is set back to `unverified`, a TrustRecord is written with `reason: "key_change_detected"`, and the worker must pass the full approval pipeline again.

**Network behavior:** The LAN is a discovery space. Network adjacency to port 8095 does not grant any trust level. The TrustBoundary is enforced regardless of the network path a manifest traversed.

---

### Flow Diagram

```
[SignedManifest arrives from discovery]
        |
        v
[TrustBoundary: §3 verification]
        |
        |--[MISSING sig]──> TrustRecord(unverified); blocked from approval pipeline
        |--[INVALID sig]──> TrustRecord(unverified); security event logged
        |--[VALID sig, new worker_id]──> TOFU; TrustRecord(sig_valid)
        |--[VALID sig, key matches stored]──> TrustRecord(sig_valid)
        |--[VALID sig, key mismatch]──> TrustRecord(unverified, reason:key_change); re-approval required
        |
        v
[§2 Worker Selection Ceremony — user decision]
        |
        |--[REJECTED]──> TrustRecord(revoked); not registered
        |--[APPROVED]──> TrustRecord(approved)
        |
        v
[Registration call → TrustRecord(registered)]
        |
        v
[Mesh member; WorkersPanel shows worker]
        |
        v
[User may revoke at any time → TrustRecord(revoked)]

PRECONDITION:  §3 ManifestVerifier active; §2 ceremony available
POSTCONDITION: TrustStore contains a complete, auditable record of every trust decision;
               only workers with TrustRecord(registered) are in the active mesh
```

---

### Doctrine Alignment

| Principle | How This Design Satisfies It |
|-----------|------------------------------|
| §3 Authentic Trust | Every trust transition is backed by cryptographic evidence |
| §2 Sovereign Domains | Trust store is entirely local; the user is the sole authority |
| §5 Voluntary Mesh | A TrustRecord(Approved) written by the user is the gateway to mesh membership |
| §8 Reversibility | Trust can be revoked to TrustRecord(revoked) at any time without side effects on other workers |

---

### Trust Model Alignment

This design makes trust transitions explicit, auditable, and user-controlled at every stage. Network proximity never advances a worker's trust level. A key-change event cannot silently elevate a new actor to the `registered` level. The trust store provides a complete audit trail that the user can inspect, and the revocation mechanism ensures that no trust relationship is ever irreversible.

---

### Interoperability Requirements

- §3 Manifest Signing Model feeds the signature verification result into the TrustBoundary.
- §2 Worker Selection Ceremony writes `TrustRecord(Approved)` or `TrustRecord(Revoked)` for each user decision.
- §4 Deploy Flow Step 9c queries the TrustStore to confirm `TrustRecord(Approved)` before each registration call.
- §9 Installer Discovery must route its discovered workers through the same TrustBoundary and approval pipeline.

---

### Migration Notes

- **Existing registered workers:** On first corrected deploy, seed the TrustStore with a `TrustRecord(registered, decided_by: "legacy-migration")` for each previously registered worker. Flag these records in the UI and prompt the user to review and explicitly re-approve or revoke each one.
- **Deprecated:** Any registration pathway that does not require a preceding `TrustRecord(Approved)`.

---

## 6. Corrected Port Model

### Purpose

The Corrected Port Model defines the canonical set of ports and protocols that Phantom services require, specifies that all required ports must be opened during deploy, and provides a single config-driven source of truth for port assignments. It eliminates silent firewall blocks and removes ambiguity between port roles across all layers.

This model satisfies:
- **§4 Transparent Operation** — all communication paths are documented, opened, and reachable; no service fails silently because its port was never opened.
- **§6 Consistent Behavior** — port assignments and their roles are identical across Rust, Python, and installer layers.

---

### Problem Statement

RC-5 and RC-9 (correction map): the deploy flow opens only one port (8080/tcp), leaving the worker HTTP API (8090/tcp) and discovery listener (8095/udp) inaccessible on systems with host firewalls, and the WorkersPanel tooltip conflates the worker API port with the discovery port, causing users to open the wrong firewall rules.

---

### Design Specification

**Canonical port table:**

| Port | Protocol | Service | Traffic Direction | Required by Deploy |
|------|----------|---------|-------------------|--------------------|
| 8080 | TCP | Controller API (HTTP/WebSocket) | Inbound | Yes |
| 8090 | TCP | Worker HTTP API | Inbound (LAN) | Yes |
| 8095 | UDP | Discovery listener | Inbound (LAN broadcast + unicast) | Yes |

> Note: Port 8081 (Socket Infrastructure WebSocket) may also be opened depending on whether the socket layer is included in the deploy scope. This is configuration-dependent and should be listed in `phantom_config.json` alongside the three required ports above.

**Required components:**

| Component | Responsibility |
|-----------|----------------|
| `PortPolicy` | Enumerated, config-driven list of all required ports and protocols; single source of truth |
| Port-opening step (Step 6) | Iterates `PortPolicy`; opens each port/protocol combination via the platform firewall API |

**PortPolicy schema (in phantom_config.json):**
```
"ports": {
  "controller_api":    { "port": 8080, "protocol": "tcp", "required": true  },
  "worker_http":       { "port": 8090, "protocol": "tcp", "required": true  },
  "discovery_udp":     { "port": 8095, "protocol": "udp", "required": true  },
  "socket_infra":      { "port": 8081, "protocol": "tcp", "required": false }
}
```

**Operational rules:**
- All ports marked `required: true` must be opened at Step 6 before workers are started (Step 8) and before discovery runs (Step 9a).
- Port-opening failures for required ports must be logged as warnings and surfaced to the UI. They are non-fatal — the deploy continues — but the user must be informed that affected services may be unreachable.
- No port may be hardcoded in the deploy logic. Port assignments must always be read from `phantom_config.json`.
- Port assignments in the UI (tooltips, labels, descriptions) must match the `PortPolicy` values exactly.

**UI correction:**  
The WorkersPanel discovery tooltip must distinguish the two roles: "Workers are discovered via UDP broadcast on port 8095 · The Worker HTTP API is available on TCP port 8090." These must never be conflated.

---

### Flow Diagram

```
[Deploy Step 6: Open ports]
        |
        |-- Read PortPolicy from phantom_config.json
        |
        |-- For each port entry where required = true:
        |     Apply firewall rule: <port>/<protocol> inbound allow
        |     Log: "Opened <port>/<protocol> for <service>"
        |
        |-- For each port entry where required = false (e.g. 8081):
        |     Apply rule only if the corresponding service is enabled in config
        |     Log: "Opened <port>/<protocol> for <service> (optional)"
        |
        |-- On failure for any required port:
        |     Log warning with port, protocol, and error detail
        |     Surface warning to UI: "Port <port>/<protocol> could not be opened;
        |       <service> may be unreachable — open this port manually if needed"
        |
        v
[Steps 7, 8, 9a: all services start with required ports already open]

PRECONDITION:  Step 5 complete (controller started); firewall management available
POSTCONDITION: 8080/tcp, 8090/tcp, 8095/udp open and logged;
               8081/tcp open if socket layer is enabled in config
```

---

### Doctrine Alignment

| Principle | How This Design Satisfies It |
|-----------|------------------------------|
| §4 Transparent Operation | Every port opened or attempted is logged; failures surface to the user |
| §6 Consistent Behavior | One PortPolicy; identical port assignments on Linux and Windows; UI matches config |

---

### Trust Model Alignment

Correct port opening ensures that the discovery channel (8095/udp) and worker API (8090/tcp) are reachable when the manifest signing and verification pipeline runs. An inaccessible discovery port would silently prevent signature-verified manifests from being received, breaking the trust chain without any error visible to the user. Opening the correct ports is therefore a precondition for the trust model to function.

---

### Interoperability Requirements

- `PortPolicy` is defined in `phantom_config.json`, written at §8 Config Model Step 4.5.
- §4 Deploy Flow Step 6 iterates `PortPolicy`.
- §7 Readiness Model depends on 8095/udp being open before the readiness probe runs.
- §9 Installer Discovery Model must also open 8095/udp before running its discovery stage.
- UI components that reference port numbers must read from `PortPolicy`, not hardcoded values.

---

### Migration Notes

- **Existing installs:** Only 8080/tcp is currently opened. On the first corrected deploy, Step 6 opens 8090/tcp and 8095/udp additionally. No existing rules are removed.
- **Permission failures:** On systems where the deploy user lacks firewall management permissions, all three required ports must be listed in the post-deploy output with instructions for manual opening.
- **Deprecated:** Hardcoded single-port logic in the port-opening step; any UI label that conflates 8090 and 8095.

## 7. Corrected Readiness Model

### Purpose

The Corrected Readiness Model replaces the fixed post-spawn sleep with an active readiness probe that confirms the local worker's discovery listener is bound and responsive before the deploy flow advances to Step 9a. It also corrects the worker spawn failure log to be accurate regardless of GPU presence.

This model satisfies:
- **§4 Transparent Operation** — deploy status accurately reflects whether the local worker is ready; no silent race condition passes undetected.
- **§6 Consistent Behavior** — readiness is probed identically on all platforms and all hardware configurations; there are no platform-specific timing assumptions.

---

### Problem Statement

RC-4 and RC-13 (correction map): a fixed two-second sleep after worker spawn is an unreliable readiness gate — on systems where GPU detection or plugin initialization takes longer, the local worker's discovery listener is not yet bound when Step 9a runs, and the worker is silently absent from the discovery results.

---

### Design Specification

**Architecture:**  
Immediately after spawning the worker process, the deployer enters a `ReadinessProbe` loop. The probe sends a unicast `PHANTOM_DISCOVER_WORKERS` UDP packet to `127.0.0.1:8095` and waits for a `WORKER_MANIFEST` response. The loop exits when the worker responds, or after `max_attempts` are exhausted. In either case, Step 9a proceeds — the probe is a best-effort gate, not a hard dependency.

**Required components:**

| Component | Responsibility |
|-----------|----------------|
| `ReadinessProbe` | Sends unicast PHANTOM_DISCOVER_WORKERS to 127.0.0.1:8095; waits for WORKER_MANIFEST response |
| `ReadinessConfig` | Configurable probe parameters; stored in `phantom_config.json` under `worker.*` (§8) |

**ReadinessConfig schema:**
```
{
  probe_interval_ms:      uint   // default 500 — wait between attempts
  max_attempts:           uint   // default 20  — 10 seconds total at defaults
  attempt_timeout_ms:     uint   // default 1000 — per-attempt response window
}
```

**Probe sequence:**
1. Spawn worker process.
2. Send unicast `PHANTOM_DISCOVER_WORKERS` → `127.0.0.1:8095`.
3. Wait `attempt_timeout_ms` for a `WORKER_MANIFEST` response.
4. On response: worker is ready; advance to Step 9a immediately.
5. On timeout: increment attempt counter; wait `probe_interval_ms`; retry from step 2.
6. On `max_attempts` exhausted: log a clear warning — "Local worker did not respond within the readiness window. Discovery will proceed; the worker may appear in the LAN scan if it completes startup shortly." Advance to Step 9a.

**Worker spawn log text (all platforms):**  
On any spawn failure, the log message must be: `"Failed to start local worker: <reason>"`. GPU presence must never be asserted in a spawn failure message. The worker supports CPU-only mode; a spawn failure is not evidence of a GPU requirement.

**Error handling:** Readiness timeout is non-fatal. Step 9a's broadcast discovery is the authoritative step for finding workers. If the local worker starts after the readiness window, it will respond to the broadcast in Step 9a.

---

### Flow Diagram

```
[Deploy Step 8: Start local worker]
        |
        |-- Spawn worker process
        |-- Begin ReadinessProbe loop (attempt = 0)
        |
        v
[ReadinessProbe loop]
        |
        |-- Send unicast PHANTOM_DISCOVER_WORKERS → 127.0.0.1:8095
        |-- Wait attempt_timeout_ms for WORKER_MANIFEST
        |
        |--[WORKER_MANIFEST received]──> Worker ready; exit loop
        |
        |--[Timeout]──> attempt++
        |               attempt < max_attempts? → wait probe_interval_ms → retry
        |               attempt == max_attempts? → log warning; exit loop
        |
        v
[Deploy Step 9a: Discovery broadcast proceeds]

PRECONDITION:  Worker process spawned; 8095/udp open (§6)
POSTCONDITION: Either worker confirmed ready via probe response,
               or timeout logged and Step 9a proceeds with best-effort discovery
```

---

### Doctrine Alignment

| Principle | How This Design Satisfies It |
|-----------|------------------------------|
| §4 Transparent Operation | Readiness outcome is logged and surfaced; no silent advancement past an unready worker |
| §6 Consistent Behavior | One probe mechanism; same behavior on all platforms; no platform-specific timing |

---

### Trust Model Alignment

The probe response is a `WORKER_MANIFEST` governed by §3 Manifest Signing Model. A worker that responds to the readiness probe has already demonstrated its ability to produce a signed manifest, which is the minimum requirement for appearing in the §2 selection ceremony. The probe therefore acts as an early-stage trust signal, not just a liveness check.

---

### Interoperability Requirements

- Requires 8095/udp to be open before the probe runs — §6 Port Model Step 6 must precede Step 8.
- `ReadinessConfig` parameters are stored in `phantom_config.json` (§8); the probe reads these values, not hardcoded constants.
- The probe response is a `SignedManifest` (§3); the ManifestVerifier should verify it even during the readiness phase.
- §4 Deploy Flow positions the probe within Step 8, between worker spawn and Step 9a.

---

### Migration Notes

- **Existing behavior:** Fixed `sleep(2s)` after spawn. On migration, the sleep is removed and the probe loop is substituted. On fast machines, the probe typically resolves in under one second — faster than the original sleep. On slow machines, the probe waits up to 10 seconds instead of silently missing the worker.
- **Config tuning:** `ReadinessConfig` defaults are conservative. Operators running on fast hardware may reduce `max_attempts`; operators running on slow GPU systems may increase it.
- **Deprecated:** Any fixed sleep after worker spawn; the "GPU required" wording in spawn failure log messages.

---

## 8. Corrected Config Model

### Purpose

The Corrected Config Model defines the lifecycle of `phantom_config.json` — when it is written, what it contains, and who reads it — and establishes Step 4.5 as the authoritative write point. It ensures that the config file exists and is coherent before the controller starts (Step 5), and that all subsequent steps read from this single source of truth rather than from hardcoded defaults.

This model satisfies:
- **§4 Transparent Operation** — config state is deterministic; no component silently defaults to a value because the config file was absent.
- **§6 Consistent Behavior** — all components (controller, worker, ports, readiness probe) read from the same config; there are no divergent hardcoded values.
- **§8 Reversibility** — config is written atomically; a timestamped backup is preserved before any overwrite.

---

### Problem Statement

RC-7 and RC-14 (correction map): `phantom_config.json` is currently written late in the deploy sequence but read early, meaning the controller starts before its own configuration exists and silently falls back to default values for security level and other parameters.

---

### Design Specification

**Config lifecycle:**

| Deploy phase | Config action |
|-------------|---------------|
| Pre-0 (§1 ceremony) | `ControllerPlacementParams` collected; config not yet written |
| Steps 0–4 | Environment setup; config not yet written |
| **Step 4.5** | `ConfigBootstrap` writes `phantom_config.json` atomically |
| Step 5 | Controller reads `phantom_config.json`; file guaranteed to exist |
| Steps 6–9c | Port policy, readiness config, and other values consumed from config |
| Step 10 | Execution modes step is idempotent; adds only fields absent from the Step 4.5 write |

**Required components:**

| Component | Responsibility |
|-----------|----------------|
| `ConfigBootstrap` | Collects all pre-deploy inputs; writes `phantom_config.json` atomically at Step 4.5 |
| `ConfigSchema` | Defines all fields, types, and defaults; the single contract for the config file |

**`phantom_config.json` schema:**
```
{
  "controller": {
    "host":                 string,   // from ControllerPlacementParams (§1)
    "port":                 uint16,   // from ControllerPlacementParams (§1)
    "security":             string,   // "disabled" | "basic" | "full"; from user selection
    "identity_fingerprint": string    // from IdentityManager (§1)
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
    "default_mode": string
  },
  "config_version":  string,
  "written_at":      timestamp,
  "written_by_step": "4.5"
}
```

**Write semantics:**
- Atomic write: `ConfigBootstrap` writes to a `.tmp` file, then renames it to `phantom_config.json`.
- Before overwriting, any existing `phantom_config.json` is copied to `phantom_config.json.bak.<timestamp>`.
- The backup is retained through the next successful deploy.
- `written_by_step: "4.5"` is the authoritative annotation; no other step claims ownership of the initial write.

**Read semantics:**
- Step 5 reads `phantom_config.json`; no fallback is applied. If the file is absent, Step 5 fails and surfaces an error — it does not silently default.
- All other consuming steps (6, 8, 9a) read from the same file. Port assignments, readiness parameters, and security level all come from this single source.

---

### Flow Diagram

```
[Pre-0: ControllerPlacementParams confirmed]
        |
        v
[Steps 0–4: environment setup]
        |
        v
[Step 4.5: ConfigBootstrap]
        |
        |-- Collect inputs: ControllerPlacementParams, security level, PortPolicy, ReadinessConfig
        |-- If phantom_config.json exists: copy to phantom_config.json.bak.<timestamp>
        |-- Write to phantom_config.json.tmp
        |-- Rename .tmp → phantom_config.json (atomic)
        |-- Log: "phantom_config.json written at step 4.5"
        |
        v
[Step 5: start controller]
        |-- Read phantom_config.json (guaranteed present)
        |-- No fallback applied
        |
        v
[Steps 6–9c: consume port policy, readiness config from phantom_config.json]
        |
        v
[Step 10: execution modes — idempotent; adds only absent fields]

PRECONDITION:  Pre-0 ceremony complete; Steps 0–4 complete
POSTCONDITION: phantom_config.json exists, is coherent, and is the sole
               source of runtime parameters for all subsequent steps
```

---

### Doctrine Alignment

| Principle | How This Design Satisfies It |
|-----------|------------------------------|
| §4 Transparent Operation | Config is written before it is read; no silent fallbacks; annotation is correct |
| §6 Consistent Behavior | All components read from one file; no component has divergent hardcoded values |
| §8 Reversibility | Atomic write prevents partial state; timestamped backup enables rollback |

---

### Trust Model Alignment

The security level and controller identity fingerprint stored in `phantom_config.json` are set by the user at the §1 ceremony — they are never silently defaulted. The config file therefore carries the user's explicit security intent into every component that reads it, preventing security drift between what the user chose at ceremony time and what the controller actually runs with.

---

### Interoperability Requirements

- `ControllerPlacementParams` from §1 populates the `controller` block.
- `PortPolicy` from §6 is stored in the `ports` block; the port-opening step reads from here.
- `ReadinessConfig` from §7 is stored in the `worker` block; the readiness probe reads from here.
- §4 Deploy Flow Step 4.5 is the sole write point for the initial config.
- §5 Trust Model reads `controller.identity_fingerprint` from this config to confirm controller identity continuity.

---

### Migration Notes

- **Legacy read-before-write:** On first corrected deploy, Step 4.5 is inserted and writes the config before Step 5 reads it. For existing single-node installs, the written values match the prior behavior (local address, existing security level), so there is no functional change.
- **Existing config files:** Any pre-existing `phantom_config.json` is backed up before ConfigBootstrap writes the new one. The user is informed.
- **Deprecated:** Any mechanism that reads `phantom_config.json` with a fallback value when the file is absent; any annotation claiming a step other than 4.5 owns the initial write.

---

## 9. Corrected Installer Discovery Model

### Purpose

The Corrected Installer Discovery Model establishes a single canonical discovery protocol — UDP broadcast to port 8095 with `SignedManifest` responses — and requires all discovery paths to use it: the Tauri deploy path, the installer path, and any future clients. It replaces the installer's broken TCP-based probe with a protocol that workers actually speak, and applies the same manifest signing verification (§3) and worker selection ceremony (§2) on the installer path as on the Tauri path.

This model satisfies:
- **§6 Consistent Behavior** — every discovery client uses the same protocol, schema, timeout, and deduplication logic; there are no path-specific discovery dialects.
- **§4 Transparent Operation** — discovery results reflect what workers actually report; fabricated fallback records are prohibited.
- **§7 Evolution Without Drift** — the TCP placeholder is retired permanently; there is one protocol, owned by this specification.

---

### Problem Statement

RC-8 (correction map): the installer's worker discovery sends a raw JSON payload over TCP to worker ports, which is incompatible with the HTTP protocol workers actually use; as a result, the installer never retrieves real worker identity or capabilities, and falls back to fabricated records that contain no meaningful information.

---

### Design Specification

**Architecture:**  
The installer's Stage S2 (Worker Discovery) is rebuilt around an `InstallerDiscoveryClient` that implements the canonical discovery contract: UDP broadcast + unicast, `PHANTOM_DISCOVER_WORKERS` request format, 1500ms timeout, `SignedManifest` response schema, deduplication by `worker_id`. This is exactly the contract implemented by the Tauri `discovery.rs` module. The same contract governs all future discovery clients.

**Canonical discovery contract:**

| Property | Canonical value |
|----------|----------------|
| Protocol | UDP |
| Discovery port | 8095 |
| Request message type | `PHANTOM_DISCOVER_WORKERS` |
| Response schema | `SignedManifest` (§3) |
| Timeout per subnet | 1500 ms |
| Deduplication key | `worker_id` |
| Signature requirement | All responses verified per §3; unsigned flagged, not silently accepted |

**Required components:**

| Component | Responsibility |
|-----------|----------------|
| `InstallerDiscoveryClient` | Sends UDP broadcast + unicast; collects and deduplicates SignedManifest responses |
| `InstallerManifestVerifier` | Applies §3 verification to each collected manifest; sets `signature_verified` flag |
| Installer Stage S3 | Worker selection ceremony (mirrors §2); user approves or rejects each discovered worker |

**Discovery sequence:**
1. `InstallerDiscoveryClient` sends `PHANTOM_DISCOVER_WORKERS` UDP broadcast to `<subnet-broadcast>:8095`.
2. Also sends unicast to `127.0.0.1:8095` to find the local worker.
3. Collects `SignedManifest` responses for 1500ms.
4. Deduplicates by `worker_id`.
5. `InstallerManifestVerifier` applies §3 verification; sets `signature_verified` for each.
6. Passes `DiscoveredManifest[]` to Stage S3 (Worker Selection Ceremony).

**No fabricated records:** If no workers respond within the timeout, the installer reports "No workers discovered on this subnet" and presents an empty selection list. It does not create placeholder entries with fabricated worker IDs, addresses, or capabilities.

**Error handling:** An empty discovery result is a valid, expected outcome. It is surfaced to the user with instructions for verifying that target workers are running and that port 8095/udp is reachable.

---

### Flow Diagram

```
[Installer Stage S2: Worker Discovery]
        |
        |-- InstallerDiscoveryClient:
        |     UDP broadcast PHANTOM_DISCOVER_WORKERS → <broadcast>:8095
        |     UDP unicast  PHANTOM_DISCOVER_WORKERS → 127.0.0.1:8095
        |     Wait 1500ms
        |     Collect SignedManifest responses
        |     Deduplicate by worker_id
        |
        |-- InstallerManifestVerifier (§3):
        |     VALID sig, new worker_id     → signature_verified = true  (TOFU)
        |     VALID sig, known key match   → signature_verified = true
        |     VALID sig, key mismatch      → flag suspicious; require re-approval
        |     INVALID sig                  → signature_verified = false; include with warning
        |     MISSING sig                  → signature_verified = false; grace period flag
        |
        |-- No responses within timeout → "No workers discovered"; empty list
        |
        v
[Installer Stage S3: Worker Selection Ceremony]
        |   (mirrors §2 Worker Selection Ceremony exactly)
        |   Display each DiscoveredManifest:
        |     worker_id | address | capabilities | VERIFIED / UNVERIFIED / INVALID
        |   User checks/unchecks; confirms selection
        |
        v
[Installer Stage S4: Register approved workers]
        |-- Re-verify signature for each approved manifest
        |-- POST to controller registration endpoint
        |-- Apply TrustRecord(registered) in TrustStore (§5)

PRECONDITION:  Workers running; 8095/udp reachable from installer host
POSTCONDITION: Real worker data surfaced to S3; only user-approved workers registered;
               no fabricated worker records in any data store
```

---

### Doctrine Alignment

| Principle | How This Design Satisfies It |
|-----------|------------------------------|
| §6 Consistent Behavior | One discovery protocol across Tauri and installer paths; same schema, timeout, and dedup |
| §4 Transparent Operation | Actual worker data, not fabricated; empty results reported accurately |
| §7 Evolution Without Drift | TCP placeholder retired; canonical protocol owned by this spec; no path-specific dialects |

---

### Trust Model Alignment

The installer path is now subject to the identical trust pipeline as the Tauri deploy path: §3 signature verification, §2-style worker selection ceremony, §5 TrustRecord writes, and §5 TrustStore persistence. A worker discovered by the installer and approved by the user receives the same `TrustRecord(registered)` as one discovered via Tauri. There is no installer-specific trust bypass and no weaker verification path for installer-originated workers.

---

### Interoperability Requirements

- Implements the same canonical discovery contract as `discovery.rs` (Tauri); both must be kept in sync.
- Consumes `SignedManifest` schema from §3; any schema change must propagate to both paths simultaneously.
- Stage S3 worker selection mirrors §2 Worker Selection Ceremony; the UX and approval semantics must be identical.
- §5 Trust Model applies to installer-discovered workers; the TrustStore is shared, not installer-specific.
- Port 8095/udp must be open on the installer host before Stage S2 runs; see §6 Port Model.

---

### Migration Notes

- **Legacy TCP probe:** The TCP raw-JSON discovery function is removed entirely on migration. There is no transitional mode; the protocol was always broken and produced no usable data.
- **Fabricated records:** Any `Worker-{ip}` placeholder records in installer data stores are invalid and must not be migrated forward. Users are informed that prior installer discovery results are unreliable.
- **Deprecated:** The TCP discovery function; the fabricated-fallback path; any installer stage that registers workers without a preceding selection ceremony.

---

## Cross-Domain Dependency Map

```
§1 Controller Selection
    ──writes ControllerPlacementParams──> §8 Config (Step 4.5)
    ──provides controller keypair root──> §3 Manifest Signing

§3 Manifest Signing
    ──provides signature_verified field──> §2 Worker Selection
    ──provides signature_verified field──> §9 Installer Discovery
    ──writes TOFU public_key records──> §5 Trust Model

§2 Worker Selection
    ──gates registration at Step 9b──> §4 Deploy Flow
    ──writes TrustRecord(approved/revoked)──> §5 Trust Model

§4 Deploy Flow
    ──positions ceremony at Pre-0──> §1
    ──triggers config write at Step 4.5──> §8
    ──opens ports at Step 6──> §6
    ──invokes readiness probe at Step 8──> §7
    ──runs discovery+signing+ceremony at Steps 9a–9c──> §3, §2

§5 Trust Model
    ──receives all TrustRecord writes from──> §2, §3, §9

§6 Port Model
    ──port policy stored in──> §8 Config (ports block)
    ──8095/udp open enables──> §7 Readiness probe
    ──8095/udp open enables──> §9 Installer discovery
    ──8090/tcp open enables──> worker registration calls in §2, §9

§7 Readiness Model
    ──ReadinessConfig stored in──> §8 Config (worker block)
    ──depends on 8095/udp from──> §6 Port Model
    ──precedes discovery Step 9a in──> §4 Deploy Flow

§8 Config Model
    ──written at Step 4.5, read at Step 5 and beyond──> §4 Deploy Flow
    ──provides port policy to──> §6
    ──provides readiness config to──> §7
    ──provides controller identity to──> §5

§9 Installer Discovery
    ──mirrors canonical protocol of──> §3, §2
    ──writes TrustRecords via same pipeline as──> §5
    ──requires 8095/udp from──> §6
```

---

*End of document. No code. No implementation details. Design only.*  
*Senior engineers implementing this design must treat each section as an authoritative specification and cross-reference the linked input documents — FINAL_ARCHITECTURAL_CORRECTION_MAP.md, GAP_ANALYSIS_AUDIT_REPORT.md, ROOT_CAUSE_ANALYSIS_REPORT.md, and doctrine/PHANTOM_DOCTRINE.md — for detailed evidence of each root cause addressed.*
