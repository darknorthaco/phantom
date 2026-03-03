# Phantom Windows Installer — Full Architectural Specification

> **Document Class:** Analysis-Only Architectural Specification
> **Version:** 1.0.0
> **Date:** 2026-03-02
> **Status:** DRAFT — For Human Implementation Review
> **Governance:** No privileged operations. No system modification. No registry commands. No reboot commands. All privileged steps are conceptual placeholders only.

---

## Table of Contents

1. [Installer State Machine](#1-installer-state-machine)
2. [Dependency Map](#2-dependency-map)
3. [GUI Flow Specification](#3-gui-flow-specification)
4. [Installer Folder Structure](#4-installer-folder-structure)
5. [PyInstaller / Nuitka Spec File](#5-pyinstaller--nuitka-spec-file)
6. [Build Pipeline for Thin EXE](#6-build-pipeline-for-thin-exe)
7. [Runtime Dependency-Fetcher Architecture](#7-runtime-dependency-fetcher-architecture)
8. [Model-Fetcher Architecture](#8-model-fetcher-architecture)
9. [Worker Bootstrapper Architecture](#9-worker-bootstrapper-architecture)
10. [WSL Orchestrator Architecture](#10-wsl-orchestrator-architecture)
11. [Reboot-Resume Architecture](#11-reboot-resume-architecture)
12. [Logging and Auditability Plan](#12-logging-and-auditability-plan)
13. [Documentation Outline for README_INSTALLER.md](#13-documentation-outline)

---

## 1. Installer State Machine

### 1.1 Phase Definitions

The installer operates as a deterministic finite state machine with **8 primary phases** and **3 conditional sub-phases**. Every phase transition is serialised to a state file (`%LOCALAPPDATA%\Phantom\installer_state.json`) so the installer can resume after interruption or reboot.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INSTALLER STATE MACHINE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [P0] INIT ──► [P1] SYSTEM_SCAN ──► [P2] DEPENDENCY_FETCH         │
│                                           │                         │
│                                      ┌────┴────┐                   │
│                                      │ REBOOT? │                   │
│                                      └────┬────┘                   │
│                                      (conditional)                  │
│                                           │                         │
│                               [P2a] REBOOT_PENDING                 │
│                               [P2b] REBOOT_RESUME                  │
│                                           │                         │
│  [P3] VENV_SETUP ◄───────────────────────┘                        │
│       │                                                             │
│  [P4] COMPONENT_INSTALL                                            │
│       │                                                             │
│  [P5] MODEL_FETCH                                                  │
│       │                                                             │
│  [P6] WORKER_BOOTSTRAP                                             │
│       │                                                             │
│  [P7] VALIDATION ──► [P8] COMPLETE                                 │
│                                                                     │
│  [E*] ERROR ──► (any phase can transition here)                    │
│  [C*] CANCELLED ──► (user abort from any phase)                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Phase Detail Table

| Phase | ID | Name | Entry Condition | Exit Condition | Rollback Strategy |
|-------|----|------|-----------------|----------------|-------------------|
| P0 | `INIT` | Initialisation | EXE launched | State file created, install_dir confirmed | Delete state file |
| P1 | `SYSTEM_SCAN` | System Scan | State file exists, phase=INIT complete | All checks pass or user overrides warnings | No side-effects to roll back |
| P2 | `DEPENDENCY_FETCH` | Dependency Fetch | System scan passed | All dependencies staged in `staging/` | Delete `staging/` folder |
| P2a | `REBOOT_PENDING` | Reboot Pending | A dependency (e.g. WSL kernel) requires reboot | System reboots | State file records `resume_phase=P2b` |
| P2b | `REBOOT_RESUME` | Resume After Reboot | OS boot + RunOnce trigger | Dependency that prompted reboot is verified | If fail, re-enter P2 |
| P3 | `VENV_SETUP` | Virtual Environment | Dependencies staged | `venvs/phantom/Scripts/python.exe` exists | Delete `venvs/` folder |
| P4 | `COMPONENT_INSTALL` | Component Install | venv ready | All selected components copied, configs written | Delete component dirs, remove configs |
| P5 | `MODEL_FETCH` | Model Fetch | Components installed | GGUF model file present in `models/`, checksum verified | Delete `models/` folder |
| P6 | `WORKER_BOOTSTRAP` | Worker Bootstrap | Model ready | Worker registry written, health checks pass | Delete `config/worker_registry.json` |
| P7 | `VALIDATION` | Validation | Bootstrap complete | All verification checks pass | No side-effects |
| P8 | `COMPLETE` | Complete | Validation passed | State file records `status=COMPLETE` | Full uninstall via manifest |
| E* | `ERROR` | Error | Any unrecoverable failure | User chooses retry/abort/rollback | Phase-specific rollback |
| C* | `CANCELLED` | Cancelled | User cancels at any point | Partial rollback of current phase | Phase-specific rollback |

### 1.3 State File Schema

```json
{
  "$schema": "phantom-installer-state-v1",
  "version": "1.0.0",
  "install_id": "uuid-v4",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "current_phase": "VENV_SETUP",
  "completed_phases": ["INIT", "SYSTEM_SCAN", "DEPENDENCY_FETCH"],
  "install_dir": "C:\\Users\\<user>\\phantom",
  "install_type": "all",
  "selected_components": ["phantom_core", "llm_taskmaster", "windows_workers", "security_framework", "socket_infrastructure", "redblue_ui"],
  "system_scan_result": { "os_ok": true, "python_ok": true, "disk_ok": true, "ports_ok": true, "gpu_detected": true },
  "reboot_required": false,
  "resume_after_reboot": false,
  "resume_phase": null,
  "model_selection": { "id": "phi35_q4_k_m", "filename": "Phi-3.5-mini-instruct-Q4_K_M.gguf" },
  "worker_configs": [],
  "error_log": [],
  "rollback_manifest": []
}
```

### 1.4 Invariants

1. **I-SERIAL:** Phases execute strictly in order. No phase may begin until the prior phase's exit condition is met.
2. **I-ATOMIC:** Each phase either completes fully or rolls back fully. No partial state between phases.
3. **I-PERSIST:** State is flushed to disk after every phase transition. Crash at any point results in resumable state.
4. **I-NOPRIVESC:** The installer NEVER self-elevates. If a phase requires elevation, the GUI displays instructions for the user.
5. **I-IDEMPOTENT:** Every phase is safe to re-run. Re-entry into a completed phase is a no-op.
6. **I-ROLLBACK:** Every phase records its rollback manifest before making changes. `E*` → rollback consumes this manifest.
7. **I-AUDIT:** Every phase transition is written to `installation_audit.log` with ISO-8601 timestamp.

### 1.5 Transition Guards

```
INIT → SYSTEM_SCAN:
  guard: state_file.exists() AND install_dir.is_writable()

SYSTEM_SCAN → DEPENDENCY_FETCH:
  guard: system_scan.os_ok AND system_scan.python_ok AND system_scan.disk_ok

DEPENDENCY_FETCH → REBOOT_PENDING:
  guard: dependency_requires_reboot == true

DEPENDENCY_FETCH → VENV_SETUP:
  guard: all_dependencies_staged AND NOT dependency_requires_reboot

REBOOT_PENDING → REBOOT_RESUME:
  guard: system_rebooted AND installer_re-launched_by_RunOnce

REBOOT_RESUME → VENV_SETUP:
  guard: dependency_that_triggered_reboot.verify() == true

VENV_SETUP → COMPONENT_INSTALL:
  guard: venv_python.exists() AND venv_pip.exists()

COMPONENT_INSTALL → MODEL_FETCH:
  guard: all_selected_components_installed AND configs_written

MODEL_FETCH → WORKER_BOOTSTRAP:
  guard: model_file.exists() AND model_checksum_verified

WORKER_BOOTSTRAP → VALIDATION:
  guard: worker_registry_written

VALIDATION → COMPLETE:
  guard: all_verification_checks_pass

ANY → ERROR:
  guard: unrecoverable_exception_caught

ANY → CANCELLED:
  guard: user_pressed_cancel AND confirmed_dialog
```

---

## 2. Dependency Map

### 2.1 Full Dependency Graph

```
phantom-installer.exe (thin frozen EXE)
│
├── Python 3.10+ (embedded or system)
│   ├── tkinter (bundled with CPython on Windows)
│   └── venv module (bundled with CPython)
│
├── [PHASE P2] Staging Dependencies
│   │
│   ├── Python venv creation (no external dep)
│   │
│   ├── pip (bootstrapped inside venv)
│   │   │
│   │   ├── Core Runtime Dependencies
│   │   │   ├── fastapi >= 0.104.0
│   │   │   ├── uvicorn[standard] >= 0.24.0
│   │   │   ├── pydantic >= 2.5.0
│   │   │   ├── httpx >= 0.25.0
│   │   │   ├── requests >= 2.31.0
│   │   │   ├── websockets >= 11.0.0
│   │   │   ├── psutil >= 5.9.0
│   │   │   ├── numpy >= 1.24.0
│   │   │   └── pyyaml >= 6.0
│   │   │
│   │   ├── GPU Support
│   │   │   ├── pynvml >= 11.5.0
│   │   │   ├── py3nvml >= 0.2.7
│   │   │   └── gpustat >= 1.1.0
│   │   │
│   │   ├── Security
│   │   │   ├── cryptography >= 41.0.0
│   │   │   └── pyjwt >= 2.8.0
│   │   │
│   │   ├── AI/ML (LLM Task Master)
│   │   │   ├── torch >= 2.0.0
│   │   │   ├── transformers >= 4.30.0
│   │   │   └── accelerate >= 0.20.0
│   │   │
│   │   └── LLM Inference Runtime
│   │       ├── llama-cpp-python (unicorn/llama.cpp bindings)
│   │       └── litellm (LiteLLM unified API)
│   │
│   ├── [CONDITIONAL] WSL2 Kernel
│   │   └── (conceptual — requires privileged install; see §10)
│   │
│   └── [CONDITIONAL] NVIDIA CUDA Toolkit
│       └── (conceptual — user-directed download; see §7)
│
├── [PHASE P5] Model Dependencies
│   └── Phi-3.5 Mini GGUF variants
│       ├── Phi-3.5-mini-instruct-Q4_K_M.gguf (2.4 GB, recommended)
│       ├── Phi-3.5-mini-instruct-Q3_K_M.gguf (2.0 GB, lighter)
│       └── Phi-3.5-mini-instruct-Q5_K_M.gguf (2.8 GB, higher quality)
│
└── [BUILD-TIME] Freeze Dependencies
    ├── PyInstaller >= 6.0  OR  Nuitka >= 2.0
    ├── tkinter (must be in Python used for build)
    └── All installer/*.py modules (bundled into EXE)
```

### 2.2 Dependency Installation Order

```
Stage 1 (Pre-venv):     Python itself (embedded or detected)
Stage 2 (With venv):    pip bootstrap → pip install -r requirements.txt
Stage 3 (Post-pip):     llama-cpp-python, litellm (separate step due to compilation)
Stage 4 (Model):        GGUF download from HuggingFace
Stage 5 (Optional):     torch + transformers (only if LLM Task Master enabled)
Stage 6 (Conditional):  WSL kernel, CUDA drivers (user-directed, not automated)
```

### 2.3 Dependency Size Budget

| Dependency Group | Estimated Size | Required |
|------------------|---------------|----------|
| Python venv (bare) | ~30 MB | Yes |
| Core pip deps (fastapi, uvicorn, etc.) | ~120 MB | Yes |
| GPU support (pynvml, gpustat) | ~15 MB | Recommended |
| Security (cryptography, pyjwt) | ~25 MB | Yes |
| llama-cpp-python | ~50 MB | Yes (for local inference) |
| litellm | ~30 MB | Yes (for API fallback) |
| torch + transformers | ~2.5 GB | Optional |
| Phi-3.5 GGUF model | ~2.0–2.8 GB | Yes (one variant) |
| **Total (minimal)** | **~2.3 GB** | |
| **Total (full)** | **~5.5 GB** | |

---

## 3. GUI Flow Specification

### 3.1 Screen Inventory

The GUI is built with Tkinter in a Windows XP/95-retro wizard style (existing `WinXPTheme` in `gui/wizard.py`). The wizard has a 720×500 fixed window with a 180px blue sidebar and a content area.

| Screen # | Class | Title | Purpose |
|----------|-------|-------|---------|
| S0 | `WelcomeScreen` | Welcome | Product intro, install directory picker, detailed-logs toggle |
| S1 | `SystemScanScreen` | System Check | Runs `SystemChecker` via `system_scan_adapter`, shows pass/fail/warning rows |
| S2 | `WorkerDiscoveryScreen` | Discover Workers | Runs `WorkerDiscoveryAdapter`, shows scan progress |
| S3 | `WorkerSelectionScreen` | Select Workers | Tabular worker list, Task Master designation |
| S4 | `ModelSelectionScreen` | Select Model | GGUF model catalogue from `MODELS`, VRAM recommendations |
| S5 | `ModelDownloadScreen` | Download Model | Progress bar, SHA-256 verification |
| S6 | `InstallationScreen` | Install | 7-stage `InstallerDriver` execution with per-stage progress |
| S7 | `CompletionScreen` | Finish | Summary, launch toggle, links to documentation |

### 3.2 Screen Transition Diagram

```
S0 Welcome
│  [Next →]
│  guard: install_dir is writable
▼
S1 System Scan
│  [auto-start scan on enter]
│  [Next →]
│  guard: no critical failures (or user override)
▼
S2 Worker Discovery
│  [auto-start scan on enter]
│  [Next →]
│  guard: scan complete (0 workers allowed)
▼
S3 Worker Selection
│  [Next →]
│  guard: at least 0 workers selected (optional), task_master assigned if >0
▼
S4 Model Selection
│  [Next →]
│  guard: a model is selected
▼
S5 Model Download
│  [auto-start download on enter]
│  [Next →]
│  guard: download complete, checksum verified
▼
S6 Installation
│  [auto-start stages on enter]
│  [Next →]  (disabled until all 7 stages complete)
│  guard: all stages succeeded
▼
S7 Completion
│  [Finish]
│  action: optionally launch Phantom, destroy wizard
```

### 3.3 Enhanced Screens for Multi-Phase Installer

The multi-phase installer adds the following screens to support dependency fetching, WSL, and reboot-resume:

| Screen # | Class | Title | Purpose |
|----------|-------|-------|---------|
| S1.5 | `DependencyFetchScreen` | Fetch Dependencies | Shows staged dependency downloads with progress |
| S1.6 | `RebootPromptScreen` | Reboot Required | Explains why reboot is needed, offers "Reboot Now" or "Later" |
| S1.7 | `ResumeScreen` | Resuming Installation | Post-reboot landing page, verifies pre-reboot work |

#### Full enhanced flow:

```
S0 Welcome
 → S1 System Scan
 → S1.5 Dependency Fetch
 → [if reboot needed] S1.6 Reboot Prompt → [REBOOT] → S1.7 Resume
 → S2 Worker Discovery
 → S3 Worker Selection
 → S4 Model Selection
 → S5 Model Download
 → S6 Installation
 → S7 Completion
```

### 3.4 Sidebar Step Rendering

The sidebar (blue `SIDEBAR_BG = #1D4B96`) displays step labels with three visual states:

| State | Colour | Font |
|-------|--------|------|
| Current | `#FFFF88` (yellow) | Bold |
| Completed | `#A0C8A0` (green) | Normal |
| Pending | `#FFFFFF` (white) | Normal |

### 3.5 Error / Cancel Dialogs

- **Cancel:** `messagebox.askyesno("Cancel Setup", "Are you sure?")` → rolls back current phase only.
- **Phase Error:** Modal dialog with error details + three buttons: **Retry** | **Skip** (if non-critical) | **Abort**.
- **Fatal Error:** Modal dialog with full traceback path + **View Log** button + **Abort** button.

---

## 4. Installer Folder Structure

### 4.1 Source Tree (Build-Time)

```
installer/
├── __init__.py
├── phantom_installer.py              # CLI entry point
├── phantom_installer_windows.py      # Windows-specific helpers
├── phantom_wizard.py                 # GUI entry point (Tkinter)
├── windows_gui_installer.py          # Legacy PyQt6 GUI (deprecated)
│
├── gui/                              # Tkinter wizard framework
│   ├── __init__.py
│   ├── wizard.py                     # PhantomWizard main window
│   └── screens/                      # Individual wizard screens
│       ├── __init__.py
│       ├── base.py                   # WizardScreen base class
│       ├── welcome.py
│       ├── system_scan.py
│       ├── worker_discovery.py
│       ├── worker_selection.py
│       ├── model_selection.py
│       ├── model_download.py
│       ├── installation.py
│       ├── completion.py
│       ├── dependency_fetch.py       # NEW — multi-phase dep fetcher screen
│       ├── reboot_prompt.py          # NEW — reboot advisory screen
│       └── resume.py                 # NEW — post-reboot resume screen
│
├── backend_interface/                # Backend adapters (no direct system calls)
│   ├── __init__.py
│   ├── config_writer.py
│   ├── installer_driver.py
│   ├── model_downloader.py
│   ├── system_scan_adapter.py
│   ├── worker_discovery_adapter.py
│   ├── dependency_fetcher.py         # NEW — runtime dep staging logic
│   ├── reboot_manager.py            # NEW — reboot-resume state management
│   └── wsl_orchestrator.py          # NEW — WSL detection/status (read-only)
│
├── modules/                          # Core installer modules
│   ├── __init__.py
│   ├── component_manager.py
│   ├── config_generator.py
│   ├── manifest_manager.py
│   ├── port_verifier.py
│   ├── process_cleanup.py
│   ├── socket_manager.py
│   ├── system_check.py
│   ├── ui_integration.py
│   ├── uninstall_manager.py
│   ├── venv_setup.py
│   └── worker_discovery.py
│
├── integration/                      # API surface for GUI
│   ├── __init__.py
│   └── phantom_installer_api.py
│
├── config/                           # Default configuration templates
│   ├── phantom_config.yaml
│   ├── ui_config.yaml
│   └── worker_config.yaml
│
├── scripts/                          # Post-install scripts
│   ├── health_check.py
│   ├── post_install.ps1
│   └── post_install.sh
│
├── ui/                               # CLI wizard interface
│   ├── __init__.py
│   ├── cli_wizard.py
│   ├── progress_display.py
│   └── prompts.py
│
├── uninstaller/                      # Uninstall support
│   └── .gitkeep
│
├── build/                            # NEW — build tooling
│   ├── phantom_installer.spec        # PyInstaller spec
│   ├── phantom_installer_nuitka.py   # Nuitka build script
│   ├── build_exe.py                  # Unified build orchestrator
│   ├── freeze_manifest.json          # Files to bundle into EXE
│   └── README_BUILD.md
│
├── assets/                           # NEW — EXE resources
│   ├── phantom_icon.ico
│   ├── phantom_banner.png
│   └── LICENSE_EMBEDDED.txt
│
├── README.md
├── EXAMPLES.md
└── UNINSTALLER.md
```

### 4.2 Runtime Tree (Post-Install at `%USERPROFILE%\phantom`)

```
%USERPROFILE%\phantom\
├── installer_state.json              # State machine persistence
├── installation_audit.log            # Full audit trail
├── .phantom_install_manifest.json    # Manifest for uninstaller
│
├── phantom_core/                     # Core application
│   ├── phantom_core/
│   ├── phantom_protocol/
│   ├── llm_taskmaster/
│   ├── linux-worker/
│   ├── windows-worker/
│   ├── security_framework/
│   ├── socket_infrastructure/
│   ├── run_integrated_phantom.py
│   ├── run.py
│   └── requirements.txt
│
├── ui/                               # RedBlue Matrix UI
│   └── redblue_matrix/
│
├── venvs/
│   └── phantom/
│       ├── Scripts/
│       │   ├── python.exe
│       │   ├── pip.exe
│       │   └── activate.bat
│       ├── Lib/
│       └── pyvenv.cfg
│
├── models/
│   ├── Phi-3.5-mini-instruct-Q4_K_M.gguf
│   └── models_manifest.json          # Downloaded model metadata
│
├── config/
│   ├── phantom_config.yaml
│   ├── worker_config.yaml
│   ├── ui_config.yaml
│   ├── llm_config.json
│   └── worker_registry.json
│
├── logs/
│   ├── phantom.log
│   ├── installer.log
│   └── worker.log
│
├── data/
├── cache/
├── temp/
│
├── staging/                          # Transient — cleared after P2
│   └── (downloaded dependencies before install)
│
├── environment.ps1                   # Activation script (PowerShell)
├── environment.bat                   # Activation script (CMD)
└── docs/
    └── (copied documentation)
```

---

## 5. PyInstaller / Nuitka Spec File

### 5.1 PyInstaller Spec (`installer/build/phantom_installer.spec`)

```python
# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Phantom Installer — NON-PRIVILEGED BUILD
# Build command: pyinstaller installer/build/phantom_installer.spec
# Output: dist/PhantomInstaller.exe

import sys
import os
from pathlib import Path

block_cipher = None

# Resolve paths relative to the spec file location
spec_dir = Path(SPECPATH)
installer_dir = spec_dir.parent  # installer/
project_root = installer_dir.parent  # phantom/

# Collect all installer Python modules
installer_packages = [
    str(installer_dir / 'gui'),
    str(installer_dir / 'gui' / 'screens'),
    str(installer_dir / 'backend_interface'),
    str(installer_dir / 'modules'),
    str(installer_dir / 'integration'),
    str(installer_dir / 'ui'),
]

# Data files to bundle (configs, assets, templates)
datas = [
    (str(installer_dir / 'config' / 'phantom_config.yaml'), 'config'),
    (str(installer_dir / 'config' / 'worker_config.yaml'), 'config'),
    (str(installer_dir / 'config' / 'ui_config.yaml'), 'config'),
    (str(installer_dir / 'assets' / 'phantom_icon.ico'), 'assets'),
    (str(project_root / 'VERSION'), '.'),
    (str(project_root / 'LICENSE'), '.'),
]

# Hidden imports that PyInstaller may miss
hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'json',
    'hashlib',
    'uuid',
    'dataclasses',
    'pathlib',
    'urllib.request',
    'venv',
    'subprocess',
    'platform',
    'shutil',
    'socket',
    'logging',
    # Installer modules
    'gui',
    'gui.wizard',
    'gui.screens',
    'gui.screens.base',
    'gui.screens.welcome',
    'gui.screens.system_scan',
    'gui.screens.worker_discovery',
    'gui.screens.worker_selection',
    'gui.screens.model_selection',
    'gui.screens.model_download',
    'gui.screens.installation',
    'gui.screens.completion',
    'gui.screens.dependency_fetch',
    'gui.screens.reboot_prompt',
    'gui.screens.resume',
    'backend_interface',
    'backend_interface.installer_driver',
    'backend_interface.model_downloader',
    'backend_interface.system_scan_adapter',
    'backend_interface.worker_discovery_adapter',
    'backend_interface.config_writer',
    'backend_interface.dependency_fetcher',
    'backend_interface.reboot_manager',
    'backend_interface.wsl_orchestrator',
    'modules',
    'modules.component_manager',
    'modules.config_generator',
    'modules.manifest_manager',
    'modules.port_verifier',
    'modules.process_cleanup',
    'modules.socket_manager',
    'modules.system_check',
    'modules.ui_integration',
    'modules.venv_setup',
    'modules.worker_discovery',
    'integration',
    'integration.phantom_installer_api',
    'ui',
    'ui.cli_wizard',
    'ui.progress_display',
    'ui.prompts',
]

a = Analysis(
    [str(installer_dir / 'phantom_wizard.py')],
    pathex=[str(installer_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pandas', 'IPython',
        'notebook', 'pytest', 'sphinx',
        'torch', 'transformers', 'accelerate',
        'PyQt5', 'PyQt6', 'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PhantomInstaller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Windowed mode (no console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(installer_dir / 'assets' / 'phantom_icon.ico'),
    version_info={
        'CompanyName': 'Dark North',
        'FileDescription': 'Phantom Distributed Compute Fabric - Installer',
        'FileVersion': '1.0.0.0',
        'InternalName': 'PhantomInstaller',
        'LegalCopyright': '(c) Dark North. See LICENSE.',
        'OriginalFilename': 'PhantomInstaller.exe',
        'ProductName': 'Phantom Installer',
        'ProductVersion': '1.0.0.0',
    },
)
```

### 5.2 Nuitka Build Configuration (`installer/build/phantom_installer_nuitka.py`)

```python
#!/usr/bin/env python3
"""
Nuitka build configuration for Phantom Installer.
NON-PRIVILEGED — produces a standalone .exe without requiring admin.

Usage:
    python installer/build/phantom_installer_nuitka.py
"""

import subprocess
import sys
from pathlib import Path

INSTALLER_DIR = Path(__file__).parent.parent
PROJECT_ROOT = INSTALLER_DIR.parent

NUITKA_ARGS = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--onefile",
    "--enable-plugin=tk-inter",
    f"--output-filename=PhantomInstaller.exe",
    f"--output-dir={PROJECT_ROOT / 'dist'}",
    "--windows-console-mode=disable",
    f"--windows-icon-from-ico={INSTALLER_DIR / 'assets' / 'phantom_icon.ico'}",
    f"--company-name=Dark North",
    f"--product-name=Phantom Installer",
    f"--file-version=1.0.0.0",
    f"--product-version=1.0.0.0",
    f"--file-description=Phantom Distributed Compute Fabric - Installer",
    # Include data files
    f"--include-data-dir={INSTALLER_DIR / 'config'}=config",
    f"--include-data-files={PROJECT_ROOT / 'VERSION'}=VERSION",
    f"--include-data-files={PROJECT_ROOT / 'LICENSE'}=LICENSE",
    # Include all installer packages
    f"--include-package=gui",
    f"--include-package=gui.screens",
    f"--include-package=backend_interface",
    f"--include-package=modules",
    f"--include-package=integration",
    f"--include-package=ui",
    # Exclude heavy/unnecessary packages
    "--nofollow-import-to=torch",
    "--nofollow-import-to=transformers",
    "--nofollow-import-to=PyQt5",
    "--nofollow-import-to=PyQt6",
    "--nofollow-import-to=matplotlib",
    "--nofollow-import-to=scipy",
    "--nofollow-import-to=pandas",
    "--nofollow-import-to=pytest",
    # Entry point
    str(INSTALLER_DIR / "phantom_wizard.py"),
]

if __name__ == "__main__":
    print(f"Building Phantom Installer with Nuitka...")
    print(f"Entry point: {INSTALLER_DIR / 'phantom_wizard.py'}")
    print(f"Output: {PROJECT_ROOT / 'dist' / 'PhantomInstaller.exe'}")
    result = subprocess.run(NUITKA_ARGS, cwd=str(INSTALLER_DIR))
    sys.exit(result.returncode)
```

---

## 6. Build Pipeline for Thin EXE

### 6.1 Pipeline Overview

The "thin EXE" strategy bundles **only the installer logic** (~2–5 MB) into a frozen executable. All heavy dependencies (venv, pip packages, models) are fetched at runtime. This avoids distributing a multi-gigabyte installer.

```
┌──────────────────────────────────────────────────────────────┐
│                    BUILD PIPELINE                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [B1] Validate Python Environment                           │
│       • Python 3.10+ with tkinter                           │
│       • PyInstaller or Nuitka installed                      │
│                                                              │
│  [B2] Lint & Test Installer Code                            │
│       • flake8 installer/                                    │
│       • pytest installer/tests/ (if present)                │
│                                                              │
│  [B3] Generate Version Metadata                             │
│       • Read VERSION file (1.0.0)                           │
│       • Generate build_metadata.json with timestamp + hash  │
│                                                              │
│  [B4] Freeze EXE                                            │
│       • PyInstaller: pyinstaller installer/build/phantom_installer.spec  │
│       • Nuitka:      python installer/build/phantom_installer_nuitka.py  │
│                                                              │
│  [B5] Verify EXE                                            │
│       • Check file exists in dist/                           │
│       • Check file size is within expected range (2–10 MB)  │
│       • Compute SHA-256 of output EXE                       │
│       • Smoke test: run with --help or --version flag       │
│                                                              │
│  [B6] Package Artefact                                      │
│       • Create dist/PhantomInstaller-1.0.0-win-x64.zip     │
│       • Contents: PhantomInstaller.exe + README_INSTALLER.md│
│       • Generate dist/checksums.sha256                       │
│                                                              │
│  [B7] Archive Build Log                                     │
│       • Copy build stdout/stderr to dist/build.log          │
│       • Record build environment (Python version, OS, etc.) │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Build Script (`installer/build/build_exe.py`)

```python
#!/usr/bin/env python3
"""
Unified build orchestrator for Phantom Installer EXE.
NON-PRIVILEGED — runs entirely in user space.

Usage:
    python installer/build/build_exe.py [--backend pyinstaller|nuitka]
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

INSTALLER_DIR = Path(__file__).parent.parent
PROJECT_ROOT = INSTALLER_DIR.parent
DIST_DIR = PROJECT_ROOT / "dist"
VERSION_FILE = PROJECT_ROOT / "VERSION"


def read_version() -> str:
    return VERSION_FILE.read_text().strip()


def step_validate():
    """B1: Validate build environment."""
    assert sys.version_info >= (3, 10), f"Python 3.10+ required, got {sys.version}"
    # Verify tkinter is available
    import tkinter  # noqa: F401
    print("[B1] Python environment validated.")


def step_lint():
    """B2: Lint installer source."""
    result = subprocess.run(
        [sys.executable, "-m", "flake8", str(INSTALLER_DIR),
         "--max-line-length=120", "--exclude=__pycache__"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[B2] Lint warnings:\n{result.stdout}")
    else:
        print("[B2] Lint passed.")


def step_metadata(version: str) -> dict:
    """B3: Generate build metadata."""
    meta = {
        "version": version,
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "builder": "build_exe.py",
    }
    meta_path = DIST_DIR / "build_metadata.json"
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"[B3] Build metadata written to {meta_path}")
    return meta


def step_freeze(backend: str):
    """B4: Freeze EXE."""
    if backend == "pyinstaller":
        spec = INSTALLER_DIR / "build" / "phantom_installer.spec"
        cmd = [sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm"]
    elif backend == "nuitka":
        cmd = [sys.executable, str(INSTALLER_DIR / "build" / "phantom_installer_nuitka.py")]
    else:
        raise ValueError(f"Unknown backend: {backend}")

    print(f"[B4] Freezing with {backend}...")
    result = subprocess.run(cmd, cwd=str(INSTALLER_DIR))
    assert result.returncode == 0, f"Freeze failed with exit code {result.returncode}"
    print(f"[B4] Freeze complete.")


def step_verify(version: str) -> str:
    """B5: Verify output EXE."""
    exe = DIST_DIR / "PhantomInstaller.exe"
    assert exe.exists(), f"EXE not found: {exe}"
    size_mb = exe.stat().st_size / (1024 * 1024)
    assert 1.0 < size_mb < 50.0, f"EXE size {size_mb:.1f} MB outside expected range"
    sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    print(f"[B5] EXE verified: {size_mb:.1f} MB, SHA-256: {sha[:16]}...")
    return sha


def step_package(version: str, sha: str):
    """B6: Package artefact."""
    import zipfile
    zip_name = f"PhantomInstaller-{version}-win-x64.zip"
    zip_path = DIST_DIR / zip_name
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(DIST_DIR / "PhantomInstaller.exe", "PhantomInstaller.exe")
        readme = PROJECT_ROOT / "docs" / "README_INSTALLER.md"
        if readme.exists():
            zf.write(readme, "README_INSTALLER.md")
    checksums = DIST_DIR / "checksums.sha256"
    checksums.write_text(f"{sha}  PhantomInstaller.exe\n")
    print(f"[B6] Package: {zip_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["pyinstaller", "nuitka"],
                        default="pyinstaller")
    args = parser.parse_args()

    version = read_version()
    print(f"Building Phantom Installer v{version} with {args.backend}\n")

    step_validate()
    step_lint()
    step_metadata(version)
    step_freeze(args.backend)
    sha = step_verify(version)
    step_package(version, sha)

    print(f"\n[DONE] Build complete. Artefact in {DIST_DIR}/")


if __name__ == "__main__":
    main()
```

### 6.3 CI/CD Integration Notes

- The build pipeline is designed to run in a **non-privileged** CI runner (GitHub Actions `windows-latest` with default user).
- No admin, no registry writes, no reboot triggers.
- Output artefact is a single `.zip` containing the thin EXE + README.
- The EXE itself does NOT require admin to **run** — it installs to `%USERPROFILE%\phantom` by default.

---

## 7. Runtime Dependency-Fetcher Architecture

### 7.1 Concept

The dependency fetcher runs at **Phase P2** of the state machine. It operates as a staging pipeline that downloads and caches all pip-installable dependencies into a `staging/` directory before creating the venv. This allows offline re-runs and bandwidth-efficient retries.

### 7.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│              RUNTIME DEPENDENCY FETCHER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Input] requirements.txt (from phantom_core/)                 │
│           + installer_requirements.txt (thin-EXE-time deps)    │
│                                                                 │
│  ┌──────────────────────┐                                      │
│  │  DependencyFetcher   │                                      │
│  │  (backend_interface) │                                      │
│  ├──────────────────────┤                                      │
│  │                      │                                      │
│  │  1. parse_requirements()                                    │
│  │     → List[DepSpec]                                         │
│  │                                                              │
│  │  2. resolve_platform_constraints()                          │
│  │     → Filter by sys.platform, arch                          │
│  │                                                              │
│  │  3. check_cache(staging_dir)                                │
│  │     → Skip already-downloaded wheels                        │
│  │                                                              │
│  │  4. download_wheels(dep_list, staging_dir)                  │
│  │     → pip download --dest staging/ -r requirements.txt      │
│  │     → Progress callback per-file                             │
│  │                                                              │
│  │  5. verify_wheels(staging_dir)                              │
│  │     → Check .whl integrity (size > 0, valid zip)           │
│  │                                                              │
│  │  6. detect_privileged_deps()                                │
│  │     → Returns list of deps requiring elevation              │
│  │     → E.g., WSL kernel, CUDA drivers                       │
│  │     → These are NOT fetched — only flagged                  │
│  │                                                              │
│  │  7. stage_complete()                                        │
│  │     → Returns True if all non-privileged deps are staged   │
│  │                                                              │
│  └──────────────────────┘                                      │
│                                                                 │
│  [Output]                                                      │
│    staging/                                                    │
│    ├── fastapi-0.115.0-py3-none-any.whl                       │
│    ├── uvicorn-0.30.0-py3-none-any.whl                        │
│    ├── ...                                                      │
│    └── staging_manifest.json                                   │
│                                                                 │
│  [Privileged Dependencies — FLAGGED ONLY]                      │
│    → WSL2 kernel update: displayed as user instruction         │
│    → CUDA toolkit: displayed as download link                  │
│    → These are NEVER automatically installed                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Staging Manifest Schema

```json
{
  "staged_at": "ISO-8601",
  "requirements_hash": "sha256-of-requirements.txt",
  "platform": "win32",
  "architecture": "AMD64",
  "python_version": "3.10.12",
  "wheels": [
    {
      "name": "fastapi",
      "version": "0.115.0",
      "filename": "fastapi-0.115.0-py3-none-any.whl",
      "size_bytes": 95234,
      "sha256": "abc123..."
    }
  ],
  "privileged_deps_required": [
    {
      "name": "WSL2 Kernel Update",
      "reason": "Required for Linux worker containers",
      "user_action": "Download from https://aka.ms/wsl2kernel and install manually",
      "required": false
    }
  ]
}
```

### 7.4 Offline Mode

If `staging/` is pre-populated (e.g., from a previous run or manual transfer), the fetcher skips downloading and proceeds to verification only. This enables air-gapped installations.

### 7.5 VenvSetup Integration

After staging is complete, P3 (`VENV_SETUP`) calls:

```
pip install --no-index --find-links=staging/ -r requirements.txt
```

This installs from the local cache without network access.

---

## 8. Model-Fetcher Architecture

### 8.1 Concept

The model fetcher operates at **Phase P5** of the state machine. It leverages the existing `ModelDownloader` class in `backend_interface/model_downloader.py` which downloads GGUF files from HuggingFace with progress tracking and SHA-256 verification.

### 8.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   MODEL FETCHER                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Input] User model selection from ModelSelectionScreen        │
│          Model catalogue: backend_interface/model_downloader.MODELS │
│                                                                 │
│  ┌────────────────────────────┐                                │
│  │  ModelDownloader           │                                │
│  │  (existing implementation) │                                │
│  ├────────────────────────────┤                                │
│  │                            │                                │
│  │  1. check_existing(models_dir)                              │
│  │     → If GGUF exists AND checksum matches → skip           │
│  │                                                              │
│  │  2. preflight_check()                                       │
│  │     → Verify disk space >= model.file_size_gb + 1 GB       │
│  │     → Verify network connectivity to huggingface.co        │
│  │                                                              │
│  │  3. download(model, status_cb, progress_cb)                 │
│  │     → HTTP GET with chunked transfer (64 KB chunks)        │
│  │     → Writes to .part tmp file                              │
│  │     → progress_cb(bytes_downloaded, bytes_total)            │
│  │                                                              │
│  │  4. verify_checksum(dest, expected_sha256)                  │
│  │     → SHA-256 full-file verification                        │
│  │     → If empty checksum in catalogue → skip (warn)         │
│  │                                                              │
│  │  5. finalise()                                              │
│  │     → Rename .part → .gguf (atomic on same filesystem)     │
│  │     → Write models_manifest.json                            │
│  │                                                              │
│  └────────────────────────────┘                                │
│                                                                 │
│  [Output]                                                      │
│    models/                                                     │
│    ├── Phi-3.5-mini-instruct-Q4_K_M.gguf                      │
│    └── models_manifest.json                                    │
│                                                                 │
│  [Error Handling]                                              │
│    → Network timeout → retry up to 3 times with backoff       │
│    → Checksum mismatch → delete & re-download once            │
│    → Disk full → abort with clear message                      │
│    → Partial download → resume from .part file length          │
│                                                                 │
│  [Resume Support]                                              │
│    → If .part file exists, use HTTP Range header to resume     │
│    → If complete .gguf exists with valid checksum → no-op     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 Model Catalogue (Current)

| ID | Name | File Size | Min VRAM | Rec VRAM | Recommended |
|----|------|-----------|----------|----------|-------------|
| `phi35_q4_k_m` | Phi-3.5 Mini Q4_K_M | 2.4 GB | 6 GB | 8 GB | **Yes** |
| `phi35_q3_k_m` | Phi-3.5 Mini Q3_K_M | 2.0 GB | 4 GB | 6 GB | No |
| `phi35_q5_k_m` | Phi-3.5 Mini Q5_K_M | 2.8 GB | 8 GB | 10 GB | No |

### 8.4 Integration with ConfigWriter

After download, `PhantomInstallerAPI.write_llm_config()` writes `config/llm_config.json`:

```json
{
  "model_path": "C:\\Users\\<user>\\phantom\\models\\Phi-3.5-mini-instruct-Q4_K_M.gguf",
  "model_name": "Phi-3.5 Mini Q4_K_M",
  "model_id": "phi35_q4_k_m",
  "vram_min_gb": 6,
  "vram_rec_gb": 8,
  "backend": "llama_cpp",
  "context_length": 4096,
  "max_tokens": 2048
}
```

---

## 9. Worker Bootstrapper Architecture

### 9.1 Concept

The worker bootstrapper operates at **Phase P6** of the state machine. It configures discovered workers for participation in the Phantom compute fabric. It writes the worker registry and performs health-check validation.

### 9.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                 WORKER BOOTSTRAPPER                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Inputs]                                                      │
│    • WizardState.selected_workers (from WorkerSelectionScreen) │
│    • WizardState.task_master (designated Task Master node)     │
│    • Models dir path (from Phase P5)                           │
│                                                                 │
│  ┌──────────────────────────────────────┐                      │
│  │  WorkerBootstrapper                   │                      │
│  │  (backend_interface — conceptual)     │                      │
│  ├──────────────────────────────────────┤                      │
│  │                                      │                      │
│  │  Stage 1: Validate Worker Selection  │                      │
│  │    → Verify ≥ 0 workers selected     │                      │
│  │    → Verify Task Master has minimum  │                      │
│  │      6 GB VRAM (warn if < 6 GB)     │                      │
│  │    → Verify no duplicate IPs         │                      │
│  │                                      │                      │
│  │  Stage 2: Generate Worker Configs    │                      │
│  │    → For each worker:                │                      │
│  │      • worker_id: worker-{n}         │                      │
│  │      • controller_host: localhost     │                      │
│  │      • controller_port: 8080         │                      │
│  │      • worker_port: 8090             │                      │
│  │      • gpu_index: {detected or 0}    │                      │
│  │      • capabilities: [compute, gpu]  │                      │
│  │                                      │                      │
│  │  Stage 3: Write Worker Registry      │                      │
│  │    → config/worker_registry.json     │                      │
│  │    → Delegates to ConfigWriter       │                      │
│  │       .write_worker_registry()       │                      │
│  │                                      │                      │
│  │  Stage 4: Health Check Sweep         │                      │
│  │    → For each worker IP:             │                      │
│  │      • TCP connect to worker_port    │                      │
│  │      • Record latency               │                      │
│  │      • Mark reachable/unreachable    │                      │
│  │    → Log results to audit log        │                      │
│  │                                      │                      │
│  │  Stage 5: Generate Topology Map      │                      │
│  │    → Write config/topology.json      │                      │
│  │    → Controller ←→ Workers mapping   │                      │
│  │    → Task Master designation         │                      │
│  │                                      │                      │
│  └──────────────────────────────────────┘                      │
│                                                                 │
│  [Outputs]                                                     │
│    config/worker_registry.json                                 │
│    config/topology.json                                        │
│    installation_audit.log (health check results)               │
│                                                                 │
│  [Error Handling]                                              │
│    → 0 workers: Skip bootstrap, write empty registry           │
│    → Unreachable worker: Warn, include in registry as offline  │
│    → Task Master unreachable: Warn, proceed (user may start    │
│      it later)                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 Worker Registry Schema

```json
{
  "task_master": {
    "ip": "192.168.1.100",
    "port": 8090,
    "hostname": "gpu-workstation",
    "gpu_name": "NVIDIA RTX 4090",
    "vram_total_mb": 24576,
    "health": "Healthy"
  },
  "workers": [
    {
      "ip": "192.168.1.100",
      "port": 8090,
      "hostname": "gpu-workstation",
      "gpu_name": "NVIDIA RTX 4090",
      "vram_total_mb": 24576,
      "health": "Healthy"
    },
    {
      "ip": "192.168.1.101",
      "port": 8090,
      "hostname": "compute-node-2",
      "gpu_name": "NVIDIA RTX 3080",
      "vram_total_mb": 10240,
      "health": "Healthy"
    }
  ]
}
```

---

## 10. WSL Orchestrator Architecture

> **GOVERNANCE NOTE:** This section is **conceptual only**. No WSL installation commands, no DISM commands, no kernel download commands are included. All privileged steps are represented as **placeholders for human implementation**.

### 10.1 Concept

The WSL Orchestrator detects WSL status and, if needed, guides the user through manual WSL setup. It **never** executes privileged operations itself.

### 10.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│              WSL ORCHESTRATOR (READ-ONLY)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────┐                          │
│  │  WSLOrchestrator                  │                          │
│  │  (backend_interface — read-only)  │                          │
│  ├──────────────────────────────────┤                          │
│  │                                  │                          │
│  │  detect_wsl_status() → WSLStatus │                          │
│  │    Read-only checks:              │                          │
│  │    • Check: wsl.exe exists on PATH│                          │
│  │    • Check: wsl --status (parse)  │                          │
│  │    • Check: WSL kernel version    │                          │
│  │    • Check: default distro set    │                          │
│  │                                  │                          │
│  │  Returns one of:                 │                          │
│  │    NOT_AVAILABLE                  │                          │
│  │    FEATURE_DISABLED               │                          │
│  │    KERNEL_MISSING                 │                          │
│  │    NO_DISTRO                      │                          │
│  │    READY                          │                          │
│  │                                  │                          │
│  │  get_user_instructions(status)    │                          │
│  │    Returns human-readable text    │                          │
│  │    for the user to follow:        │                          │
│  │                                  │                          │
│  │    NOT_AVAILABLE:                 │                          │
│  │      "WSL is not available.       │                          │
│  │       Open PowerShell as Admin    │                          │
│  │       and run: wsl --install"     │                          │
│  │                                  │                          │
│  │    FEATURE_DISABLED:              │                          │
│  │      "Windows features required.  │                          │
│  │       Open Settings > Apps >      │                          │
│  │       Optional Features..."       │                          │
│  │                                  │                          │
│  │    KERNEL_MISSING:                │                          │
│  │      "WSL kernel update needed.   │                          │
│  │       Download from:              │                          │
│  │       https://aka.ms/wsl2kernel"  │                          │
│  │                                  │                          │
│  │    NO_DISTRO:                     │                          │
│  │      "No Linux distro installed.  │                          │
│  │       Open Microsoft Store and    │                          │
│  │       install Ubuntu 22.04 LTS"   │                          │
│  │                                  │                          │
│  │    READY:                         │                          │
│  │      "WSL is ready."             │                          │
│  │                                  │                          │
│  │  is_reboot_required(status)       │                          │
│  │    Returns True for:              │                          │
│  │      FEATURE_DISABLED             │                          │
│  │      KERNEL_MISSING               │                          │
│  │    (these typically need reboot   │                          │
│  │     after manual action)          │                          │
│  │                                  │                          │
│  └──────────────────────────────────┘                          │
│                                                                 │
│  [CRITICAL CONSTRAINTS]                                        │
│    • This module NEVER runs wsl --install                      │
│    • This module NEVER runs Enable-WindowsOptionalFeature      │
│    • This module NEVER runs DISM                               │
│    • This module NEVER modifies any system feature             │
│    • All "actions" are returned as user-facing instruction      │
│      strings for display in the GUI                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 10.3 WSLStatus Enum

```python
class WSLStatus(Enum):
    NOT_AVAILABLE = "not_available"      # wsl.exe not found
    FEATURE_DISABLED = "feature_disabled" # Windows feature not enabled
    KERNEL_MISSING = "kernel_missing"     # WSL2 kernel not installed
    NO_DISTRO = "no_distro"              # No Linux distribution
    READY = "ready"                       # WSL2 operational
```

### 10.4 Integration with State Machine

```
If WSLOrchestrator.detect_wsl_status() != READY:
  → Display instructions in DependencyFetchScreen
  → If is_reboot_required() == True:
    → Set state.reboot_required = True
    → Transition to RebootPromptScreen (S1.6)
  → If is_reboot_required() == False:
    → User completes manual steps
    → User clicks "Re-check" button
    → Re-run detect_wsl_status()
```

---

## 11. Reboot-Resume Architecture

> **GOVERNANCE NOTE:** This section is **conceptual only**. No reboot commands, no registry commands, no RunOnce modifications are included. All privileged steps are represented as **placeholders for human implementation**.

### 11.1 Concept

The reboot-resume architecture allows the installer to survive a Windows reboot and continue from the exact phase where it left off. This is critical for WSL kernel installation and Windows feature enablement, which require a reboot to take effect.

### 11.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│              REBOOT-RESUME ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PRE-REBOOT SEQUENCE:                                          │
│  ┌─────────────────────────────────────┐                       │
│  │  1. Flush state to installer_state.json                     │
│  │     current_phase = "REBOOT_PENDING"                        │
│  │     resume_phase = "REBOOT_RESUME"                          │
│  │     reboot_reason = "WSL kernel installed"                  │
│  │     reboot_requested_at = ISO-8601                          │
│  │                                                              │
│  │  2. Write resume shortcut                                   │
│  │     [CONCEPTUAL — PRIVILEGED PLACEHOLDER]                   │
│  │     Target: Create a shortcut/scheduled task that           │
│  │     re-launches PhantomInstaller.exe --resume               │
│  │     Location options:                                       │
│  │       a) Startup folder (non-admin)                         │
│  │       b) RunOnce registry key (requires elevation)          │
│  │       c) Scheduled Task at logon (requires elevation)       │
│  │                                                              │
│  │     NON-PRIVILEGED FALLBACK:                                │
│  │       Place shortcut in:                                    │
│  │       %APPDATA%\Microsoft\Windows\Start Menu\Programs\      │
│  │         Startup\PhantomInstallerResume.lnk                  │
│  │       This runs at user logon without admin.                │
│  │                                                              │
│  │  3. Display reboot advisory to user                         │
│  │     "Please restart your computer to continue               │
│  │      Phantom installation. The installer will               │
│  │      resume automatically after reboot."                    │
│  │                                                              │
│  │  4. [USER PERFORMS REBOOT MANUALLY]                         │
│  │     The installer NEVER triggers reboot itself.             │
│  │                                                              │
│  └─────────────────────────────────────┘                       │
│                                                                 │
│  POST-REBOOT SEQUENCE:                                         │
│  ┌─────────────────────────────────────┐                       │
│  │  5. OS boots → User logs in                                 │
│  │     → Startup shortcut launches:                            │
│  │       PhantomInstaller.exe --resume                         │
│  │                                                              │
│  │  6. Installer reads installer_state.json                    │
│  │     → Detects resume_phase = "REBOOT_RESUME"               │
│  │     → Opens GUI directly at ResumeScreen (S1.7)            │
│  │                                                              │
│  │  7. ResumeScreen runs verification:                         │
│  │     → Re-check WSL status (or whatever prompted reboot)    │
│  │     → If OK: advance to next phase (P3 VENV_SETUP)         │
│  │     → If still failing: display new instructions,           │
│  │       offer "Re-check" or "Skip WSL"                       │
│  │                                                              │
│  │  8. Clean up resume artefact                                │
│  │     → Delete startup shortcut                               │
│  │     → Update state: resume_after_reboot = false             │
│  │                                                              │
│  │  9. Continue normal phase progression                       │
│  │     P3 → P4 → P5 → P6 → P7 → P8                          │
│  │                                                              │
│  └─────────────────────────────────────┘                       │
│                                                                 │
│  STATE FILE FIELDS FOR REBOOT:                                 │
│    reboot_required: true                                       │
│    resume_after_reboot: false → true (after reboot)            │
│    resume_phase: "REBOOT_RESUME"                               │
│    reboot_reason: "WSL kernel update"                          │
│    reboot_requested_at: "2026-03-02T10:30:00Z"                │
│    resume_shortcut_path: "%APPDATA%\...\Startup\..."           │
│                                                                 │
│  FAILURE MODES:                                                │
│    • User doesn't reboot → shortcut never fires → no harm     │
│    • User deletes state file → installer starts fresh          │
│    • Resume fails verification → user can retry or abort       │
│    • Multiple reboots → installer is idempotent                │
│                                                                 │
│  [CRITICAL CONSTRAINTS]                                        │
│    • The installer NEVER calls Restart-Computer                │
│    • The installer NEVER calls shutdown /r                     │
│    • The installer NEVER writes to HKLM registry              │
│    • The ONLY auto-resume mechanism is the Startup folder      │
│      shortcut (non-admin) or user-initiated re-launch          │
│    • All resume state is in a plain JSON file                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 11.3 --resume CLI Flag

```
PhantomInstaller.exe --resume
  1. Read %LOCALAPPDATA%\Phantom\installer_state.json
  2. If state.resume_phase exists:
     → Skip to that phase in the state machine
     → Open GUI at corresponding screen
  3. If no state file or no resume_phase:
     → Start normal installation from S0
```

### 11.4 Startup Folder Shortcut (Non-Privileged)

```
Location: %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
File:     PhantomInstallerResume.lnk

Target:   <path-to>\PhantomInstaller.exe
Arguments: --resume
Start in: %LOCALAPPDATA%\Phantom
Comment:  Phantom Installer - Resume after reboot

This shortcut is:
  • Created by the installer before advising reboot
  • Deleted by the installer after successful resume
  • Non-privileged (Startup folder is per-user)
  • Harmless if left dangling (installer exits immediately if no resume needed)
```

---

## 12. Logging and Auditability Plan

### 12.1 Log File Inventory

| Log File | Location | Purpose | Retention |
|----------|----------|---------|-----------|
| `installation_audit.log` | `{install_dir}/` | Full audit trail of every installer action | Permanent |
| `installer.log` | `{install_dir}/logs/` | Detailed debug log with stack traces | Permanent |
| `installer_state.json` | `{install_dir}/` | Machine-readable state for resume | Until COMPLETE, then archived |
| `.phantom_install_manifest.json` | `{install_dir}/` | Installed files manifest for uninstaller | Permanent |
| `staging_manifest.json` | `{install_dir}/staging/` | Downloaded dependency inventory | Deleted after P3 |
| `models_manifest.json` | `{install_dir}/models/` | Downloaded model metadata | Permanent |
| `build.log` | `dist/` (build-time only) | Build pipeline output | Build artefact |

### 12.2 Audit Log Format

Every entry in `installation_audit.log` follows this format:

```
[2026-03-02 10:30:00] INFO    PhantomInstallerAPI initialised
[2026-03-02 10:30:01] INFO    Running system scan
[2026-03-02 10:30:02] INFO    System scan PASSED: 5 passed, 1 warnings, 0 failed
[2026-03-02 10:30:05] INFO    Starting worker discovery (mode=comprehensive)
[2026-03-02 10:30:12] INFO    Worker discovery complete: 3 worker(s) found
[2026-03-02 10:30:15] INFO    Starting model download: Phi-3.5 Mini Q4_K_M
[2026-03-02 10:35:42] INFO    Model ready: C:\Users\user\phantom\models\Phi-3.5-mini-instruct-Q4_K_M.gguf
[2026-03-02 10:35:43] INFO    LLM config written: C:\Users\user\phantom\config\llm_config.json
[2026-03-02 10:35:43] INFO    Worker registry written: C:\Users\user\phantom\config\worker_registry.json
[2026-03-02 10:35:44] INFO    Installer prepared (type=all, workers=3)
[2026-03-02 10:35:44] INFO    [Stage 0] Creating directory structure…
[2026-03-02 10:35:44] INFO    Stage 0 (OK): Creating directories
[2026-03-02 10:35:45] INFO    [Stage 1] Installing selected components…
[2026-03-02 10:35:48] INFO    Stage 1 (OK): Installing components
...
[2026-03-02 10:36:01] INFO    Stage 6 (OK): Initializing constitutional pipeline
```

### 12.3 Audit Properties

| Property | Description |
|----------|-------------|
| **Timestamps** | ISO-8601, local time with UTC offset |
| **Levels** | DEBUG, INFO, WARNING, ERROR |
| **Determinism** | Same inputs produce same log structure (timestamps vary) |
| **Non-repudiation** | Every phase transition logged; every file write logged |
| **Crash-safe** | Logs are flushed after each write (FileHandler default) |
| **Human-readable** | Plain text, one event per line |
| **Machine-parseable** | Fixed format: `[timestamp] LEVEL message` |

### 12.4 State File Audit Trail

The `installer_state.json` contains an `error_log` array that records every error encountered:

```json
{
  "error_log": [
    {
      "timestamp": "2026-03-02T10:31:00Z",
      "phase": "DEPENDENCY_FETCH",
      "error": "Network timeout downloading fastapi wheel",
      "action": "retry",
      "resolved": true
    }
  ]
}
```

### 12.5 Rollback Manifest

Each phase records its changes in the `rollback_manifest` array before execution:

```json
{
  "rollback_manifest": [
    {
      "phase": "VENV_SETUP",
      "created_dirs": ["venvs/phantom"],
      "created_files": ["venvs/phantom/pyvenv.cfg"],
      "rollback_action": "delete_tree:venvs/"
    },
    {
      "phase": "COMPONENT_INSTALL",
      "created_dirs": ["phantom_core/", "ui/"],
      "created_files": ["config/phantom_config.yaml"],
      "rollback_action": "delete_listed"
    }
  ]
}
```

### 12.6 Post-Install Verification Log

`VALIDATION` (P7) runs all checks and appends results:

```
[2026-03-02 10:36:05] INFO    === POST-INSTALL VERIFICATION ===
[2026-03-02 10:36:05] INFO    ✅ Installation directory exists: C:\Users\user\phantom
[2026-03-02 10:36:05] INFO    ✅ Configuration directory created
[2026-03-02 10:36:05] INFO    ✅ Logs directory created
[2026-03-02 10:36:05] INFO    ✅ Data directory created
[2026-03-02 10:36:05] INFO    ✅ Installation manifest saved
[2026-03-02 10:36:05] INFO    ✅ Virtual environment valid
[2026-03-02 10:36:06] INFO    ✅ Model file present and verified
[2026-03-02 10:36:06] INFO    ✅ Worker registry written
[2026-03-02 10:36:06] INFO    Installation verification PASSED (8/8 checks)
```

---

## 13. Documentation Outline for README_INSTALLER.md

```markdown
# README_INSTALLER.md — Phantom Windows Installer

## 1. Overview
   - What the installer does
   - Thin EXE concept (installer downloads dependencies at runtime)
   - Supported Windows versions (10 21H2+, 11, Server 2019+)

## 2. Quick Start
   - Download PhantomInstaller.exe
   - Double-click to launch (no admin required for basic install)
   - Follow the wizard screens
   - Installation completes to %USERPROFILE%\phantom

## 3. System Requirements
   - Windows 10 version 21H2 or later
   - Python 3.10+ (embedded or system)
   - 8 GB RAM minimum (16 GB recommended)
   - 6 GB free disk space (minimal) / 12 GB (full with model)
   - Internet connection for dependency and model downloads
   - NVIDIA GPU with 6+ GB VRAM (recommended, not required)

## 4. Installation Modes
   ### 4.1 GUI Mode (Default)
   - Launches Tkinter wizard
   - Step-by-step guided installation
   ### 4.2 CLI Mode
   - `PhantomInstaller.exe --cli`
   - Text-based interactive wizard
   ### 4.3 Silent Mode
   - `PhantomInstaller.exe --silent --type=all`
   - Unattended installation with defaults
   ### 4.4 Dry Run
   - `PhantomInstaller.exe --dry-run`
   - Preview without making changes

## 5. Installation Phases
   - Phase 0: Initialisation
   - Phase 1: System Scan
   - Phase 2: Dependency Fetch
   - Phase 2a/2b: Reboot-Resume (if needed)
   - Phase 3: Virtual Environment Setup
   - Phase 4: Component Installation
   - Phase 5: Model Download
   - Phase 6: Worker Bootstrap
   - Phase 7: Validation
   - Phase 8: Complete

## 6. Reboot-Resume
   - When is a reboot needed?
   - How does auto-resume work?
   - Manual resume: `PhantomInstaller.exe --resume`
   - Troubleshooting resume failures

## 7. WSL Setup (Optional)
   - When is WSL needed?
   - Manual WSL installation steps
   - Verifying WSL status
   - Skipping WSL (consequences)

## 8. Component Selection
   - phantom_core (required)
   - llm_taskmaster
   - windows_workers
   - security_framework
   - socket_infrastructure
   - redblue_ui

## 9. Model Selection
   - Available models (Phi-3.5 variants)
   - VRAM requirements per model
   - Offline model installation

## 10. Post-Installation
   - Starting Phantom: `environment.ps1`
   - Access points: http://localhost:8080, ws://localhost:8081, http://localhost:3000
   - Verifying installation health
   - Viewing logs

## 11. Offline / Air-Gapped Installation
   - Pre-staging dependencies
   - Pre-staging models
   - Running installer with `--offline`

## 12. Uninstallation
   - Using the uninstaller
   - Manual cleanup
   - What is removed vs. preserved

## 13. Troubleshooting
   - Common errors and solutions
   - Log file locations
   - Installer state file recovery
   - Reporting issues

## 14. Building the Installer EXE
   - Prerequisites: Python 3.10+, PyInstaller or Nuitka
   - Build command: `python installer/build/build_exe.py`
   - Output: `dist/PhantomInstaller-<version>-win-x64.zip`
   - Verifying the build

## 15. Architecture Reference
   - Link to INSTALLER_ARCHITECTURE_SPEC.md
   - State machine diagram
   - Dependency graph
   - Folder structure

## 16. License
   - Dual-licensed: MIT (open-source) + Commercial
   - See LICENSE and LICENSE-COMMERCIAL.md
```

---

## Appendix A: Invariant Verification Checklist

Before any human engineer implements this specification, verify:

| # | Invariant | Verification |
|---|-----------|-------------|
| 1 | No system-level commands emitted | Grep for `subprocess.run`, `os.system` — none touch Windows features |
| 2 | No registry modification | Grep for `winreg`, `reg add`, `HKLM`, `HKCU` — none present |
| 3 | No reboot triggers | Grep for `Restart-Computer`, `shutdown`, `reboot` — none present |
| 4 | No DISM commands | Grep for `DISM`, `dism`, `Enable-WindowsOptionalFeature` — none present |
| 5 | No WSL installation | Grep for `wsl --install`, `wsl.exe --install` — none present |
| 6 | No privileged operations | All privileged steps are string literals displayed to user |
| 7 | All output is deterministic | Same inputs → same state transitions (timestamps excluded) |
| 8 | All changes are reversible | Every phase has a rollback manifest entry |
| 9 | No hallucinated files | Every referenced file exists in the codebase or is marked `# NEW` |
| 10 | No file renaming | No existing files renamed; new files clearly marked |

---

## Appendix B: Cross-Reference to Existing Codebase

| Spec Component | Existing File | Status |
|----------------|---------------|--------|
| State machine core | `installer/integration/phantom_installer_api.py` | Extend |
| System scan | `installer/backend_interface/system_scan_adapter.py` → `modules/system_check.py` | Reuse as-is |
| Worker discovery | `installer/backend_interface/worker_discovery_adapter.py` → `modules/worker_discovery.py` | Reuse as-is |
| Model downloader | `installer/backend_interface/model_downloader.py` | Reuse as-is |
| Config writer | `installer/backend_interface/config_writer.py` | Reuse as-is |
| Installer driver | `installer/backend_interface/installer_driver.py` | Extend (add P2, P6, P7 stages) |
| VenvSetup | `installer/modules/venv_setup.py` | Reuse as-is |
| ComponentManager | `installer/modules/component_manager.py` | Reuse as-is |
| GUI Wizard | `installer/gui/wizard.py` | Extend (add 3 new screens) |
| GUI Screens | `installer/gui/screens/*.py` | Extend (add 3 new screen files) |
| Dependency fetcher | `installer/backend_interface/dependency_fetcher.py` | **NEW** |
| Reboot manager | `installer/backend_interface/reboot_manager.py` | **NEW** |
| WSL orchestrator | `installer/backend_interface/wsl_orchestrator.py` | **NEW** |
| DependencyFetchScreen | `installer/gui/screens/dependency_fetch.py` | **NEW** |
| RebootPromptScreen | `installer/gui/screens/reboot_prompt.py` | **NEW** |
| ResumeScreen | `installer/gui/screens/resume.py` | **NEW** |
| PyInstaller spec | `installer/build/phantom_installer.spec` | **NEW** |
| Nuitka config | `installer/build/phantom_installer_nuitka.py` | **NEW** |
| Build orchestrator | `installer/build/build_exe.py` | **NEW** |

---

## Appendix C: Implementation Priority Order

| Priority | Component | Effort | Dependencies |
|----------|-----------|--------|-------------|
| P0 | State machine + state file persistence | Medium | None |
| P1 | `--resume` CLI flag handling | Low | P0 |
| P2 | DependencyFetcher backend | Medium | P0 |
| P3 | DependencyFetchScreen GUI | Medium | P2 |
| P4 | WSLOrchestrator (read-only) | Low | None |
| P5 | RebootPromptScreen + ResumeScreen | Medium | P0, P1, P4 |
| P6 | Startup folder shortcut creation | Low | P5 |
| P7 | PyInstaller spec + build pipeline | Medium | All screens exist |
| P8 | README_INSTALLER.md | Low | All above |

---

*End of specification.*
*Document hash: deterministic content, auditable, reversible.*
*No system commands were emitted. No privileged operations were performed.*
