# Phantom Scripts & Commands Reference

> **Single authoritative reference for all scripts, entry points, and operational commands in the Phantom unified distribution.**
>
> Version: 1.0.0 | Last Updated: 2026-02-23 | Maintainer: Dark North Co.

### Canonical install (Phase 2)

| Path | Notes |
|------|--------|
| **`phantom_app/`** (Tauri) | **Supported** end-user install, deploy ceremony, **`uninstall_phantom`** / **`upgrade_phantom_deployment`** invokes — see root **`INSTALL.md`** |
| **`installer/*.py`**, **`package/install.*`** | **Deprecated** by default; require **`PHANTOM_ALLOW_LEGACY_INSTALLER=1`** or **`PHANTOM_ALLOW_LEGACY_PACKAGE_INSTALL=1`** |
| **`installer/offline_bundle.py`** | **Phase 3** — build/verify air-gap bundles (`generate`, `verify`); see **`docs/offline_install.md`** |

---

## Quick Reference Index

| Category | Count | Platform Coverage |
|----------|-------|-------------------|
| Build | 3 | Windows / Linux / macOS |
| Install | 7 | Windows / Linux / macOS |
| Uninstall | 5 | Windows / Linux / macOS |
| Runtime | 5 | Cross-platform |
| Dev / Debug | 4 | Linux / Cross-platform |
| Monitoring | 1 | Linux / macOS |
| Certs / Security | 2 | Linux / macOS / Cross-platform |
| Deployment | 3 | Linux / macOS |
| Health Check | 2 | Linux / Cross-platform |
| Test | 1 | Linux / macOS |
| **Total** | **33** | — |

