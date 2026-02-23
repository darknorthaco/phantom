# Uninstallation Guide

This guide covers complete removal of Phantom from your system. The uninstallers are designed for **bulletproof cleanup** — all processes are terminated, all ports are freed, and all files are removed or backed up.

---

## Windows Uninstallation

### Automated Uninstaller (Recommended)

Run the batch uninstaller as Administrator:

```cmd
package\uninstall.bat
```

The uninstaller will:
1. Stop the Phantom Windows service
2. Terminate all running Phantom processes
3. Verify ports 8765, 8082, 8080 are free
4. Remove the Windows service registration
5. Remove Desktop and Start Menu shortcuts
6. Back up the installation directory (renamed with timestamp)
7. Clean Windows Registry entries

### Manual Uninstallation (Windows)

If the automated uninstaller fails:

```cmd
:: 1. Stop and remove the service
sc stop Phantom
sc delete Phantom

:: 2. Kill any remaining processes
taskkill /f /im python.exe /fi "WINDOWTITLE eq phantom*"

:: 3. Verify ports are free
netstat -ano | findstr "8765 8082 8080"

:: 4. Remove the installation directory
rmdir /s /q "C:\Program Files\Phantom"

:: 5. Remove shortcuts
del "%PUBLIC%\Desktop\Phantom.lnk"
rmdir /s /q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Phantom"

:: 6. Clean registry (optional)
reg delete "HKLM\SOFTWARE\Phantom" /f
reg delete "HKCU\SOFTWARE\Phantom" /f
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Phantom" /f
```

---

## Linux / macOS Uninstallation

### Automated Uninstaller (Recommended)

Run the shell uninstaller as root:

```bash
sudo ./package/uninstall.sh
```

The uninstaller will:
1. Stop the Phantom systemd service
2. Disable and remove the service unit
3. Terminate all Phantom processes (SIGTERM → 5s wait → SIGKILL)
4. Verify ports 8765, 8082, 8080 are free
5. Back up the installation directory (renamed with timestamp)
6. Remove the installation directory
7. Verify complete cleanup

### Manual Uninstallation (Linux/macOS)

If the automated uninstaller fails:

```bash
# 1. Stop and remove the service
sudo systemctl stop phantom
sudo systemctl disable phantom
sudo rm /etc/systemd/system/phantom.service
sudo systemctl daemon-reload

# 2. Kill any remaining processes
pkill -f phantom || true
sleep 2
pkill -9 -f phantom || true

# 3. Verify ports are free
ss -tlnp | grep -E '8765|8082|8080'
# or
lsof -i :8765 -i :8082 -i :8080

# 4. Remove the installation directory
sudo rm -rf /opt/phantom

# 5. Remove the user (if created during installation)
sudo userdel phantom 2>/dev/null || true
```

---

## Data and Backup Retention

### Automated Uninstaller Behavior

The automated uninstallers **do not permanently delete** the installation directory. Instead, they rename it with a timestamp:

- **Windows:** `C:\Program Files\Phantom.uninstalled.YYYYMMDD_HHMM\`
- **Linux:** `/opt/phantom.backup.YYYYMMDD_HHMMSS/`

This allows you to:
- Recover configuration files if needed
- Inspect logs from the previous installation
- Restore the installation if uninstall was accidental

**To permanently remove the backup:**

```bash
# Linux
sudo rm -rf /opt/phantom.backup.*

# Windows (run as Administrator)
rmdir /s /q "C:\Program Files\Phantom.uninstalled.*"
```

### What Is Removed

| Component | Automated | Manual |
|-----------|-----------|--------|
| Phantom service | Yes | Must stop/delete manually |
| Running processes | Yes (graceful + forced) | Must kill manually |
| Network ports | Verified free | Must verify manually |
| Installation files | Backed up, then removed | Must delete manually |
| Desktop shortcuts | Yes (Windows) | Must delete manually |
| Start Menu entries | Yes (Windows) | Must delete manually |
| Registry entries | Yes (Windows) | Must clean manually |
| Systemd unit | Yes (Linux) | Must remove manually |
| Python virtual environment | Yes (inside install dir) | Must delete manually |

### What Is NOT Removed

- User data stored outside the installation directory
- System Python installation
- Other applications using the same ports
- Firewall rules you may have created manually

---

## Verification

After uninstallation, verify the system is clean:

```bash
# Check no Phantom processes are running
# Linux:
ps aux | grep phantom
# Windows:
tasklist | findstr phantom

# Check ports are free
# Linux:
ss -tlnp | grep -E '8765|8082|8080'
# Windows:
netstat -ano | findstr "8765 8082 8080"

# Check service is removed
# Linux:
systemctl status phantom
# Windows:
sc query Phantom
```

All commands above should return empty results or "not found" status.

---

## Troubleshooting

### Process Won't Terminate

If a Phantom process refuses to terminate:

```bash
# Linux — force kill by PID
kill -9 <pid>

# Windows — force kill by PID
taskkill /f /pid <pid>
```

### Port Still in Use After Uninstall

Find and kill the process holding the port:

```bash
# Linux
sudo lsof -i :8765 | awk 'NR>1 {print $2}' | xargs kill -9

# Windows
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8765') do taskkill /f /pid %a
```

### Service Won't Delete (Windows)

If `sc delete Phantom` fails, try:
1. Open `services.msc`
2. Find "Phantom" and stop it
3. Reboot the system
4. Run `sc delete Phantom` again

### Permission Denied

Uninstallation requires the same privilege level as installation:
- **Windows:** Run as Administrator
- **Linux/macOS:** Use `sudo`
