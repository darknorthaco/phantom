# Phantom Installer - Windows Entry Point
# PowerShell Script

param(
    [string]$InstallDir = "",
    [ValidateSet("all", "controller", "worker")]
    [string]$Type = "all",
    [switch]$Silent = $false,
    [switch]$DryRun = $false,
    [switch]$Force = $false,
    [string]$LogFile = "",
    [switch]$SkipVenv = $false,
    [switch]$Help = $false
)

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO]    $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR]   $Message" -ForegroundColor Red
}

if ($Help) {
    Write-Host @"
Phantom Distributed Compute Fabric - Installer

Usage: .\phantom_installer.ps1 [OPTIONS]

Options:
    -InstallDir <path>              Installation directory (auto-detected if not specified)
    -Type <all|controller|worker>   Installation type (default: all)
    -Silent                         No prompts; use defaults for all steps
    -DryRun                         Preview installation without making changes
    -Force                          Skip confirmation prompts
    -LogFile <path>                 Write timestamped log output to file
    -SkipVenv                       Skip virtual environment creation
    -Help                           Show this help message

Examples:
    .\phantom_installer.ps1                                       # Interactive installation
    .\phantom_installer.ps1 -Silent                               # Silent install with defaults
    .\phantom_installer.ps1 -Silent -Type worker                  # Silent worker-only install
    .\phantom_installer.ps1 -Silent -Type controller -Force       # Silent controller install
    .\phantom_installer.ps1 -DryRun                               # Preview without changes
    .\phantom_installer.ps1 -Silent -LogFile C:\Logs\install.log  # Silent with log file
"@
    exit 0
}

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Display banner
Write-Host @"

╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗
║   ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║
║   ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║
║   ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║
║   ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║
║   ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝
║                                                               ║
║            Unified Installation Wizard                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# Check Python installation
Write-Info "Checking Python installation..."

$PythonCmd = $null
$PythonCommands = @("python", "python3", "py")

foreach ($cmd in $PythonCommands) {
    try {
        $version = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $PythonCmd = $cmd
            break
        }
    } catch {
        continue
    }
}

if (-not $PythonCmd) {
    Write-Error "Python 3 is not installed"
    Write-Host "Please install Python 3.8 or later from https://www.python.org/downloads/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation."
    exit 1
}

$PythonVersion = & $PythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
Write-Success "Found Python $PythonVersion"

# Check minimum Python version (3.8)
$VersionParts = $PythonVersion.Split('.')
$Major = [int]$VersionParts[0]
$Minor = [int]$VersionParts[1]

if (($Major -lt 3) -or (($Major -eq 3) -and ($Minor -lt 8))) {
    Write-Error "Python 3.8 or later is required (found $PythonVersion)"
    exit 1
}

Write-Info "Starting installation wizard..."
Write-Host ""

# Build arguments for Python script
$pythonArgs = @("$ScriptDir\phantom_installer.py")

if ($InstallDir) {
    $pythonArgs += "--install-dir", $InstallDir
}

$pythonArgs += "--type", $Type

if ($Silent) {
    $pythonArgs += "--silent"
}

if ($DryRun) {
    $pythonArgs += "--dry-run"
}

if ($Force) {
    $pythonArgs += "--force"
}

if ($LogFile) {
    $pythonArgs += "--log-file", $LogFile
}

if ($SkipVenv) {
    $pythonArgs += "--skip-venv"
}

# Run the Python installer
& $PythonCmd $pythonArgs
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Success "Installation completed successfully"
}
else {
    Write-Error "Installation failed with exit code $exitCode"
}

exit $exitCode
