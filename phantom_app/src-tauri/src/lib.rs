mod backend;
mod security;

use backend::phantom_api::PhantomApiClient;
use backend::phantom_deployer::{
    CompleteDeploymentRequest, DeploymentPreScanResult, PhantomDeployer,
};
use backend::phantom_state::{AppPhase, AppState, DeploymentProgress, PhantomMetrics};
use security::audit_logger::AuditLogger;
use security::identity_manager::IdentityManager;
use security::tls_manager::TlsManager;
use std::path::{Path, PathBuf};
use tauri::{Emitter, Manager};
use tokio::sync::Mutex as AsyncMutex;

pub struct ManagedState {
    app: AppState,
    identity: AsyncMutex<IdentityManager>,
    tls: AsyncMutex<TlsManager>,
    audit: AuditLogger,
}

/// Phase 4 — payload for ``save_phantom_tls_settings`` (camelCase from UI).
#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PhantomTlsSettings {
    pub wan_mode: bool,
    pub tls_enabled: bool,
    pub tls_cert_path: String,
    pub tls_key_path: String,
}

/// Optional flags for deployment pre-scan (Phase 3 offline / air-gap).
#[derive(Debug, Clone, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DeploymentPreScanOptions {
    #[serde(default)]
    pub offline: Option<bool>,
    #[serde(default)]
    pub offline_bundle_path: Option<String>,
}

