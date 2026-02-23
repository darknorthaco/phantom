# Installation Guide

## System Requirements

### Minimum Requirements
- **Python:** 3.8 or higher
- **Disk Space:** 500 MB
- **RAM:** 512 MB (1 GB recommended)
- **Privileges:** Administrator (Windows) or root (Linux/macOS)
- **Network Ports:** 8765, 8082, 8080 must be available

### Supported Platforms

| Platform | Status | Installer |
|----------|--------|-----------|
| Windows 10/11 | Supported | GUI wizard + CLI batch |
| Ubuntu 20.04+ | Supported | CLI shell script + systemd |
| Debian 11+ | Supported | CLI shell script + systemd |
| RHEL 8+ / CentOS Stream | Supported | CLI shell script + systemd |
| macOS 12+ | Beta | CLI shell script |

---

## Windows Installation

### Option 1: GUI Installer (Recommended)

The GUI installer provides a wizard-style experience with system requirements checking, component selection, and progress tracking.

```cmd
python installer\windows_gui_installer.py
```

The wizard will guide you through:
1. Welcome and feature overview
2. License agreement acceptance
3. Installation type selection (Complete / Core Only / Custom)
4. System requirements verification
5. Installation with real-time progress
6. Completion summary with access points

**Requirements:** PyQt6 (installed automatically if missing)

### Option 2: CLI Installer

Run the batch installer as Administrator:

```cmd
package\install.bat
```

This provides:
- Administrator privilege checking
- System requirements verification
- Component selection (Complete / Core Only / Custom)
- Python virtual environment setup
- Windows service creation (`Phantom` service)
- Desktop and Start Menu shortcuts
- Port verification

### Post-Installation (Windows)

After installation:
- **Web UI:** Open http://localhost:8080
- **Service Management:**
  - Start: `sc start Phantom`
  - Stop: `sc stop Phantom`
  - Status: `sc query Phantom`
- **Desktop shortcut** opens the Web UI directly

---

## Linux / macOS Installation

### CLI Installer

Run the shell installer as root:

```bash
sudo ./package/install.sh
```

This provides:
- Root privilege verification
- Component selection (Complete / Core Only / Custom)
- Python virtual environment setup
- Systemd service creation and enablement
- Port verification and cleanup
- Post-installation verification

### Installation Options

| Option | Components |
|--------|-----------|
| **Complete** (recommended) | Phantom Core + RedBlue Matrix UI + all components |
| **Core Only** | Phantom Core engine only, no UI |
| **Custom** | Choose individual components |

### Post-Installation (Linux/macOS)

After installation:
- **Web UI:** Open http://localhost:8080
- **Service Management:**
  - Start: `sudo systemctl start phantom`
  - Stop: `sudo systemctl stop phantom`
  - Status: `sudo systemctl status phantom`
  - Logs: `sudo journalctl -u phantom -f`

---

## Manual Installation

If you prefer to install manually without the wizard:

```bash
# 1. Clone the repository
git clone <repo-url> phantom
cd phantom

# 2. Create a virtual environment
python -m venv venv

# 3. Activate the environment
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 4. Install dependencies
pip install -r phantom_core/requirements.txt

# 5. Run Phantom
python phantom_core/run_integrated_phantom.py
```

---

## Verification

After installation, verify the system is running:

1. **Check service status:**
   - Windows: `sc query Phantom`
   - Linux: `systemctl status phantom`

2. **Check port availability:**
   - `netstat -tlnp | grep -E '8765|8082|8080'` (Linux)
   - `netstat -ano | findstr "8765 8082 8080"` (Windows)

3. **Access the Web UI:**
   - Open http://localhost:8080 in a browser

4. **Check API endpoint:**
   - `curl http://localhost:8765` or open in a browser

---

## Troubleshooting

### Port Already in Use

If installation reports ports are in use:

```bash
# Linux — find what's using the port
sudo lsof -i :8765
sudo ss -tlnp | grep 8765

# Windows — find what's using the port
netstat -ano | findstr :8765
```

Kill the conflicting process or choose alternative ports.

### Python Version Issues

Phantom requires Python 3.8+. Verify your version:

```bash
python --version
# or
python3 --version
```

### Permission Denied

Installation requires elevated privileges:
- **Windows:** Right-click Command Prompt → "Run as administrator"
- **Linux/macOS:** Use `sudo` before the install command

### Service Fails to Start

Check the service logs:
- **Windows:** Event Viewer → Windows Logs → Application
- **Linux:** `sudo journalctl -u phantom -f`

Common causes:
- Python virtual environment not created properly
- Missing dependencies in `requirements.txt`
- Port conflicts with other services

---

## Next Steps

- Read the [README.md](README.md) for feature overview
- Review [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- Explore the [UI Framework](docs/UI_FRAMEWORK.md) to customize the interface
- See [UNINSTALLATION.md](UNINSTALLATION.md) for removal instructions
