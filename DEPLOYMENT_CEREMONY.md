# Deployment ceremony (Tauri, canonical)

The Phantom Stone-Home app deploys through a single canonical pipeline:

`Act A → Act B → Act C → Act D → Act E → Act F`

The operator remains sovereign (explicit Deploy button, explicit placement), and
LAN-first behavior is invariant.

## Phases (app)

1. **Welcome / consent** — Intro and explicit consent.
2. **Controller selection** — Placement and identity confirmation (Act A input).
3. **Front porch deploy** — Runs preflight and then Acts A→C.
4. **Deployment ceremony** — Controller/worker selection context + Acts D→F.
5. **TOC** — Available only after ceremony reaches `CS_OPERATIONAL`.

## WAN ceremony path (Phase 4)

After the controller is deployed and **TOC** is available:

1. Open **Experimental — Identity, Trust & WAN**.
2. **Generate certificate** or **Import certificate** (local PEM only).
3. Enable **WAN mode** (TLS is required and forced on) *or* enable **Enable TLS** alone for HTTPS on LAN.
4. Confirm **Controller cert path** / **key path** match the generated or imported files.
5. **Save to phantom_config.json** (requires Step 4.5 to have created the file).
6. **Restart** the Phantom controller service so the API binds with TLS.

Workers that are not co-located must receive config with `tls_enabled: true` and `tls_controller_cert_path` pointing at the controller’s PEM. See **`docs/tls.md`** and **`docs/phantom_config_reference.md`**.

## Backend mapping

| UI step | Rust / backend |
|--------|----------------|
| Ceremony deploy (canonical) | `ceremony_commit_placement` (Act A) → `ceremony_run_act_b` (Act B, materialize) → `ceremony_run_act_c` (Act C, LAN discovery) → `ceremony_run_act_d/e/f` (configure/attest/register). Optional `offlineBundlePath` on Acts B/C is explicit-only; no WAN probe, no auto-fallback. |
| Deploy mode introspection | `deploy_mode` returns compile-time mode + features so UI always exposes real mode. |
| Legacy commands | Removed from canonical binary surface in Phase 13 hardening. |

## Configuration artifacts

| File | Role |
|------|------|
| `controller_placement.json` | Written by `confirm_controller_placement` (host, port, identity fingerprint) — required before bootstrap |
| `phantom_config.json` | Written at deploy step 4.5 (`bootstrap_config`) — includes `controller.socket_integrated` |
| `deployed.marker` | Present when deploy pipeline marked complete |
| `config/`, `state/` | LLM / worker registry / controller persistence as deployed |
| `state/offline_install.json` | Written after successful offline pre-scan |
| `state/model_catalogue_offline.json` | Cached catalogue from `install_offline_bundle` |
| `state/pending_offline_bundle_path.txt` | Absolute path to bundle for next launch |

## Gating rules

- TOC is blocked until the ceremony completes with **at least one worker** in the pool and a **selected controller** (unless product policy changes).  
- Discovery failure (`worker_count == 0`) surfaces **diagnostics** only.

## Implementation checklist

See **`DEPLOYMENT_CEREMONY_IMPLEMENTATION_CHECKLIST.md`** for the authoritative tick-list (Phases 1–8).

## Related

- **`INSTALL.md`** — build, uninstall (`uninstall_phantom`)  
- **`docs/offline_install.md`** — bundle generation, verification, air-gap policy  
- **`deployment/worker_lifecycle.md`** — worker ↔ controller task callbacks  