> **Note:** Some Python entry points have standalone `if __name__ == "__main__"` blocks for direct invocation but are primarily libraries (e.g., `controller_api.py`, `hybrid_socket_server.py`). These are documented in [Section 4 — Runtime Commands](#4-runtime-commands) where they serve as entry points.

---

## Platform Selection Guide

> Use this table when multiple scripts serve the same purpose on different platforms.

| Task | Windows (CMD) | Windows (PS1) | Windows (GUI) | Linux / macOS | Python (Cross-platform) |
|------|--------------|---------------|---------------|---------------|-------------------------|
| **Install Phantom (canonical)** | — | — | — | — | Build/run **`phantom_app`** per **`INSTALL.md`** |
| **Install Phantom (legacy, opt-in)** | `package/install.bat`¹ | `installer/phantom_installer.ps1` | `installer/windows_gui_installer.py`² | `package/install.sh`¹ | `installer/phantom_installer.py`² |

¹ Requires `PHANTOM_ALLOW_LEGACY_PACKAGE_INSTALL=1`. ² Requires `PHANTOM_ALLOW_LEGACY_INSTALLER=1`.
| **Uninstall Phantom (Linux, recommended)** | — | — | — | `rm-phantom` (external) | `installer/phantom_uninstaller.py` |
| **Uninstall Phantom (built-in)** | `package/uninstall.bat` | `installer/phantom_uninstaller.ps1` | — | `package/uninstall.sh` | `installer/phantom_uninstaller.py` |
| **Build package** | `package/build_complete.bat` | — | — | `package/build_complete.sh` | — |
| **Start system** | — | — | — | `phantom_core/start_complete_phantom.sh` | `phantom_core/run_integrated_phantom.py` |
| **Start controller only** | — | — | — | — | `phantom_core/run.py` |
| **Post-install setup** | — | `installer/scripts/post_install.ps1` | — | `installer/scripts/post_install.sh` | — |
| **Health check** | — | — | — | — | `installer/scripts/health_check.py` |
| **Run tests** | — | — | — | `phantom_core/scripts/run_tests.sh` | `pytest tests/` |

---

## 1. Build Scripts

> Scripts that compile, package, and prepare Phantom for distribution.

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `package/build_complete.sh` | Linux / macOS | No | Full package build — creates `.tar.gz` archive with SHA256 checksum. Auto-detects OS and architecture. |
| `package/build_complete.bat` | Windows | No | Full package build — creates `.zip` archive with checksum. Detects x86/x64. |
| `ui/redblue_matrix/phantom-matrix-android/build-android.sh` | Linux / macOS | No | React Native Android build — installs npm dependencies, runs `react-native bundle`, generates APK. Requires Node.js and Android SDK. |

### Usage Examples

```bash
# Linux/macOS — Build distribution package
./package/build_complete.sh

# Windows — Build distribution package
package\build_complete.bat

# Android — Build Matrix UI APK (run from phantom-matrix-android/ directory)
cd ui/redblue_matrix/phantom-matrix-android
./build-android.sh
```

### Key Details

- Build scripts read version from the root `VERSION` file (falls back to `1.0.0`)
- Output is placed in `build/` directory (excluded from Git via `.gitignore`)
- Package name format: `phantom-complete-{VERSION}-{os}-{arch}.{tar.gz|zip}`

---

## 2. Install Scripts

> Scripts that install Phantom on a target system.

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `package/install.sh` | Linux | Yes (root) | Professional CLI installer — system requirements check, component selection, systemd service creation, desktop shortcuts, virtual environment setup. Target: `/opt/phantom`. |
| `package/install.bat` | Windows | Yes (Admin) | CLI installer — admin check, component selection, service creation, shortcut setup, Python venv. Target: `%ProgramFiles%\Phantom`. |
| `installer/phantom_installer.sh` | Linux / macOS | Yes (root) | Shell wrapper — checks Python, then launches `phantom_installer.py` with banner. |
| `installer/phantom_installer.ps1` | Windows | Yes (Admin) | PowerShell wrapper — checks Python, then launches `phantom_installer.py` with banner. |
| `installer/phantom_installer.py` | Cross-platform | Yes | Python-based unified installer — platform-detected installation with CLI wizard, virtual environment setup, component manager. |
| `installer/phantom_installer_windows.py` | Windows | Yes (Admin) | Windows-specific installation logic — execution policy checks, service creation, shortcut generation. Called by `phantom_installer.py`. |
| `installer/windows_gui_installer.py` | Windows | Yes (Admin) | PyQt6 GUI installer — multi-page wizard with component selection, progress bars, visual feedback. Requires `PyQt6` (auto-installs if missing). |

### Key Arguments

```bash
# Linux — Package installer (interactive)
sudo ./package/install.sh

# Windows — Package installer (interactive)
# Right-click → "Run as administrator"
package\install.bat

# Cross-platform Python installer
python3 installer/phantom_installer.py

# Windows GUI installer
python installer/windows_gui_installer.py

# Windows PowerShell wrapper
.\phantom_core\installer\phantom_installer.ps1
```

### How to Choose

| Need | Use |
|------|-----|
| Standard Linux install | `package/install.sh` |
| Standard Windows install | `package/install.bat` |
| Windows with GUI wizard | `installer/windows_gui_installer.py` |
| Cross-platform / scripted | `installer/phantom_installer.py` |
| PowerShell-native launcher | `installer/phantom_installer.ps1` |

---

## 3. Uninstall Scripts

> Scripts that cleanly remove Phantom from a target system.

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `rm-phantom` (external) | Linux | Yes (root) | **Official Linux uninstaller.** External tool — install separately: `pip install rm-phantom`. When present on PATH, `installer/phantom_uninstaller.sh` delegates to it automatically. See [rm-phantom on GitHub](https://github.com/darknorthaco/rm-phantom). |
| `package/uninstall.sh` | Linux | Yes (root) | Built-in uninstaller — stops services, terminates processes, frees ports (8765, 8082, 8080), removes files, desktop shortcuts, systemd unit. Interactive confirmation. Used as fallback when rm-phantom is not installed. |
| `package/uninstall.bat` | Windows | Yes (Admin) | CLI uninstaller — stops service, terminates processes, verifies ports free, removes service/shortcuts/files. Interactive confirmation. |
| `installer/phantom_uninstaller.sh` | Linux / macOS | Yes (root) | Shell wrapper — detects and delegates to rm-phantom on Linux when available; otherwise checks Python and launches `phantom_uninstaller.py`. |
| `installer/phantom_uninstaller.ps1` | Windows | Yes (Admin) | PowerShell uninstaller with rich parameter support (see flags below). |
| `installer/phantom_uninstaller.py` | Cross-platform | Yes | Python orchestrator — manifest-based removal, backup, verification. |

### Key Arguments

```bash
# Linux — rm-phantom (recommended, install separately)
rm-phantom           # interactive
rm-phantom --silent  # non-interactive

# Linux — Package uninstaller (built-in fallback)
sudo ./package/uninstall.sh

# Windows — Package uninstaller (interactive, run as Admin)
package\uninstall.bat

# PowerShell uninstaller with options
.\phantom_core\installer\phantom_uninstaller.ps1 -Mode full -Force
.\phantom_core\installer\phantom_uninstaller.ps1 -DryRun          # Preview only
.\phantom_core\installer\phantom_uninstaller.ps1 -NoBackup        # Skip config backup
.\phantom_core\installer\phantom_uninstaller.ps1 -Help            # Show help

# Python uninstaller
python installer/phantom_uninstaller.py
```

### PowerShell Uninstaller Flags

| Flag | Default | Description |
|------|---------|-------------|
| `-InstallDir <path>` | Auto-detected | Override installation directory |
| `-Mode <safe\|full>` | `safe` | `safe` = preserve configs; `full` = remove everything |
| `-DryRun` | `$false` | Preview uninstallation without making changes |
| `-NoBackup` | `$false` | Skip configuration backup (full mode only) |
| `-Force` | `$false` | Skip confirmation prompts |
| `-Help` | — | Show help message |

---

## 4. Runtime Commands

> Scripts and entry points used to start, stop, and manage a running Phantom instance.

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `phantom_core/start_complete_phantom.sh` | Linux / macOS | No | **Primary runtime manager** — start/stop/restart/status/logs/health for the complete integrated system. |
| `phantom_core/run_integrated_phantom.py` | Cross-platform | No | Full integrated system launcher — controller + socket infrastructure + security + LLM taskmaster. |
| `phantom_core/run.py` | Cross-platform | No | Basic controller launcher — starts only the Phantom controller API. |
| `phantom_core/phantom_core/controller_api.py` | Cross-platform | No | FastAPI controller — can be run directly for development. Usually started via `run.py` or `run_integrated_phantom.py`. |
| `phantom_core/socket_infrastructure/hybrid_socket_server.py` | Cross-platform | No | Standalone WebSocket server — can be run independently for debugging socket layer. |

### `start_complete_phantom.sh` Subcommands

```bash
# Start the complete system (controller + workers)
./phantom_core/start_complete_phantom.sh start

# Stop all Phantom processes
./phantom_core/start_complete_phantom.sh stop

# Restart the system
./phantom_core/start_complete_phantom.sh restart

# Show system status
./phantom_core/start_complete_phantom.sh status

# Show recent logs
./phantom_core/start_complete_phantom.sh logs

# Run health check
./phantom_core/start_complete_phantom.sh health
```

### `run.py` Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Host to bind to |
| `--port` | `8080` | Port to bind to |
| `--reload` | off | Enable auto-reload (development) |
| `--integrated` | off | Start with socket infrastructure |
| `--security` | `basic` | Security level: `disabled`, `basic`, `enhanced`, `enterprise` |

```bash
# Basic controller start
python3 phantom_core/run.py --host 0.0.0.0 --port 8765

# With socket infrastructure and enhanced security
python3 phantom_core/run.py --integrated --security enhanced
```

### `run_integrated_phantom.py` Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Host to bind to |
| `--port` | `8080` | Controller port |
| `--socket-port` | `8081` | Socket infrastructure port |
| `--security` | `basic` | Security level: `disabled`, `basic`, `enhanced`, `enterprise` |
| `--enable-llm-taskmaster` | off | Enable LLM Task Master (optimized for GTX 1080) |
| `--reload` | off | Enable auto-reload |
| `--log-level` | `INFO` | Logging level |

```bash
# Full integrated system with LLM taskmaster
python3 phantom_core/run_integrated_phantom.py \
    --host 0.0.0.0 --port 8765 --socket-port 8082 \
    --security enhanced --enable-llm-taskmaster
```

---

## 5. Dev / Debug Tools

> Scripts for development, testing, and debugging. **NOT for production use.**

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `phantom_core/scripts/dev_tools.sh` | Linux / macOS | No | Multi-command dev toolkit — system status, benchmarks, log monitoring, worker debugging, network checks, config validation, artifact cleanup. |
| `phantom_core/validate_execution_modes.py` | Cross-platform | No | Validates execution mode logic (AUTO/HYBRID/MANUAL) without requiring a running system. Quick functional check. |
| `installer/demo_installer.py` | Cross-platform | No | Non-interactive demo of installer features — showcases system check, component manager, worker discovery, socket manager, UI integration. |
| `ui/examples/terminal_ui/terminal_ui.py` | Cross-platform | No | Interactive terminal UI example — demonstrates the PhantomUI framework with a `cmd`-based CLI. Dev/reference only. |

### `dev_tools.sh` Subcommands

```bash
# Show system status and resource usage
./phantom_core/scripts/dev_tools.sh status

# Run performance benchmarks (controller + task submission)
./phantom_core/scripts/dev_tools.sh benchmark

# Monitor system logs in real time
./phantom_core/scripts/dev_tools.sh logs

# Debug worker connections
./phantom_core/scripts/dev_tools.sh workers

# Check network connectivity
./phantom_core/scripts/dev_tools.sh network

# Validate configuration files
./phantom_core/scripts/dev_tools.sh config

# Clean up development artifacts (logs, caches, temp files)
./phantom_core/scripts/dev_tools.sh cleanup

# Show help
./phantom_core/scripts/dev_tools.sh help
```

### Execution Mode Validation

```bash
# Quick validation of AUTO/HYBRID/MANUAL modes
python3 phantom_core/validate_execution_modes.py
```

---

## 6. Monitoring Scripts

> Scripts for system health monitoring and log inspection.

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `phantom_core/scripts/monitor_system.sh` | Linux / macOS | No | **Real-time continuous system monitor** — CPU, memory, GPU utilization, service health, alerting. Runs in an infinite loop with configurable refresh interval. Press `Ctrl+C` to exit. |

### Behavior

The monitor runs **continuously by default** — there is no one-shot mode. It loops every `REFRESH_INTERVAL` seconds (default: 5), checks system metrics, and logs alerts when thresholds are exceeded.

### Alert Thresholds (Default)

| Metric | Threshold | Action |
|--------|-----------|--------|
| CPU | > 80% | Log warning |
| Memory | > 85% | Log warning |
| GPU | > 90% | Log warning |

### Usage

```bash
# Start continuous monitoring (Ctrl+C to stop)
./phantom_core/scripts/monitor_system.sh

# Logs are saved to logs/monitor.log
```

### Internal Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REFRESH_INTERVAL` | `5` | Seconds between status refreshes |
| `LOG_FILE` | `logs/monitor.log` | Log file location |
| `ALERT_THRESHOLD_CPU` | `80` | CPU alert threshold (%) |
| `ALERT_THRESHOLD_MEMORY` | `85` | Memory alert threshold (%) |
| `ALERT_THRESHOLD_GPU` | `90` | GPU alert threshold (%) |

> **Requires:** `bc` calculator for metric calculations. Install with `apt-get install bc` or `yum install bc` if missing.

---

## 7. Certs / Security Scripts

> Scripts for TLS certificate generation and security framework.

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `phantom_core/scripts/generate_certs.sh` | Linux / macOS | No | Generates a self-signed TLS certificate (RSA 2048, 365 days) for development/testing. Creates `cert.pem` and `key.pem`. |
| `phantom_core/security_framework/integrated_security.py` | Cross-platform | No | Integrated security framework — JWT authentication, role-based access control, IP filtering, rate limiting. Supports four security levels. Can be run directly for testing. |

### Certificate Generation

```bash
# Generate certs in default directory (certs/)
./phantom_core/scripts/generate_certs.sh

# Generate certs in custom directory
./phantom_core/scripts/generate_certs.sh /path/to/output
```

**Output:**
- `cert.pem` (mode 644) — Public certificate
- `key.pem` (mode 600) — Private key
- Subject: `CN=phantom-controller, O=Phantom, C=US`

### Security Levels

| Level | Description |
|-------|-------------|
| `disabled` | No authentication or encryption |
| `basic` | Token-based authentication |
| `enhanced` | JWT + IP filtering + rate limiting |
| `enterprise` | Full mutual TLS + audit logging |

---

## 8. Deployment Scripts

> Scripts for deploying Phantom to remote systems or specific environments.

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `phantom_core/linux-worker/deploy_workers.sh` | Linux | No (may need root for GPU access) | Deploys multiple worker instances based on detected GPUs (NVIDIA/AMD). Auto-configures ports starting from `BASE_WORKER_PORT`. |
| `phantom_core/complete_integration.sh` | Linux / macOS | No | Full integration setup — generates `integrated_config.yaml`, wires all components (controller, sockets, LLM taskmaster, security), runs validation. |
| `ui/redblue_matrix/matrix-web-ui/deploy-matrix-ui.sh` | Linux / macOS | No | Deploys the Matrix-style web UI to a web server. Configures Phantom backend connection. Default target: `/var/www/html`, port 3000. |

### Worker Deployment

```bash
# Deploy workers with defaults (controller at localhost:8080, base port 8090)
./phantom_core/linux-worker/deploy_workers.sh

# Deploy workers pointing to custom controller
CONTROLLER_HOST=192.168.1.100 CONTROLLER_PORT=8765 \
    ./phantom_core/linux-worker/deploy_workers.sh
```

### Integration Setup

```bash
# Run full integration (generates config, validates components)
./phantom_core/complete_integration.sh
```

### Matrix UI Deployment

```bash
# Deploy web UI (interactive prompts for host/port config)
cd ui/redblue_matrix/matrix-web-ui
./deploy-matrix-ui.sh
```

---

## 9. Health Check Scripts

> Scripts that verify Phantom is running correctly and all components are healthy.

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `installer/scripts/health_check.py` | Cross-platform | No | Post-installation health checker — validates directory structure, configuration files, service status, port availability, component connectivity. |
| `installer/scripts/post_install.sh` | Linux / macOS | Yes (root) | Post-installation setup — sets file permissions, creates systemd service, configures firewall rules, runs validation. |
| `installer/scripts/post_install.ps1` | Windows | Yes (Admin) | Post-installation setup — creates Windows service configuration, sets environment variables, creates shortcuts, runs validation. |

### Health Check

```bash
# Run health check against installation directory
python3 installer/scripts/health_check.py

# Post-install setup and verification (Linux)
sudo ./installer/scripts/post_install.sh

# Post-install setup and verification (Windows PowerShell)
.\phantom_core\installer\scripts\post_install.ps1
```

---

## 10. Test Runner

> Scripts for running the automated test suite.

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `phantom_core/scripts/run_tests.sh` | Linux / macOS | No | Comprehensive test runner — unit, integration, performance, and security tests via pytest. Generates XML reports and HTML coverage. |

### Test Runner Flags

```bash
# Run all tests
./phantom_core/scripts/run_tests.sh

# Run specific test categories
./phantom_core/scripts/run_tests.sh --unit
./phantom_core/scripts/run_tests.sh --integration
./phantom_core/scripts/run_tests.sh --performance
./phantom_core/scripts/run_tests.sh --security

# Show help
./phantom_core/scripts/run_tests.sh --help
```

### Test Configuration Defaults

| Setting | Value |
|---------|-------|
| Test directory | `tests/` |
| Minimum coverage | 70% |
| Timeout per test | 300 seconds |
| Output | `test_results/` (XML reports + HTML coverage) |

---

## 11. Utility / Infrastructure Scripts

> Scripts that support the system but are not user-facing.

| Script | Platform | Elevated? | Description |
|--------|----------|-----------|-------------|
| `phantom_core/fix_phantom_sockets.sh` | Linux | Yes (root) | **Maintenance utility** — kills orphaned processes on port 8081, patches old socket startup code in controller, fixes handle_client signature. Hardcoded to `/opt/phantom_test`. |
| `phantom_core/llm_taskmaster/lightweight_llm_setup.py` | Cross-platform | No | LLM Task Master setup and standalone runner — AI-powered task routing optimized for GTX 1080. Can be invoked directly for testing. |
| `phantom_core/linux-worker/plugins/plugin_manager.py` | Cross-platform | No | GPU plugin manager — discovers and loads GPU-specific task execution plugins. Can be run directly for plugin listing. |
| `phantom_core/linux-worker/linux_worker/gpu/gpu_info_linux.py` | Linux | No | GPU detection utility — discovers NVIDIA (CUDA) and AMD (ROCm) GPUs. Can be run directly for hardware inventory. |

---

## Empty Directories (Placeholders)

> These directories are reserved for future use and contain only `.gitkeep` files.

| Directory | Purpose |
|-----------|---------|
| `installer/uninstaller/` | Placeholder — uninstaller modules will be added here |
| `ui/examples/custom_react_ui/` | Placeholder — custom React UI example will be added here (see [UI_FRAMEWORK.md](UI_FRAMEWORK.md) for the interface contract) |

---

## Elevated Privilege Summary

> Scripts requiring Administrator (Windows) or root (Linux/macOS) access.

| Script | Platform | Reason |
|--------|----------|--------|
| `package/install.sh` | Linux | Writes to `/opt/phantom`, creates systemd service |
| `package/install.bat` | Windows | Writes to `%ProgramFiles%`, creates Windows service |
| `package/uninstall.sh` | Linux | Stops services, removes system files, frees ports |
| `package/uninstall.bat` | Windows | Stops services, removes system files |
| `installer/phantom_installer.sh` | Linux / macOS | Wraps `phantom_installer.py` (system-level install) |
| `installer/phantom_installer.ps1` | Windows | Wraps `phantom_installer.py` (system-level install) |
| `installer/phantom_installer.py` | Cross-platform | System-level file operations, service creation |
| `installer/phantom_installer_windows.py` | Windows | Service creation, registry operations |
| `installer/windows_gui_installer.py` | Windows | System-level installation via GUI |
| `installer/phantom_uninstaller.py` | Cross-platform | Removes system files, stops services |
| `installer/phantom_uninstaller.sh` | Linux / macOS | Wraps uninstaller Python script |
| `installer/phantom_uninstaller.ps1` | Windows | Stops services, removes system files |
| `installer/scripts/post_install.sh` | Linux / macOS | Sets permissions, creates systemd service, firewall rules |
| `installer/scripts/post_install.ps1` | Windows | Creates Windows service, environment variables |
| `phantom_core/fix_phantom_sockets.sh` | Linux | Kills processes, modifies system files via `sudo` |

---

## Environment Variables Reference

> Environment variables that modify script behavior across multiple scripts.

| Variable | Default | Affects | Description |
|----------|---------|---------|-------------|
| `CONTROLLER_HOST` | `127.0.0.1` | `start_complete_phantom.sh`, `deploy_workers.sh` | Host address for the Phantom controller |
| `CONTROLLER_PORT` | `8080` | `start_complete_phantom.sh`, `deploy_workers.sh` | Controller API port |
| `SOCKET_PORT` | `8081` | `start_complete_phantom.sh` | Socket infrastructure port |
| `SECURITY_LEVEL` | `basic` | `start_complete_phantom.sh` | Security level: `disabled`, `basic`, `enhanced`, `enterprise` |
| `ENABLE_LLM_TASKMASTER` | `true` | `start_complete_phantom.sh` | Enable/disable LLM Task Master |
| `BASE_WORKER_PORT` | `8090` | `deploy_workers.sh` | Starting port for worker instances |

---

## Port Reference

| Port | Protocol | Component | Configurable? | Set By |
|------|----------|-----------|---------------|--------|
| 8765 | HTTP / WebSocket | Controller API | Yes (`--port`) | `run.py`, `run_integrated_phantom.py` |
| 8082 | WebSocket | Socket Infrastructure | Yes (`--socket-port`) | `run_integrated_phantom.py` |
| 8080 | HTTP | Default controller / Web UI | Yes (`CONTROLLER_PORT`) | `start_complete_phantom.sh` |
| 8081 | WebSocket | Socket Infrastructure (alt) | Yes (`SOCKET_PORT`) | `start_complete_phantom.sh` |
| 8090+ | TCP | Worker instances | Yes (`BASE_WORKER_PORT`) | `deploy_workers.sh` |
| 3000 | HTTP | Matrix Web UI (deployed) | Yes | `deploy-matrix-ui.sh` |

> **Note:** Ports 8080/8081 and 8765/8082 represent two different default configurations. The `start_complete_phantom.sh` script uses 8080/8081. The Python entry points (`run.py`, `run_integrated_phantom.py`) default to 8080/8081 but are typically configured to 8765/8082 for production. See [ARCHITECTURE.md](ARCHITECTURE.md) for the canonical production port assignment.

---

## Related Documentation

- [README.md](../README.md) — Project overview and quick start
- [INSTALLATION.md](../INSTALLATION.md) — Full installation guide
- [UNINSTALLATION.md](../UNINSTALLATION.md) — Full uninstallation guide
- [ARCHITECTURE.md](ARCHITECTURE.md) — System architecture and component layout
- [UI_FRAMEWORK.md](UI_FRAMEWORK.md) — UI framework interface contract
- [SECURITY.md](../SECURITY.md) — Security policy and vulnerability reporting
- [PHANTOM_TEN_COMMANDMENTS.md](../PHANTOM_TEN_COMMANDMENTS.md) — Operational governance

---

*This reference is auto-catalogued from the Phantom v1.0.0 unified repository.*
*To report a missing script or incorrect entry, open an issue tagged `documentation`.*
