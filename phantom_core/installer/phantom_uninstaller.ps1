# Phantom Distributed Compute Fabric - Uninstaller
# Windows Entry Point (PowerShell)

param(
    [string]$InstallDir = "",
    [ValidateSet("safe", "full")]
    [string]$Mode = "safe",
    [switch]$DryRun = $false,
    [switch]$NoBackup = $false,
    [switch]$Force = $false,
    [switch]$Help = $false
)

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
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
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

if ($Help) {
    Write-Host @"
Phantom Distributed Compute Fabric - Uninstaller

Usage: .\phantom_uninstaller.ps1 [OPTIONS]

Options:
    -InstallDir <path>    Installation directory (auto-detected if not specified)
    -Mode <safe|full>     Uninstall mode (default: safe)
    -DryRun               Preview uninstallation without making changes
    -NoBackup             Skip configuration backup (full mode only)
    -Force                Skip confirmation prompts
    -Help                 Show this help message

Examples:
    .\phantom_uninstaller.ps1                    # Safe uninstall (interactive)
    .\phantom_uninstaller.ps1 -Mode full         # Full uninstall
    .\phantom_uninstaller.ps1 -DryRun            # Preview without changes
"@
    exit 0
}

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check for Python
Write-Info "Checking for Python..."
$PythonCmd = $null

foreach ($cmd in @("python", "python3", "py")) {
    try {
        $version = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $PythonCmd = $cmd
            Write-Info "Found Python: $version"
            break
        }
    }
    catch {
        continue
    }
}

if (-not $PythonCmd) {
    Write-Error "Python 3 is required but not found"
    Write-Host "Please install Python 3.8 or higher from https://www.python.org/"
    exit 1
}

# Check Python version
$versionOutput = & $PythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
$versionParts = $versionOutput -split '\.'
$major = [int]$versionParts[0]
$minor = [int]$versionParts[1]

if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 8)) {
    Write-Error "Python 3.8 or higher is required (found $versionOutput)"
    exit 1
}

# Check for admin rights (may be needed for service removal)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Not running as administrator - may not be able to remove Windows services"
}

# Build arguments for Python script
$pythonArgs = @("$ScriptDir\phantom_uninstaller.py")

if ($InstallDir) {
    $pythonArgs += "--install-dir", $InstallDir
}

$pythonArgs += "--mode", $Mode

if ($DryRun) {
    $pythonArgs += "--dry-run"
}

if ($NoBackup) {
    $pythonArgs += "--no-backup"
}

if ($Force) {
    $pythonArgs += "--force"
}

# Launch Python uninstaller
Write-Info "Launching Phantom Uninstaller..."
Write-Host ""

& $PythonCmd $pythonArgs
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Success "Uninstaller completed successfully"
}
else {
    Write-Error "Uninstaller failed with exit code $exitCode"
}

exit $exitCode
