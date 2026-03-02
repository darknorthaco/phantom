# Phantom Post-Installation Script
# Windows PowerShell

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Split-Path -Parent $ScriptDir

Write-Host "🔧 Phantom Post-Installation Setup" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

function Print-Success {
    param($Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Print-Warning {
    param($Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Print-Error {
    param($Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

# Function to create Windows service
function Create-WindowsService {
    Write-Host "Creating Windows service configuration..."
    
    $ServiceScript = "$InstallDir\phantom_service.ps1"
    
    @"
# Phantom Service Script
`$VenvPython = "$InstallDir\venvs\phantom\Scripts\python.exe"
`$RunScript = "$InstallDir\run_integrated_phantom.py"

Set-Location "$InstallDir"
& `$VenvPython `$RunScript
"@ | Out-File -FilePath $ServiceScript -Encoding UTF8
    
    Print-Success "Service script created at $ServiceScript"
    Write-Host "  To create service, run as Administrator:"
    Write-Host "  New-Service -Name 'PhantomController' -BinaryPathName 'powershell.exe -File $ServiceScript' -DisplayName 'Phantom Distributed Compute Fabric' -StartupType Automatic"
}

# Function to create convenience scripts
function Create-ConvenienceScripts {
    Write-Host "Creating convenience scripts..."
    
    # Start script
    @"
# Start Phantom
`$InstallDir = Split-Path -Parent `$MyInvocation.MyCommand.Path
`$VenvActivate = "`$InstallDir\venvs\phantom\Scripts\Activate.ps1"
`$RunScript = "`$InstallDir\run_integrated_phantom.py"

& `$VenvActivate
Set-Location `$InstallDir
python `$RunScript
"@ | Out-File -FilePath "$InstallDir\start_phantom.ps1" -Encoding UTF8
    
    # Stop script
    @"
# Stop Phantom using PID file
`$PIDFile = Join-Path `$PSScriptRoot "run\phantom.pid"

if (Test-Path `$PIDFile) {
    `$PID = Get-Content `$PIDFile
    if (Get-Process -Id `$PID -ErrorAction SilentlyContinue) {
        Write-Host "Stopping Phantom (PID: `$PID)..."
        Stop-Process -Id `$PID -Force
        Remove-Item `$PIDFile -Force
        Write-Host "Phantom stopped" -ForegroundColor Green
    } else {
        Write-Host "PID file exists but process not running" -ForegroundColor Yellow
        Remove-Item `$PIDFile -Force
    }
} else {
    Write-Host "Phantom not running (no PID file)" -ForegroundColor Yellow
}
"@ | Out-File -FilePath "$InstallDir\stop_phantom.ps1" -Encoding UTF8
    
    # Status script
    @"
# Check Phantom Status
`$Process = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {`$_.CommandLine -like '*run_integrated_phantom.py*'}
if (`$Process) {
    Write-Host "✅ Phantom is running" -ForegroundColor Green
    try {
        `$Response = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 5
        Write-Host "  Health check: OK" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️ Health check failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ Phantom is not running" -ForegroundColor Red
}
"@ | Out-File -FilePath "$InstallDir\status_phantom.ps1" -Encoding UTF8
    
    Print-Success "Convenience scripts created"
}

# Main execution
Write-Host "Install directory: $InstallDir"
Write-Host ""

Create-WindowsService
Create-ConvenienceScripts

Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Print-Success "Post-installation complete!"
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📋 Next steps:"
Write-Host "  1. Install Windows service (optional, requires Administrator)"
Write-Host "  2. Install Python dependencies:"
Write-Host "     $InstallDir\venvs\phantom\Scripts\pip.exe install -r requirements.txt"
Write-Host "  3. Start Phantom:"
Write-Host "     .\start_phantom.ps1"
Write-Host ""
