//! Act B — materialize venv + pip + engine copy (Phase 2 / Phase 11.2).
//! Delegates to `PhantomDeployer` steps 0–2 only (no service install / config acts).

use std::path::{Path, PathBuf};

use crate::backend::phantom_deployer::PhantomDeployer;

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
pub async fn execute_materialize(
    phantom_root: &Path,
    engine_source: &Path,
    offline_bundle: Option<PathBuf>,
    app_handle: Option<tauri::AppHandle>,
) -> Result<(), String> {
    let deployer = PhantomDeployer::new(phantom_root, engine_source, app_handle)
        .with_offline_bundle(offline_bundle);
    for step in 0..=2u8 {
        deployer
            .run_step(step as usize)
            .await
            .map_err(|e| format!("Act B materialize step {step}: {e}"))?;
    }
    Ok(())
}
