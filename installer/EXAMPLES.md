# Installer Usage Examples

## Basic Interactive Installation

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

## Demonstration Mode

Run a non-interactive demo to see installer features:

```bash
cd installer
python3 demo_installer.py
```

Example output:
```
======================================================================
    🚀 PHANTOM DISTRIBUTED COMPUTE FABRIC
    Unified Installation Wizard
======================================================================

DEMO: System Requirements Check
============================================================
✅ PASSED:
  • Python 3.12.3 (>= 3.8)
  • Operating System: Linux
  • Disk space: 91.02 GB available (>= 5.0 GB)
  • Virtual environment support: Available
  • Network connectivity: OK
  • Git: git version 2.52.0
============================================================

DEMO: Component Selection
======================================================================
Available Components:
  [✓ Required] Phantom Core
  [  Optional] LLM Task Master
  [  Optional] Socket Infrastructure
  [  Optional] RedBlue UI
  ...
```

## Installation with Custom Directory

```bash
./phantom_installer.sh --install-dir ~/my-phantom
```

## Dry Run (Preview Only)

Preview what will be installed without making changes:

```bash
./phantom_installer.sh --dry-run
```

## Skip Virtual Environment

Install without creating a virtual environment:

```bash
./phantom_installer.sh --skip-venv
```

## Health Check After Installation

Verify installation:

```bash
python3 scripts/health_check.py /opt/phantom
```

Output example:
```
============================================================
HEALTH CHECK REPORT
============================================================

✅ PASSED:
  • Directory exists: config/
  • Directory exists: logs/
  • Directory exists: data/
  • Config file exists: phantom_config.yaml
  • Virtual environment exists
  • Python executable found in venv
============================================================
✅ Installation health check passed!
============================================================
```

## Post-Installation Scripts

### Linux/Mac

Run post-installation setup:
```bash
cd /opt/phantom
./scripts/post_install.sh
```

This creates:
- Systemd service configuration
- Convenience scripts (start_phantom.sh, stop_phantom.sh, status_phantom.sh)
- File permissions setup

### Windows

Run post-installation setup:
```powershell
cd C:\Program Files\Phantom
.\scripts\post_install.ps1
```

This creates:
- Windows service configuration
- Convenience scripts (start_phantom.ps1, stop_phantom.ps1, status_phantom.ps1)

## Start Phantom After Installation

### Linux/Mac
```bash
# Activate virtual environment
source /opt/phantom/activate_phantom.sh

# Start Phantom
/opt/phantom/start_phantom.sh

# Check status
/opt/phantom/status_phantom.sh
```

### Windows
```powershell
# Activate virtual environment
.\activate_phantom.bat

# Start Phantom
.\start_phantom.ps1

# Check status
.\status_phantom.ps1
```

## Worker Discovery Examples

### Manual Discovery Mode
```
Select worker discovery mode:
  [1] Manual selection (basic ping scan)
  [2] Comprehensive auto-detection
  [3] Skip (configure workers later)

Selection: 1

🔍 Scanning network 192.168.1.0/24...
  Found: 192.168.1.102
  Found: 192.168.1.103
  Found: 192.168.1.104

Discovered workers:
  ✓ [1] 192.168.1.102 - Worker1
  ✓ [2] 192.168.1.103 - Worker2
  ✓ [3] 192.168.1.104 - Worker3

Select workers to configure [enter space-separated numbers]: 1 2
```

### Comprehensive Discovery Mode
```
Select worker discovery mode:
  [1] Manual selection (basic ping scan)
  [2] Comprehensive auto-detection
  [3] Skip (configure workers later)

Selection: 2

🔍 Auto-discovering Phantom workers on 192.168.1.0/24...
  ✓ Found: 192.168.1.102:8090 - Worker1
  ✓ Found: 192.168.1.103:8091 - Worker2

Discovered workers:
  ✓ [1] 192.168.1.102 - Worker1 (GPU: RTX 3080)
  ✓ [2] 192.168.1.103 - Worker2 (GPU: RTX 4090)

Select workers to configure? [Y/n]: Y
```

## Component Selection Examples

### Install All Components
```
Select components to install:
(Required components will be installed automatically)

  [✓ Required] Phantom Core
      Core distributed compute fabric
  [  Optional] LLM Task Master
      AI-powered intelligent task routing
  [  Optional] Linux Workers
      Linux worker nodes with GPU support
  [  Optional] Security Framework
      Multi-level security with authentication
  [  Optional] Socket Infrastructure
      WebSocket-based real-time communication
  [  Optional] RedBlue UI
      Web-based monitoring and control UI

Install all optional components? [Y/n]: Y
```

### Selective Installation
```
Install all optional components? [Y/n]: n

Select optional components to install:
  [1] LLM Task Master
  [2] Linux Workers
  [3] Security Framework
  [4] Socket Infrastructure
  [5] RedBlue UI

Enter space-separated numbers (e.g., '1 3 5') or 'all' for all options
Selection: 1 4 5

Selected Components:
  • Phantom Core
  • LLM Task Master
  • Socket Infrastructure
  • RedBlue UI
```

## Security Configuration Examples

```
Select security level:
  [1] Disabled
  [2] Development
  [3] Production

Select option [1-3] (default: 1): 2

✅ Security level set to: development
```

## Network Configuration Examples

```
Controller host address [localhost]: 192.168.1.103
Controller port [8080]: 8080
Socket port [8081]: 8081
UI port [3000]: 3000
```

## Full Installation Summary

```
====================================
Installation Summary
====================================
Installation Directory: /opt/phantom
Controller: 192.168.1.103:8080
Security Level: development
Socket Infrastructure: Enabled
RedBlue UI: Enabled

Selected Components:
  • Phantom Core
  • LLM Task Master
  • Socket Infrastructure
  • Security Framework
  • RedBlue UI

Configured Workers: 2
  • 192.168.1.102 - Worker1
  • 192.168.1.103 - Worker2

Proceed with installation? [Y/n]: Y
```
