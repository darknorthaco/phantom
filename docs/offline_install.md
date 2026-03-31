# Phantom offline / air-gapped installation (Phase 3)

The canonical path remains the **Tauri Stone-Home app**. Offline support layers a **reproducible bundle** (wheels + engine + sovereign model catalogue snapshot) so deploy can complete without PyPI or WAN discovery.

## What the bundle contains

| Path | Purpose |
|------|---------|
| `wheelhouse/` | Pip wheels (and optional sdists) for `requirements-deploy.txt` |
| `engine/` | Full `phantom_core` tree (must include `run.py`) |
| `models/model_catalogue.json` | Sovereign-filtered catalogue + `models_sha256` metadata |
| `config_templates/` | JSON/YAML-style templates + TLS placeholder readme |
| `binaries/` | Optional archival payloads (see `binaries/README.txt`; no separate `phantom_controller` binary in this repo) |
| `requirements-deploy.txt` | Same contract as Tauri `install_python_deps` (see `installer/requirements-deploy.txt`) |
| `resolver_manifest.json` | Build metadata (platform, Python version, wheel count) |
| `manifest.json` | **SHA-256 for every file** (integrity gate) |

`staging_mode.txt` appears only when generating with `--skip-pip-download` (CI/layout only — not for production air-gap).

## Generate a bundle (online build machine)

From the repository root, with Python 3.9+ and network access:

```bash
python installer/offline_bundle.py generate --output ./dist/phantom_offline_bundle --engine-root ./phantom_core
```

Optional:

- `PHANTOM_OFFLINE_BUNDLE_VERSION=1.2.3` — recorded in `manifest.json`
- `--skip-pip-download` — directory layout only (no wheels)

Verify:

```bash
python installer/offline_bundle.py verify --bundle ./dist/phantom_offline_bundle
```

## Install on an air-gapped machine

1. Copy the verified bundle directory to removable media or shared storage.
2. Open the Phantom app. Invoke **`install_offline_bundle`** with the absolute path to the bundle (or set `PHANTOM_OFFLINE_BUNDLE` to that path, or place the bundle at `~/.phantom/offline_bundle` with a valid `manifest.json`).
3. Run deployment (**`run_deployment_pre_scan`**). The backend will:
   - Use **`--no-index`** pip against `wheelhouse/`
   - Copy **`engine/`** from the bundle
   - Skip **LAN UDP discovery** (synthetic `local-worker` for ceremony continuity)
   - Log **`PHANTOM OFFLINE MODE ENABLED`**
4. Complete the ceremony and **`complete_deployment_with_selection`** as usual.

**Trust note:** The offline synthetic `local-worker` row may carry an empty `public_key_b64` until real worker keys are wired; `approve_worker` may log warnings. Prefer registering workers with valid keys when policy requires explicit trust records (TrustRecord approved).

## After install: discovery telemetry and Workers panel

| Path | Meaning |
|------|---------|
| Deploy with a bundle | UDP LAN discovery is **not** run; the UI receives one **synthetic** `local-worker` row (`discovery_mode: offline_synthetic` in the discovery log). The ceremony **pre-selects** that row so you can continue without a verified signature. |
| `state/offline_install.json` | Written after a successful offline pre-scan. Marks the profile as offline/air-gap. **`scan_and_register_workers` (Workers panel “Scan LAN”)** skips UDP discovery and returns `lanScanSkipped` with an explanatory reason — this is intentional, not a silent failure. |
| `workers_panel_lan_udp` | Field in `offline_install.json` (currently `false`): documents that LAN UDP from the Workers panel is disabled while the marker exists. Delete `offline_install.json` only if you deliberately want LAN scans from this machine again. |

Online deploys use **`discovery_mode: lan_udp`** and only pre-select workers whose manifests have **verified** signatures.

## Platform behavior (Windows / Linux / macOS)

| Area | Linux | Windows | macOS |
|------|-------|---------|-------|
| **Local worker (deploy step)** | `engine/linux-worker` via venv Python | `engine/windows-worker` | Same **linux-worker** tree as Linux (Unix venv); GPU naming may differ; readiness UDP probe runs like Linux |
| **GPU pre-check (deploy)** | NVIDIA probe | Windows GPU probe | Logged skip — worker still probes at runtime |
| **Service install (deploy)** | User systemd unit | `sc`/NSSM path | Skipped — use app or your own **launchctl** plist |
| **Firewall (deploy)** | ufw / iptables attempt | `netsh` rules | **No auto rules** — open controller / worker TCP and discovery UDP in **System Settings** (or **pf**) using ports from `phantom_config.json` |
| **Uninstall / stop services** | systemctl user unit | `sc stop` + rule cleanup | No bundled service — stop processes manually |

Other Unix-like OS builds skip the bundled local worker and log a **scan-log** line; use LAN discovery for workers.

Explicit flags (frontend / invoke payload):

```json
{ "options": { "offline": true, "offlineBundlePath": "D:\\\\Phantom\\\\offline_bundle" } }
```

Environment overrides:

| Variable | Effect |
|----------|--------|
| `PHANTOM_OFFLINE_BUNDLE` | Default bundle path if not passed in UI |
| `PHANTOM_FORCE_OFFLINE=1` | Treat network as down (testing) |
| `PHANTOM_ASSUME_ONLINE=1` | Skip WAN probe (CI / strict firewalls) |

## Integrity (SHA-256)

- **Python:** `offline_bundle_lib.verify_manifest(bundle_root)`
- **Rust / app:** `verify_offline_bundle(path)` command
- **CLI:** `python installer/offline_bundle.py verify --bundle <dir>`

If any file drifts from `manifest.json`, verification fails with path-level errors.

## Offline upgrade

Use **`upgrade_phantom_deployment`** as in Phase 2. To refresh from a **new** bundle, generate a new offline bundle on a connected machine, verify it, replace the bundle directory (or update `pending_offline_bundle_path.txt` via `install_offline_bundle`), then run upgrade or re-deploy per your runbook.

## Python helper (pip)

`installer/offline_install_helper.py` runs the same argv as the Rust deployer (for diagnostics):

```bash
python installer/offline_install_helper.py --bundle /path/to/offline_bundle --pip /path/to/venv/bin/pip install-deps
```

## Tests (no network)

```bash
python installer/tests/test_offline_bundle.py
```
