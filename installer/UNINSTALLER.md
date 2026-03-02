# Phantom Uninstaller Documentation

## Overview

The Phantom Unified Uninstallation Wizard provides a safe and complete way to remove Phantom Distributed Compute Fabric from your system. It supports two modes:

- **Safe Mode** (default): Stops services and removes runtime files, but preserves your installation and configurations
- **Full Mode**: Completely removes Phantom, including all files, services, and configurations

## Quick Start

### Linux/macOS

```bash
cd installer
./phantom_uninstaller.sh
```

### Windows

```powershell
cd installer
.\phantom_uninstaller.ps1
```

## Uninstall Modes

### Safe Mode (Default)

Safe mode is ideal when you want to stop Phantom services temporarily or clean up runtime artifacts without losing your installation or configuration.

**What Safe Mode Does:**
- ✓ Stop all Phantom services (systemd, Windows services, launchd)
- ✓ Stop all Phantom processes using PID files
- ✓ Remove PID files
- ✓ Remove log files
- ✓ Close network ports
- ✓ Release GPU locks

**What Safe Mode Preserves:**
- ✗ Installation directory
- ✗ Virtual environment
- ✗ Configuration files
- ✗ Python packages
- ✗ Source code

**Usage:**
```bash
# Linux/Mac
./phantom_uninstaller.sh --mode safe

# Windows
.\phantom_uninstaller.ps1 -Mode safe
```

### Full Mode

Full mode completely removes Phantom from your system. Use this when you want to do a clean uninstall.

**What Full Mode Does:**
- ✓ Everything from Safe Mode
- ✓ Remove service definitions (systemd units, Windows services, launchd plists)
- ✓ Remove virtual environment
- ✓ Remove all installation files
- ✓ Remove all directories
- ✓ Remove installation manifest
- ✓ Optional: Backup configurations before removal

**Usage:**
```bash
# Linux/Mac
./phantom_uninstaller.sh --mode full

# Windows
.\phantom_uninstaller.ps1 -Mode full
```

## Command-Line Options

### Common Options

| Option | Description |
|--------|-------------|
| `--install-dir <path>` | Specify installation directory (auto-detected if not provided) |
| `--mode <safe\|full>` | Uninstall mode (default: safe) |
| `--dry-run` | Preview what would be removed without making changes |
| `--force` | Skip confirmation prompts |
| `--help` | Show help message |

### Full Mode Only

| Option | Description |
|--------|-------------|
| `--no-backup` | Skip configuration backup (not recommended) |

## Examples

### Basic Usage

```bash
# Interactive safe uninstall (default)
./phantom_uninstaller.sh

# Interactive full uninstall
./phantom_uninstaller.sh --mode full

# Specify installation directory
./phantom_uninstaller.sh --install-dir /opt/phantom --mode full
```

### Dry Run (Preview)

Preview what would be removed without making any changes:

```bash
# Preview safe uninstall
./phantom_uninstaller.sh --dry-run

# Preview full uninstall
./phantom_uninstaller.sh --mode full --dry-run
```

### Non-Interactive

Skip confirmation prompts (useful for automation):

```bash
# Force safe uninstall
./phantom_uninstaller.sh --force

# Force full uninstall without backup
./phantom_uninstaller.sh --mode full --force --no-backup
```

## What Gets Removed

### Services

The uninstaller automatically detects and removes:

- **Linux**: systemd service units from `/etc/systemd/system/`
- **Windows**: Windows services created with `sc` or `New-Service`
- **macOS**: launchd plists from `~/Library/LaunchAgents/` or `/Library/LaunchDaemons/`

### Processes

The uninstaller stops processes by:

1. Stopping services using system service managers
2. Reading PID files and terminating processes
3. Using graceful shutdown (SIGTERM) first, then force kill (SIGKILL) if needed

### Files and Directories

In **safe mode**, only runtime files are removed:
- PID files (`*.pid`)
- Log files (from manifest or found in installation directory)
- Socket files

In **full mode**, everything is removed:
- All files tracked in the installation manifest
- The entire installation directory
- Virtual environment
- Service definition files

### Configuration Backup

In full mode with backup enabled (default), configurations are backed up to:

```
<parent_of_install_dir>/phantom_backup_<timestamp>/
```

Example:
```
/opt/phantom_backup_20260218_150000/
  ├── phantom_config.yaml
  ├── worker_config.json
  └── security_config.yaml
```

## Installation Manifest

