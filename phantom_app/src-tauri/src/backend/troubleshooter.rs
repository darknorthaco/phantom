//! Deployment Troubleshooter — OS-aware probes, port cycling, and config updates.
//! No admin shell required; uses local bind tests and optional read-only netstat on Windows.

use std::net::{SocketAddr, TcpListener};
use std::path::Path;

use serde_json::{json, Value};
use tokio::io::AsyncWriteExt;
use tokio::net::TcpStream;
use tokio::time::{timeout, Duration};

use super::deployment_chronicle::{append, ChronicleRecord};
use super::phantom_api::PhantomApiClient;
use super::phantom_deployer::PhantomDeployer;

/// Ordered cycle (primary typical first). Up to 8 TCP ports total; advance one step per user action.
pub const CONTROLLER_PORT_CYCLE: &[u16] = &[8080, 8081, 8082, 8090, 8091, 8095, 8100, 8101];

pub fn next_port_in_cycle(current: u16) -> Option<u16> {
    let idx = CONTROLLER_PORT_CYCLE.iter().position(|&p| p == current)?;
    CONTROLLER_PORT_CYCLE.get(idx + 1).copied()
}

/// ``127.0.0.1:port`` bind probe — if another process listens, bind usually fails with EADDRINUSE.
pub fn tcp_bind_available(port: u16) -> Result<(), String> {
    let addr: SocketAddr = format!("127.0.0.1:{port}")
        .parse()
        .map_err(|e| format!("invalid address: {e}"))?;
    let listener = TcpListener::bind(addr).map_err(|e| format!("port {port}: {e}"))?;
    drop(listener);
    Ok(())
}

#[cfg(target_os = "windows")]
fn netstat_lines_for_port(port: u16) -> String {
    use std::process::Command;
    let needle = format!(":{port}");
    let Ok(out) = Command::new("cmd")
        .args(["/C", "netstat", "-ano", "-p", "tcp"])
        .output()
    else {
        return "(netstat unavailable)".to_string();
    };
    let text = String::from_utf8_lossy(&out.stdout);
    let hits: Vec<&str> = text
        .lines()
        .filter(|l| l.contains(&needle) && l.contains("LISTENING"))
        .take(12)
        .collect();
    if hits.is_empty() {
        format!("No LISTENING rows for TCP {needle} in netstat output (port may be blocked differently).")
    } else {
        hits.join("\n")
    }
}

#[cfg(not(target_os = "windows"))]
fn netstat_lines_for_port(_port: u16) -> String {
    "(use ss/lsof on this platform — see pre-deploy checks)".to_string()
}

pub async fn scan_controller_port(
    phantom_root: &Path,
    port: u16,
) -> Result<serde_json::Value, String> {
    let bind_ok = tcp_bind_available(port).is_ok();
    let hint = netstat_lines_for_port(port);
    let rec = ChronicleRecord::new("troubleshooter", "info", format!("Port scan {port}"))
        .with_details(json!({ "port": port, "bindProbeFree": bind_ok }));
    let _ = append(phantom_root, rec).await;
    Ok(json!({
        "port": port,
        "bindProbeFree": bind_ok,
        "netstatHint": hint,
    }))
}

