mod backend;
mod security;

/// Phase 11 — ceremony types and orchestrator (integration tests, future consumers).
pub mod ceremony {
    pub use crate::backend::ceremony::{
        atomic_write, load, ActDetailDto, CeremonyOrchestrator, CeremonyStateFile, CeremonyStatusDto,
        DiscoverySnapshot, OperationalEvaluation, OperationalEvaluationClause, ProcessStatus,
        RegistrationAttempt,
    };
    pub use crate::backend::ceremony::act_e::{
        ENV_FORCE_DEGRADED, ENV_SKIP_CONTROLLER_HEALTH, OUTCOME_SUCCEEDED_WITH_WARNINGS,
    };
    pub use crate::backend::ceremony::act_f::{
        ENV_FORCE_FAILED, ENV_FORCE_PARTIAL, ENV_SKIP_REGISTER, OUTCOME_PARTIAL_REGISTRATION,
    };
    pub use crate::backend::ceremony::phase::CeremonyPhase;
}

use backend::ceremony::{
    CeremonyOrchestrator, CeremonyStatusDto, OperationalEvaluation,
};
use backend::phantom_api::PhantomApiClient;
use backend::phantom_deployer::{
    CompleteDeploymentRequest, DeploymentPreScanResult, PhantomDeployer, WorkerRegistrationSummary,
};
use backend::phantom_state::{AppPhase, AppState, DeployFailureInfo, DeploymentProgress, PhantomMetrics};
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
    /// Phase 11 — sole writer of `state/ceremony_state.json` for unified ceremony.
    ceremony: AsyncMutex<CeremonyOrchestrator>,
}

fn emit_deploy_failed(
    app: &tauri::AppHandle,
    phantom_root: &std::path::Path,
    message: String,
    step_index: Option<usize>,
    step_label: Option<String>,
) {
    let rec = backend::deployment_chronicle::ChronicleRecord::new("deploy", "error", message.clone())
        .with_details(serde_json::json!({
            "stepIndex": step_index,
            "stepLabel": step_label.clone(),
            "fullMessage": message.clone(),
        }));
    let _ = backend::deployment_chronicle::append_blocking(phantom_root, &rec);
    let payload = DeployFailureInfo {
        message,
        step_index,
        step_label,
    };
    let _ = app.emit("deploy-failed", &payload);
}

/// Refresh ``controller_url`` from ``phantom_config.json`` (scheme, host, port, ``tls_enabled``).
fn sync_controller_url_mutex(app: &AppState) {
    let cfg = app.phantom_root.join("phantom_config.json");
    if let Ok((url, _)) = PhantomApiClient::controller_base_url_from_config(&cfg) {
        if let Ok(mut g) = app.controller_url.lock() {
            *g = url;
        }
    }
}

