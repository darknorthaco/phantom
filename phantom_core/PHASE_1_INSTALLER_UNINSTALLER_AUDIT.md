# PHASE 1 — Installer & Uninstaller Audit Report

**Audit Classification:** DARPA-Grade Technical Assessment  
**Date:** 2025-02-18  
**Scope:** Phantom PTR — Installation Wizard, Post-Install, Uninstall Capabilities  
**Auditor:** Automated Phase 1 Compliance Engine  
**Status:** DRAFT — Findings Require Remediation  

---

## Table of Contents

1. [Installer Architecture](#1-installer-architecture)
2. [Platform Support](#2-platform-support)
3. [Critical Gaps](#3-critical-gaps)
4. [Configuration Generation](#4-configuration-generation)
5. [Uninstaller Analysis](#5-uninstaller-analysis)
6. [Post-Install Analysis](#6-post-install-analysis)
7. [Recommendations](#7-recommendations)

---

## 1. Installer Architecture

### 1.1 Overview

The installer is a **6-step interactive CLI wizard** implemented in Python, launched via platform-specific shell wrappers (`phantom_installer.sh` for Linux/macOS, `phantom_installer.ps1` for Windows).

**Entry points:**

| Platform | Wrapper | Python Entry | Lines |
|----------|---------|-------------|-------|
| Linux/macOS | `installer/phantom_installer.sh` | `installer/phantom_installer.py` | 151 |
| Windows | `installer/phantom_installer.ps1` | `installer/phantom_installer_windows.py` | 136 |
| Demo | — | `installer/demo_installer.py` | 166 |

### 1.2 Module Architecture

| Module | File | Lines | Purpose | Status |
|--------|------|-------|---------|--------|
| **CLIWizard** | `installer/ui/cli_wizard.py` | 399 | Interactive 6-step wizard flow | Complete |
| **Prompts** | `installer/ui/prompts.py` | 177 | User input collection, validation | Complete |
| **SystemChecker** | `installer/modules/system_check.py` | 229 | Prerequisite validation (Python, disk, ports, network) | Complete |
| **ComponentManager** | `installer/modules/component_manager.py` | 220 | Component installation, git clone / archive download | Partial |
| **WorkerDiscovery** | `installer/modules/worker_discovery.py` | 239 | Network scanning for existing workers | Complete |
| **SocketManager** | `installer/modules/socket_manager.py` | 78 | WebSocket configuration | Complete |
| **UIIntegration** | `installer/modules/ui_integration.py` | 71 | UI configuration | Complete |
| **VenvSetup** | `installer/modules/venv_setup.py` | 132 | Python virtual environment creation | Complete |
| **ConfigGenerator** | `installer/modules/config_generator.py` | 183 | YAML/JSON configuration file generation | Complete |
| **HealthCheck** | `installer/scripts/health_check.py` | 209 | Post-install system verification | Complete |

### 1.3 Installation Steps

The wizard (`cli_wizard.py`, lines 59–108) collects configuration across 9 interactive prompts, then executes in 6 steps:

**Interactive Prompts (Pre-Execution):**

| # | Prompt | Location | Purpose |
|---|--------|----------|---------|
| 1 | Welcome screen | `cli_wizard.py:63` | Display banner, version info |
| 2 | System checks | `cli_wizard.py:66` | Validate prerequisites |
| 3 | Install directory | `cli_wizard.py:70` | Choose installation path |
| 4 | Component selection | `cli_wizard.py:74` | Pick modules to install |
| 5 | Network configuration | `cli_wizard.py:78` | Controller host/port, worker ports |
| 6 | Worker discovery | `cli_wizard.py:82` | Scan for existing workers |
| 7 | Socket configuration | `cli_wizard.py:86` | WebSocket host/port/SSL |
| 8 | UI configuration | `cli_wizard.py:90` | RedBlue UI host/port |
| 9 | Security configuration | `cli_wizard.py:94` | Auth level, TLS settings |

**Execution Steps (Post-Confirmation):**

| Step | Action | Location | Detail |
|------|--------|----------|--------|
| 1 | Create directory structure | `cli_wizard.py:345` | `mkdir -p` for install directories |
| 2 | Install components | `cli_wizard.py:351` | Git clone or archive extraction |
| 3 | Generate configurations | `cli_wizard.py:362` | Write YAML/JSON config files |
| 4 | Create environment scripts | `cli_wizard.py:381` | Shell/batch scripts for env activation |
| 5 | Virtual environment setup | `cli_wizard.py:386` | Python venv creation and pip install |
| 6 | Finalization | `cli_wizard.py:390` | Summary, post-install instructions |

### 1.4 System Checks

**Location:** `installer/modules/system_check.py` (229 lines)

| Check | Requirement | Location | Failure Mode |
|-------|-------------|----------|-------------|
| Python version | ≥ 3.8 | Line 27 | Error, halt |
| OS detection | Linux, Darwin, Windows | Line 41 | Warning |
| Disk space | ≥ 5 GB free | Line 52 | Error, halt |
| Port availability | 8080, 8081, 3000, 5000 | Line 84 | Warning |
| Network connectivity | DNS resolve `github.com` | Line 109 | Warning |
| Git availability | `git --version` | Line 139 | Warning (archive fallback) |
| Virtual env support | `venv` module importable | Line 159 | Warning |
| CLI tools | `curl`, `wget`, `tar`, `unzip` | Line 186 | Info |

### 1.5 Installable Components

**Location:** `installer/modules/component_manager.py`, lines 19–64

| Component | Key | Required? | Platform | Source |
|-----------|-----|-----------|----------|--------|
| Phantom Core | `phantom_core` | **Yes** | All | GitHub repo (git clone) |
| LLM Task Master | `llm_taskmaster` | No | All | GitHub repo (git clone) |
| Linux Workers | `linux_workers` | No | **Linux only** | GitHub repo (git clone) |
| Windows Workers | `windows_workers` | No | **Windows only** | GitHub repo (git clone) |
| Security Framework | `security_framework` | No | All | GitHub repo (git clone) |
| Socket Infrastructure | `socket_infrastructure` | No | All | GitHub repo (git clone) |
| RedBlue UI | `redblue_ui` | No | All | GitHub repo (git clone) |

---

## 2. Platform Support

### 2.1 Linux

| Aspect | Status | Detail |
|--------|--------|--------|
| Shell wrapper | ✅ Complete | `phantom_installer.sh` — sets up Python, launches wizard |
| System checks | ✅ Complete | Full prerequisite validation |
| Component install | ✅ Complete | Git clone from GitHub |
| Worker discovery | ✅ Complete | Ping sweep + port scan |
| Config generation | ✅ Complete | YAML/JSON for all components |
| Post-install | ⚠️ Partial | systemd service to `/tmp/` (see §6) |
| Virtual env | ✅ Complete | Python venv creation |

### 2.2 Windows

| Aspect | Status | Detail |
|--------|--------|--------|
| Shell wrapper | ✅ Complete | `phantom_installer.ps1` — PowerShell launcher |
| Windows installer | ⚠️ Partial | `phantom_installer_windows.py` — 136 lines |
| System checks | ✅ Complete | Reuses cross-platform `system_check.py` |
| Component install | ✅ Complete | Git clone from GitHub |
| Post-install | ⚠️ Partial | Service template only |

**Windows-Specific Methods (`phantom_installer_windows.py`):**

| Method | Status | Lines | Detail |
|--------|--------|-------|--------|
| PowerShell execution policy check | ✅ Functional | 20–44 | Verifies script execution is allowed |
| Windows service setup | ✅ Functional | 46–82 | Creates service via PowerShell |
| Registry entries | ❌ **Stub/Hint** | 84–88 | Prints tip; does not write registry |
| Desktop shortcut | ❌ **Stub/Hint** | 98–102 | Prints tip; does not create shortcut |
| Windows Firewall rules | ❌ **Stub/Hint** | 104–111 | Prints tip; does not configure firewall |

**3 out of 5 Windows-specific methods are no-ops** that print advisory messages but perform no system modifications.

### 2.3 macOS

| Aspect | Status | Detail |
|--------|--------|--------|
| Shell wrapper | ✅ Uses Linux wrapper | `phantom_installer.sh` works on Darwin |
| System checks | ✅ Complete | Detects Darwin, adjusts defaults |
| Default install path | `~/phantom` | macOS-specific default |
| Worker support | ❌ None | No macOS GPU worker implementation |
| Service management | ❌ None | No launchd plist generation |

---

## 3. Critical Gaps

### 3.1 Non-Interactive Mode — NOT IMPLEMENTED

**Severity:** HIGH  
**Location:** `installer/phantom_installer.py`, lines 76–78

```python
if args.non_interactive:
    print("Non-interactive mode not yet implemented.")
    return 1
```

The `--non-interactive` flag is accepted by the argument parser (advertised in help text and documentation) but immediately returns an error code of 1. This blocks:
- CI/CD pipeline integration
- Automated deployments
- Configuration management tool integration (Ansible, Puppet, Chef)
- Air-gapped deployment scripts

### 3.2 Dry-Run Mode — INCOMPLETE

**Severity:** MEDIUM  
**Location:** `installer/phantom_installer.py`, lines 80–83, 93

The `--dry-run` flag is accepted and prints a banner message (`"🔍 DRY RUN MODE - No changes will be made"`). However:
- The wizard still executes all interactive prompts
- Directory creation is NOT skipped
- Component installation (git clone) IS skipped only because venv setup is bypassed
- Config file generation still occurs
- There is no comprehensive simulation that shows what WOULD happen without actually doing it

**Expected behavior:** A true dry-run should simulate the entire installation, showing exactly what files, directories, services, and configurations would be created — without modifying the filesystem.

### 3.3 Archive Download Fallback — STUB

**Severity:** HIGH  
**Location:** `installer/modules/component_manager.py`, line 129

When `git` is unavailable, the component manager falls back to archive download. However:
- No archive URLs are defined
- No URL-to-component mapping exists
- The fallback function is a placeholder that logs a warning and returns failure
- Air-gapped installations cannot succeed without pre-staged archives

### 3.4 Worker Discovery Protocol — UNDEFINED

**Severity:** HIGH  
**Location:** `installer/modules/worker_discovery.py`, lines 130–146

The comprehensive discovery mode scans ports 8090–8094 and sends a JSON identification request:

```json
{"type": "identify", "source": "installer"}
```

**No Phantom worker implements this protocol.** The Linux worker registers via HTTP POST to the controller — it does not listen for or respond to JSON identification requests. The discovery system will find open ports but cannot verify they belong to Phantom workers.

**Cross-reference:** See NET-003 in [PHASE_1_NETWORK_AND_GPU_VALIDATION.md](PHASE_1_NETWORK_AND_GPU_VALIDATION.md)

### 3.5 Gap Summary Table

| ID | Gap | Severity | Impact |
|----|-----|----------|--------|
| **INS-001** | Non-interactive mode returns error | **HIGH** | Blocks CI/CD, automation |
| **INS-002** | Dry-run mode incomplete — still writes files | **MEDIUM** | Misleading to users |
| **INS-003** | Archive download fallback is stub | **HIGH** | Blocks air-gapped install |
| **INS-004** | Worker discovery protocol undefined | **HIGH** | Discovery results unreliable |
| **INS-005** | No rollback on partial install failure | **HIGH** | Leaves system in inconsistent state |

---

## 4. Configuration Generation

### 4.1 Generated Configuration Files

**Location:** `installer/modules/config_generator.py` (183 lines)

| Config File | Format | Location (relative to install dir) | Purpose |
|-------------|--------|-------------------------------------|---------|
| `phantom_config.yaml` | YAML | `config/phantom_config.yaml` | Main system configuration |
| `worker_*.json` | JSON | `config/worker_{id}.json` | Per-worker settings |
| Socket config | YAML | `config/socket_config.yaml` | WebSocket infrastructure |
| UI config | YAML | `config/ui_config.yaml` | RedBlue UI settings |

### 4.2 Main Configuration (`phantom_config.yaml`)

**Lines 21–46:** Generated with the following structure:

```yaml
phantom:
  controller:
    host: "0.0.0.0"  # or user-specified
    port: 8080
  security:
    level: "disabled"        # DEFAULT: DISABLED
    authentication: "none"   # DEFAULT: NO AUTH
  logging:
    level: "INFO"
    file: "phantom.log"
  data:
    directory: "./data"
```

### 4.3 Security Defaults — PRODUCTION UNSAFE

**Severity:** HIGH  
**Location:** `config_generator.py`, lines 34–36, 127

| Setting | Default Value | Production Recommended | Status |
|---------|--------------|----------------------|--------|
| Security level | `"disabled"` | `"production"` | ❌ Unsafe |
| Authentication | `"none"` | `"api_key"` or `"oauth2"` | ❌ Unsafe |
| TLS/SSL | Not configured | Required | ❌ Missing |
| Rate limiting | Not configured | Required | ❌ Missing |

**Impact:** A default installation has:
- No authentication on any API endpoint
- No encryption of data in transit
- No rate limiting (DoS vulnerable)
- No session management
- Controller API exposed on `0.0.0.0` (all interfaces)

**The security framework exists** (`security_framework/integrated_security.py`, 664 lines) but is **disabled by default** in generated configurations. Users must manually enable it.

### 4.4 Socket & UI Configuration Defaults

| Config | Default Host | Default Port | Issue |
|--------|-------------|-------------|-------|
| Socket server | `0.0.0.0` | `8081` | Binds to all interfaces |
| RedBlue UI | `0.0.0.0` | `3000` | Binds to all interfaces |
| Controller API | `0.0.0.0` | `8080` | Binds to all interfaces |

**All three services default to `0.0.0.0`**, exposing them to the entire network. In a production or sensitive environment, this is a security risk. Default should be `127.0.0.1` with explicit opt-in for network exposure.

---

## 5. Uninstaller Analysis

### 5.1 Current State: NO UNINSTALLER EXISTS

**Severity:** CRITICAL

A comprehensive search of the entire repository reveals:
- **No uninstaller script** (Python, Bash, or PowerShell)
- **No uninstaller module** in the `installer/` directory
- **No `uninstall` subcommand** in the CLI wizard
- **No manifest of installed files** (no record of what was installed or where)

The only uninstall guidance is manual deletion documented in `UNINSTALL_WIZARD_PROPOSALS.md`, which is a **design proposal** — not an implementation.

### 5.2 What Does Not Exist

| Capability | Status | Impact |
|------------|--------|--------|
| Safe/interactive uninstall mode | ❌ Missing | Cannot preview what will be removed |
| Destructive/forced uninstall mode | ❌ Missing | Cannot force-remove on failure |
| Selective component removal | ❌ Missing | All-or-nothing removal |
| Configuration backup before removal | ❌ Missing | Config permanently lost |
| Service stop before removal | ❌ Missing | Running services orphaned |
| Rollback to pre-install state | ❌ Missing | No snapshot/checkpoint capability |
| Install manifest | ❌ Missing | No record of installed files |
| User data preservation | ❌ Missing | Task data, logs deleted with system |
| Registry cleanup (Windows) | ❌ Missing | Registry entries orphaned |
| systemd service removal | ❌ Missing | Service file persists (if copied from `/tmp/`) |

### 5.3 Current "Uninstall" Method

The only documented method is:

```bash
rm -rf /path/to/phantom_install
```

This:
- Does not stop running services
- Does not remove systemd service files
- Does not clean up PID files (`phantom_integrated.pid`)
- Does not remove Python virtual environments
- Does not clean up `/tmp/cuda_cache` or `/tmp/phantom.service`
- Does not notify the controller to deregister workers
- Does not preserve configuration or logs
- Does not remove Windows registry entries or shortcuts

### 5.4 UNINSTALL_WIZARD_PROPOSALS.md Analysis

The proposals document (`UNINSTALL_WIZARD_PROPOSALS.md`) outlines a design for:
- Safe mode (interactive, preserves configs)
- Destructive mode (force, removes everything)
- Component-level removal
- Rollback capability

**Status:** Design only. Zero lines of implementation code exist.

---

## 6. Post-Install Analysis

### 6.1 Linux Post-Install (`installer/scripts/post_install.sh`)

**systemd Service Creation (Lines 47–74):**

```ini
[Unit]
Description=Phantom Distributed Compute
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/run_integrated_phantom.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Critical Issues:**

| ID | Issue | Severity | Detail |
|----|-------|----------|--------|
| **INS-006** | Service file written to `/tmp/phantom.service` | **CRITICAL** | `/tmp/` is cleared on reboot. Service definition is lost. Should be `/etc/systemd/system/phantom.service`. |
| **INS-007** | No `ExecStop` directive | **HIGH** | systemd has no clean shutdown command. Falls back to SIGTERM, which may not cleanly deregister workers. |
| **INS-008** | `pkill -f "run_integrated_phantom.py"` in stop script | **HIGH** | Substring match via `pkill -f` can kill unrelated processes whose command line contains the string. |
| **INS-009** | `User=$USER` uses installer's user | **MEDIUM** | Should use a dedicated service account (e.g., `phantom`) for principle of least privilege. |

**Stop Script (Line 93):**

```bash
pkill -f "run_integrated_phantom.py"
```

**`pkill -f` risk:** The `-f` flag matches against the full command line. If any other process has `run_integrated_phantom.py` in its arguments (e.g., `vim run_integrated_phantom.py`, `grep run_integrated_phantom.py`), it will be killed.

**Recommended fix:** Use PID file-based shutdown:
```bash
kill $(cat /var/run/phantom.pid)
```

### 6.2 Windows Post-Install (`installer/scripts/post_install.ps1`)

| Feature | Status | Detail |
|---------|--------|--------|
| Service template | ⚠️ Template only | Provides `New-Service` command template (lines 29–46) |
| Service creation | ❌ Not automated | User must run PowerShell commands manually |
| Stop method | ⚠️ Risky | `Get-Process | Stop-Process -Force` (lines 64–69) — same substring match risk |
| Firewall rules | ❌ Not created | Tip messages printed, no `New-NetFirewallRule` executed |

### 6.3 PID File Management

**Location:** `phantom_integrated.pid` exists in repository root

| Issue | Detail |
|-------|--------|
| PID file location | Repository root — should be `/var/run/phantom.pid` or `$INSTALL_DIR/phantom.pid` |
| PID file cleanup | Not handled on shutdown — stale PID file persists |
| PID file ownership | No permission management |
| Multiple instance prevention | No lock file or PID check before start |

### 6.4 Post-Install Health Check

**Location:** `installer/scripts/health_check.py` (209 lines)

The health check script validates the installation by:

| Check | Method | Pass Criteria |
|-------|--------|--------------|
| Python version | `sys.version_info` | ≥ 3.8 |
| Module imports | `importlib.import_module()` | Core modules importable |
| Config file existence | `os.path.exists()` | Config files present |
| Port availability | `socket.connect_ex()` | Ports not in use (pre-start) or responsive (post-start) |
| Service status | `systemctl is-active` | Service running (Linux only) |

---

## 7. Recommendations

### 7.1 Priority-Ordered Fix List

| Priority | ID | Action | Effort | Addresses |
|----------|-----|--------|--------|-----------|
| **P0** | R-01 | **Implement uninstaller** — safe mode with config backup, service stop, file removal, manifest tracking | 3–5 days | §5 (all) |
| **P0** | R-02 | **Move systemd service to `/etc/systemd/system/`** and run `systemctl daemon-reload` + `systemctl enable` | 1 hour | INS-006 |
| **P0** | R-03 | **Add `ExecStop` to systemd service** — use `ExecStop=/bin/kill $MAINPID` or a dedicated shutdown script | 1 hour | INS-007 |
| **P0** | R-04 | **Replace `pkill -f` with PID-file-based shutdown** | 2 hours | INS-008 |
| **P1** | R-05 | **Implement non-interactive mode** — accept all config via CLI args or config file | 2–3 days | INS-001 |
| **P1** | R-06 | **Implement archive download URLs** for air-gapped installations | 1–2 days | INS-003 |
| **P1** | R-07 | **Change security defaults to enabled** (`"development"` for dev, `"production"` for prod) | 2 hours | §4.3 |
| **P1** | R-08 | **Change default bind to `127.0.0.1`** for all services; require explicit `0.0.0.0` opt-in | 1 hour | §4.4 |
| **P1** | R-09 | **Complete Windows installer methods** — implement registry, shortcuts, firewall rules or remove stubs | 2–3 days | §2.2 |
| **P2** | R-10 | **Implement true dry-run** — simulate all steps, output plan, touch no files | 1–2 days | INS-002 |
| **P2** | R-11 | **Define worker discovery protocol** — implement HTTP-based `/identify` endpoint on workers | 1 day | INS-004 |
| **P2** | R-12 | **Add install manifest** — JSON file recording all created files, dirs, services, configs | 1 day | §5.2 |
| **P2** | R-13 | **Add rollback capability** — snapshot pre-install state, restore on failure | 2–3 days | INS-005 |
| **P2** | R-14 | **Use dedicated service account** — create `phantom` user for systemd service | 2 hours | INS-009 |
| **P3** | R-15 | **Add macOS launchd support** — generate `com.phantom.plist` for macOS service management | 1 day | §2.3 |
| **P3** | R-16 | **Implement config backup** during uninstall and upgrade | 1 day | §5.2 |

### 7.2 Cross-Reference Matrix

| Finding ID | Report | Recommendation |
|------------|--------|----------------|
| INS-001 | This report, §3.1 | R-05 |
| INS-002 | This report, §3.2 | R-10 |
| INS-003 | This report, §3.3 | R-06 |
| INS-004 | This report, §3.4 | R-11 |
| INS-005 | This report, §3.5 | R-13 |
| INS-006 | This report, §6.1 | R-02 |
| INS-007 | This report, §6.1 | R-03 |
| INS-008 | This report, §6.1 | R-04 |
| INS-009 | This report, §6.1 | R-14 |
| ARCH-008 | Architecture Report | R-09 |
| ARCH-010 | Architecture Report | R-07 |
| NET-003 | Network Report | R-11 |
| NET-007 | Network Report | R-02 |
| NET-009 | Network Report | R-06 (air-gapped fallback) |
| NET-014 | Network Report | R-08 |

### 7.3 Installer Findings Summary

| ID | Finding | Severity | Component |
|----|---------|----------|-----------|
| **INS-001** | Non-interactive mode advertised but returns error | **HIGH** | `phantom_installer.py:76-78` |
| **INS-002** | Dry-run mode incomplete — still creates files | **MEDIUM** | `phantom_installer.py:80-93` |
| **INS-003** | Archive download fallback is stub (no URL mapping) | **HIGH** | `component_manager.py:129` |
| **INS-004** | Worker discovery protocol undefined (no worker responds) | **HIGH** | `worker_discovery.py:130-146` |
| **INS-005** | No rollback on partial install failure | **HIGH** | `cli_wizard.py` |
| **INS-006** | systemd service written to `/tmp/` (deleted on reboot) | **CRITICAL** | `post_install.sh:47` |
| **INS-007** | No `ExecStop` directive in systemd service | **HIGH** | `post_install.sh:47-74` |
| **INS-008** | `pkill -f` used for process stop (dangerous substring match) | **HIGH** | `post_install.sh:93` |
| **INS-009** | Service runs as installer user, not dedicated account | **MEDIUM** | `post_install.sh:56` |
| **INS-010** | **No uninstaller exists** — only manual `rm -rf` | **CRITICAL** | Entire repository |
| **INS-011** | Security defaults to DISABLED in generated configs | **HIGH** | `config_generator.py:34-36` |
| **INS-012** | All services default to `0.0.0.0` bind (all interfaces) | **HIGH** | `config_generator.py` |
| **INS-013** | Windows installer: 3/5 methods are stubs (registry, shortcuts, firewall) | **MEDIUM** | `phantom_installer_windows.py` |
| **INS-014** | No install manifest — no record of installed files | **HIGH** | Missing feature |

### 7.4 Severity Distribution

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 2 | INS-006, INS-010 |
| HIGH | 8 | INS-001, INS-003, INS-004, INS-005, INS-007, INS-008, INS-011, INS-012, INS-014 |
| MEDIUM | 3 | INS-002, INS-009, INS-013 |
| LOW | 0 | — |
| **Total** | **14** | — |

---

*Cross-references: See [PHASE_1_PLATFORM_ARCHITECTURE_REPORT.md](PHASE_1_PLATFORM_ARCHITECTURE_REPORT.md) for architecture findings (ARCH-*), [PHASE_1_NETWORK_AND_GPU_VALIDATION.md](PHASE_1_NETWORK_AND_GPU_VALIDATION.md) for network findings (NET-*).*

**END OF REPORT**