/// Advance controller port in ``controller_placement.json`` and patch ``phantom_config.json`` if present.
pub async fn cycle_controller_port(phantom_root: &Path) -> Result<serde_json::Value, String> {
    let placement_path = phantom_root.join("controller_placement.json");
    if !placement_path.is_file() {
        return Err("controller_placement.json missing — complete Controller Selection first.".to_string());
    }
    let raw = tokio::fs::read_to_string(&placement_path)
        .await
        .map_err(|e| e.to_string())?;
    let mut placement: Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    let current = placement
        .get("port")
        .and_then(|v| v.as_u64())
        .and_then(|u| u16::try_from(u).ok())
        .ok_or_else(|| "placement.port missing or invalid".to_string())?;
    let next = next_port_in_cycle(current).ok_or_else(|| {
        format!(
            "No further fallback ports after {current}. Try closing other apps using these ports: {:?}",
            CONTROLLER_PORT_CYCLE
        )
    })?;

    placement["port"] = json!(next);
    let tmp_p = phantom_root.join("controller_placement.json.tmp");
    tokio::fs::write(
        &tmp_p,
        serde_json::to_string_pretty(&placement).map_err(|e| e.to_string())?,
    )
    .await
    .map_err(|e| e.to_string())?;
    tokio::fs::rename(&tmp_p, &placement_path)
        .await
        .map_err(|e| e.to_string())?;

    let config_path = phantom_root.join("phantom_config.json");
    let had_config = config_path.is_file();
    if had_config {
        let cr = tokio::fs::read_to_string(&config_path)
            .await
            .map_err(|e| e.to_string())?;
        let mut cfg: Value = serde_json::from_str(&cr).map_err(|e| e.to_string())?;
        if let Some(c) = cfg.get_mut("controller").and_then(|c| c.as_object_mut()) {
            c.insert("port".to_string(), json!(next));
        }
        if let Some(p) = cfg.get_mut("ports").and_then(|p| p.as_object_mut()) {
            if let Some(api) = p.get_mut("controller_api").and_then(|x| x.as_object_mut()) {
                api.insert("port".to_string(), json!(next));
            }
        }
        let tmp_c = phantom_root.join("phantom_config.json.troubleshooter.tmp");
        tokio::fs::write(
            &tmp_c,
            serde_json::to_string_pretty(&cfg).map_err(|e| e.to_string())?,
        )
        .await
        .map_err(|e| e.to_string())?;
        tokio::fs::rename(&tmp_c, &config_path)
            .await
            .map_err(|e| e.to_string())?;
    }

    let rec = ChronicleRecord::new("troubleshooter", "info", format!("Cycled controller port {current} → {next}"))
        .with_details(json!({ "from": current, "to": next }));
    let _ = append(phantom_root, rec).await;

    Ok(json!({
        "previousPort": current,
        "newPort": next,
        "placementUpdated": true,
        "configPatched": had_config,
    }))
}

pub async fn ping_controller_health(phantom_root: &Path) -> Result<serde_json::Value, String> {
    let cfg = phantom_root.join("phantom_config.json");
    let (base_url, tls_enabled) = PhantomApiClient::controller_base_url_from_config(&cfg)
        .map_err(|e| format!("Could not read controller URL from config: {e}"))?;
    let api = PhantomApiClient::for_local_health_check(&base_url, tls_enabled)
        .map_err(|e| format!("Health client: {e}"))?;
    match api.health().await {
        Ok(h) => Ok(json!({
            "ok": true,
            "url": format!("{base_url}/health"),
            "status": h.status,
            "workersCount": h.workers_count,
        })),
        Err(e) => Ok(json!({
            "ok": false,
            "url": format!("{base_url}/health"),
            "error": e,
        })),
    }
}

pub async fn protocol_compatibility_hint(phantom_root: &Path) -> serde_json::Value {
    let cfg_path = phantom_root.join("phantom_config.json");
    let ver = tokio::fs::read_to_string(&cfg_path)
        .await
        .ok()
        .and_then(|s| serde_json::from_str::<Value>(&s).ok())
        .and_then(|v| v.get("config_version").and_then(|x| x.as_str()).map(|s| s.to_string()))
        .unwrap_or_else(|| "unknown".to_string());
    json!({
        "configVersion": ver,
        "appExpects": "1.0",
        "note": "Worker/controller HTTP+JSON API; discovery UDP 8095; optional WebSocket 8081 when integrated.",
    })
}

pub async fn stop_phantom_services_soft(
    phantom_root: &Path,
    engine_source: &Path,
    app: tauri::AppHandle,
) -> Result<(), String> {
    let deployer = PhantomDeployer::new(phantom_root, engine_source, Some(app));
    deployer.stop_service_without_uninstall().await;
    let rec = ChronicleRecord::new("troubleshooter", "info", "Stop Phantom services (best effort, no uninstall)");
    let _ = append(phantom_root, rec).await;
    Ok(())
}

async fn probe_tcp(host: &str, port: u16) -> Value {
    let target = format!("{host}:{port}");
    let addr: SocketAddr = match target.parse() {
        Ok(a) => a,
        Err(e) => {
            return json!({
                "ok": false,
                "target": target,
                "error": format!("address parse: {e}"),
            });
        }
    };
    match timeout(Duration::from_secs(3), TcpStream::connect(addr)).await {
        Ok(Ok(mut stream)) => {
            let _ = stream.shutdown();
            json!({ "ok": true, "target": target })
        }
        Ok(Err(e)) => json!({ "ok": false, "target": target, "error": e.to_string() }),
        Err(_) => json!({ "ok": false, "target": target, "error": "timeout (3s)" }),
    }
}

