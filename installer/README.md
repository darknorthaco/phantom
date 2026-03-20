# Phantom Unified Installation Wizard

> **Canonical install path:** Use the **Tauri desktop app** (`phantom_app/`). See **[INSTALL.md](../INSTALL.md)** in the repository root.  
> This Python/shell tree is **deprecated** for end users. Entry points exit unless **`PHANTOM_ALLOW_LEGACY_INSTALLER=1`**. Policy: [CANONICAL_INSTALL_TAURI.md](CANONICAL_INSTALL_TAURI.md).

### Offline bundle (Phase 3, maintainer / air-gap)

- **Generator:** [`offline_bundle.py`](offline_bundle.py) — `generate` / `verify` subcommands; produces `wheelhouse/`, `engine/`, `models/model_catalogue.json`, `manifest.json` (SHA-256 for all files).  
- **Verification helpers:** [`offline_bundle_lib.py`](offline_bundle_lib.py) — shared with tests.  
- **Pip helper:** [`offline_install_helper.py`](offline_install_helper.py) — `--no-index` install from a bundle.  
- **Deploy requirements pin:** [`requirements-deploy.txt`](requirements-deploy.txt) — must match Tauri `install_python_deps`.  
- **Documentation:** [../docs/offline_install.md](../docs/offline_install.md)

## Overview

The Phantom Unified Installation Wizard is a modular, cross-platform installer that enables both Linux and Windows users to install the complete Phantom ecosystem with a single execution flow.

**NEW:** Phantom now includes a comprehensive uninstaller for safe and complete removal. See [UNINSTALLER.md](UNINSTALLER.md) for details.

## Features

- **Unified Entry Point**: Single wizard for the entire Phantom ecosystem
- **Cross-Platform**: Supports Linux, macOS, and Windows
- **Modular Design**: Toggle components independently
- **Worker Discovery**: Manual and comprehensive auto-detection modes
- **Virtual Environment Management**: Isolated Python environment setup
- **Optional UI Integration**: RedBlue UI can be added or removed
- **Interactive CLI**: User-friendly command-line interface
- **Installation Manifest**: Tracks all installed files for safe uninstallation

> **UI Source:** RedBlue UI lives in the private repository:
> https://github.com/darknorthaco/redblue-private

## Components

The installer can set up the following components:

1. **Phantom Core** (Required) - Distributed compute fabric
2. **LLM Task Master** (Optional) - Mode-aware task routing
3. **Linux Workers** (Optional) - Linux worker nodes with GPU support
4. **Windows Workers** (Optional) - Windows worker nodes with GPU support
5. **Security Framework** (Optional) - Multi-level security
6. **Socket Infrastructure** (Optional) - Real-time WebSocket communication
7. **RedBlue UI** (Optional) - Web-based monitoring and control (from `darknorthaco/redblue-private`)

## Quick Start

### Linux/Mac

```bash
cd installer
./phantom_installer.sh
```

### Windows

```powershell
cd installer
.\phantom_installer.ps1
```

## Installation Options

### Interactive Mode (Default)

```bash
./phantom_installer.sh
```

The wizard will guide you through:
1. System requirements check
2. Installation directory selection
3. Component selection
4. Network configuration
5. Worker discovery
6. Socket infrastructure setup
7. UI integration
8. Security configuration
9. Installation execution

### Command-Line Options

```bash
# Preview installation without making changes
./phantom_installer.sh --dry-run

# Skip virtual environment creation
./phantom_installer.sh --skip-venv

# Specify installation directory
./phantom_installer.sh --install-dir /opt/phantom
```

## Command-Line Reference

### Flags

| Flag | Description |
|------|-------------|
| `--silent` | No prompts; uses defaults for all steps |
| `--type=<all\|controller\|worker>` | Pre-select component set (default: `all`) |
| `--force` | Skip all confirmation prompts |
| `--dry-run` | Preview installation without making changes |
| `--install-dir <path>` | Override installation directory |
| `--log-file <path>` | Write timestamped log output to file |
| `--skip-venv` | Skip virtual environment creation |

### Installation Types

| Type | Components installed |
|------|---------------------|
| `all` (default) | All optional components |
| `controller` | `phantom_core` + LLM Task Master + Security Framework + Socket Infrastructure |
| `worker` | `phantom_core` + Linux/Windows Workers (OS-appropriate) + Security Framework |

### Examples

**Linux/Mac:**
```bash
# Interactive (default)
./phantom_installer.sh

# Silent full install to /opt/phantom, log to file
./phantom_installer.sh --silent --install-dir /opt/phantom --log-file /var/log/phantom_install.log

# Silent controller-only install
./phantom_installer.sh --silent --type=controller

# Silent worker install, force through system check failures
./phantom_installer.sh --silent --type=worker --force

# Dry-run preview
./phantom_installer.sh --dry-run
```

**Windows (PowerShell):**
```powershell
# Interactive (default)
.\phantom_installer.ps1

# Silent install with defaults
.\phantom_installer.ps1 -Silent

# Silent worker install with log file
.\phantom_installer.ps1 -Silent -Type worker -LogFile C:\Logs\phantom_install.log

# Dry-run preview
.\phantom_installer.ps1 -DryRun

# Show help
.\phantom_installer.ps1 -Help
```

## Worker Discovery

### Manual Mode
- Performs basic LAN ping scan
- User selects workers from discovered devices
- Quick and simple

### Comprehensive Mode
- Auto-detects workers with Phantom capability
- Queries worker information (GPU, etc.)
- Allows accept/deselect/continue flow

### Skip Mode
- Configure workers later
- Useful for single-node installations

## Directory Structure

