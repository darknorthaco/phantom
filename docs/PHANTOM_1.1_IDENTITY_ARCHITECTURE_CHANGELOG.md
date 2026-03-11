# PHANTOM 1.1 — IDENTITY + ARCHITECTURE CHANGELOG

**Release:** Phantom 1.1  
**Date:** 2026-03-11  
**Classification:** Identity + Architecture Complete  
**Audience:** Operators, architects, security assessors  

---

## 1. Overview

Phantom 1.1 is the first release to achieve **full doctrine compliance** and **identity consistency** across all surfaces. This release completes the Corrected Architecture Design (CORRECTED_ARCHITECTURE_DESIGN.md), implements all nine corrected domains (§1–§9), and establishes Phantom as a **doctrine-complete**, **identity-complete**, **operationally ready**, and **architecturally mature** distributed compute fabric.

**High-level characterization:**

| Attribute | Status |
|-----------|--------|
| Doctrine compliance | Complete (54/54 requirements) |
| Identity overhaul | Complete (logo, icons, branding) |
| TrustBoundary enforcement | Enforced at registration endpoint |
| Ceremony gates | Pre-0 (controller) + Step 9b (worker) |
| Discovery protocol | Unified UDP 8095 |
| Readiness model | Active probe (no fixed sleep) |
| Config fabric | Deterministic, atomic, ceremony-driven |
| Installer path | Aligned with Tauri path |

---

## 2. Identity Overhaul

All branding surfaces have been updated to use the official Phantom logo (stylized head silhouette with cyan/purple halo on black).

### 2.1 Asset Additions

| Location | Asset | Purpose |
|----------|-------|---------|
| `phantom_app/public/` | `phantom.png` | Primary logo for web UI, splash, deploy screens |
| `phantom_app/src/assets/` | `phantom_logo.png` | Importable asset for programmatic use |

### 2.2 UI Surfaces Updated

| Surface | Change |
|---------|--------|
| Splash / welcome / deploy screens | `phantom.svg` → `phantom.png` in WizardWelcome, ControllerSelectionScreen, FrontPorchDeploy, DeploymentCeremony |
| Favicon | `index.html` favicon: `phantom.svg` → `phantom.png` |
| TOC header | MetricsBar: new `toc-header-logo` class, 24px height logo at metrics bar lead |

### 2.3 Tauri Icon Regeneration

All Tauri bundle icons regenerated from `public/phantom.png` via `npx tauri icon`:

| Platform | Artifacts |
|----------|-----------|
| Windows | `icon.ico`, `32x32.png`, `128x128.png`, `128x128@2x.png` |
| macOS | `icon.icns` |
| Linux | PNG set (32×32, 64×64, 128×128, 128×128@2x) |
| Windows Store (Appx) | `StoreLogo.png`, `Square30x30Logo.png` … `Square310x310Logo.png` |
| iOS | Full `AppIcon-*` set |
| Android | `mipmap-*` launcher set |

**Tauri bundle references (tauri.conf.json):** Unchanged; continues to reference `icons/32x32.png`, `icons/128x128.png`, `icons/icon.ico`, `icons/icon.icns`. NSIS `installerIcon` and `headerImage` use regenerated icons.

### 2.4 Installer Branding Updates

| Asset | Location | Use |
|-------|----------|-----|
| `phantom.ico` | `installer/assets/` | Tk wizard window icon |
| `phantom_icon.ico` | `installer/assets/` | Qt (Windows) installer window icon |
| `sidebar_logo.png` | `installer/assets/` | 128×128 branding (from Tauri `icons/128x128.png`) |

**Code changes:**
- `installer/gui/wizard.py`: `iconbitmap(default=...)` set to `assets/phantom.ico` when present
- `installer/windows_gui_installer.py`: `setWindowIcon(QIcon(...))` uses `assets/phantom_icon.ico` via resolved path

---

## 3. Architecture Compliance (Sections §1–§9)

Each corrected domain is implemented and compliant with the Corrected Architecture Design.

### §1 Controller Selection Ceremony

| Item | Detail |
|------|--------|
| Doctrine requirement | User asserts controller placement; identity fingerprint visible before deploy; no installation without confirmed ControllerPlacementParams |
| Implementation | `ControllerSelectionScreen` between WizardWelcome and deploy; placement options (Local CPU, Local GPU, Custom IP:Port); IdentityManager fingerprint; `confirm_controller_placement` Tauri command writes `controller_placement.json` |
| Compliance status | **COMPLIANT** |

### §2 Worker Selection Ceremony

| Item | Detail |
|------|--------|
| Doctrine requirement | No worker registered without explicit user approval; unverified workers default unchecked |
| Implementation | Step 9a (discover) → 9b (ceremony) → 9c (register selected); `WorkerSelectionPanel` / Screen 4 Part 2; `applyPreScanResult` pre-selects only `signatureVerified` workers |
| Compliance status | **COMPLIANT** |

