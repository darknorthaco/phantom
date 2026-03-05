# Phantom Desktop App - Build Instructions
# ==========================================

Write-Host "=== Phantom Desktop App Build Script ===" -ForegroundColor Cyan
Write-Host "This script will build the Phantom Tauri desktop application.`n" -ForegroundColor White

# Check prerequisites
Write-Host "[1/4] Checking Prerequisites..." -ForegroundColor Yellow

$rustInstalled = $false
$nodeInstalled = $false

try {
    $cargoVersion = cargo --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Rust: $cargoVersion" -ForegroundColor Green
        $rustInstalled = $true
    }
} catch {
    Write-Host "  ✗ Rust not found" -ForegroundColor Red
}

try {
    $nodeVersion = node --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Node.js: $nodeVersion" -ForegroundColor Green
        $nodeInstalled = $true
    }
} catch {
    Write-Host "  ✗ Node.js not found" -ForegroundColor Red
}

if (-not $rustInstalled -or -not $nodeInstalled) {
    Write-Host "`n❌ Missing prerequisites!" -ForegroundColor Red
    Write-Host "`nPlease install the following:" -ForegroundColor Yellow
    
    if (-not $rustInstalled) {
        Write-Host "`n1. Rust (1.85+ required):" -ForegroundColor Cyan
        Write-Host "   Download from: https://rustup.rs/" -ForegroundColor White
        Write-Host "   Or run: winget install Rustlang.Rustup" -ForegroundColor White
    }
    
    if (-not $nodeInstalled) {
        Write-Host "`n2. Node.js (18+ required):" -ForegroundColor Cyan
        Write-Host "   Download from: https://nodejs.org/" -ForegroundColor White
        Write-Host "   Or run: winget install OpenJS.NodeJS.LTS" -ForegroundColor White
    }
    
    Write-Host "`n3. System packages (may require VS Build Tools):" -ForegroundColor Cyan
    Write-Host "   Visual Studio Build Tools with C++ workload" -ForegroundColor White
    Write-Host "   Download from: https://visualstudio.microsoft.com/downloads/" -ForegroundColor White
    
    Write-Host "`nAfter installation, restart PowerShell and run this script again." -ForegroundColor Yellow
    exit 1
}

# Navigate to app directory
Write-Host "`n[2/4] Navigating to phantom_app directory..." -ForegroundColor Yellow
$appPath = "c:\Users\david\OneDrive\Documents\GitHub\phantom\phantom_app"
if (-not (Test-Path $appPath)) {
    Write-Host "  ✗ phantom_app directory not found at: $appPath" -ForegroundColor Red
    exit 1
}
Set-Location $appPath
Write-Host "  ✓ Working directory: $appPath" -ForegroundColor Green

# Install npm dependencies
Write-Host "`n[3/4] Installing npm dependencies..." -ForegroundColor Yellow
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ npm install failed" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ npm dependencies installed" -ForegroundColor Green

# Build the application
Write-Host "`n[4/4] Building Tauri application..." -ForegroundColor Yellow
Write-Host "  This may take several minutes for first build (Rust compilation)..." -ForegroundColor Gray

npm run tauri build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Build failed" -ForegroundColor Red
    exit 1
}

Write-Host "`n✅ Build Complete!" -ForegroundColor Green
Write-Host "`nThe executable should be located at:" -ForegroundColor Cyan
Write-Host "  $appPath\src-tauri\target\release\phantom_app.exe" -ForegroundColor White

Write-Host "`nTo run the application:" -ForegroundColor Yellow
Write-Host "  cd $appPath" -ForegroundColor White
Write-Host "  .\src-tauri\target\release\phantom_app.exe" -ForegroundColor White

Write-Host "`nOr for development mode with hot-reload:" -ForegroundColor Yellow
Write-Host "  npm run tauri dev" -ForegroundColor White