The uninstaller uses an installation manifest (`.phantom_install_manifest.json`) to track what was installed. This manifest is created by the installer and includes:

- Installed components
- Created files and directories
- Service definitions
- Configuration files
- PID files
- Log files
- Virtual environment path

If no manifest is found, the uninstaller will attempt cleanup based on the directory structure.

## Auto-Detection

If you don't specify `--install-dir`, the uninstaller searches for Phantom in common locations:

1. `~/phantom`
2. `/opt/phantom`
3. `/usr/local/phantom`
4. `~/.phantom`
5. Current working directory

The first directory containing `.phantom_install_manifest.json` is used.

## Permissions

### Linux/macOS

Removing systemd services requires `sudo` privileges. The uninstaller will:

1. Check if `sudo` is available
2. Use `sudo` for service management operations
3. Warn if `sudo` is not available

**Running as root is not recommended** but is supported with a warning prompt.

### Windows

Removing Windows services requires administrator privileges. Run PowerShell as Administrator:

```powershell
# Right-click PowerShell -> "Run as Administrator"
cd installer
.\phantom_uninstaller.ps1 -Mode full
```

## Troubleshooting

### "Could not find Phantom installation"

If auto-detection fails:

```bash
./phantom_uninstaller.sh --install-dir /path/to/phantom
```

### "Permission denied" when removing services

On Linux/macOS, ensure `sudo` is available:

```bash
sudo ./phantom_uninstaller.sh --mode full
```

On Windows, run PowerShell as Administrator.

### Processes still running after uninstall

Check for orphaned processes:

```bash
# Linux/macOS
ps aux | grep phantom
kill <PID>

# Windows
Get-Process | Where-Object {$_.ProcessName -like "*phantom*"}
Stop-Process -Id <PID> -Force
```

### Incomplete uninstall

If the uninstaller fails partway through:

1. Re-run the uninstaller with `--force`
2. Check the error messages for specific issues
3. Manually remove remaining files if necessary

### Manual cleanup (if uninstaller fails)

```bash
# Stop services
sudo systemctl stop phantom
sudo systemctl disable phantom

# Remove files
sudo rm -rf /opt/phantom
sudo rm /etc/systemd/system/phantom.service
sudo systemctl daemon-reload
```

## Safety Features

1. **Confirmation prompts** - Interactive mode asks for confirmation before removing anything
2. **Dry run** - Preview changes with `--dry-run` before executing
3. **Configuration backup** - Automatically backs up configs in full mode (unless `--no-backup`)
4. **Graceful shutdown** - Uses SIGTERM before SIGKILL
5. **Safe mode default** - Default mode preserves installation and configs
6. **Manifest tracking** - Only removes files explicitly tracked by installer

## Integration with CI/CD

The uninstaller supports non-interactive mode for automation:

```bash
# In your CI/CD pipeline
./phantom_uninstaller.sh --mode full --force --no-backup

# In Ansible playbook
- name: Uninstall Phantom
  command: /opt/phantom/installer/phantom_uninstaller.sh --mode full --force
  args:
    chdir: /opt/phantom/installer
```

## Comparison: Safe vs Full

| Feature | Safe Mode | Full Mode |
|---------|-----------|-----------|
| Stop services | ✓ | ✓ |
| Stop processes | ✓ | ✓ |
| Remove PID files | ✓ | ✓ |
| Remove log files | ✓ | ✓ |
| Remove services | ✗ | ✓ |
| Remove venv | ✗ | ✓ |
| Remove configs | ✗ | ✓ |
| Remove installation | ✗ | ✓ |
| Backup configs | N/A | ✓ (optional) |
| Time to re-install | Fast | Slow |
| Use case | Temporary stop | Complete removal |

## Related Documentation

- [Installation Guide](README.md) - Installing Phantom
- [PHASE_1_INSTALLER_UNINSTALLER_AUDIT.md](../phantom_core/PHASE_1_INSTALLER_UNINSTALLER_AUDIT.md) - Audit findings and recommendations
- [UNINSTALL_WIZARD_PROPOSALS.md](../phantom_core/UNINSTALL_WIZARD_PROPOSALS.md) - Original design proposals

## Support

If you encounter issues with the uninstaller:

1. Run with `--dry-run` to see what would be removed
2. Check the error messages for specific issues
3. Review the troubleshooting section above
4. Create an issue on GitHub with:
   - Your OS and version
   - Installation directory
   - Full error output
   - Output of `--dry-run`