### §3 Manifest Signing Model

| Item | Detail |
|------|--------|
| Doctrine requirement | Every manifest cryptographically signed; verification before approval; TOFU key recording |
| Implementation | `SignedManifest` (public_key, signature, signed_at); `ManifestSigner` / `ManifestVerifier`; `signature_verified` propagated to ceremony |
| Compliance status | **COMPLIANT** |

### §4 Corrected Deploy Flow

| Item | Detail |
|------|--------|
| Doctrine requirement | Fully ordered, ceremony-gated sequence; Pre-0, Step 4.5, Step 6 (three ports), Step 8 (readiness probe), Steps 9a/9b/9c |
| Implementation | Pre-0 (controller ceremony) before steps; Step 4.5 (config bootstrap); Step 6 opens 8080/tcp, 8090/tcp, 8095/udp; Step 8 uses readiness probe; Step 9 decomposed into 9a/9b/9c |
| Compliance status | **COMPLIANT** |

### §5 Corrected Trust Model

| Item | Detail |
|------|--------|
| Doctrine requirement | TrustStore append-only; registration requires TrustRecord(Approved); no registration without user approval |
| Implementation | `TrustStore` (Python + Rust); `POST /workers/approve`; `register_worker` checks TrustStore and returns HTTP 403 if not approved; ceremony calls approve before register |
| Compliance status | **COMPLIANT** |

### §6 Corrected Port Model

| Item | Detail |
|------|--------|
| Doctrine requirement | Canonical ports 8080/tcp, 8090/tcp, 8095/udp; PortPolicy in config; all required ports opened at Step 6 |
| Implementation | PortPolicy in `phantom_config.json`; Step 6 opens all three; UI tooltips distinguish discovery (8095) vs worker API (8090) |
| Compliance status | **COMPLIANT** |

### §7 Corrected Readiness Model

| Item | Detail |
|------|--------|
| Doctrine requirement | Active readiness probe; no fixed sleep; config-driven probe params; spawn failure message without "GPU required" |
| Implementation | `run_readiness_probe()`; `probe_worker_readiness()` unicast to 127.0.0.1:8095; config: `probe_interval_ms`, `max_attempts`, `attempt_timeout_ms`; spawn log: "Failed to start local worker" |
| Compliance status | **COMPLIANT** |

### §8 Corrected Config Model

| Item | Detail |
|------|--------|
| Doctrine requirement | Config written at Step 4.5 before controller start; atomic write; ControllerPlacementParams + identity_fingerprint in config |
| Implementation | `bootstrap_config()` reads `controller_placement.json`; writes `phantom_config.json` atomically (tmp → rename); controller block from ceremony; timestamped backup |
| Compliance status | **COMPLIANT** |

### §9 Corrected Installer Discovery Model

| Item | Detail |
|------|--------|
| Doctrine requirement | Canonical UDP 8095 discovery; same protocol as Tauri; no fabricated records; Worker Selection Ceremony on installer path |
| Implementation | `WorkerDiscoveryAdapter` uses `InstallerDiscoveryClient` (UDP 8095, PHANTOM_DISCOVER_WORKERS, SignedManifest); replaces legacy TCP/ping `WorkerDiscovery` |
| Compliance status | **COMPLIANT** |

---

## 4. Trust Model Enhancements

### 4.1 Append-Only Trust Ledger

- **TrustStore** (`phantom_core/phantom_core/trust_store.py`, `phantom_app/src-tauri/src/backend/trust_store.rs`)
- Persisted as `trust_store.jsonl` under state directory
- Records never modified or deleted

### 4.2 TOFU Key Management

- First contact from a `worker_id` → `TrustRecord(first_seen)` then `TrustRecord(sig_valid)` if signature valid
- Key-change detection: different `public_key` for known `worker_id` → `TrustRecord(unverified, key_change_detected)`; re-approval required
- `approve_worker_with_key()` supports first-contact approval from ceremony

### 4.3 Approval-Before-Registration Enforcement

- `POST /workers/approve` records `TrustRecord(approved)` with `worker_id` and `public_key`
- `POST /workers/register`: if TrustStore present, `get_current_level(worker_id)` must be `approved` or `registered`
- Rejection: HTTP 403 with message `"Worker {id} must be approved before registration"`

### 4.4 Trust Workflow

```
unverified (discovery arrival)
    → sig_valid (signature verified; TOFU if new)
    → approved (user approves in ceremony)
    → registered (POST /workers/register succeeds)
    → revoked (user revokes; optional)
```

---

## 5. Discovery & Readiness Improvements

### 5.1 Unified UDP 8095 Discovery

| Path | Before | After |
|------|--------|-------|
| Tauri app | UDP 8095 (already correct) | Unchanged |
| Installer | TCP/ping sweep (WorkerDiscovery) | UDP 8095 (InstallerDiscoveryClient) |