/// Resolve whether to use an offline bundle for deploy / pre-scan.
async fn resolve_deploy_offline_bundle(
    phantom_root: &PathBuf,
    state: &ManagedState,
    options: &Option<DeploymentPreScanOptions>,
) -> Result<Option<PathBuf>, String> {
    let invoke_path = options
        .as_ref()
        .and_then(|o| o.offline_bundle_path.clone());
    let explicit = options.as_ref().and_then(|o| o.offline).unwrap_or(false);
    let state_path = state
        .app
        .offline_bundle_path
        .lock()
        .map_err(|e| e.to_string())?
        .clone();

    let candidate = backend::offline_bundle::resolve_offline_bundle_candidate(
        phantom_root,
        invoke_path,
        state_path,
    );
    let network_ok = backend::offline_bundle::network_reachable_for_deploy().await;

    // Online + not explicit → never force wheelhouse. No WAN or explicit `--offline` → require bundle.
    let use_offline = explicit || !network_ok;
    if !use_offline {
        return Ok(None);
    }

    candidate
        .ok_or_else(|| {
            if explicit {
                "Offline install requested but no valid bundle found (manifest.json missing). \
                 Use install_offline_bundle, set PHANTOM_OFFLINE_BUNDLE, or place a bundle at ~/.phantom/offline_bundle."
                    .to_string()
            } else {
                "Network unreachable and no offline bundle found. Provide a bundle with manifest.json."
                    .to_string()
            }
        })
        .map(Some)
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

/// §1 Pre-0 — persist ControllerPlacementParams so Step 4.5 can read them.
#[tauri::command]
async fn confirm_controller_placement(
    state: tauri::State<'_, ManagedState>,
    host: String,
    port: u16,
    device_label: String,
    identity_fingerprint: String,
) -> Result<(), String> {
    let phantom_root = state.app.phantom_root.clone();
    let path = phantom_root.join("controller_placement.json");
    tokio::fs::create_dir_all(&phantom_root)
        .await
        .map_err(|e| format!("Failed to create phantom root: {e}"))?;
    let params = serde_json::json!({
        "host": host,
        "port": port,
        "device_label": device_label,
        "identity_fingerprint": identity_fingerprint,
        "confirmed_at": chrono::Utc::now().to_rfc3339(),
    });
    let tmp = phantom_root.join("controller_placement.json.tmp");
    tokio::fs::write(
        &tmp,
        serde_json::to_string_pretty(&params).map_err(|e| e.to_string())?,
    )
    .await
    .map_err(|e| format!("Failed to write controller_placement.json: {e}"))?;
    tokio::fs::rename(&tmp, &path)
        .await
        .map_err(|e| format!("Failed to persist controller_placement.json: {e}"))?;
    state
        .audit
        .log_event(
            "controller_placement_confirmed",
            serde_json::json!({"host": host, "port": port}),
        )
        .await
        .ok();
    Ok(())
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

/// Phase 4 — generate self-signed PEM (rcgen); optional ``common_name`` for SAN/CN.
#[tauri::command]
async fn generate_self_signed_cert(
    state: tauri::State<'_, ManagedState>,
    common_name: Option<String>,
) -> Result<serde_json::Value, String> {
    let cn = common_name.unwrap_or_else(|| "phantom-controller.local".to_string());
    let paths = {
        let mgr = state.tls.lock().await;
        mgr.generate_self_signed_cert(&cn).await?
    };
    state
        .audit
        .log_event(
            "tls_self_signed_generated",
            serde_json::json!({"cert": paths.cert.to_string_lossy()}),
        )
        .await
        .ok();
    serde_json::to_value(&paths).map_err(|e| e.to_string())
}

/// Phase 4 — copy PEM cert/key into local ``state/tls/`` (never uploaded).
#[tauri::command]
async fn import_tls_cert(
    state: tauri::State<'_, ManagedState>,
    cert_source: String,
    key_source: String,
) -> Result<serde_json::Value, String> {
    let cert = PathBuf::from(&cert_source);
    let key = PathBuf::from(&key_source);
    security::tls_manager::validate_tls_cert_pem(&cert)?;
    security::tls_manager::validate_tls_key_pem(&key)?;
    let paths = {
        let mgr = state.tls.lock().await;
        mgr.import_tls_cert_pair(&cert, &key).await?
    };
    state
        .audit
        .log_event(
            "tls_cert_imported",
            serde_json::json!({"cert": paths.cert.to_string_lossy()}),
        )
        .await
        .ok();
    serde_json::to_value(&paths).map_err(|e| e.to_string())
}

/// Phase 4 — validate a PEM certificate file (local read only).
#[tauri::command]
fn validate_tls_cert(path: String) -> Result<serde_json::Value, String> {
    security::tls_manager::validate_tls_cert_pem(Path::new(&path))?;
    Ok(serde_json::json!({"ok": true, "path": path}))
}

/// Phase 4 — merge WAN/TLS fields into ``phantom_config.json`` (WAN requires TLS).
#[tauri::command]
async fn save_phantom_tls_settings(
    state: tauri::State<'_, ManagedState>,
    settings: PhantomTlsSettings,
) -> Result<(), String> {
    let PhantomTlsSettings {
        wan_mode,
        tls_enabled,
        tls_cert_path,
        tls_key_path,
    } = settings;
    if wan_mode && !tls_enabled {
        return Err(
            "WAN mode requires tls_enabled (encrypted controller API).".to_string(),
        );
    }
    if tls_enabled && (tls_cert_path.is_empty() || tls_key_path.is_empty()) {
        return Err(
            "tls_cert_path and tls_key_path are required when tls_enabled is true.".to_string(),
        );
    }
    if tls_enabled {
        let cp = PathBuf::from(&tls_cert_path);
        let kp = PathBuf::from(&tls_key_path);
        if !cp.is_file() || !kp.is_file() {
            return Err("tls_cert_path or tls_key_path does not exist on disk.".to_string());
        }
    }
    let cfg_path = state.app.phantom_root.join("phantom_config.json");
    if !cfg_path.is_file() {
        return Err(
            "phantom_config.json not found — complete deploy Step 4.5 first.".to_string(),
        );
    }
    let raw = tokio::fs::read_to_string(&cfg_path)
        .await
        .map_err(|e| e.to_string())?;
    let mut v: serde_json::Value =
        serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    v["wan_mode"] = serde_json::json!(wan_mode);
    v["tls_enabled"] = serde_json::json!(tls_enabled);
    v["tls_cert_path"] = serde_json::json!(tls_cert_path);
    v["tls_key_path"] = serde_json::json!(tls_key_path);
    let body = serde_json::to_string_pretty(&v).map_err(|e| e.to_string())?;
    let tmp = state.app.phantom_root.join("phantom_config.json.tls.tmp");
    tokio::fs::write(&tmp, body)
        .await
        .map_err(|e| e.to_string())?;
    tokio::fs::rename(&tmp, &cfg_path)
        .await
        .map_err(|e| e.to_string())?;
    state
        .audit
        .log_event(
            "phantom_tls_settings_saved",
            serde_json::json!({ "wan_mode": wan_mode, "tls_enabled": tls_enabled }),
        )
        .await
        .ok();
    Ok(())
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

/// Run steps 0–9 + discovery (no registration). Returns result for deployment ceremony.
#[tauri::command]
async fn run_deployment_pre_scan(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
    options: Option<DeploymentPreScanOptions>,
) -> Result<DeploymentPreScanResult, String> {
    {
        let mut phase = state.app.phase.lock().map_err(|e| e.to_string())?;
        *phase = AppPhase::Deploying;
    }

    state
        .audit
        .log_event("deployment_pre_scan_started", serde_json::json!({}))
        .await
        .ok();

    let engine_source = find_engine_source(&app);
    let phantom_root = state.app.phantom_root.clone();
    let offline_bundle = resolve_deploy_offline_bundle(&phantom_root, &state, &options).await?;
    let deployer = PhantomDeployer::new(&phantom_root, &engine_source, Some(app.clone()))
        .with_offline_bundle(offline_bundle);

    let result = deployer.run_pre_scan_deployment().await?;

    let _ = app.emit("deploy-discovery-result", &result);

    Ok(result)
}

/// Register selected workers and complete deployment (step 11). Call after ceremony.
#[tauri::command]
async fn complete_deployment_with_selection(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
    request: CompleteDeploymentRequest,
) -> Result<(), String> {
    let engine_source = find_engine_source(&app);
    let phantom_root = state.app.phantom_root.clone();
    let deployer = PhantomDeployer::new(&phantom_root, &engine_source, Some(app.clone()));

    deployer
        .complete_deployment_with_selection(
            request.worker_pool,
            request.run_controller_llm,
        )
        .await?;

    let steps = PhantomDeployer::steps();
    let total = steps.len();
    let _ = app.emit(
        "deploy-progress",
        &DeploymentProgress {
            step: total,
            total_steps: total,
            label: "Deployment complete".to_string(),
            fraction: 1.0,
        },
    );

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
async fn deploy_phantom(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
    options: Option<DeploymentPreScanOptions>,
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
    let offline_bundle = resolve_deploy_offline_bundle(&phantom_root, &state, &options).await?;
    let deployer = PhantomDeployer::new(&phantom_root, &engine_source, Some(app.clone()))
        .with_offline_bundle(offline_bundle);
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

/// Remove Phantom services, firewall rules (Windows), and delete `~/.phantom` (or `%USERPROFILE%\.phantom`).
#[tauri::command]
async fn uninstall_phantom(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let engine_source = find_engine_source(&app);
    let phantom_root = state.app.phantom_root.clone();
    let deployer = PhantomDeployer::new(&phantom_root, &engine_source, Some(app.clone()));

    // Audit before removing ~/.phantom (audit log lives under that tree).
    state
        .audit
        .log_event(
            "phantom_uninstall_started",
            serde_json::json!({ "phantom_root": phantom_root.to_string_lossy() }),
        )
        .await
        .ok();

    let summary = deployer.uninstall_deployment().await?;

    {
        let mut phase = state.app.phase.lock().map_err(|e| e.to_string())?;
        *phase = AppPhase::FrontPorch;
    }

    Ok(summary)
}

/// Refresh bundled engine under `.phantom/engine` while preserving `phantom_config.json`, placement, `config/`, `state/`.
#[tauri::command]
async fn upgrade_phantom_deployment(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let engine_source = find_engine_source(&app);
    let phantom_root = state.app.phantom_root.clone();
    let deployer = PhantomDeployer::new(&phantom_root, &engine_source, Some(app.clone()));

    let summary = deployer.upgrade_engine_preserve_state().await?;

    state
        .audit
        .log_event("phantom_upgrade_complete", summary.clone())
        .await
        .ok();

    Ok(summary)
}

#[tauri::command]
async fn verify_offline_bundle(path: String) -> Result<serde_json::Value, String> {
    let root = PathBuf::from(path);
    let report = backend::offline_bundle::verify_offline_bundle_root(&root).await?;
    serde_json::to_value(&report).map_err(|e| e.to_string())
}

#[tauri::command]
async fn load_offline_model_catalogue(path: String) -> Result<serde_json::Value, String> {
    let root = PathBuf::from(path);
    backend::offline_bundle::load_offline_catalogue_value(&root).await
}

/// Verify bundle integrity, cache model catalogue under ``state/``, and pin bundle for deploy.
#[tauri::command]
async fn install_offline_bundle(
    state: tauri::State<'_, ManagedState>,
    path: String,
) -> Result<serde_json::Value, String> {
    let root = PathBuf::from(path);
    let report = backend::offline_bundle::verify_offline_bundle_root(&root).await?;
    if !report.ok {
        return Err(report.errors.join("; "));
    }
    let catalogue = backend::offline_bundle::load_offline_catalogue_value(&root).await?;
    let phantom_root = state.app.phantom_root.clone();
    let state_dir = phantom_root.join("state");
    tokio::fs::create_dir_all(&state_dir)
        .await
        .map_err(|e| e.to_string())?;
    tokio::fs::write(
        state_dir.join("model_catalogue_offline.json"),
        serde_json::to_string_pretty(&catalogue).map_err(|e| e.to_string())?,
    )
    .await
    .map_err(|e| e.to_string())?;
    tokio::fs::write(
        state_dir.join("pending_offline_bundle_path.txt"),
        root.to_string_lossy().as_ref(),
    )
    .await
    .map_err(|e| e.to_string())?;
    {
        let mut g = state
            .app
            .offline_bundle_path
            .lock()
            .map_err(|e| e.to_string())?;
        *g = Some(root.clone());
    }
    Ok(serde_json::json!({
        "verified": true,
        "checked_files": report.checked_files,
        "bundle": root.to_string_lossy(),
        "catalogue_cached": "state/model_catalogue_offline.json",
    }))
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
            get_identity, sign_message, verify_signature, confirm_controller_placement,
            generate_certificate,
            generate_self_signed_cert,
            import_tls_cert,
            validate_tls_cert,
            save_phantom_tls_settings,
            get_trust_ledger, approve_peer, reject_peer,
            get_audit_log,
            set_execution_mode, load_llm_config,
            get_system_metrics,
            check_integrity,
            get_deployment_status,
            run_deployment_pre_scan, complete_deployment_with_selection,
            deploy_phantom,
            verify_offline_bundle, load_offline_model_catalogue, install_offline_bundle,
            get_phantom_health, get_workers, get_stats,
            submit_task, scan_and_register_workers,
            uninstall_phantom, upgrade_phantom_deployment,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Phantom application");
}
