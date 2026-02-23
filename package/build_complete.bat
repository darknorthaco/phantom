@echo off
REM Professional package builder for Windows

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM Colors (using color codes)
REM Note: Windows CMD doesn't support ANSI colors well, using plain text

REM Configuration
if exist "%PROJECT_ROOT%\VERSION" (
    set /p VERSION=<"%PROJECT_ROOT%\VERSION"
) else (
    echo Warning: VERSION file not found, using default
    set "VERSION=1.0.0"
)

set "BUILD_DIR=%PROJECT_ROOT%\build"
set "PACKAGE_NAME=phantom-complete-%VERSION%"
set "PACKAGE_DIR=%BUILD_DIR%\%PACKAGE_NAME%"

REM Detect architecture
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set "ARCH=x64"
) else if "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
    set "ARCH=x64"
) else (
    set "ARCH=x86"
)

set "FINAL_PACKAGE=%BUILD_DIR%\%PACKAGE_NAME%-windows-%ARCH%.zip"

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║          Phantom Complete Package Builder               ║
echo ║                     Windows                             ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo Version: %VERSION%
echo Architecture: %ARCH%
echo Output: %FINAL_PACKAGE%
echo.

call :log_info "Starting build process..."

call :check_requirements
if errorlevel 1 exit /b 1

call :create_package_structure
if errorlevel 1 exit /b 1

call :copy_components
if errorlevel 1 exit /b 1

call :generate_metadata
if errorlevel 1 exit /b 1

call :generate_checksums
if errorlevel 1 exit /b 1

call :create_archive
if errorlevel 1 exit /b 1

call :verify_package
if errorlevel 1 exit /b 1

echo.
echo [SUCCESS] Build completed successfully!
echo.
echo Package: %FINAL_PACKAGE%
call :get_file_size "%FINAL_PACKAGE%"
echo SHA256: 
powershell -command "Get-FileHash -Algorithm SHA256 '%FINAL_PACKAGE%' | Select-Object -ExpandProperty Hash"
echo.
echo Next steps:
echo 1. Extract: Right-click %PACKAGE_NAME%-windows-%ARCH%.zip ^> Extract All
echo 2. Install: cd %PACKAGE_NAME% ^& run install.bat as Administrator
echo 3. Verify: Open http://localhost:8080 in browser
echo.
goto :eof

:log_info
echo [INFO] %~1
goto :eof

:log_success
echo [SUCCESS] %~1
goto :eof

:log_error
echo [ERROR] %~1
goto :eof

:log_warning
echo [WARNING] %~1
goto :eof

:check_requirements
call :log_info "Checking build requirements..."

REM Check for required commands
where powershell >nul 2>&1
if errorlevel 1 (
    call :log_error "PowerShell required"
    exit /b 1
)

where tar >nul 2>&1
if errorlevel 1 (
    call :log_error "tar command required (install Git Bash or similar)"
    exit /b 1
)

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    call :log_error "Python 3 required"
    exit /b 1
)

call :log_success "Requirements check passed"
goto :eof

:create_package_structure
call :log_info "Creating package structure..."

REM Clean previous build
if exist "%PACKAGE_DIR%" rmdir /s /q "%PACKAGE_DIR%"
mkdir "%PACKAGE_DIR%"

REM Create subdirectories
mkdir "%PACKAGE_DIR%\phantom_core"
mkdir "%PACKAGE_DIR%\ui"
mkdir "%PACKAGE_DIR%\installer"
mkdir "%PACKAGE_DIR%\docs"
mkdir "%PACKAGE_DIR%\governance"
mkdir "%PACKAGE_DIR%\scripts"

call :log_success "Package structure created"
goto :eof

:copy_components
call :log_info "Copying components..."

REM Copy phantom core
if exist "%PROJECT_ROOT%\phantom_core" (
    xcopy "%PROJECT_ROOT%\phantom_core\*" "%PACKAGE_DIR%\phantom_core\" /E /I /H /Y >nul
    call :log_info "Copied phantom_core"
) else (
    call :log_warning "phantom_core directory not found"
)

REM Copy UI components
if exist "%PROJECT_ROOT%\ui" (
    xcopy "%PROJECT_ROOT%\ui\*" "%PACKAGE_DIR%\ui\" /E /I /H /Y >nul
    call :log_info "Copied ui"
) else (
    call :log_warning "ui directory not found"
)

REM Copy installer
if exist "%PROJECT_ROOT%\installer" (
    xcopy "%PROJECT_ROOT%\installer\*" "%PACKAGE_DIR%\installer\" /E /I /H /Y >nul
    call :log_info "Copied installer"
) else (
    call :log_warning "installer directory not found"
)

REM Copy docs
if exist "%PROJECT_ROOT%\docs" (
    xcopy "%PROJECT_ROOT%\docs\*" "%PACKAGE_DIR%\docs\" /E /I /H /Y >nul
    call :log_info "Copied docs"
) else (
    call :log_warning "docs directory not found"
)

REM Copy governance
if exist "%PROJECT_ROOT%\governance" (
    xcopy "%PROJECT_ROOT%\governance\*" "%PACKAGE_DIR%\governance\" /E /I /H /Y >nul
    call :log_info "Copied governance"
) else (
    call :log_warning "governance directory not found"
)

