# Phantom — Canonical Installation (Tauri)

**The supported way to install and operate Phantom is the Phantom desktop application** (Tauri + React), not the legacy Python or `package/` shell installers.

## Prerequisites

- **Node.js** 18+ and **npm**
- **Rust** toolchain (`rustup`, stable)
- **Python** 3.9+ on the target machine (used for the controller venv created under the user profile)
- Windows: WebView2 runtime (usually present on Windows 10/11)

## Build and run (development)

```bash
cd phantom_app
npm install
npm run tauri dev
```

## Production build

```bash
cd phantom_app
npm install
npm run tauri build
```

Installers and bundles are emitted under `phantom_app/src-tauri/target/release/bundle/` (platform-dependent).

## What the app installs

Under **`~/.phantom`** (Linux/macOS) or **`%USERPROFILE%\.phantom`** (Windows), the deployer:

| Concern | Handled by deployer |
|--------|---------------------|
| Dependency checks | venv creation, `pip install` for controller stack |
| Firewall | Linux: `ufw` / `iptables`; Windows: `netsh advfirewall` (8080, 8090, 8095, 8081 when socket integration is on) |
| Service registration | Linux: user `systemd` unit `phantom.service`; Windows: `sc create phantom` |
| Integrated runtime | `phantom_config.json` → `controller.socket_integrated`; launches `run_integrated_phantom.py` when enabled |
| `phantom_config.json` | Step 4.5 bootstrap after controller placement ceremony |

See **`DEPLOYMENT_CEREMONY.md`** for the full UI flow (controller selection → Acts A–F → TOC).

## TLS / WAN (Phase 4)

Phantom can serve the **controller HTTP API over HTTPS** and require workers to use **`https://`** when TLS is enabled. **LAN default remains plaintext HTTP** (`wan_mode: false`, `tls_enabled: false`) so Phases 1–3 behavior is unchanged.

| Policy | Meaning |
|--------|---------|
| **WAN mode** | `wan_mode: true` in `phantom_config.json` — **requires** `tls_enabled: true` and valid PEM paths (enforced in Python and in the Tauri **Save TLS settings** command). |
| **No silent downgrade** | Workers never fall back from HTTPS to HTTP when TLS is enabled; controller config does not mix schemes. |
| **No public CA** | Use **Generate certificate** or **Import certificate** under **Experimental — Identity, Trust & WAN**; files stay under your `.phantom` profile. |

**Worker side:** set `tls_enabled` and `tls_controller_cert_path` (PEM) in worker config so `httpx` pins the controller certificate. The deployer mirrors controller `tls_cert_path` into the local worker config when TLS is on.

**Docs:** **`docs/tls.md`** (behavior, ceremony), **`docs/phantom_config_reference.md`** (field reference).

### WAN deployment notes

- Complete normal deployment first so **`phantom_config.json`** exists (Step 4.5).
- Generate or import TLS material, then **Save to phantom_config.json** from the Experimental panel.
- Restart the **phantom** controller service so uvicorn loads the new certificate.
- For each remote worker, use the same controller host/port, `tls_enabled: true`, and a filesystem path (or deployed copy) of the **controller certificate PEM** as `tls_controller_cert_path`.

## Offline / air-gapped install (Phase 3)

1. On a **connected** machine, generate a bundle:  
   `python installer/offline_bundle.py generate --output ./dist/offline_bundle --engine-root ./phantom_core`  
   (See **`docs/offline_install.md`** for layout, verification, and `staging_mode` caveats.)
2. Copy the bundle to the target. In the app, call **`install_offline_bundle`** with the bundle path (or set **`PHANTOM_OFFLINE_BUNDLE`**, or place the bundle at **`~/.phantom/offline_bundle`** with a valid `manifest.json`).
3. Run the ceremony with an **explicit** offline bundle path on Act B:
   `ceremony_run_act_b` with `{ "offlineBundlePath": "<absolute-path>" }`.
   **Doctrine (I-OfflineExplicit):** offline mode is **never auto-selected**. WAN
   reachability does not change deploy behaviour — a LAN-only host runs the
   canonical ceremony unchanged. A missing WAN is *not* a signal to use a
   bundle; the operator must request it explicitly.
4. Tauri commands: **`verify_offline_bundle`**, **`load_offline_model_catalogue`**, **`install_offline_bundle`**.

### Offline troubleshooting

| Symptom | Check |
|--------|--------|
| `pip install (offline) failed` | Wheels in `wheelhouse/` must match `requirements-deploy.txt` and target OS/Python ABI |
| `Offline install requested but no bundle found` | Bundle path wrong or missing `manifest.json`; set `PHANTOM_OFFLINE_BUNDLE` or call `install_offline_bundle` |
| LAN-only host without WAN | Expected behavior: ceremony still runs online/LAN-first unless offline bundle is explicitly requested |

## Uninstall and upgrade (Tauri commands)

Invoked from the desktop app via Tauri **`invoke`** (wire into Settings / Deployments UI as needed):

| Command | Purpose |
|---------|---------|
| `uninstall_phantom` | Stops services, removes Windows Phantom firewall rules, deletes the entire `.phantom` directory |
| *(planned)* ceremony upgrade command | Upgrade will be exposed via ceremony-first flow; legacy one-shot upgrade is quarantined in compat builds only |

**Note:** Run **`uninstall_phantom`** only when you accept loss of local identity, audit logs, venv, and engine copy under `.phantom`.

## Legacy installers (deprecated)

Python installers under `installer/` and scripts under `package/` are **deprecated**. They exit unless:

- `PHANTOM_ALLOW_LEGACY_INSTALLER=1` (Python entry points), or  
- `PHANTOM_ALLOW_LEGACY_PACKAGE_INSTALL=1` (`package/install.sh`, `package/install.bat`).

Use this only for CI or exceptional maintenance.

## Further reading

- `docs/tls.md` — TLS/WAN controller API, worker pinning, Tauri commands  
- `docs/phantom_config_reference.md` — `phantom_config.json` fields (including Phase 4)  
- `docs/offline_install.md` — offline bundle, integrity, upgrade  
- `DEPLOYMENT_CEREMONY.md` — deployment ceremony and TOC gating  
- `INSTALLATION.md` — historical / supplemental material  
- `installer/CANONICAL_INSTALL_TAURI.md` — policy note for the `installer/` tree  
- `phantom_core/DEPLOYMENT_GUIDE.md` — cluster and worker operations  
