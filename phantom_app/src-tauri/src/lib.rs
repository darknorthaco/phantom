mod backend;
mod security;

use backend::phantom_api::PhantomApiClient;
use backend::phantom_deployer::PhantomDeployer;
use backend::phantom_state::{AppPhase, AppState, DeploymentProgress, PhantomMetrics};
use security::audit_logger::AuditLogger;
use security::identity_manager::IdentityManager;
use security::tls_manager::TlsManager;
use std::path::PathBuf;
use tauri::{Emitter, Manager};
use tokio::sync::Mutex as AsyncMutex;

pub struct ManagedState {
    app: AppState,
    identity: AsyncMutex<IdentityManager>,
    tls: AsyncMutex<TlsManager>,
    audit: AuditLogger,
}

// ── Phase 1: Identity ──────────────────────────────────────────────

#[tauri::command]
async fn get_identity(state: tauri::State<'_, ManagedState>) -> Result<serde_json::Value, String> {
    let info = {
        let mut mgr = state.identity.lock().await;
        mgr.load_or_create().await?
    };
    state
        .audit
        .log_event("identity_loaded", serde_json::to_value(&info).unwrap())
        .await
        .ok();
    serde_json::to_value(info).map_err(|e| e.to_string())
}

#[tauri::command]
async fn sign_message(
    state: tauri::State<'_, ManagedState>,
    message: String,
) -> Result<String, String> {
    let mgr = state.identity.lock().await;
    mgr.sign_message(message.as_bytes())
}

#[tauri::command]
fn verify_signature(
    public_key_b64: String,
    message: String,
    signature_b64: String,
) -> Result<bool, String> {
    IdentityManager::verify_signature(&public_key_b64, message.as_bytes(), &signature_b64)
}

// ── Phase 2: TLS ───────────────────────────────────────────────────

#[tauri::command]
async fn generate_certificate(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let paths = {
        let mgr = state.tls.lock().await;
        mgr.generate_self_signed_cert("phantom-controller").await?
    };
    state
        .audit
        .log_event(
            "tls_cert_generated",
            serde_json::json!({"cert": paths.cert.to_string_lossy()}),
        )
        .await
        .ok();
    serde_json::to_value(paths).map_err(|e| e.to_string())
}

// ── Phase 3: Trust ─────────────────────────────────────────────────

#[tauri::command]
async fn get_trust_ledger(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let mgr = state.tls.lock().await;
    let book = &mgr.address_book;
    let ledger = serde_json::json!({
        "pending": book.pending_peers(),
        "approved": book.approved_peers(),
        "rejected": book.rejected_peers(),
    });
    Ok(ledger)
}

#[tauri::command]
async fn approve_peer(
    state: tauri::State<'_, ManagedState>,
    peer_id: String,
) -> Result<(), String> {
    {
        let mut mgr = state.tls.lock().await;
        mgr.address_book.approve_peer(&peer_id)?;
        mgr.save_address_book().await?;
    }
    state
        .audit
        .log_event("trust_approved", serde_json::json!({"peer_id": peer_id}))
        .await
        .ok();
    Ok(())
}

#[tauri::command]
async fn reject_peer(
    state: tauri::State<'_, ManagedState>,
    peer_id: String,
) -> Result<(), String> {
    {
        let mut mgr = state.tls.lock().await;
        mgr.address_book.reject_peer(&peer_id)?;
        mgr.save_address_book().await?;
    }
    state
        .audit
        .log_event("trust_rejected", serde_json::json!({"peer_id": peer_id}))
        .await
        .ok();
    Ok(())
}

// ── Phase 4: Audit ─────────────────────────────────────────────────

#[tauri::command]
async fn get_audit_log(
    state: tauri::State<'_, ManagedState>,
    limit: usize,
) -> Result<serde_json::Value, String> {
    let entries = state.audit.read_entries(limit).await?;
    serde_json::to_value(entries).map_err(|e| e.to_string())
}

// ── Phase 5: Execution modes ───────────────────────────────────────

#[tauri::command]
async fn set_execution_mode(
    state: tauri::State<'_, ManagedState>,
    mode: String,
) -> Result<serde_json::Value, String> {
    let url = {
        state.app.controller_url.lock().map_err(|e| e.to_string())?.clone()
    };
    let client = reqwest::Client::new();
    let resp = client
        .post(format!("{url}/mode"))
        .json(&serde_json::json!({"mode": mode}))
        .send()
        .await
        .map_err(|e| format!("Failed to set mode: {e}"))?
        .json::<serde_json::Value>()
        .await
        .map_err(|e| format!("Parse error: {e}"))?;

    state
        .audit
        .log_event("mode_changed", serde_json::json!({"mode": mode}))
        .await
        .ok();

    Ok(resp)
}