- Single protocol: `PHANTOM_DISCOVER_WORKERS` over UDP to port 8095
- Unicast to 127.0.0.1 + broadcast per subnet
- Response schema: `SignedManifest` with verification
- 1500 ms timeout per subnet; deduplication by `worker_id`

### 5.2 Readiness Probe with Retry Logic

- Fixed 2s sleep after worker spawn **removed**
- `run_readiness_probe()`: unicast `PHANTOM_DISCOVER_WORKERS` → 127.0.0.1:8095
- Configurable: `probe_interval_ms`, `max_attempts`, `attempt_timeout_ms` (defaults: 500, 20, 1000)
- Timeout non-fatal; proceeds to Step 9a with warning
- Discovery listener bind retry (up to 3 attempts) in `discovery_listener.py`

### 5.3 Enhanced Diagnostics

- `DiscoveryLog`: `readiness_probe_attempts`, `readiness_probe_success`, `diagnostic_hints`
- Zero workers: hints for probe timeout, firewall (8095/udp), worker startup, retry
- Sanitized copy/paste-ready diagnostic string for support

### 5.4 Removal of Misleading GPU Error Messages

- Spawn failure log: ~~"Failed to start local worker (GPU required)"~~ → **"Failed to start local worker: {reason}"**
- Worker supports CPU-only; spawn failure is not treated as GPU requirement

---

## 6. Config Fabric Improvements

### 6.1 Deterministic Ceremony → Config → Runtime Pipeline

1. **Pre-0:** User confirms controller placement and identity → `controller_placement.json`
2. **Step 4.5:** `bootstrap_config()` reads `controller_placement.json`, writes `phantom_config.json`
3. **Step 5:** Controller reads `phantom_config.json` (no fallback; file guaranteed)
4. **Steps 6–9c:** Port policy, readiness config, security level from `phantom_config.json`

### 6.2 Atomic Config Writes

- Write to `phantom_config.json.tmp` → rename to `phantom_config.json`
- Before overwrite: backup to `phantom_config.json.bak.{timestamp}`

### 6.3 Identity Fingerprint Stored in Config

- `phantom_config.json` includes `controller.identity_fingerprint` from Pre-0 ceremony
- Source: IdentityManager Ed25519 public key (hex fingerprint)

### 6.4 ControllerPlacementParams Integration

- Schema: `host`, `port`, `device_label`, `identity_fingerprint`, `confirmed_at`
- Persisted at Pre-0 via `confirm_controller_placement` Tauri command
- Step 4.5 reads this file; deploy blocked if absent

---

## 7. Installer Path Corrections

### 7.1 UDP Discovery in Installer

- `WorkerDiscoveryAdapter` switched from `WorkerDiscovery` (TCP/ping) to `InstallerDiscoveryClient` (UDP 8095)
- Broadcast addresses from `WorkerDiscovery.get_local_network()` for subnet broadcast
- Output format preserved for GUI compatibility; `signature_verified`, `public_key_b64` propagated

### 7.2 Updated Icons and Branding

- `phantom.ico` for Tk wizard
- `phantom_icon.ico` for Qt installer
- `sidebar_logo.png` (128×128) from Tauri icon set
- Paths resolved relative to installer root

### 7.3 TrustStore Integration

- Installer-discovered workers flow through same approval/registration path as Tauri
- No installer-specific trust bypass
- Registration requires prior `TrustRecord(approved)` from ceremony or equivalent user action

---

## 8. Summary Table

| Category | Requirements | Compliant |
|----------|--------------|-----------|
| §1 Controller Selection Ceremony | 6 | 6 |
| §2 Worker Selection Ceremony | 6 | 6 |
| §3 Manifest Signing Model | 6 | 6 |
| §4 Corrected Deploy Flow | 6 | 6 |
| §5 Corrected Trust Model | 6 | 6 |
| §6 Corrected Port Model | 6 | 6 |
| §7 Corrected Readiness Model | 6 | 6 |
| §8 Corrected Config Model | 6 | 6 |
| §9 Installer Discovery Model | 6 | 6 |
| **Total** | **54** | **54** |

---

## 9. Final Statement

Phantom 1.1 is:

- **Architecturally complete** — All nine corrected domains (§1–§9) are implemented as specified in CORRECTED_ARCHITECTURE_DESIGN.md.

- **Doctrine-aligned** — Sovereign domains (§2), authentic trust (§3), transparent operation (§4), voluntary mesh participation (§5), reversibility (§8), and consistent behavior (§6) are enforced across the fabric.

- **Identity-consistent** — The official Phantom logo is applied to splash screens, deploy flows, TOC header, favicon, window icons, installer icons, and installer branding. No surface retains legacy branding.

- **Ready for operational deployment** — TrustBoundary enforcement, ceremony gates, unified discovery, readiness probe, and atomic config fabric provide a production-grade foundation for sovereign distributed compute.

---

*End of changelog. Evidence-based. No speculation.*
