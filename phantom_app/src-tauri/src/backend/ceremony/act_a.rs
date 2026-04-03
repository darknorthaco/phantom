//! Act A — placement only (Phase 2 / Phase 11). Does not touch `S_ceremony`; orchestrator owns transitions.

use std::path::Path;

/// Validate placement payload before write.
pub fn validate_placement(host: &str, port: u16, device_label: &str, identity_fingerprint: &str) -> Result<(), String> {
    if host.trim().is_empty() {
        return Err("host must not be empty".to_string());
    }
    if port == 0 {
        return Err("port must be > 0".to_string());
    }
    if device_label.trim().is_empty() {
        return Err("device_label must not be empty".to_string());
    }
    if identity_fingerprint.trim().is_empty() {
        return Err("identity_fingerprint must not be empty".to_string());
    }
    Ok(())
}

/// Persist `controller_placement.json` atomically (same contract as legacy confirm_controller_placement).
pub async fn write_placement_file(
    phantom_root: &Path,
    host: &str,
    port: u16,
    device_label: &str,
    identity_fingerprint: &str,
) -> Result<(), String> {
    validate_placement(host, port, device_label, identity_fingerprint)?;
    tokio::fs::create_dir_all(phantom_root)
        .await
        .map_err(|e| format!("create phantom root: {e}"))?;
    let path = phantom_root.join("controller_placement.json");
    let params = serde_json::json!({
        "host": host,
        "port": port,
        "device_label": device_label,
        "identity_fingerprint": identity_fingerprint,
        "confirmed_at": chrono::Utc::now().to_rfc3339(),
    });
    let tmp = phantom_root.join("controller_placement.json.tmp");
    let body = serde_json::to_string_pretty(&params).map_err(|e| e.to_string())?;
    tokio::fs::write(&tmp, body)
        .await
        .map_err(|e| format!("write placement tmp: {e}"))?;
    tokio::fs::rename(&tmp, &path)
        .await
        .map_err(|e| format!("rename placement: {e}"))?;
    Ok(())
}