#[tauri::command]
async fn load_llm_config(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let config_path = state.app.phantom_root.join("llm_config.json");
    if !config_path.exists() {
        let default = serde_json::json!({
            "execution_mode": "manual",
            "allow_per_task_override": false,
            "model": "phi-3.5-mini",
            "auto_withdraw_on_human_activity": true,
            "confidence_threshold": 0.85
        });
        let data = serde_json::to_string_pretty(&default).map_err(|e| e.to_string())?;
        tokio::fs::create_dir_all(&state.app.phantom_root).await.ok();
        tokio::fs::write(&config_path, data)
            .await
            .map_err(|e| format!("Failed to write llm_config.json: {e}"))?;
        return Ok(default);
    }
    let content = tokio::fs::read_to_string(&config_path)
        .await
        .map_err(|e| format!("Failed to read llm_config.json: {e}"))?;
    serde_json::from_str(&content).map_err(|e| format!("Invalid llm_config.json: {e}"))
}

// ── Phase 6: System metrics ────────────────────────────────────────

#[tauri::command]
async fn get_system_metrics(
    state: tauri::State<'_, ManagedState>,
) -> Result<PhantomMetrics, String> {
    use sysinfo::System;

    // CPU / RAM from sysinfo (synchronous, cheap)
    let (cpu_percent, memory_used_mb, memory_total_mb) = {
        let mut sys = System::new_all();
        sys.refresh_all();
        (
            sys.global_cpu_usage() as f64,
            sys.used_memory() / (1024 * 1024),
            sys.total_memory() / (1024 * 1024),
        )
    };

    // Worker count and active tasks from the live controller health endpoint
    let url = {
        state.app.controller_url.lock().map_err(|e| e.to_string())?.clone()
    };
    let client = PhantomApiClient::new(&url);

    let (workers_count, active_tasks) = match client.health().await {
        Ok(h) => (h.workers_count, h.active_tasks),
        Err(_) => (0, 0), // controller not reachable yet — return zeros gracefully
    };

    Ok(PhantomMetrics {
        cpu_percent,
        memory_used_mb,
        memory_total_mb,
        workers_count,
        active_tasks,
        throughput: 0.0,
    })
}

// ── Phase 7: Dependency integrity ──────────────────────────────────

#[tauri::command]
async fn check_integrity(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let deps_dir = state.app.phantom_root.join("engine");
    let manifest = deps_dir.join("manifest.json");
    let result =
        security::dependency_integrity::check_dependency_integrity(&deps_dir, &manifest).await?;

    state
        .audit
        .log_event("integrity_check", serde_json::to_value(&result).unwrap())
        .await
        .ok();

    serde_json::to_value(result).map_err(|e| e.to_string())
}

// ── Original commands ──────────────────────────────────────────────

#[tauri::command]
async fn get_deployment_status(
    state: tauri::State<'_, ManagedState>,
) -> Result<String, String> {
    if state.app.is_deployed() {
        return Ok("deployed".to_string());
    }
    let phase = state.app.phase.lock().map_err(|e| e.to_string())?;
    match &*phase {
        AppPhase::FrontPorch => Ok("front_porch".to_string()),
        AppPhase::Deploying => Ok("deploying".to_string()),
        AppPhase::Deployed => Ok("deployed".to_string()),
        AppPhase::Error(msg) => Ok(format!("error:{msg}")),
    }
}

