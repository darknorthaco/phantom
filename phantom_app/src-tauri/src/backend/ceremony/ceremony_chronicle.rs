//! Phase 11 — Ceremony chronicle (JSONL, `schema_version` **2** per Phase 12 PR-A).
//!
//! Schema v2 (PR-A / I-ChronicleSeverity):
//!   - Adds `severity` (enum) so doctrine drift is machine-readable.
//!   - Keeps `outcome_class` for back-compat but severity is authoritative.
//!   - CI gates (PR-D) read this field; `DoctrineViolation` MUST fail release.
//!
//! Severity taxonomy:
//!   - Info            — normal lifecycle events (act begin/end).
//!   - Warn            — recoverable anomalies (partial registration, degraded /health).
//!   - Critical        — ceremony failure requiring recovery.
//!   - DoctrineViolation — legacy / quarantined path invoked; MUST NOT appear in a
//!                         clean-install release chronicle.

use std::io::Write;
use std::path::Path;

use serde::Serialize;

pub const CEREMONY_CHRONICLE_SCHEMA_VERSION: &str = "2";

/// PR-A: machine-readable severity classification for chronicle entries.
#[derive(Debug, Clone, Copy, Serialize, PartialEq, Eq)]
#[serde(rename_all = "PascalCase")]
pub enum Severity {
    Info,
    Warn,
    Critical,
    DoctrineViolation,
}

impl Severity {
    pub fn as_str(&self) -> &'static str {
        match self {
            Severity::Info => "Info",
            Severity::Warn => "Warn",
            Severity::Critical => "Critical",
            Severity::DoctrineViolation => "DoctrineViolation",
        }
    }
}

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
    /// PR-A: severity is authoritative. Defaults to `Info` on legacy callers via
    /// `new()`; doctrine-sensitive call sites must use `new_with_severity()`.
    pub severity: Severity,
    pub summary: String,
}

impl CeremonyChronicleLine {
    /// Legacy constructor — defaults severity to `Info`. Prefer
    /// `new_with_severity` for any doctrine-sensitive event.
    pub fn new(
        event_type: impl Into<String>,
        correlation_id: Option<String>,
        act: Option<String>,
        s_ceremony_before: impl Into<String>,
        s_ceremony_after: impl Into<String>,
        outcome_class: Option<String>,
        summary: impl Into<String>,
    ) -> Self {
        Self::new_with_severity(
            event_type,
            correlation_id,
            act,
            s_ceremony_before,
            s_ceremony_after,
            outcome_class,
            Severity::Info,
            summary,
        )
    }

    /// PR-A: doctrine-aware constructor. Use for any event that can be a
    /// `Warn` / `Critical` / `DoctrineViolation`.
    #[allow(clippy::too_many_arguments)]
    pub fn new_with_severity(
        event_type: impl Into<String>,
        correlation_id: Option<String>,
        act: Option<String>,
        s_ceremony_before: impl Into<String>,
        s_ceremony_after: impl Into<String>,
        outcome_class: Option<String>,
        severity: Severity,
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
            severity,
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

/// Recovery hint when ceremony remains on an arbitrary phase.
pub fn append_recovery_target_for_phase(
    phantom_root: &Path,
    correlation_id: Option<&str>,
    target_act: &str,
    s_ceremony: &str,
) -> Result<(), String> {
    append_ceremony_line(
        phantom_root,
        &CeremonyChronicleLine::new_with_severity(
            "recovery_target",
            correlation_id.map(String::from),
            Some(target_act.to_string()),
            s_ceremony,
            s_ceremony,
            None,
            Severity::Warn,
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn severity_serializes_as_pascal_case() {
        let line = CeremonyChronicleLine::new_with_severity(
            "test",
            None,
            None,
            "-",
            "-",
            None,
            Severity::DoctrineViolation,
            "test",
        );
        let json = serde_json::to_string(&line).unwrap();
        assert!(json.contains("\"severity\":\"DoctrineViolation\""), "{json}");
        assert!(json.contains("\"schemaVersion\":\"2\""), "{json}");
    }

    #[test]
    fn default_constructor_is_info() {
        let line = CeremonyChronicleLine::new("test", None, None, "-", "-", None, "msg");
        assert_eq!(line.severity, Severity::Info);
    }
}