/// TCP reachability for controller and local worker HTTP ports; optional placement host for remote controller.
pub async fn network_reachability_probes(phantom_root: &Path) -> Value {
    let (cfg_host, ctrl_port, worker_http, _) =
        super::phantom_deployer::read_runtime_tcp_endpoints(phantom_root);
    let placement_path = phantom_root.join("controller_placement.json");
    let placement_host = tokio::fs::read_to_string(&placement_path)
        .await
        .ok()
        .and_then(|s| serde_json::from_str::<Value>(&s).ok())
        .and_then(|v| v.get("host").and_then(|x| x.as_str()).map(|s| s.to_string()));

    let host_for_ctrl = placement_host
        .as_deref()
        .filter(|h| !h.is_empty())
        .unwrap_or(cfg_host.as_str());

    let controller_cfg = probe_tcp(&cfg_host, ctrl_port).await;
    let controller_placement = probe_tcp(host_for_ctrl, ctrl_port).await;
    let worker_local = probe_tcp("127.0.0.1", worker_http).await;

    json!({
        "controllerFromConfig": controller_cfg,
        "controllerFromPlacementHost": controller_placement,
        "workerHttpLocalhost": worker_local,
        "interpretation": "Open TCP means something accepted the connection; HTTP /health uses the Ping controller button.",
    })
}

/// Readable checks for state_dir layout (no shell).
pub async fn verify_deployment_artifacts(phantom_root: &Path) -> Value {
    let placement = phantom_root.join("controller_placement.json");
    let config = phantom_root.join("phantom_config.json");
    let venv = phantom_root.join("venv");
    let engine = phantom_root.join("engine");
    let state = phantom_root.join("state");
    let chronicle = phantom_root.join("deployment_chronicle.jsonl");

    let venv_ok = venv.is_dir()
        && (venv.join("Scripts").join("python.exe").is_file()
            || venv.join("bin").join("python").is_file()
            || venv.join("bin").join("python3").is_file());

    let out = json!({
        "phantomRoot": phantom_root.to_string_lossy(),
        "phantomRootExists": phantom_root.is_dir(),
        "controllerPlacement": placement.is_file(),
        "phantomConfig": config.is_file(),
        "venvPresent": venv_ok,
        "engineDir": engine.is_dir(),
        "stateDir": state.is_dir(),
        "deploymentChronicle": chronicle.is_file(),
    });

    let rec = ChronicleRecord::new("troubleshooter", "info", "Verified deployment artifacts (files/dirs)")
        .with_details(out.clone());
    let _ = append(phantom_root, rec).await;

    out
}

pub async fn troubleshooter_restart_controller(
    phantom_root: &Path,
    engine_source: &Path,
    app: tauri::AppHandle,
) -> Result<(), String> {
    let deployer = PhantomDeployer::new(phantom_root, engine_source, Some(app));
    let r = deployer.troubleshooter_restart_controller().await;
    let rec = ChronicleRecord::new(
        "troubleshooter",
        if r.is_ok() { "info" } else { "error" },
        match &r {
            Ok(()) => "Restart controller completed".to_string(),
            Err(e) => format!("Restart controller failed: {e}"),
        },
    );
    let _ = append(phantom_root, rec).await;
    r
}

pub async fn troubleshooter_restart_local_worker(
    phantom_root: &Path,
    engine_source: &Path,
    app: tauri::AppHandle,
) -> Result<(), String> {
    let deployer = PhantomDeployer::new(phantom_root, engine_source, Some(app));
    let r = deployer.troubleshooter_restart_local_worker().await;
    let rec = ChronicleRecord::new(
        "troubleshooter",
        if r.is_ok() { "info" } else { "error" },
        match &r {
            Ok(()) => "Restart local worker completed".to_string(),
            Err(e) => format!("Restart local worker failed: {e}"),
        },
    );
    let _ = append(phantom_root, rec).await;
    r
}
