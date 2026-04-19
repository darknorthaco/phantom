//! Act B — materialize venv + pip + engine copy (Phase 2 / Phase 11.2).
//! Delegates to `PhantomDeployer` steps 0–2 only (no service install / config acts).

use std::path::{Path, PathBuf};

use crate::backend::phantom_deployer::PhantomDeployer;

/// Bootstrap log: human-readable trail of Act B materialize attempts (success or failure).
/// Surfaced verbatim by the UI so the very first deploy reports actionable errors
/// (missing Python, pip resolver fail, wheel compile errors, etc.).
const BOOTSTRAP_LOG_REL: &str = "state/act_b_bootstrap.log";

fn bootstrap_log_path(phantom_root: &Path) -> std::path::PathBuf {
    phantom_root.join(BOOTSTRAP_LOG_REL)
}

/// Append a single timestamped record to `state/act_b_bootstrap.log`.
/// Best effort: errors are swallowed because we never want logging to mask the
/// real failure that triggered the write.
fn append_bootstrap_log(phantom_root: &Path, status: &str, step: u8, body: &str) {
    let path = bootstrap_log_path(phantom_root);
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let ts = chrono::Utc::now().to_rfc3339();
    let header = format!("--- {ts} step={step} status={status} ---\n");
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
    {
        use std::io::Write as _;
        let _ = f.write_all(header.as_bytes());
        let _ = f.write_all(body.as_bytes());
        if !body.ends_with('\n') {
            let _ = f.write_all(b"\n");
        }
    }
}

/// Validate `controller_placement.json` exists and has required fields.
pub async fn validate_placement_prerequisites(phantom_root: &Path) -> Result<(), String> {
    let p = phantom_root.join("controller_placement.json");
    if !p.is_file() {
        return Err(
            "controller_placement.json missing — complete Act A (placement) first.".to_string(),
        );
    }
    let raw = tokio::fs::read_to_string(&p)
        .await
        .map_err(|e| format!("read controller_placement.json: {e}"))?;
    let v: serde_json::Value =
        serde_json::from_str(&raw).map_err(|e| format!("invalid controller_placement.json: {e}"))?;
    let host = v
        .get("host")
        .and_then(|x| x.as_str())
        .filter(|s| !s.trim().is_empty())
        .ok_or_else(|| "controller_placement.json: host missing or empty".to_string())?;
    if host.is_empty() {
        return Err("controller_placement.json: host empty".to_string());
    }
    v.get("port")
        .and_then(|x| x.as_u64())
        .ok_or_else(|| "controller_placement.json: port missing or invalid".to_string())?;
    Ok(())
}

/// Run venv (0), pip deps (1), engine copy (2). No scan events unless `app_handle` set.
///
/// Each step's outcome is recorded in `state/act_b_bootstrap.log` so the very
/// first deploy on a clean host has an audit trail the UI can surface verbatim
/// (e.g. pip resolver errors, missing system deps). Doctrine: never depend on
/// WAN, never auto-mutate, only diagnose.
pub async fn execute_materialize(
    phantom_root: &Path,
    engine_source: &Path,
    offline_bundle: Option<PathBuf>,
    app_handle: Option<tauri::AppHandle>,
) -> Result<(), String> {
    append_bootstrap_log(
        phantom_root,
        "begin",
        0,
        &format!(
            "engine_source={} offline_bundle={}",
            engine_source.display(),
            offline_bundle
                .as_ref()
                .map(|p| p.display().to_string())
                .unwrap_or_else(|| "<none>".to_string())
        ),
    );
    let deployer = PhantomDeployer::new(phantom_root, engine_source, app_handle)
        .with_offline_bundle(offline_bundle);
    for step in 0..=2u8 {
        match deployer.run_step(step as usize).await {
            Ok(()) => append_bootstrap_log(phantom_root, "ok", step, ""),
            Err(e) => {
                append_bootstrap_log(phantom_root, "fail", step, &e);
                return Err(format!("Act B materialize step {step}: {e}"));
            }
        }
    }
    append_bootstrap_log(phantom_root, "complete", 2, "all steps ok");
    Ok(())
}
