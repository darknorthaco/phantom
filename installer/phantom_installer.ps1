# Phantom Installer - Windows Entry Point
# PowerShell Script

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallerScript = Join-Path $ScriptDir "phantom_installer.py"

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
Write-Host "Checking Python installation..." -ForegroundColor Yellow

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
    Write-Host "❌ Python 3 is not installed" -ForegroundColor Red
    Write-Host "Please install Python 3.8 or later from https://www.python.org/downloads/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation."
    exit 1
}

$PythonVersion = & $PythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
Write-Host "✅ Found Python $PythonVersion" -ForegroundColor Green

# Check minimum Python version (3.8)
$VersionParts = $PythonVersion.Split('.')
$Major = [int]$VersionParts[0]
$Minor = [int]$VersionParts[1]

if (($Major -lt 3) -or (($Major -eq 3) -and ($Minor -lt 8))) {
    Write-Host "❌ Python 3.8 or later is required" -ForegroundColor Red
    Write-Host "Current version: $PythonVersion"
    exit 1
}

Write-Host ""
Write-Host "Starting installation wizard..." -ForegroundColor Yellow
Write-Host ""

# Run the Python installer
& $PythonCmd $InstallerScript $args

exit $LASTEXITCODE
