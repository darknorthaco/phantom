# Canonical installer: Tauri desktop app

As of Phase 2 (production readiness), **Phantom’s single supported installation path is the Tauri-based Phantom application** in `phantom_app/`.

## This directory (`installer/`)

The Python wizard, CLI orchestrator, and integration tests under `installer/` remain in the tree for:

- Reference implementations of worker discovery, model download, and config writers  
- Automated tests (`phantom_core/tests/test_wizard_backend.py`, etc.)  
- Emergency use when `PHANTOM_ALLOW_LEGACY_INSTALLER=1` is set  

They **must not** be presented to end users as the default install path. User-facing documentation lives in **`INSTALL.md`** (repository root).

## Entry points gated by default

| Script | Behavior without env override |
|--------|-------------------------------|
| `phantom_installer.py` | Exits with code 2 + message |
| `phantom_wizard.py` | Exits with code 2 + message |
| `phantom_installer_windows.py` | Exits with code 2 + message |
| `windows_gui_installer.py` | Exits with code 2 + message |
| `demo_installer.py` | Exits with code 2 + message |

Override: **`PHANTOM_ALLOW_LEGACY_INSTALLER=1`**

## Uninstaller scripts

`phantom_uninstaller.*` remain available for environments that still rely on legacy layouts; prefer **`uninstall_phantom`** from the Tauri app for the `~/.phantom` / `%USERPROFILE%\.phantom` layout.
