//! Surgical uninstall — deterministic teardown of Phantom-owned artifacts only.
//! Does **not** terminate the running ``phantom_app`` when ``from_running_phantom_app`` is true.
//! Appends a JSON uninstall report to the Deployment Chronicle before removing ``phantom_root``.

use std::path::{Path, PathBuf};

use serde_json::{json, Value};
use tokio::fs;
use tokio::process::Command;

use super::deployment_chronicle::{append_blocking, ChronicleRecord};

#[derive(Clone, Copy, Debug)]
pub struct SurgicalUninstallOptions {
    pub from_running_phantom_app: bool,
}

const PHANTOM_TCP_PORTS: &[u16] = &[8080, 8081, 8082, 8090, 8091, 8095, 8100, 8101];

fn now_rfc3339() -> String {
    chrono::Utc::now().to_rfc3339()
}

async fn remove_dir_all_logged(path: &Path, removed: &mut Vec<String>, errors: &mut Vec<Value>) {
    if !path.exists() {
        return;
    }
    let s = path.to_string_lossy().to_string();
    match fs::remove_dir_all(path).await {
        Ok(()) => removed.push(s),
        Err(e) => errors.push(json!({"op": "remove_dir_all", "path": s, "detail": e.to_string()})),
    }
}

async fn remove_file_logged(path: &Path, removed: &mut Vec<String>, errors: &mut Vec<Value>) {
    if !path.is_file() {
        return;
    }
    let s = path.to_string_lossy().to_string();
    match fs::remove_file(path).await {
        Ok(()) => removed.push(s),
        Err(e) => errors.push(json!({"op": "remove_file", "path": s, "detail": e.to_string()})),
    }
}

async fn stop_phantom_os_services(removed: &mut Vec<String>) {
    #[cfg(target_os = "linux")]
    {
        let _ = Command::new("systemctl")
            .args(["--user", "stop", "phantom"])
            .output()
            .await;
        let _ = Command::new("systemctl")
            .args(["--user", "disable", "phantom"])
            .output()
            .await;
        let home = std::env::var("HOME").unwrap_or_default();
        let unit = PathBuf::from(home).join(".config/systemd/user/phantom.service");
        let _ = fs::remove_file(&unit).await;
        let _ = Command::new("systemctl")
            .args(["--user", "daemon-reload"])
            .output()
            .await;
        removed.push("Linux: systemd user phantom service stopped".into());
    }
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("sc")
            .args(["stop", "phantom"])
            .output()
            .await;
        if let Err(e) = super::windows::service_installer::uninstall_service("phantom").await {
            log::warn!("Windows service remove: {e}");
        }
        removed.push("Windows: sc stop phantom + service uninstall (best effort)".into());
    }
    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    {
        log::info!("stop_phantom_os_services: no bundled service on this OS");
    }
}

async fn remove_windows_firewall_rules(removed: &mut Vec<String>) {
    #[cfg(target_os = "windows")]
    {
        for name in [
            "PhantomController",
            "PhantomWorker",
            "PhantomDiscovery",
            "PhantomSocket",
        ] {
            let _ = Command::new("netsh")
                .args([
                    "advfirewall",
                    "firewall",
                    "delete",
                    "rule",
                    &format!("name={name}"),
                ])
                .output()
                .await;
        }
        removed.push("Windows firewall Phantom rules (best effort)".into());
    }
}