/// Controller API client: reads ``phantom_config.json`` when present (scheme, port, TLS);
/// otherwise uses the mutex default URL (pre-bootstrap).
fn phantom_api_for_app(app: &AppState) -> PhantomApiClient {
    let fallback = app
        .controller_url
        .lock()
        .map(|g| g.clone())
        .unwrap_or_else(|_| "http://127.0.0.1:8080".to_string());
    PhantomApiClient::from_phantom_root_or_fallback(&app.phantom_root, &fallback)
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
    let explicit_offline_flag = options.as_ref().and_then(|o| o.offline).unwrap_or(false);
    let state_path = state
        .app
        .offline_bundle_path
        .lock()
        .map_err(|e| e.to_string())?
        .clone();
    // Bundle path set via invoke argument or persisted app state comes from explicit operator action.
    let explicit_bundle_path = invoke_path.is_some() || state_path.is_some();

    let candidate = backend::offline_bundle::resolve_offline_bundle_candidate(
        phantom_root,
        invoke_path,
        state_path,
    );
    // Doctrine: LAN-first ceremony is canonical and WAN is optional.
    // Offline bundle mode is explicit-only; WAN reachability must never alter deploy path selection.
    let offline_requested = explicit_offline_flag || explicit_bundle_path;
    if !offline_requested {
        return Ok(None);
    }

    candidate
        .ok_or_else(|| {
            "Offline install requested but no valid bundle found (manifest.json missing). \
             Use install_offline_bundle, set PHANTOM_OFFLINE_BUNDLE, or place a bundle at ~/.phantom/offline_bundle."
                .to_string()
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
        .log_event_best_effort("identity_loaded", serde_json::to_value(&info).unwrap())
        .await;
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
        .log_event_best_effort(
            "controller_placement_confirmed",
            serde_json::json!({"host": host, "port": port}),
        )
        .await;
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
        .log_event_best_effort(
            "tls_cert_generated",
            serde_json::json!({"cert": paths.cert.to_string_lossy()}),
        )
        .await;
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
        .log_event_best_effort(
            "tls_self_signed_generated",
            serde_json::json!({"cert": paths.cert.to_string_lossy()}),
        )
        .await;
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
        .log_event_best_effort(
            "tls_cert_imported",
            serde_json::json!({"cert": paths.cert.to_string_lossy()}),
        )
        .await;
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

    sync_controller_url_mutex(&state.app);

    state
        .audit
        .log_event_best_effort(
            "phantom_tls_settings_saved",
            serde_json::json!({ "wan_mode": wan_mode, "tls_enabled": tls_enabled }),
        )
        .await;
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
        .log_event_best_effort("trust_approved", serde_json::json!({"peer_id": peer_id}))
        .await;
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
        .log_event_best_effort("trust_rejected", serde_json::json!({"peer_id": peer_id}))
        .await;
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
async fn get_execution_mode(state: tauri::State<'_, ManagedState>) -> Result<serde_json::Value, String> {
    let client = phantom_api_for_app(&state.app);
    client.get_execution_mode().await
}

#[tauri::command]
async fn get_controller_base_url(state: tauri::State<'_, ManagedState>) -> Result<String, String> {
    let g = state
        .app
        .controller_url
        .lock()
        .map_err(|e| e.to_string())?;
    Ok((*g).clone())
}

#[tauri::command]
async fn get_task_status(
    state: tauri::State<'_, ManagedState>,
    task_id: String,
) -> Result<serde_json::Value, String> {
    let client = phantom_api_for_app(&state.app);
    client.get_task(&task_id).await
}

#[tauri::command]
async fn set_execution_mode(
    state: tauri::State<'_, ManagedState>,
    mode: String,
) -> Result<serde_json::Value, String> {
    let client = phantom_api_for_app(&state.app);
    let resp = client.post_execution_mode(mode.clone()).await?;

    state
        .audit
        .log_event_best_effort("mode_changed", serde_json::json!({"mode": mode}))
        .await;

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
        if let Err(e) = tokio::fs::create_dir_all(&state.app.phantom_root).await {
            log::warn!(
                target: "phantom_app",
                "create_dir_all phantom_root failed path={} error={}",
                state.app.phantom_root.display(),
                e
            );
        }
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
    let client = phantom_api_for_app(&state.app);

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
        .log_event_best_effort("integrity_check", serde_json::to_value(&result).unwrap())
        .await;

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
    // Phase 12 doctrine guard: ceremony-first is canonical. The legacy
    // PhantomDeployer pre-scan path is retained for the in-flight UI migration
    // and is permitted by default. Operators / CI can enforce ceremony-first
    // ahead of the UI cutover by setting `PHANTOM_BLOCK_LEGACY_DEPLOY=1`.
    // Either way the invocation is chronicled so doctrine drift is auditable.
    let legacy_blocked = std::env::var("PHANTOM_BLOCK_LEGACY_DEPLOY")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);
    {
        let outcome = if legacy_blocked { "BLOCKED" } else { "PERMITTED" };
        let line = backend::ceremony::ceremony_chronicle::CeremonyChronicleLine::new(
            "legacy_deploy_invoked",
            None,
            None,
            "-",
            "-",
            Some(outcome.to_string()),
            "legacy run_deployment_pre_scan invoked; ceremony-first is canonical (Phase 12 transition)",
        );
        let _ = backend::ceremony::ceremony_chronicle::append_ceremony_line(
            &state.app.phantom_root,
            &line,
        );
    }
    if legacy_blocked {
        return Err(
            "legacy deploy path blocked by PHANTOM_BLOCK_LEGACY_DEPLOY. \
             Use ceremony_commit_placement / ceremony_run_act_* / ceremony_dry_run \
             to drive the deploy via the unified ceremony orchestrator."
                .to_string(),
        );
    }
    {
        let mut phase = state.app.phase.lock().map_err(|e| e.to_string())?;
        *phase = AppPhase::Deploying;
    }

    state
        .audit
        .log_event_best_effort(
            "deployment_pre_scan_started",
            serde_json::json!({"legacy_compat_flag": true}),
        )
        .await;

    let engine_source = find_engine_source(&app);
    let phantom_root = state.app.phantom_root.clone();
    let offline_bundle = resolve_deploy_offline_bundle(&phantom_root, &state, &options).await?;
    let deployer = PhantomDeployer::new(&phantom_root, &engine_source, Some(app.clone()))
        .with_offline_bundle(offline_bundle);

    let result = match deployer.run_pre_scan_deployment().await {
        Ok(r) => r,
        Err(e) => {
            log::error!("deployment pre-scan failed: {e}");
            emit_deploy_failed(
                &app,
                &phantom_root,
                e.clone(),
                None,
                Some("Deployment pre-scan".to_string()),
            );
            {
                let mut phase = state.app.phase.lock().map_err(|e| e.to_string())?;
                *phase = AppPhase::FrontPorch;
            }
            return Err(e);
        }
    };

    sync_controller_url_mutex(&state.app);

    log::info!(
        target: "phantom_deploy",
        "deployment_pre_scan_ok discovery_failed={} workers={} offline_mode={}",
        result.discovery_failed,
        result.discovered_workers.len(),
        result.offline_mode
    );

    let _ = app.emit("deploy-discovery-result", &result);

    Ok(result)
}

/// Register selected workers and complete deployment (step 11). Call after ceremony.
#[tauri::command]
async fn complete_deployment_with_selection(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
    request: CompleteDeploymentRequest,
) -> Result<WorkerRegistrationSummary, String> {
    let engine_source = find_engine_source(&app);
    let phantom_root = state.app.phantom_root.clone();
    let deployer = PhantomDeployer::new(&phantom_root, &engine_source, Some(app.clone()));

    let summary = match deployer
        .complete_deployment_with_selection(
            request.worker_pool,
            request.run_controller_llm,
        )
        .await
    {
        Ok(s) => s,
        Err(e) => {
            log::error!("complete_deployment_with_selection failed: {e}");
            emit_deploy_failed(
                &app,
                &phantom_root,
                e.clone(),
                None,
                Some("Registration & finalize deployment".to_string()),
            );
            return Err(e);
        }
    };

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
        .log_event_best_effort(
            "deployment_complete",
            serde_json::json!({
                "selectedCount": summary.selected_count,
                "trustFailedCount": summary.trust_failed_count,
                "registeredCount": summary.registered_count,
                "registrationFailedCount": summary.registration_failed_count,
                "poolFullyRegistered": summary.pool_fully_registered(),
            }),
        )
        .await;

    log::info!(
        target: "phantom_deploy",
        "ceremony_registration_ok selected={} registered={} trust_failed={} registration_failed={} pool_complete={}",
        summary.selected_count,
        summary.registered_count,
        summary.trust_failed_count,
        summary.registration_failed_count,
        summary.pool_fully_registered()
    );

    {
        let mut phase = state.app.phase.lock().map_err(|e| e.to_string())?;
        *phase = AppPhase::Deployed;
    }

    sync_controller_url_mutex(&state.app);

    Ok(summary)
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
        .log_event_best_effort("deployment_started", serde_json::json!({}))
        .await;

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
            .log_event_best_effort(
                "deployment_step",
                serde_json::json!({"step": i, "label": label}),
            )
            .await;

        if let Err(e) = deployer.run_step(i).await {
            log::error!("Step {} ({}) failed: {}", i, label, e);
            state
                .audit
                .log_event_best_effort(
                    "deployment_step_failed",
                    serde_json::json!({"step": i, "label": label, "error": &e}),
                )
                .await;
            emit_deploy_failed(
                &app,
                &phantom_root,
                e.clone(),
                Some(i),
                Some((*label).to_string()),
            );
            {
                let mut phase = state.app.phase.lock().map_err(|e| e.to_string())?;
                *phase = AppPhase::FrontPorch;
            }
            return Err(e);
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
        .log_event_best_effort("deployment_complete", serde_json::json!({}))
        .await;

    {
        let mut phase = state.app.phase.lock().map_err(|e| e.to_string())?;
        *phase = AppPhase::Deployed;
    }

    sync_controller_url_mutex(&state.app);

    log::info!(
        target: "phantom_deploy",
        "deploy_phantom_all_steps_ok total_steps={}",
        total
    );

    Ok(())
}

#[tauri::command]
async fn get_phantom_health(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let client = phantom_api_for_app(&state.app);
    let health = client.health().await?;
    serde_json::to_value(health).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_workers(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let client = phantom_api_for_app(&state.app);
    let w = client.list_workers().await?;
    serde_json::to_value(w).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_stats(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let client = phantom_api_for_app(&state.app);
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
    let client = phantom_api_for_app(&state.app);
    let task = backend::phantom_api::TaskSubmission {
        task_type, parameters, priority, target_worker: None,
    };
    let r = client.submit_task(&task).await?;
    serde_json::to_value(r).map_err(|e| e.to_string())
}

async fn run_phantom_uninstall_internal(
    app: tauri::AppHandle,
    state: &ManagedState,
) -> Result<serde_json::Value, String> {
    let engine_source = find_engine_source(&app);
    let phantom_root = state.app.phantom_root.clone();
    let deployer = PhantomDeployer::new(&phantom_root, &engine_source, Some(app.clone()));

    state
        .audit
        .log_event_best_effort(
            "phantom_uninstall_started",
            serde_json::json!({ "phantom_root": phantom_root.to_string_lossy() }),
        )
        .await;

    let summary = deployer.uninstall_deployment().await?;

    {
        let mut phase = state.app.phase.lock().map_err(|e| e.to_string())?;
        *phase = AppPhase::FrontPorch;
    }

    Ok(summary)
}

/// Remove Phantom services, firewall rules (Windows), surgical removal of ``.phantom`` and Windows app data.
#[tauri::command]
async fn uninstall_phantom(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    run_phantom_uninstall_internal(app, &state).await
}

/// Troubleshooter **Full Reset** — same surgical uninstall as ``uninstall_phantom`` (chronicle + teardown).
#[tauri::command]
async fn troubleshooter_full_reset(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    run_phantom_uninstall_internal(app, &state).await
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
        .log_event_best_effort("phantom_upgrade_complete", summary.clone())
        .await;

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
    backend::phantom_deployer::scan_and_register_workers(&phantom_root, Some(app)).await
}

/// Phase 4 — deterministic pre-deploy checklist (placement, engine, venv, TLS, optional /health).
#[tauri::command]
async fn run_pre_deploy_validation(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<backend::pre_deploy_validator::PreDeployReport, String> {
    let phantom_root = state.app.phantom_root.clone();
    let engine_source = find_engine_source(&app);
    let bundle = state
        .app
        .offline_bundle_path
        .lock()
        .map_err(|e| e.to_string())?
        .clone();

    let report = backend::pre_deploy_validator::validate_pre_deploy(
        &phantom_root,
        &engine_source,
        bundle.as_deref(),
    )
    .await;

    let failed_checks: Vec<serde_json::Value> = report
        .checks
        .iter()
        .filter(|c| c.status == "fail")
        .map(|c| {
            serde_json::json!({
                "id": &c.id,
                "name": &c.name,
                "detail": &c.detail,
            })
        })
        .collect();
    let warn_checks: Vec<serde_json::Value> = report
        .checks
        .iter()
        .filter(|c| c.status == "warn")
        .map(|c| {
            serde_json::json!({
                "id": &c.id,
                "name": &c.name,
                "detail": &c.detail,
            })
        })
        .collect();

    state
        .audit
        .log_event_best_effort(
            "pre_deploy_validation",
            serde_json::json!({
                "ok": report.ok,
                "failCount": failed_checks.len(),
                "warnCount": warn_checks.len(),
                "failedChecks": failed_checks,
                "warnChecks": warn_checks,
                "phantomRoot": report.phantom_root,
                "engineSource": report.engine_source,
            }),
        )
        .await;

    log::info!(
        target: "phantom_deploy",
        "pre_deploy_validation_ran ok={} fail_count={} warn_count={}",
        report.ok,
        failed_checks.len(),
        warn_checks.len()
    );

    Ok(report)
}

// ── Phase 11 — Unified ceremony (orchestrator) ─────────────────────

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct CeremonyCommitPlacementArgs {
    host: String,
    port: u16,
    device_label: String,
    identity_fingerprint: String,
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct CeremonyRunActBArgs {
    #[serde(default)]
    offline_bundle_path: Option<String>,
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct CeremonyRunActCArgs {
    #[serde(default)]
    offline_bundle_path: Option<String>,
}

#[tauri::command]
async fn ceremony_status(state: tauri::State<'_, ManagedState>) -> Result<CeremonyStatusDto, String> {
    let orch = state.ceremony.lock().await;
    orch.ceremony_status()
}

#[tauri::command]
async fn operational_evaluate(
    state: tauri::State<'_, ManagedState>,
) -> Result<OperationalEvaluation, String> {
    let orch = state.ceremony.lock().await;
    Ok(orch.operational_evaluate())
}

#[tauri::command]
async fn ceremony_commit_placement(
    state: tauri::State<'_, ManagedState>,
    args: CeremonyCommitPlacementArgs,
) -> Result<CeremonyStatusDto, String> {
    let orch = state.ceremony.lock().await;
    let out = orch
        .commit_placement(
            args.host,
            args.port,
            args.device_label,
            args.identity_fingerprint,
        )
        .await?;
    drop(orch);
    if let Ok(mut ph) = state.app.phase.lock() {
        *ph = CeremonyOrchestrator::project_to_app_phase(&out.s_ceremony);
    }
    Ok(out)
}

#[tauri::command]
async fn ceremony_run_act_b(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
    args: CeremonyRunActBArgs,
) -> Result<CeremonyStatusDto, String> {
    let engine_source = find_engine_source(&app);
    let offline_bundle = args.offline_bundle_path.map(PathBuf::from);
    let orch = state.ceremony.lock().await;
    let out = orch
        .run_act_b(engine_source, offline_bundle, Some(app.clone()))
        .await?;
    drop(orch);
    if let Ok(mut ph) = state.app.phase.lock() {
        *ph = CeremonyOrchestrator::project_to_app_phase(&out.s_ceremony);
    }
    Ok(out)
}

#[tauri::command]
async fn ceremony_run_act_c(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
    args: CeremonyRunActCArgs,
) -> Result<CeremonyStatusDto, String> {
    let offline_bundle = args.offline_bundle_path.map(PathBuf::from);
    let orch = state.ceremony.lock().await;
    let out = orch
        .run_act_c(offline_bundle, Some(app.clone()))
        .await?;
    drop(orch);
    if let Ok(mut ph) = state.app.phase.lock() {
        *ph = CeremonyOrchestrator::project_to_app_phase(&out.s_ceremony);
    }
    Ok(out)
}

#[tauri::command]
async fn ceremony_run_act_d(
    state: tauri::State<'_, ManagedState>,
) -> Result<CeremonyStatusDto, String> {
    let orch = state.ceremony.lock().await;
    let out = orch.run_act_d().await?;
    drop(orch);
    if let Ok(mut ph) = state.app.phase.lock() {
        *ph = CeremonyOrchestrator::project_to_app_phase(&out.s_ceremony);
    }
    Ok(out)
}

#[tauri::command]
async fn ceremony_run_act_e(
    state: tauri::State<'_, ManagedState>,
) -> Result<CeremonyStatusDto, String> {
    let orch = state.ceremony.lock().await;
    let out = orch.run_act_e().await?;
    drop(orch);
    if let Ok(mut ph) = state.app.phase.lock() {
        *ph = CeremonyOrchestrator::project_to_app_phase(&out.s_ceremony);
    }
    Ok(out)
}

#[tauri::command]
async fn ceremony_run_act_f(
    state: tauri::State<'_, ManagedState>,
) -> Result<CeremonyStatusDto, String> {
    let orch = state.ceremony.lock().await;
    let out = orch.run_act_f().await?;
    drop(orch);
    if let Ok(mut ph) = state.app.phase.lock() {
        *ph = CeremonyOrchestrator::project_to_app_phase(&out.s_ceremony);
    }
    Ok(out)
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct CeremonyResumeRecoveryArgs {
    #[serde(default)]
    offline_bundle_path: Option<String>,
}

#[tauri::command]
async fn ceremony_enter_recovery(
    state: tauri::State<'_, ManagedState>,
) -> Result<CeremonyStatusDto, String> {
    let orch = state.ceremony.lock().await;
    let out = orch.enter_recovery()?;
    drop(orch);
    if let Ok(mut ph) = state.app.phase.lock() {
        *ph = CeremonyOrchestrator::project_to_app_phase(&out.s_ceremony);
    }
    Ok(out)
}

#[tauri::command]
async fn ceremony_resume_from_recovery_target(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
    args: Option<CeremonyResumeRecoveryArgs>,
) -> Result<CeremonyStatusDto, String> {
    let engine_source = Some(find_engine_source(&app));
    let offline_bundle = args
        .as_ref()
        .and_then(|a| a.offline_bundle_path.clone())
        .map(PathBuf::from);
    let orch = state.ceremony.lock().await;
    let out = orch
        .resume_from_recovery_target(engine_source, offline_bundle, Some(app.clone()))
        .await?;
    drop(orch);
    if let Ok(mut ph) = state.app.phase.lock() {
        *ph = CeremonyOrchestrator::project_to_app_phase(&out.s_ceremony);
    }
    Ok(out)
}

#[tauri::command]
async fn ceremony_preflight(
    state: tauri::State<'_, ManagedState>,
) -> Result<backend::ceremony::preflight::PreflightReport, String> {
    let root = state.app.phantom_root.clone();
    Ok(backend::ceremony::preflight::run(&root))
}

/// Phase 12 — read `state/discovery_snapshot.json` (Act C output) for UI.
/// Returns `Ok(None)` when the snapshot does not yet exist (Act C not run);
/// returns `Err` only on read / parse errors.
#[tauri::command]
async fn ceremony_get_discovery_snapshot(
    state: tauri::State<'_, ManagedState>,
) -> Result<Option<serde_json::Value>, String> {
    let path = state
        .app
        .phantom_root
        .join("state")
        .join("discovery_snapshot.json");
    if !path.is_file() {
        return Ok(None);
    }
    let raw = tokio::fs::read_to_string(&path)
        .await
        .map_err(|e| format!("read discovery_snapshot.json: {e}"))?;
    let v: serde_json::Value = serde_json::from_str(&raw)
        .map_err(|e| format!("parse discovery_snapshot.json: {e}"))?;
    Ok(Some(v))
}

/// Phase 12 — read `state/ceremony_attestation_manifest.json` (Act D output).
/// Returns `Ok(None)` when the manifest does not yet exist; `Err` only on parse error.
#[tauri::command]
async fn ceremony_get_attestation_manifest(
    state: tauri::State<'_, ManagedState>,
) -> Result<Option<serde_json::Value>, String> {
    let path = state
        .app
        .phantom_root
        .join("state")
        .join("ceremony_attestation_manifest.json");
    if !path.is_file() {
        return Ok(None);
    }
    let raw = tokio::fs::read_to_string(&path)
        .await
        .map_err(|e| format!("read ceremony_attestation_manifest.json: {e}"))?;
    let v: serde_json::Value = serde_json::from_str(&raw)
        .map_err(|e| format!("parse ceremony_attestation_manifest.json: {e}"))?;
    Ok(Some(v))
}

/// Phase 12 — tail of `state/act_b_bootstrap.log` (last N lines).
/// Returns `Ok(vec![])` when the log does not yet exist.
#[tauri::command]
async fn ceremony_read_act_b_log(
    state: tauri::State<'_, ManagedState>,
    tail_lines: usize,
) -> Result<Vec<String>, String> {
    let n = tail_lines.clamp(1, 1000);
    let path = state.app.phantom_root.join("state").join("act_b_bootstrap.log");
    if !path.is_file() {
        return Ok(Vec::new());
    }
    let raw = tokio::fs::read_to_string(&path)
        .await
        .map_err(|e| format!("read act_b_bootstrap.log: {e}"))?;
    let lines: Vec<String> = raw.lines().map(|s| s.to_string()).collect();
    let start = lines.len().saturating_sub(n);
    Ok(lines[start..].to_vec())
}

#[tauri::command]
async fn ceremony_dry_run(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
    args: Option<CeremonyRunActBArgs>,
) -> Result<CeremonyStatusDto, String> {
    let engine_source = find_engine_source(&app);
    let offline_bundle = args
        .as_ref()
        .and_then(|a| a.offline_bundle_path.clone())
        .map(PathBuf::from);
    let orch = state.ceremony.lock().await;
    let out = orch
        .dry_run_stub_graph(engine_source, offline_bundle, Some(app.clone()))
        .await?;
    drop(orch);
    if let Ok(mut ph) = state.app.phase.lock() {
        *ph = CeremonyOrchestrator::project_to_app_phase(&out.s_ceremony);
    }
    Ok(out)
}

// ── Deployment Troubleshooter (GUI + chronicle) ─────────────────────

#[tauri::command]
async fn get_deployment_chronicle(
    state: tauri::State<'_, ManagedState>,
    limit: usize,
) -> Result<Vec<String>, String> {
    let n = limit.clamp(1, 500);
    backend::deployment_chronicle::read_tail(&state.app.phantom_root, n).await
}

#[tauri::command]
async fn troubleshooter_append_note(
    state: tauri::State<'_, ManagedState>,
    note: String,
) -> Result<(), String> {
    let rec = backend::deployment_chronicle::ChronicleRecord::new("user", "info", note);
    backend::deployment_chronicle::append(&state.app.phantom_root, rec).await
}

#[tauri::command]
async fn troubleshooter_scan_port(
    state: tauri::State<'_, ManagedState>,
    port: u16,
) -> Result<serde_json::Value, String> {
    backend::troubleshooter::scan_controller_port(&state.app.phantom_root, port).await
}

#[tauri::command]
async fn troubleshooter_cycle_controller_port(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    let out = backend::troubleshooter::cycle_controller_port(&state.app.phantom_root).await?;
    sync_controller_url_mutex(&state.app);
    let _ = app.emit("phantom-config-updated", &());
    Ok(out)
}

#[tauri::command]
async fn troubleshooter_ping_controller(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    backend::troubleshooter::ping_controller_health(&state.app.phantom_root).await
}

#[tauri::command]
async fn troubleshooter_protocol_hint(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    Ok(
        backend::troubleshooter::protocol_compatibility_hint(&state.app.phantom_root).await,
    )
}

#[tauri::command]
async fn troubleshooter_stop_services(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<(), String> {
    let engine = find_engine_source(&app);
    backend::troubleshooter::stop_phantom_services_soft(
        &state.app.phantom_root,
        &engine,
        app.clone(),
    )
    .await
}

#[tauri::command]
fn troubleshooter_port_cycle_defaults() -> Vec<u16> {
    backend::troubleshooter::CONTROLLER_PORT_CYCLE.to_vec()
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct ControllerPlacementView {
    host: String,
    port: u16,
    #[serde(skip_serializing_if = "Option::is_none")]
    device_label: Option<String>,
    /// Phase 12 — exposed so the ceremony-first UI can call
    /// `ceremony_commit_placement` without a second round-trip.
    #[serde(skip_serializing_if = "Option::is_none")]
    identity_fingerprint: Option<String>,
}

#[tauri::command]
async fn get_controller_placement_info(
    state: tauri::State<'_, ManagedState>,
) -> Result<Option<ControllerPlacementView>, String> {
    let p = state.app.phantom_root.join("controller_placement.json");
    if !p.is_file() {
        return Ok(None);
    }
    let raw = tokio::fs::read_to_string(&p)
        .await
        .map_err(|e| e.to_string())?;
    let v: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    let host = v
        .get("host")
        .and_then(|x| x.as_str())
        .unwrap_or("127.0.0.1")
        .to_string();
    let port = v
        .get("port")
        .and_then(|x| x.as_u64())
        .and_then(|u| u16::try_from(u).ok())
        .ok_or_else(|| "controller_placement.json: invalid port".to_string())?;
    let device_label = v
        .get("device_label")
        .and_then(|x| x.as_str())
        .map(|s| s.to_string());
    let identity_fingerprint = v
        .get("identity_fingerprint")
        .and_then(|x| x.as_str())
        .filter(|s| !s.trim().is_empty())
        .map(|s| s.to_string());
    Ok(Some(ControllerPlacementView {
        host,
        port,
        device_label,
        identity_fingerprint,
    }))
}

#[tauri::command]
async fn troubleshooter_network_probes(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    Ok(
        backend::troubleshooter::network_reachability_probes(&state.app.phantom_root).await,
    )
}

#[tauri::command]
async fn troubleshooter_verify_artifacts(
    state: tauri::State<'_, ManagedState>,
) -> Result<serde_json::Value, String> {
    Ok(
        backend::troubleshooter::verify_deployment_artifacts(&state.app.phantom_root).await,
    )
}

#[tauri::command]
async fn troubleshooter_restart_controller(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<(), String> {
    let engine = find_engine_source(&app);
    let r = backend::troubleshooter::troubleshooter_restart_controller(
        &state.app.phantom_root,
        &engine,
        app.clone(),
    )
    .await;
    if r.is_ok() {
        sync_controller_url_mutex(&state.app);
        let _ = app.emit("phantom-config-updated", &());
    }
    r
}

#[tauri::command]
async fn troubleshooter_restart_local_worker(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
) -> Result<(), String> {
    let engine = find_engine_source(&app);
    backend::troubleshooter::troubleshooter_restart_local_worker(
        &state.app.phantom_root,
        &engine,
        app.clone(),
    )
    .await
}

#[tauri::command]
async fn run_local_ci_check(
    app: tauri::AppHandle,
    state: tauri::State<'_, ManagedState>,
    options: Option<backend::local_ci_runner::LocalCiOptions>,
) -> Result<backend::local_ci_runner::LocalCiInvokeResult, String> {
    let engine = find_engine_source(&app);
    if !engine.join("run.py").is_file() {
        return Err(
            "Phantom engine (phantom_core with run.py) not found. Use a build with bundled resources or a dev layout."
                .to_string(),
        );
    }
    let opts = options.unwrap_or_default();
    backend::local_ci_runner::run_local_ci_check(
        app,
        state.app.phantom_root.clone(),
        engine,
        opts,
    )
    .await
}

fn find_engine_source(app: &tauri::AppHandle) -> PathBuf {
    match app.path().resource_dir() {
        Ok(res_dir) => {
            let bundled = res_dir.join("phantom_core");
            if bundled.join("run.py").is_file() {
                log::debug!(
                    "find_engine_source: using bundled phantom_core at {}",
                    bundled.display()
                );
                return bundled;
            }
            log::error!(
                "find_engine_source: bundled phantom_core missing run.py at {} — run prepare-resources before build; check bundle.resources maps resources/phantom_core/ to phantom_core/",
                bundled.display()
            );
            // Release installers must not silently use repo-relative paths (wrong or absent on user machines).
            if !cfg!(debug_assertions) {
                return bundled;
            }
            log::warn!("find_engine_source: debug build — trying workspace fallbacks after incomplete bundle");
        }
        Err(e) => {
            log::error!("find_engine_source: resource_dir() failed: {e}");
            if !cfg!(debug_assertions) {
                return PathBuf::new();
            }
            log::warn!("find_engine_source: debug build — trying workspace fallbacks after resource_dir error");
        }
    }

    #[cfg(debug_assertions)]
    {
        for c in &[
            PathBuf::from("/workspace/phantom_core"),
            PathBuf::from("../phantom_core"),
        ] {
            if c.join("run.py").exists() {
                log::debug!(
                    "find_engine_source: using dev workspace path {}",
                    c.display()
                );
                return c.clone();
            }
        }
        let home = std::env::var_os("HOME")
            .or_else(|| std::env::var_os("USERPROFILE"))
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("."));
        let deployed = home.join(".phantom/engine");
        if deployed.join("run.py").exists() {
            log::debug!(
                "find_engine_source: using existing deploy engine {}",
                deployed.display()
            );
            return deployed;
        }
        log::warn!("find_engine_source: no dev engine found; defaulting to /workspace/phantom_core");
        return PathBuf::from("/workspace/phantom_core");
    }

    #[cfg(not(debug_assertions))]
    {
        // All release paths return inside `match` above.
        unreachable!("find_engine_source: release should return from bundled or empty path in match")
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();

    rustls::crypto::ring::default_provider()
        .install_default()
        .expect("install rustls ring crypto provider");

    let mut app_state = AppState::new();
    let state_dir = app_state.phantom_root.clone();

    let ceremony_orch = CeremonyOrchestrator::new(state_dir.clone());
    if let Ok(st) = ceremony_orch.ceremony_status() {
        if let Ok(mut ph) = app_state.phase.lock() {
            *ph = CeremonyOrchestrator::project_to_app_phase(&st.s_ceremony);
        }
    }

    let managed = ManagedState {
        app: app_state,
        identity: AsyncMutex::new(IdentityManager::new(&state_dir)),
        tls: AsyncMutex::new(TlsManager::new(&state_dir)),
        audit: AuditLogger::new(&state_dir),
        ceremony: AsyncMutex::new(ceremony_orch),
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
            get_execution_mode, get_controller_base_url, get_task_status,
            set_execution_mode, load_llm_config,
            get_system_metrics,
            check_integrity,
            get_deployment_status,
            ceremony_status,
            operational_evaluate,
            ceremony_commit_placement,
            ceremony_run_act_b,
            ceremony_run_act_c,
            ceremony_run_act_d,
            ceremony_run_act_e,
            ceremony_run_act_f,
            ceremony_enter_recovery,
            ceremony_resume_from_recovery_target,
            ceremony_dry_run,
            ceremony_preflight,
            ceremony_get_discovery_snapshot,
            ceremony_get_attestation_manifest,
            ceremony_read_act_b_log,
            run_deployment_pre_scan, complete_deployment_with_selection,
            run_pre_deploy_validation,
            get_deployment_chronicle,
            troubleshooter_append_note,
            troubleshooter_scan_port,
            troubleshooter_cycle_controller_port,
            troubleshooter_ping_controller,
            troubleshooter_protocol_hint,
            troubleshooter_stop_services,
            troubleshooter_port_cycle_defaults,
            get_controller_placement_info,
            troubleshooter_network_probes,
            troubleshooter_verify_artifacts,
            troubleshooter_restart_controller,
            troubleshooter_restart_local_worker,
            run_local_ci_check,
            deploy_phantom,
            verify_offline_bundle, load_offline_model_catalogue, install_offline_bundle,
            get_phantom_health, get_workers, get_stats,
            submit_task, scan_and_register_workers,
            uninstall_phantom,
            troubleshooter_full_reset,
            upgrade_phantom_deployment,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Phantom application");
}
