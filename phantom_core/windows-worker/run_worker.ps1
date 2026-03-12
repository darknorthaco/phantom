# Phantom Windows Worker Launcher
# Activates venv if present, runs: python -m windows_worker.main --config <path>

param(
    [string]$ConfigPath = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigFile = if ($ConfigPath) { $ConfigPath } else { Join-Path $ScriptDir "worker_config.json" }

# Prefer venv in .phantom if present (deployer layout)
$PhantomHome = if ($env:USERPROFILE) { $env:USERPROFILE } else { $env:HOME }
$VenvPython = Join-Path $PhantomHome ".phantom" "venv" "Scripts" "python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

# Ensure we run from windows-worker dir so imports resolve
$WorkerDir = $ScriptDir
if (-not (Test-Path (Join-Path $WorkerDir "windows_worker" "main.py"))) {
    Write-Error "Windows worker runtime not found. Expected: $WorkerDir\windows_worker\main.py"
    exit 1
}

$ConfigResolved = $ConfigFile
if (-not [System.IO.Path]::IsPathRooted($ConfigFile)) {
    $ConfigResolved = Join-Path $WorkerDir $ConfigFile
}
if (-not (Test-Path $ConfigResolved)) {
    Write-Error "Config file not found: $ConfigResolved"
    exit 1
}

$env:PYTHONPATH = $WorkerDir
& $Python -m windows_worker.main --config $ConfigResolved
exit $LASTEXITCODE
