@echo off
REM Professional installation wizard for Windows

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "INSTALL_DIR=%ProgramFiles%\Phantom"

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Running with administrator privileges
) else (
    echo This script requires administrator privileges.
    echo Please right-click and "Run as administrator"
    pause
    exit /b 1
)

REM Colors (Windows CMD approximation)
set "RED=[ERROR]"
set "GREEN=[SUCCESS]"
set "BLUE=[INFO]"
set "YELLOW=[WARNING]"

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║              Phantom Installation Wizard                 ║
echo ║                   Windows Edition                        ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

call :log_info "Starting Phantom installation..."

call :check_requirements
if errorlevel 1 exit /b 1

call :select_installation_type
if errorlevel 1 exit /b 1

call :create_installation_directory
if errorlevel 1 exit /b 1

call :install_components
if errorlevel 1 exit /b 1

call :setup_python_environment
if errorlevel 1 exit /b 1

call :create_service
if errorlevel 1 exit /b 1

call :create_shortcuts
if errorlevel 1 exit /b 1

call :start_service
if errorlevel 1 exit /b 1

call :show_completion_message

goto :eof

:log_info
echo %BLUE% %~1
goto :eof

:log_success
echo %GREEN% %~1
goto :eof

:log_error
echo %RED% %~1
goto :eof

:log_warning
echo %YELLOW% %~1
goto :eof

:check_requirements
call :log_info "Checking system requirements..."

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    call :log_error "Python 3.8+ required"
    echo Please install Python from https://python.org
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python version: %PYTHON_VERSION%

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"
if errorlevel 1 (
    call :log_error "Python 3.8+ required, found %PYTHON_VERSION%"
    exit /b 1
)

REM Check ports
call :check_ports_free

call :log_success "System requirements met"
goto :eof

:check_ports_free
set "PORTS=8765 8082 8080"
set "IN_USE="

for %%p in (%PORTS%) do (
    netstat -ano | findstr /r /c:":%%p " >nul 2>&1
    if not errorlevel 1 (
        set "IN_USE=!IN_USE! %%p"
    )
)

if defined IN_USE (
    call :log_warning "Ports in use:!IN_USE!"
    echo These ports will be freed during installation if needed.
)
goto :eof

:select_installation_type
call :log_info "Installation Type:"
echo 1. Complete Installation (Recommended)
echo    - Phantom Core
echo    - RedBlue Matrix UI
echo    - All components
echo.
echo 2. Core Only
echo    - Phantom Core only
echo    - No UI components
echo.
echo 3. Custom Installation
echo    - Choose components manually

set /p "choice=Select installation type [1-3]: "
if "%choice%"=="1" (
    set "INSTALL_TYPE=complete"
) else if "%choice%"=="2" (
    set "INSTALL_TYPE=core"
) else if "%choice%"=="3" (
    set "INSTALL_TYPE=custom"
) else (
    call :log_error "Invalid choice"
    exit /b 1
)

if "%INSTALL_TYPE%"=="custom" call :custom_component_selection
goto :eof

:custom_component_selection
call :log_info "Component Selection:"
echo ✓ phantom_core (required)

set /p "ui_choice=Install RedBlue Matrix UI? [Y/n]: "
if /i "!ui_choice!"=="n" (
    set "INSTALL_UI=false"
) else (
    set "INSTALL_UI=true"
)

set /p "examples_choice=Install UI examples? [y/N]: "
if /i "!examples_choice!"=="y" (
    set "INSTALL_EXAMPLES=true"
) else (
    set "INSTALL_EXAMPLES=false"
)
goto :eof

:create_installation_directory
call :log_info "Creating installation directory..."

if exist "%INSTALL_DIR%" (
    echo Installation directory exists. Creating backup...
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set "DATE=%%c%%a%%b"
    for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "TIME=%%a%%b"
    set "BACKUP_DIR=%INSTALL_DIR%.backup.%DATE%_%TIME: =0%"
    move "%INSTALL_DIR%" "%BACKUP_DIR%" >nul
    echo Backup created: !BACKUP_DIR!
)

mkdir "%INSTALL_DIR%" 2>nul
if not exist "%INSTALL_DIR%" (
    call :log_error "Failed to create installation directory"
    exit /b 1
)

call :log_success "Installation directory created: %INSTALL_DIR%"
goto :eof

:install_components
call :log_info "Installing components..."

REM Install core
if exist "%SCRIPT_DIR%phantom_core" (
    xcopy "%SCRIPT_DIR%phantom_core\*" "%INSTALL_DIR%\" /E /I /H /Y >nul
    call :log_info "Installed phantom_core"
) else (
    call :log_error "phantom_core not found in package"
    exit /b 1
)

