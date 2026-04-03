//! Phase 11 — `state/ceremony_state.json` atomic persistence (Phase 3 §2.1).

use std::path::Path;

use serde::{Deserialize, Serialize};

use super::phase::CeremonyPhase;

pub const CEREMONY_STATE_SCHEMA_VERSION: &str = "1";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CeremonyStateFile {
    pub schema_version: String,
    /// Canonical `S_ceremony` string e.g. `CS_IDLE`.
    pub s_ceremony: String,
    pub correlation_id: Option<String>,
    pub last_completed_act: Option<String>,
    pub outcome_class: Option<String>,
    /// Set on Act failure for recovery routing (e.g. `"B"`); cleared on success paths.
    #[serde(default)]
    pub recovery_target_act: Option<String>,
    pub snapshot_id: Option<String>,
    pub updated_at: String,
}

impl Default for CeremonyStateFile {
    fn default() -> Self {
        Self {
            schema_version: CEREMONY_STATE_SCHEMA_VERSION.to_string(),
            s_ceremony: CeremonyPhase::Idle.as_str().to_string(),
            correlation_id: None,
            last_completed_act: None,
            outcome_class: None,
            recovery_target_act: None,
            snapshot_id: None,
            updated_at: chrono::Utc::now().to_rfc3339(),
        }
    }
}

fn state_path(phantom_root: &Path) -> std::path::PathBuf {
    phantom_root.join("state").join("ceremony_state.json")
}

/// Load from disk; missing → default `CS_IDLE`; corrupt → backup and default.
pub fn load(phantom_root: &Path) -> CeremonyStateFile {
    let path = state_path(phantom_root);
    let raw = match std::fs::read_to_string(&path) {
        Ok(s) => s,
        Err(_) => return CeremonyStateFile::default(),
    };
    match serde_json::from_str::<CeremonyStateFile>(&raw) {
        Ok(v) => v,
        Err(e) => {
            log::warn!("ceremony_state.json corrupt ({}); backing up and resetting to CS_IDLE", e);
            if path.exists() {
                let bak = path.with_extension(format!(
                    "json.bak.{}",
                    chrono::Utc::now().format("%Y%m%dT%H%M%SZ")
                ));
                let _ = std::fs::rename(&path, &bak);
            }
            CeremonyStateFile::default()
        }
    }
}

/// Atomic write: tmp in same directory, then rename.
pub fn atomic_write(phantom_root: &Path, state: &CeremonyStateFile) -> Result<(), String> {
    let path = state_path(phantom_root);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let mut s = state.clone();
    s.updated_at = chrono::Utc::now().to_rfc3339();
    let body = serde_json::to_string_pretty(&s).map_err(|e| e.to_string())?;
    let tmp = path.with_extension("json.tmp");
    std::fs::write(&tmp, body).map_err(|e| e.to_string())?;
    std::fs::rename(&tmp, &path).map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn missing_file_yields_idle() {
        let dir = tempdir().unwrap();
        let root = dir.path().join(".phantom");
        let s = load(&root);
        assert_eq!(s.s_ceremony, CeremonyPhase::Idle.as_str());
    }

    #[test]
    fn round_trip_atomic() {
        let dir = tempdir().unwrap();
        let root = dir.path();
        let mut s = CeremonyStateFile::default();
        s.s_ceremony = CeremonyPhase::Placement.as_str().to_string();
        s.correlation_id = Some("test-corr".into());
        atomic_write(root, &s).unwrap();
        let s2 = load(root);
        assert_eq!(s2.s_ceremony, CeremonyPhase::Placement.as_str());
        assert_eq!(s2.correlation_id.as_deref(), Some("test-corr"));
    }
}