REM Copy package scripts
if exist "%SCRIPT_DIR%\install.bat" copy "%SCRIPT_DIR%\install.bat" "%PACKAGE_DIR%\" >nul
if exist "%SCRIPT_DIR%\uninstall.bat" copy "%SCRIPT_DIR%\uninstall.bat" "%PACKAGE_DIR%\" >nul

call :log_success "Components copied"
goto :eof

:generate_metadata
call :log_info "Generating package metadata..."

REM Create VERSION file
echo %VERSION% > "%PACKAGE_DIR%\VERSION"

REM Create BUILD_INFO
echo Phantom Complete Package > "%PACKAGE_DIR%\BUILD_INFO"
echo Version: %VERSION% >> "%PACKAGE_DIR%\BUILD_INFO"
echo Built: %DATE% %TIME% >> "%PACKAGE_DIR%\BUILD_INFO"
echo OS: Windows >> "%PACKAGE_DIR%\BUILD_INFO"
echo Architecture: %ARCH% >> "%PACKAGE_DIR%\BUILD_INFO"
for /f "tokens=*" %%i in ('whoami') do set "BUILD_USER=%%i"
echo Builder: %BUILD_USER%@%COMPUTERNAME% >> "%PACKAGE_DIR%\BUILD_INFO"

REM Create README for package
echo # Phantom Distributed Computing Platform > "%PACKAGE_DIR%\README.md"
echo. >> "%PACKAGE_DIR%\README.md"
echo Version: %VERSION% >> "%PACKAGE_DIR%\README.md"
echo Built for: Windows (%ARCH%) >> "%PACKAGE_DIR%\README.md"
echo. >> "%PACKAGE_DIR%\README.md"
echo ## Quick Start >> "%PACKAGE_DIR%\README.md"
echo. >> "%PACKAGE_DIR%\README.md"
echo 1. Extract the ZIP file >> "%PACKAGE_DIR%\README.md"
echo 2. Run install.bat as Administrator >> "%PACKAGE_DIR%\README.md"
echo 3. Access the web UI at http://localhost:8080 >> "%PACKAGE_DIR%\README.md"
echo. >> "%PACKAGE_DIR%\README.md"
echo ## Documentation >> "%PACKAGE_DIR%\README.md"
echo. >> "%PACKAGE_DIR%\README.md"
echo See docs\ directory for complete documentation. >> "%PACKAGE_DIR%\README.md"
echo. >> "%PACKAGE_DIR%\README.md"
echo ## Uninstall >> "%PACKAGE_DIR%\README.md"
echo. >> "%PACKAGE_DIR%\README.md"
echo Run uninstall.bat as Administrator >> "%PACKAGE_DIR%\README.md"
echo. >> "%PACKAGE_DIR%\README.md"
echo ## Support >> "%PACKAGE_DIR%\README.md"
echo. >> "%PACKAGE_DIR%\README.md"
echo - Documentation: docs\ >> "%PACKAGE_DIR%\README.md"
echo - Commercial: governance\COMMERCIAL.md >> "%PACKAGE_DIR%\README.md"

call :log_success "Metadata generated"
goto :eof

:generate_checksums
call :log_info "Generating checksums..."

powershell -command "Get-ChildItem -Path '%PACKAGE_DIR%' -Recurse -File | Where-Object { $_.Name -ne 'CHECKSUMS.sha256' } | Get-FileHash -Algorithm SHA256 | Select-Object @{Name='Hash';Expression={$_.Hash}}, @{Name='File';Expression={$_.Path.Replace('%PACKAGE_DIR%', '').Replace('\', '/').TrimStart('/')}} | Sort-Object File | Out-File -FilePath '%PACKAGE_DIR%\CHECKSUMS.sha256' -Encoding ASCII"

call :log_success "Checksums generated"
goto :eof

:create_archive
call :log_info "Creating archive..."

if exist "%BUILD_DIR%" mkdir "%BUILD_DIR%" 2>nul

powershell -command "Compress-Archive -Path '%PACKAGE_DIR%' -DestinationPath '%FINAL_PACKAGE%' -Force"

if exist "%FINAL_PACKAGE%" (
    call :log_success "Archive created: %FINAL_PACKAGE%"
) else (
    call :log_error "Failed to create archive"
    exit /b 1
)
goto :eof

:verify_package
call :log_info "Verifying package..."

REM Extract to temporary location for verification
set "TEMP_DIR=%TEMP%\phantom_verify_%RANDOM%"
mkdir "%TEMP_DIR%" 2>nul

powershell -command "Expand-Archive -Path '%FINAL_PACKAGE%' -DestinationPath '%TEMP_DIR%'"

REM Check for required files/directories
set "REQUIRED_FILES=phantom_core ui installer docs VERSION BUILD_INFO README.md install.bat uninstall.bat"
set "MISSING_FILES="

for %%f in (%REQUIRED_FILES%) do (
    if not exist "%TEMP_DIR%\%PACKAGE_NAME%\%%f" (
        set "MISSING_FILES=!MISSING_FILES! %%f"
    )
)

REM Cleanup
rmdir /s /q "%TEMP_DIR%" 2>nul

if defined MISSING_FILES (
    call :log_error "Missing files in package:%MISSING_FILES%"
    exit /b 1
)

call :log_success "Package verification passed"
goto :eof

:get_file_size
set "FILE=%~1"
if exist "%FILE%" (
    for %%A in ("%FILE%") do echo Size: %%~zA bytes
) else (
    echo Size: Unknown
)
goto :eof