After installation, you'll have:

```
/opt/phantom/  (or your chosen directory)
├── config/                    # Configuration files
│   ├── phantom_config.yaml   # Main config
│   ├── worker_*_config.json  # Worker configs
│   └── ...
├── logs/                      # Log files
├── data/                      # Data storage
├── venvs/                     # Virtual environments
│   └── phantom/              # Main venv
├── activate_phantom.sh        # Convenience activation script
├── environment.sh             # Environment setup
├── start_phantom.sh           # Start script
├── stop_phantom.sh            # Stop script
└── status_phantom.sh          # Status check script
```

## Post-Installation

### 1. Activate Virtual Environment

**Linux/Mac:**
```bash
source /opt/phantom/activate_phantom.sh
```

**Windows:**
```powershell
.\activate_phantom.bat
```

### 2. Verify Installation

```bash
python installer/scripts/health_check.py /opt/phantom
```

### 3. Start Phantom

```bash
/opt/phantom/start_phantom.sh
```

### 4. Check Status

```bash
/opt/phantom/status_phantom.sh
```

Or check directly:
```bash
curl http://localhost:8080/health
```

## Configuration

### Main Configuration

Edit `config/phantom_config.yaml` to customize:
- Controller settings (host, port)
- Security level
- Socket infrastructure
- UI integration
- Logging preferences

### Worker Configuration

Edit `config/worker_*_config.json` for each worker:
- Worker ID
- Controller connection
- GPU settings
- Performance tuning

## Systemd Service (Linux)

To run Phantom as a systemd service:

```bash
# Copy service file
sudo cp /tmp/phantom.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable phantom.service

# Start service
sudo systemctl start phantom.service

# Check status
sudo systemctl status phantom.service
```

## Windows Service

To run Phantom as a Windows service:

```powershell
# Run as Administrator
cd C:\Program Files\Phantom
.\install_service.ps1

# Start service
Start-Service PhantomController

# Check status
Get-Service PhantomController
```

## Troubleshooting

### Python Not Found

**Linux/Mac:**
```bash
# Install Python 3.8+
sudo apt-get install python3 python3-pip  # Debian/Ubuntu
brew install python3                       # macOS
```

**Windows:**
- Download from https://python.org
- Check "Add Python to PATH" during installation

### Permission Denied

**Linux/Mac:**
```bash
chmod +x phantom_installer.sh
```

### Port Already in Use

Check which process is using the port:

**Linux/Mac:**
```bash
lsof -i :8080
```

**Windows:**
```powershell
netstat -ano | findstr :8080
```

### Virtual Environment Issues

If venv creation fails, ensure `python3-venv` is installed:

```bash
sudo apt-get install python3-venv  # Debian/Ubuntu
```

## Advanced Usage

### Dry Run

Preview what will be installed without making changes:

```bash
./phantom_installer.sh --dry-run
```

### Custom Installation Directory

```bash
./phantom_installer.sh --install-dir ~/my-phantom
```

### Skip Virtual Environment

If you want to manage the virtual environment separately:

```bash
./phantom_installer.sh --skip-venv
```

## Uninstallation

To remove Phantom:

1. Stop services:
   ```bash
   /opt/phantom/stop_phantom.sh
   ```

2. Remove systemd service (if installed):
   ```bash
   sudo systemctl stop phantom.service
   sudo systemctl disable phantom.service
   sudo rm /etc/systemd/system/phantom.service
   sudo systemctl daemon-reload
   ```

3. Remove installation directory:
   ```bash
   rm -rf /opt/phantom
   ```

## Support

For issues or questions:
- Check documentation: `README.md`, `DEPLOYMENT_GUIDE.md`
- Review logs: `logs/phantom.log`
- Run health check: `python installer/scripts/health_check.py`

## Development

### Module Structure

```
installer/
├── phantom_installer.py          # Main orchestrator
├── phantom_installer.sh           # Linux/Mac entry
├── phantom_installer.ps1          # Windows entry
├── phantom_installer_windows.py   # Windows-specific logic
├── modules/                       # Core modules
│   ├── system_check.py
│   ├── component_manager.py
│   ├── worker_discovery.py
│   ├── socket_manager.py
│   ├── venv_setup.py
│   ├── ui_integration.py
│   └── config_generator.py
├── ui/                            # UI components
│   ├── cli_wizard.py
│   ├── progress_display.py
│   └── prompts.py
├── config/                        # Templates
├── scripts/                       # Post-install scripts
└── README.md                      # This file
```

### Testing

Run installer in dry-run mode to test:

```bash
./phantom_installer.sh --dry-run
```

## Uninstalling Phantom

Phantom includes a comprehensive uninstaller with two modes:

### Safe Mode (Default)
Stops services and removes runtime files, but preserves your installation and configurations:

```bash
# Linux/Mac
./phantom_uninstaller.sh

# Windows
.\phantom_uninstaller.ps1
```

### Full Mode
Completely removes Phantom, including all files and configurations (with optional backup):

```bash
# Linux/Mac
./phantom_uninstaller.sh --mode full

# Windows
.\phantom_uninstaller.ps1 -Mode full
```

For detailed uninstallation documentation, see [UNINSTALLER.md](UNINSTALLER.md).

## Installation Manifest

The installer creates an installation manifest (`.phantom_install_manifest.json`) that tracks:
- Installed components
- Created files and directories
- Service definitions
- Configuration files
- PID files and log files
- Virtual environment path

This manifest enables safe, complete uninstallation and helps track what was installed.

## License

Dual-licensed: MIT (open-source) and Commercial. See LICENSE and LICENSE-COMMERCIAL.md for details.
