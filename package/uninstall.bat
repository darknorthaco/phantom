@echo off
REM Professional uninstallation wizard for Windows

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
echo ║             Phantom Uninstallation Wizard                ║
echo ║                   Windows Edition                        ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

call :log_info "Starting Phantom uninstallation..."

call :stop_service
if errorlevel 1 exit /b 1

call :terminate_processes
if errorlevel 1 exit /b 1

call :verify_ports_free
if errorlevel 1 exit /b 1

call :remove_service
if errorlevel 1 exit /b 1

call :remove_shortcuts
if errorlevel 1 exit /b 1

call :remove_files
if errorlevel 1 exit /b 1

call :cleanup_registry
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

:stop_service
call :log_info "Stopping Phantom service..."

sc query Phantom >nul 2>&1
if errorlevel 1 (
    call :log_warning "Phantom service not found or already stopped"
    goto :eof
)

sc stop Phantom
timeout /t 5 /nobreak >nul

sc query Phantom | findstr "STOPPED" >nul
if errorlevel 1 (
    call :log_warning "Service did not stop gracefully. Forcing termination..."
    sc delete Phantom >nul 2>&1
) else (
    call :log_success "Phantom service stopped"
)
goto :eof

:terminate_processes
call :log_info "Terminating Phantom processes..."

REM Kill any remaining phantom processes
taskkill /f /im python.exe /fi "WINDOWTITLE eq phantom*" >nul 2>&1
taskkill /f /im python.exe /fi "IMAGENAME eq python.exe" /fi "COMMANDLINE co phantom" >nul 2>&1

REM Kill by port usage
set "PORTS=8765 8082 8080"
for %%p in (%PORTS%) do (
    for /f "tokens=5" %%i in ('netstat -ano ^| findstr :%%p') do (
        taskkill /f /pid %%i >nul 2>&1
    )
)

call :log_success "Processes terminated"
goto :eof

:verify_ports_free
call :log_info "Verifying ports are free..."

set "PORTS=8765 8082 8080"
set "STILL_IN_USE="

for %%p in (%PORTS%) do (
    netstat -ano | findstr /r /c:":%%p " >nul 2>&1
    if not errorlevel 1 (
        set "STILL_IN_USE=!STILL_IN_USE! %%p"
    )
)

if defined STILL_IN_USE (
    call :log_warning "Ports still in use:!STILL_IN_USE!"
    echo These processes may need manual termination.
    echo Press any key to continue anyway...
    pause >nul
) else (
    call :log_success "All ports are free"
)
goto :eof

:remove_service
call :log_info "Removing Windows service..."

sc delete Phantom >nul 2>&1
if errorlevel 1 (
    call :log_warning "Failed to remove service (may already be removed)"
) else (
    call :log_success "Windows service removed"
)
goto :eof

:remove_shortcuts
call :log_info "Removing shortcuts..."

REM Remove desktop shortcut
set "DESKTOP_DIR=%PUBLIC%\Desktop"
set "SHORTCUT_NAME=Phantom.lnk"
if exist "%DESKTOP_DIR%\%SHORTCUT_NAME%" (
    del "%DESKTOP_DIR%\%SHORTCUT_NAME%"
    call :log_info "Removed desktop shortcut"
)

REM Remove start menu entries
set "START_MENU_DIR=%ProgramData%\Microsoft\Windows\Start Menu\Programs\Phantom"
if exist "%START_MENU_DIR%" (
    rmdir /s /q "%START_MENU_DIR%"
    call :log_info "Removed start menu entries"
)

call :log_success "Shortcuts removed"
goto :eof

:remove_files
call :log_info "Removing installation files..."

if exist "%INSTALL_DIR%" (
    REM Create backup before removal
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set "DATE=%%c%%a%%b"
    for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "TIME=%%a%%b"
    set "BACKUP_DIR=%INSTALL_DIR%.uninstalled.%DATE%_%TIME: =0%"

    move "%INSTALL_DIR%" "%BACKUP_DIR%" >nul
    if errorlevel 1 (
        call :log_error "Failed to backup installation directory"
        exit /b 1
    )

    call :log_info "Installation backed up to: !BACKUP_DIR!"
    call :log_info "Remove backup manually if uninstallation is successful"
) else (
    call :log_warning "Installation directory not found"
)

call :log_success "Files removed"
goto :eof

:cleanup_registry
call :log_info "Cleaning up registry entries..."

REM Remove any phantom-related registry entries
reg delete "HKLM\SOFTWARE\Phantom" /f >nul 2>&1
reg delete "HKCU\SOFTWARE\Phantom" /f >nul 2>&1

REM Remove from uninstall list
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Phantom" /f >nul 2>&1

call :log_success "Registry cleaned"
goto :eof

:show_completion_message
echo.
echo %GREEN% Uninstallation completed successfully!
echo.
echo Phantom has been removed from your system.
echo.
echo What was done:
echo • Stopped and removed Phantom service
echo • Terminated all Phantom processes
echo • Freed network ports (8765, 8082, 8080)
echo • Removed desktop and start menu shortcuts
echo • Removed installation files (backed up)
echo • Cleaned registry entries
echo.
echo Backup location: Check for folders named "Phantom.uninstalled.*"
echo in your Program Files directory.
echo.
echo You can safely delete the backup folders if everything works correctly.
echo.
pause
goto :eof