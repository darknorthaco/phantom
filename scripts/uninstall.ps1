<#
.SYNOPSIS
  Windows wrapper for Phantom surgical uninstall (calls phantom_uninstall.py).

.PARAMETER DryRun
  Preview only; no filesystem changes.

.PARAMETER Force
  Skip confirmation prompt.

.PARAMETER Silent
  Less console output from this wrapper.

.PARAMETER KillApp
  Also terminates phantom_app.exe (do not use when uninstall is triggered from inside the running app).
#>
param(
    [switch] $DryRun,
    [switch] $Force,
    [switch] $Silent,
    [switch] $KillApp
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $here 'phantom_uninstall.py'

$argList = [System.Collections.Generic.List[string]]::new()
$argList.Add($pyScript)
if ($DryRun) { $argList.Add('--dry-run') }
if ($Force) { $argList.Add('--force') }
if ($Silent) { $argList.Add('--silent') }
if ($KillApp) { $argList.Add('--kill-app') }

$ran = $false
if (Get-Command py -ErrorAction SilentlyContinue) {
    if (-not $Silent) { Write-Host 'Using: py -3 phantom_uninstall.py' }
    & py -3 @argList
    $ran = $true
}
if (-not $ran -and (Get-Command python -ErrorAction SilentlyContinue)) {
    if (-not $Silent) { Write-Host 'Using: python phantom_uninstall.py' }
    & python @argList
    $ran = $true
}

if (-not $ran) {
    Write-Error 'Python not found on PATH. Install Python 3 or use Phantom in-app Uninstall / Full Reset.'
    exit 1
}

exit $LASTEXITCODE
