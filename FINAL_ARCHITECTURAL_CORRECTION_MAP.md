# Phantom Deploy Flow — Final Architectural Correction Map

**Date:** 2025-03-10  
**Basis:** GAP_ANALYSIS_AUDIT_REPORT.md, ROOT_CAUSE_ANALYSIS_REPORT.md, Phantom Doctrine, Intended UX, DARPA DevOps Audit, GPU Discovery Audit  
**Method:** Audit only. No code. No implementation details.

---

## Integrated Context

**Intended UX:** Controller choice → Worker choice → Deploy  
**Current UX:** WizardWelcome consent → FrontPorchDeploy (single button) → Steps 0–10 (no ceremonies)  
**Doctrine (relevant):** §2 Sovereign Domains, §3 Authentic Trust, §5 Voluntary Mesh, §8 Reversibility, banned: auto-discovery, auto-approve  
**Trust model:** "Trust relationships require manual approval" (.cursorrules:50)

---

## Master Correction Table

| Root Cause | Subsystem | Required Architectural Change | Deploy Flow Insertion | Doctrine Alignment | Trust Model Alignment | Risk if Unchanged | Severity |
|------------|-----------|------------------------------|----------------------|--------------------|-----------------------|-------------------|----------|
| **1. Controller selection missing** | UI, Deploy flow, Identity | Add pre-deploy ceremony: user chooses where controller runs (local CPU, local GPU, device). Display controller identity (Ed25519) after generation. Deploy flow must consume placement params; identity_manager must be invoked on first deploy and result surfaced to UI. Remove hardcoded 127.0.0.1:8080 from start_controller. | Insert **before Step 0** or between WizardWelcome and FrontPorchDeploy. Precedes all install steps. | §2 Sovereign Domains: user asserts controller placement. §3 Authentic Trust: identity visible. | User sovereignty over controller role; no implicit placement. | Multi-device and custom-placement scenarios fail; user cannot assert controller placement. | **High** |
| **2. Worker selection missing** | UI, Deploy flow | Add post-discovery, pre-registration ceremony: discover manifests, present list to user, require explicit approval of which workers to register. Remove auto-registration loop in scan_lan() and scan_and_register_workers(). Add UI to display discovered-but-unregistered workers and gate registration on user selection. | Insert **between Step 8 and Step 9**, or split Step 9 into: 9a Discover, 9b User selects, 9c Register selected only. Step 9a precedes; Step 9b is new; Step 9c replaces current register-all loop. | §5 Voluntary Mesh: joining explicit. §8 Reversibility: no irreversible trust without approval. Banned: auto-approve. | "Trust relationships require manual approval"; each worker trust is explicit. | Any reachable worker trusted; impersonation and unwanted mesh participation. | **High** |
| **3. Manifest signing missing** | Worker, Controller, Discovery, Identity | Worker must sign manifest with per-worker identity before sending. Controller must verify signature before registering. Add signature field to manifest schema. Worker needs signing capability (per-worker Ed25519 or delegated key). Controller/Tauri must verify before register_worker(). Remove assumption that LAN discovery is implicitly trusted. | Verification occurs **during Step 9** (or 9c): before each register_worker() call, verify manifest signature. Signing occurs in worker (discovery_listener) before send. | §3 Authentic Trust: identity cryptographic, all cross-entity messages signed. | Cryptographic attestation; no trust by default. | Impersonation; any host can claim any worker_id. | **High** |
| **4. Worker readiness timing too short** | Deploy flow | Replace fixed 2s sleep with readiness probe: poll worker discovery listener or health endpoint until responsive or timeout. Add configurable timeout and retry/backoff. Remove assumption that worker is always ready in 2s. | **Step 8**: after spawn, probe for readiness (e.g., unicast discovery to 127.0.0.1:8095 or GET worker /health) before proceeding. Step 9 follows only when worker is ready or timeout. | §4 Transparent Operation: no silent failures. | Indirect: reliable discovery supports accurate trust decisions. | Discovery misses local worker on slow systems; deploy completes with 0 workers. | **Medium** |
| **5. Ports 8090/8095 not opened** | Deploy flow, Config | Extend open_ports to open 8090 (worker HTTP) and 8095 (discovery UDP) in addition to 8080. Add 8081 if socket is part of deploy. Parameterize or enumerate ports; remove single-port assumption. | **Step 6** (open_ports): add rules for 8090/tcp, 8095/udp (and optionally 8081/tcp). Precedes Step 8 (worker) and Step 9 (discovery). | §4 Transparent Operation: all communication paths documented and reachable. | Firewall aligns with actual service ports; no silent discovery failure. | Discovery and worker traffic blocked on some systems; DARPA audit port conflicts. | **Medium** |
| **6. Misleading GPU log ("GPU required")** | Deploy flow | Replace "GPU required" log with generic spawn-failure message that does not assert GPU necessity. Worker has CPU fallback; log must not contradict. Align Linux and Windows log messages. | **Step 8**: log text only; no step reorder. | §4 Transparent Operation: accurate reporting. | Cosmetic; indirect clarity for user. | User believes GPU required; unnecessary debugging; contradicts GPU audit. | **Cosmetic** |
| **7. phantom_config ordering bug** | Config, Deploy flow | Write phantom_config.json before it is read. Move config bootstrap (or load_execution_modes) to run before start_controller. Correct comment ("written by step 9" → accurate step reference or remove). | **Reorder**: bootstrap phantom_config (or relevant portion) to run **before Step 5**. E.g., new Step 4.5 or move load_execution_modes earlier; alternatively split load_execution_modes so phantom_config is written before step 5. Step 5 reads after write. | §4 Transparent Operation: correct documentation. | Config reflects user choices when controller starts. | Fragile; if config becomes required for correctness, read-before-write breaks. | **Low** |
| **8. Installer discovery TCP probing** | Installer, Discovery | Replace TCP raw-JSON probe with protocol that matches worker: either UDP broadcast (align with Tauri discovery) or HTTP GET. Remove _query_worker_info raw TCP send; use HTTP or UDP. Align installer discovery with discovery.rs and discovery_listener.py. | N/A (installer path, not Tauri steps 0–10). Installer S2 Worker Discovery stage. | §4 Transparent Operation: protocol consistency. | Installer and Tauri discover same way; no protocol drift. | Installer discovery fails for HTTP workers; DARPA audit. | **High** (installer path) |
| **9. UI references wrong ports** | UI | Update WorkersPanel tooltip: discovery uses UDP 8095, not 8090. Clarify port roles (8090 = worker HTTP, 8095 = discovery). Remove conflation. | N/A (UI only; no step change). | §4 Transparent Operation: accurate documentation. | User understands which ports matter. | Misleading; user may open wrong ports. | **Cosmetic** |
| **10. Auto-registration violates trust model** | Deploy flow | Same architectural change as #2. Add worker selection ceremony; remove auto-registration. | Same as #2. | §5 Voluntary Mesh, §8 Reversibility, banned: auto-approve. | "Trust relationships require manual approval." | Same as #2. | **High** |
| **11. Legacy drift (GPU log, installer, config ordering)** | Deploy flow, Installer, Config | Consolidate corrections: (a) GPU log — see #6; (b) Installer — see #8; (c) Config ordering — see #7. Architectural principle: align all code paths with current protocol and config lifecycle; remove stale assumptions. | Distributed per sub-item. | §7 Evolution Without Drift: aligned behavior. | Legacy code reflects current trust and protocol. | Inconsistent behavior; maintenance burden. | **Medium** (consolidated) |
| **12. Deploy flow assumes LAN is trusted** | Deploy flow, Discovery, Controller | Remove implicit LAN trust. Enforce manifest signing (#3) and worker selection (#2). Discovery can still be broadcast-only; trust is established by verification and approval, not by network segment. | Addressed by #2 and #3. | §3 Authentic Trust: no peer trusted by default. | LAN is discovery space, not trust space. | Any LAN host can inject worker; trust boundary violated. | **High** |
| **13. Deploy flow assumes worker ready in 2 seconds** | Deploy flow | Same as #4. Replace fixed sleep with readiness probe. | Same as #4. | §4 Transparent Operation. | Reliable discovery. | Same as #4. | **Medium** |
| **14. Deploy flow assumes controller config exists early** | Config, Deploy flow | Same as #7. Write config before read. | Same as #7. | §4 Transparent Operation. | Config available when needed. | Same as #7. | **Low** |

---

## Subsystem Responsibility Summary

| Subsystem | Root Causes Addressed | Primary Changes |
|-----------|-----------------------|-----------------|
| **UI** | 1, 2, 9 | Controller selection screen; worker selection screen; port tooltip accuracy |
| **Deploy flow** | 1, 2, 4, 5, 6, 7, 10, 11, 12, 13, 14 | Ceremony insertion points; config ordering; port opening; readiness probe; log text |
| **Controller** | 3 | Manifest signature verification before register |
| **Worker** | 3 | Manifest signing in discovery_listener |
| **Discovery** | 3, 8 | Signed manifest schema; installer protocol alignment |
| **Identity** | 1, 3 | Controller identity in deploy; per-worker identity for signing |
| **Config** | 7, 14 | phantom_config write-before-read; bootstrap ordering |

---

## Deploy Flow Insertion Map (Corrected Sequence)

| Step | Current | Corrected Intent |
|------|---------|------------------|
| Pre-0 | — | **Controller selection ceremony** (UI + identity) |
| 0–2 | venv, deps, core | Unchanged |
| 3 | GPU verify | Unchanged |
| 4 | Service install | Unchanged |
| 4.5 (new) | — | **Config bootstrap** (phantom_config, llm_config) — before controller start |
| 5 | Start controller | Consume placement from ceremony; read phantom_config (now exists) |
| 6 | Open ports | **Add 8090/tcp, 8095/udp** (and optionally 8081/tcp) |
| 7 | State marker | Unchanged |
| 8 | Start worker | Spawn; **readiness probe** instead of 2s sleep; **fix GPU log** |
| 9a | — | **Discover** (broadcast; collect manifests) |
| 9b | — | **Worker selection ceremony** (UI; user approves/rejects) |
| 9c | — | **Verify manifest signatures**; register selected only |
| 10 | Load modes | May be redundant with 4.5; or retain for late defaults |

---

## Doctrine Alignment Index

| Doctrine Rule | Root Causes Addressed |
|---------------|------------------------|
| §2 Sovereign Domains | 1 (controller selection) |
| §3 Authentic Trust | 1, 3, 12 (identity, signing, no implicit trust) |
| §4 Transparent Operation | 4, 5, 6, 7, 9 (accuracy, ports, logs, config) |
| §5 Voluntary Mesh | 2, 10 (worker selection) |
| §7 Evolution Without Drift | 8, 11 (installer, legacy) |
| §8 Reversibility | 2, 10 (no auto-approve) |
| Banned: auto-discovery, auto-approve | 2, 10, 12 |

---

## Trust Model Alignment Index

| Trust Principle | Correction |
|-----------------|------------|
| "Trust relationships require manual approval" | Worker selection ceremony (#2, #10) |
| No peer trusted by default | Manifest signing + verification (#3, #12) |
| User sovereignty over controller role | Controller selection ceremony (#1) |
| User sovereignty over worker membership | Worker selection ceremony (#2) |
| Cryptographic attestation | Manifest signing (#3) |

---

## Risk Summary by Severity

| Severity | Root Causes | Operational | Security | UX |
|----------|-------------|-------------|----------|-----|
| **Blocking** | — | — | — | — |
| **High** | 1, 2, 3, 8, 10, 12 | Multi-device fails; installer discovery fails | Impersonation; unwanted trust | No controller/worker choice |
| **Medium** | 4, 5, 11, 13 | Discovery misses worker; ports blocked | — | Inconsistent experience |
| **Low** | 7, 14 | Config fragility | — | — |
| **Cosmetic** | 6, 9 | — | — | Misleading logs/tooltips |

---

*End of report. No code changes proposed. No implementation details.*
