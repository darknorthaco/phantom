# Phantom Package Distribution

This directory contains professional installation and packaging scripts for the Phantom distributed computing platform.

## Directory Structure

```
package/
├── build_complete.sh      # Linux/macOS package builder
├── build_complete.bat     # Windows package builder
├── install.sh            # Linux/macOS installation wizard
├── install.bat           # Windows installation wizard
├── uninstall.sh          # Linux/macOS uninstaller
├── uninstall.bat         # Windows uninstaller
└── README.md             # This file
```

## Installation Methods

### Windows

#### GUI Installer (Recommended)
```cmd
python installer\windows_gui_installer.py
```
- Professional wizard interface
- Component selection
- System requirements checking
- Progress tracking with detailed logs

#### Command Line Installer
```cmd
install.bat
```
- Automated installation script
- Service setup and shortcut creation
- Port verification and cleanup

### Linux/macOS

#### Installation Wizard
```bash
sudo ./install.sh
```
- Interactive component selection
- Systemd service management
- Requirements verification
- Professional installation experience

## Uninstallation

### Windows
```cmd
uninstall.bat
```
- Complete cleanup including services, shortcuts, and registry
- Process termination and port freeing
- Backup creation before removal

### Linux/macOS
```bash
sudo ./uninstall.sh
```
- Service removal and process cleanup
- Port verification and freeing
- Complete file removal with backup

## Building Packages

### Linux/macOS
```bash
./build_complete.sh
```
Creates a complete installation package with:
- Component organization
- Checksum verification
- Metadata generation
- Compressed archive

### Windows
```cmd
build_complete.bat
```
Creates a Windows installation package with:
- Directory structure setup
- File copying and organization
- Archive creation

## Package Contents

When built, the package contains:

- `phantom_core/` - Core distributed computing engine
- `ui/` - User interface components
  - `redblue_matrix/` - Default professional UI
  - `ui_framework/` - Swappable UI architecture
  - `examples/` - Example UI implementations
- `docs/` - Complete documentation
- `installer/` - Installation scripts and modules
- `requirements.txt` - Python dependencies

## System Requirements

### Minimum Requirements
- Python 3.8+
- 500MB disk space
- Administrator/root privileges for installation
- Network ports 8765, 8082, 8080 available

### Recommended Requirements
- Python 3.10+
- 1GB RAM
- Multi-core CPU
- GPU (optional, for AI workloads)

## Post-Installation

After installation, Phantom will be available at:
- **Web UI**: http://localhost:8080
- **API**: http://localhost:8765
- **WebSocket**: localhost:8082

The system runs as a service with automatic startup.

## Troubleshooting

### Installation Issues
- Ensure administrator/root privileges
- Check that required ports are not in use
- Verify Python version compatibility
- Check available disk space

### Service Issues
- Check service status: `sc query Phantom` (Windows) or `systemctl status phantom` (Linux)
- Review service logs in Event Viewer (Windows) or journalctl (Linux)
- Verify network port availability

### Port Conflicts
- Run uninstaller to free ports
- Manually terminate conflicting processes
- Configure alternative ports if needed

## Support

For issues or questions:
- Check the documentation in `docs/`
- Review installation logs
- Contact support with system information