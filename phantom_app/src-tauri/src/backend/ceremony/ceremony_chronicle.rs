//! Phase 11 — Ceremony chronicle (JSONL, `schema_version` 1 per Phase 3 §6).

use std::io::Write;
use std::path::Path;

use serde::Serialize;

pub const CEREMONY_CHRONICLE_SCHEMA_VERSION: &str = "1";

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CeremonyChronicleLine {
    pub schema_version: String,
    pub event_type: String,
    pub correlation_id: Option<String>,
    pub timestamp: String,
    pub act: Option<String>,
    pub s_ceremony_before: String,
    pub s_ceremony_after: String,
    pub outcome_class: Option<String>,
    pub summary: String,
}

impl CeremonyChronicleLine {
    pub fn new(
        event_type: impl Into<String>,
        correlation_id: Option<String>,
        act: Option<String>,
        s_ceremony_before: impl Into<String>,
        s_ceremony_after: impl Into<String>,
        outcome_class: Option<String>,
        summary: impl Into<String>,
    ) -> Self {
        Self {
            schema_version: CEREMONY_CHRONICLE_SCHEMA_VERSION.to_string(),
            event_type: event_type.into(),
            correlation_id,
            timestamp: chrono::Utc::now().to_rfc3339(),
            act,
            s_ceremony_before: s_ceremony_before.into(),
            s_ceremony_after: s_ceremony_after.into(),
            outcome_class,
            summary: summary.into(),
        }
    }
}

fn chronicle_path(phantom_root: &Path) -> std::path::PathBuf {
    phantom_root.join("state").join("ceremony_chronicle.jsonl")
}

/// Recovery routing hint when ceremony remains on `CS_PLACEMENT` (e.g. Act B failure).
pub fn append_recovery_target(
    phantom_root: &Path,
    correlation_id: Option<&str>,
    target_act: &str,
) -> Result<(), String> {
    append_recovery_target_for_phase(phantom_root, correlation_id, target_act, "CS_PLACEMENT")
}

/// Recovery hint when ceremony remains on an arbitrary phase (e.g. `CS_MATERIALIZE` after Act C failure).
pub fn append_recovery_target_for_phase(
    phantom_root: &Path,
    correlation_id: Option<&str>,
    target_act: &str,
    s_ceremony: &str,
) -> Result<(), String> {
    append_ceremony_line(
        phantom_root,
        &CeremonyChronicleLine::new(
            "recovery_target",
            correlation_id.map(String::from),
            Some(target_act.to_string()),
            s_ceremony,
            s_ceremony,
            None,
            format!("recovery_target_act={target_act}"),
        ),
    )
}

/// Append one JSON line (valid JSONL). Best-effort: errors returned to caller.
pub fn append_ceremony_line(phantom_root: &Path, line: &CeremonyChronicleLine) -> Result<(), String> {
    let path = chronicle_path(phantom_root);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let json = serde_json::to_string(line).map_err(|e| e.to_string())?;
    let mut f = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|e| format!("open ceremony chronicle: {e}"))?;
    writeln!(f, "{json}").map_err(|e| e.to_string())?;
    Ok(())
}
