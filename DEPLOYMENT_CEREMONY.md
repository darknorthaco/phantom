# Deployment ceremony (Tauri)

The Phantom **Stone-Home** app guides installation through a **deployment ceremony** so the human explicitly chooses the controller host and worker pool before the Table of Contents (TOC) is unlocked.

## Phases (app)

1. **Welcome / consent** — Intro and explicit consent (governance).  
2. **Front porch deploy** — Progress UI for steps 0–9 (venv, deps, engine copy, GPU check, service unit, bootstrap config, controller start, firewall, state, local worker, **LAN scan**).  
   - **Offline path (Phase 3):** With a verified bundle, deps install from `wheelhouse/` (`--no-index`), engine copies from `bundle/engine/`, UDP LAN discovery is **skipped**, and the pre-scan returns a **synthetic `local-worker`** entry so the ceremony can proceed without WAN. Logs include **`PHANTOM OFFLINE MODE`**.  
3. **Deployment ceremony** — If workers were discovered: choose **exactly one** controller-capable host, select **worker pool**, optional controller LLM toggle. If **zero** workers: diagnostics + discovery log only.  
4. **Complete deployment** — `complete_deployment_with_selection` registers approved workers and finalizes step 11 (execution modes).  
5. **TOC** — Main application shell (Console, Workers, Routing, etc.).

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
| Pre-scan deploy | `run_deployment_pre_scan` → `PhantomDeployer::run_pre_scan_deployment` (steps 0–9 + discovery **without** auto-registration). Optional **`options`**: `{ offline, offlineBundlePath }`; auto-offline when WAN probe fails and a bundle exists. |
| Ceremony continue | `complete_deployment_with_selection` → `PhantomDeployer::complete_deployment_with_selection` |
| Legacy one-shot | `deploy_phantom` (all steps in sequence; kept for compatibility) |

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

- **`INSTALL.md`** — build, uninstall (`uninstall_phantom`), upgrade (`upgrade_phantom_deployment`)  
- **`docs/offline_install.md`** — bundle generation, verification, air-gap policy  
- **`deployment/worker_lifecycle.md`** — worker ↔ controller task callbacks  