#[tauri::command]
async fn deploy_phantom(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<(), String> {
    {
        let mut phase = state.app.phase.lock().map_err(|e| e.to_string())?;
        *phase = AppPhase::Deploying;
    }

    state
        .audit
        .log_event("deployment_started", serde_json::json!({}))
        .await
        .ok();

    let engine_source = find_engine_source(&app);
    let phantom_root = state.app.phantom_root.clone();
    let deployer = PhantomDeployer::new(&phantom_root, &engine_source, Some(app.clone()));
    let steps = PhantomDeployer::steps();
    let total = steps.len();

    for (i, label) in steps.iter().enumerate() {
        let progress = DeploymentProgress {
            step: i,
            total_steps: total,
            label: label.to_string(),
            fraction: (i as f64) / (total as f64),
        };
        let _ = app.emit("deploy-progress", &progress);

        state
            .audit
            .log_event(
                "deployment_step",
                serde_json::json!({"step": i, "label": label}),
            )
            .await
            .ok();

        if let Err(e) = deployer.run_step(i).await {
            log::warn!("Step {} ({}) failed: {}", i, label, e);
            state
                .audit
                .log_event(
                    "deployment_step_failed",
                    serde_json::json!({"step": i, "error": e}),
                )
                .await
                .ok();
        }
    }

    let done = DeploymentProgress {
        step: total,
        total_steps: total,
        label: "Deployment complete".to_string(),
        fraction: 1.0,
    };
    let _ = app.emit("deploy-progress", &done);

    state
        .audit
        .log_event("deployment_complete", serde_json::json!({}))
        .await
        .ok();

    {
        let mut phase = state.app.phase.lock().map_err(|e| e.to_string())?;
        *phase = AppPhase::Deployed;
    }

    Ok(())
}

#[tauri::command]
async fn get_phantom_health(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let url = {
        state.app.controller_url.lock().map_err(|e| e.to_string())?.clone()
    };
    let client = PhantomApiClient::new(&url);
    let health = client.health().await?;
    serde_json::to_value(health).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_workers(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let url = {
        state.app.controller_url.lock().map_err(|e| e.to_string())?.clone()
    };
    let client = PhantomApiClient::new(&url);
    let w = client.list_workers().await?;
    serde_json::to_value(w).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_stats(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let url = {
        state.app.controller_url.lock().map_err(|e| e.to_string())?.clone()
    };
    let client = PhantomApiClient::new(&url);
    let s = client.get_stats().await?;
    serde_json::to_value(s).map_err(|e| e.to_string())
}

#[tauri::command]
async fn submit_task(
    state: tauri::State<'_, ManagedState>,
    task_type: String,
    parameters: serde_json::Value,
    priority: u32,
) -> Result<serde_json::Value, String> {
    let url = {
        state.app.controller_url.lock().map_err(|e| e.to_string())?.clone()
    };
    let client = PhantomApiClient::new(&url);
    let task = backend::phantom_api::TaskSubmission {
        task_type, parameters, priority, target_worker: None,
    };
    let r = client.submit_task(&task).await?;
    serde_json::to_value(r).map_err(|e| e.to_string())
}

#[tauri::command]
fn scan_lan(base_ip: String, port: u16) -> Vec<backend::lan_scanner::DiscoveredNode> {
    backend::lan_scanner::scan_subnet(&base_ip, port)
}

#[tauri::command]
async fn scan_and_register_workers(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<backend::phantom_deployer::ScanResult, String> {
    let phantom_root = state.app.phantom_root.clone();
    let url = state
        .app
        .controller_url
        .lock()
        .map_err(|e| e.to_string())?
        .clone();
    backend::phantom_deployer::scan_and_register_workers(
        &phantom_root,
        &url,
        Some(app),
    )
    .await
}

fn find_engine_source(app: &tauri::AppHandle) -> PathBuf {
    // 1. Distribution: bundled resources inside the installed app
    if let Ok(res_dir) = app.path().resource_dir() {
        let bundled = res_dir.join("phantom_core");
        if bundled.join("run.py").exists() {
            return bundled;
        }
    }
    // 2. Dev: workspace layout (Cursor / cargo run)
    for c in &[
        PathBuf::from("/workspace/phantom_core"),
        PathBuf::from("../phantom_core"),
    ] {
        if c.join("run.py").exists() {
            return c.clone();
        }
    }
    // 3. Already-deployed engine (from a previous install)
    let home = std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    let deployed = home.join(".phantom/engine");
    if deployed.join("run.py").exists() {
        return deployed;
    }
    PathBuf::from("/workspace/phantom_core")
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();

    let app_state = AppState::new();
    let state_dir = app_state.phantom_root.clone();

    let managed = ManagedState {
        app: app_state,
        identity: AsyncMutex::new(IdentityManager::new(&state_dir)),
        tls: AsyncMutex::new(TlsManager::new(&state_dir)),
        audit: AuditLogger::new(&state_dir),
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(managed)
        .invoke_handler(tauri::generate_handler![
            get_identity, sign_message, verify_signature,
            generate_certificate,
            get_trust_ledger, approve_peer, reject_peer,
            get_audit_log,
            set_execution_mode, load_llm_config,
            get_system_metrics,
            check_integrity,
            get_deployment_status, deploy_phantom,
            get_phantom_health, get_workers, get_stats,
            submit_task, scan_lan, scan_and_register_workers,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Phantom application");
}