REM Install UI based on selection
if "%INSTALL_TYPE%"=="complete" (
    set "INSTALL_UI=true"
    set "INSTALL_EXAMPLES=true"
)

if "!INSTALL_UI!"=="true" (
    if exist "%SCRIPT_DIR%ui" (
        xcopy "%SCRIPT_DIR%ui\*" "%INSTALL_DIR%ui\" /E /I /H /Y >nul
        call :log_info "Installed UI components"
    )
)

if "!INSTALL_EXAMPLES!"=="true" (
    if exist "%SCRIPT_DIR%ui\examples" (
        xcopy "%SCRIPT_DIR%ui\examples" "%INSTALL_DIR%ui\" /E /I /H /Y >nul
        call :log_info "Installed UI examples"
    )
)

REM Install docs
if exist "%SCRIPT_DIR%docs" (
    xcopy "%SCRIPT_DIR%docs\*" "%INSTALL_DIR%docs\" /E /I /H /Y >nul
    call :log_info "Installed documentation"
)

call :log_success "Components installed"
goto :eof

:setup_python_environment
call :log_info "Setting up Python environment..."

cd /d "%INSTALL_DIR%"

REM Create virtual environment
python -m venv venv
if errorlevel 1 (
    call :log_error "Failed to create virtual environment"
    exit /b 1
)
call :log_info "Created virtual environment"

REM Activate and install requirements
call venv\Scripts\activate.bat
if exist "requirements.txt" (
    pip install -r requirements.txt
    if errorlevel 1 (
        call :log_error "Failed to install Python dependencies"
        exit /b 1
    )
    call :log_info "Installed Python dependencies"
)

call :log_success "Python environment ready"
goto :eof

:create_service
call :log_info "Setting up Windows service..."

REM Create service using sc command
set "SERVICE_EXE=%INSTALL_DIR%\venv\Scripts\python.exe"
set "SERVICE_ARGS=%INSTALL_DIR%\run_integrated_phantom.py"

sc create Phantom binPath= "\"%SERVICE_EXE%\" \"%SERVICE_ARGS%\"" start= auto
if errorlevel 1 (
    call :log_error "Failed to create Windows service"
    exit /b 1
)

sc description Phantom "Phantom Distributed Computing Platform"
call :log_success "Windows service created"
goto :eof

:create_shortcuts
call :log_info "Creating desktop shortcuts..."

REM Create desktop shortcut for UI
set "DESKTOP_DIR=%PUBLIC%\Desktop"
set "SHORTCUT_NAME=Phantom.lnk"

powershell -command "
$WshShell = New-Object -comObject WScript.Shell;
$Shortcut = $WshShell.CreateShortcut('%DESKTOP_DIR%\%SHORTCUT_NAME%');
$Shortcut.TargetPath = 'http://localhost:8080';
$Shortcut.IconLocation = 'shell32.dll,13';
$Shortcut.Save();
"

REM Create start menu entry
set "START_MENU_DIR=%ProgramData%\Microsoft\Windows\Start Menu\Programs\Phantom"
mkdir "%START_MENU_DIR%" 2>nul

powershell -command "
$WshShell = New-Object -comObject WScript.Shell;
$Shortcut = $WshShell.CreateShortcut('%START_MENU_DIR%\Phantom UI.lnk');
$Shortcut.TargetPath = 'http://localhost:8080';
$Shortcut.IconLocation = 'shell32.dll,13';
$Shortcut.Save();
"

call :log_success "Desktop shortcuts created"
goto :eof

:start_service
call :log_info "Starting Phantom service..."

sc start Phantom
timeout /t 3 /nobreak >nul

sc query Phantom | findstr "RUNNING" >nul
if errorlevel 1 (
    call :log_warning "Service may have failed to start. Check Event Viewer for details."
) else (
    call :log_success "Phantom service started"
)
goto :eof

:show_completion_message
echo.
echo %GREEN% Installation completed successfully!
echo.
echo Phantom has been installed to: %INSTALL_DIR%
echo.
echo Service Status:
sc query Phantom
echo.
echo Access Points:
echo • Web UI: http://localhost:8080
echo • API: http://localhost:8765
echo • Socket: localhost:8082
echo.
echo Management:
echo • Start: sc start Phantom
echo • Stop: sc stop Phantom
echo • Restart: sc stop Phantom ^& sc start Phantom
echo.
echo Documentation: %INSTALL_DIR%\docs\
echo Uninstall: Run uninstall.bat as Administrator
echo.
pause
goto :eof