#[cfg(target_os = "windows")]
async fn terminate_phantom_processes_windows(
    opts: SurgicalUninstallOptions,
    removed: &mut Vec<String>,
    errors: &mut Vec<Value>,
) {
    let ps_kill_python = r#"
$ErrorActionPreference = 'SilentlyContinue'
$venv = [regex]::Escape([IO.Path]::Combine($env:USERPROFILE, '.phantom', 'venv'))
$localPhantom = [regex]::Escape([IO.Path]::Combine($env:LOCALAPPDATA, 'Phantom'))
$localBundle = [regex]::Escape([IO.Path]::Combine($env:LOCALAPPDATA, 'com.darknorth.phantom'))
Get-CimInstance Win32_Process | Where-Object {
  ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.ExecutablePath
} | ForEach-Object {
  $p = $_.ExecutablePath
  if ($p -match $venv -or $p -match $localPhantom -or $p -match $localBundle) {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
}
"#;
    let out = Command::new("powershell")
        .args(["-NoProfile", "-NonInteractive", "-Command", ps_kill_python])
        .output()
        .await;
    match out {
        Ok(o) if o.status.success() => {
            removed.push("processes: Phantom-related python (PowerShell filter)".into());
        }
        Ok(o) => errors.push(json!({
            "op": "terminate_python",
            "detail": String::from_utf8_lossy(&o.stderr).to_string(),
        })),
        Err(e) => errors.push(json!({"op": "terminate_python", "detail": e.to_string()})),
    }

    if !opts.from_running_phantom_app {
        let _ = Command::new("taskkill")
            .args(["/F", "/IM", "phantom_app.exe"])
            .output()
            .await;
        removed.push("taskkill phantom_app.exe".into());
    }
}

#[cfg(not(target_os = "windows"))]
async fn terminate_phantom_processes_windows(
    _opts: SurgicalUninstallOptions,
    _removed: &mut Vec<String>,
    _errors: &mut Vec<Value>,
) {
}

#[cfg(target_os = "windows")]
async fn remove_windows_install_artifacts(
    removed: &mut Vec<String>,
    skipped: &mut Vec<Value>,
    errors: &mut Vec<Value>,
) {
    let local = std::env::var("LOCALAPPDATA").unwrap_or_default();
    let appdata = std::env::var("APPDATA").unwrap_or_default();
    let candidates = [
        PathBuf::from(&local).join("Phantom"),
        PathBuf::from(&local).join("com.darknorth.phantom"),
        PathBuf::from(&appdata).join("Phantom"),
        PathBuf::from(&appdata).join("com.darknorth.phantom"),
        PathBuf::from(&appdata).join("phantom_app"),
    ];

    let current_exe = std::env::current_exe().ok();
    for root in candidates {
        if !root.exists() {
            continue;
        }
        if let Some(ref exe) = current_exe {
            if Some(root.as_path()) == exe.parent() {
                if let Ok(mut rd) = fs::read_dir(&root).await {
                    while let Ok(Some(e)) = rd.next_entry().await {
                        let p = e.path();
                        if p == *exe {
                            skipped.push(json!({"path": p.to_string_lossy().to_string(), "reason": "current executable"}));
                            continue;
                        }
                        if p.is_dir() {
                            remove_dir_all_logged(&p, removed, errors).await;
                        } else {
                            remove_file_logged(&p, removed, errors).await;
                        }
                    }
                }
                continue;
            }
        }
        remove_dir_all_logged(&root, removed, errors).await;
    }

    for key in [
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\com.darknorth.phantom",
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Phantom",
    ] {
        let out = Command::new("reg").args(["delete", key, "/f"]).output().await;
        if let Ok(o) = out {
            if o.status.success() {
                removed.push(format!("registry: {key}"));
            }
        }
    }

    let public = std::env::var("ProgramData").unwrap_or_default();
    let user_profile = std::env::var("USERPROFILE").unwrap_or_default();
    let shortcut_dirs = [
        PathBuf::from(&public).join("Microsoft/Windows/Start Menu/Programs"),
        PathBuf::from(&user_profile).join("AppData/Roaming/Microsoft/Windows/Start Menu/Programs"),
        PathBuf::from(&user_profile).join("Desktop"),
    ];
    for dir in shortcut_dirs {
        if let Ok(mut rd) = fs::read_dir(&dir).await {
            while let Ok(Some(e)) = rd.next_entry().await {
                let name = e.file_name().to_string_lossy().to_lowercase();
                if name.contains("phantom") && (name.ends_with(".lnk") || name.ends_with(".url")) {
                    remove_file_logged(&e.path(), removed, errors).await;
                }
            }
        }
    }
}

#[cfg(not(target_os = "windows"))]
async fn remove_windows_install_artifacts(
    _removed: &mut Vec<String>,
    _skipped: &mut Vec<Value>,
    _errors: &mut Vec<Value>,
) {
}

#[cfg(target_os = "windows")]
async fn verify_ports_free(errors: &mut Vec<Value>) {
    let list: Vec<String> = PHANTOM_TCP_PORTS.iter().map(|p| p.to_string()).collect();
    let joined = list.join(",");
    let ps = format!(
        r#"$ports = @({joined}); $busy = @(); foreach ($port in $ports) {{ $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; if ($c) {{ $busy += $port }} }}; if ($busy.Count -gt 0) {{ Write-Output ($busy -join ',') }}"#
    );
    if let Ok(o) = Command::new("powershell")
        .args(["-NoProfile", "-NonInteractive", "-Command", &ps])
        .output()
        .await
    {
        let s = String::from_utf8_lossy(&o.stdout).trim().to_string();
        if !s.is_empty() {
            errors.push(json!({
                "op": "verify_ports",
                "detail": format!("TCP ports still listening (verify manually): {s}"),
            }));
        }
    }
}

#[cfg(not(target_os = "windows"))]
async fn verify_ports_free(_errors: &mut Vec<Value>) {}

pub async fn execute(
    phantom_root: &Path,
    opts: SurgicalUninstallOptions,
) -> Result<Value, String> {
    let mut removed: Vec<String> = Vec::new();
    let mut skipped: Vec<Value> = Vec::new();
    let mut errors: Vec<Value> = Vec::new();

    stop_phantom_os_services(&mut removed).await;
    remove_windows_firewall_rules(&mut removed).await;
    terminate_phantom_processes_windows(opts, &mut removed, &mut errors).await;

    tokio::time::sleep(std::time::Duration::from_millis(800)).await;

    let ts = now_rfc3339();
    let pre_report = json!({
        "status": "complete",
        "removed": &removed,
        "skipped": &skipped,
        "errors": &errors,
        "timestamp": &ts,
        "note": "Chronicle entry before phantom_root removal",
    });
    let rec = ChronicleRecord::new("uninstall", "info", "Surgical uninstall report (pre-removal)")
        .with_details(pre_report);
    if phantom_root.exists() {
        let _ = append_blocking(phantom_root, &rec);
    }

    remove_dir_all_logged(phantom_root, &mut removed, &mut errors).await;

    #[cfg(target_os = "windows")]
    remove_windows_install_artifacts(&mut removed, &mut skipped, &mut errors).await;

    #[cfg(target_os = "windows")]
    verify_ports_free(&mut errors).await;

    let status = if errors.is_empty() { "complete" } else { "partial" };
    Ok(json!({
        "status": status,
        "removed": removed,
        "skipped": skipped,
        "errors": errors,
        "timestamp": now_rfc3339(),
        "fromRunningApp": opts.from_running_phantom_app,
    }))
}
