//! Deployment Chronicle — append-only JSONL at ``<phantom_root>/deployment_chronicle.jsonl``.
//! Survives controller/worker failures (written from the Tauri shell, not Python).

use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;

use serde::Serialize;
#[derive(Debug, Clone, Serialize)]
pub struct ChronicleRecord {
    pub ts: String,
    /// e.g. ``deploy_failed``, ``troubleshooter``, ``port_cycle``, ``user``
    pub source: String,
    pub level: String,
    pub summary: String,
    pub details: serde_json::Value,
}

impl ChronicleRecord {
    pub fn new(source: impl Into<String>, level: impl Into<String>, summary: impl Into<String>) -> Self {
        Self {
            ts: chrono::Utc::now().to_rfc3339(),
            source: source.into(),
            level: level.into(),
            summary: summary.into(),
            details: serde_json::json!({}),
        }
    }

    pub fn with_details(mut self, details: serde_json::Value) -> Self {
        self.details = details;
        self
    }
}

fn chronicle_path(phantom_root: &Path) -> std::path::PathBuf {
    phantom_root.join("deployment_chronicle.jsonl")
}

/// Blocking append (safe from sync ``emit`` paths and async commands via ``spawn_blocking``).
pub fn append_blocking(phantom_root: &Path, record: &ChronicleRecord) -> Result<(), String> {
    let path = chronicle_path(phantom_root);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let line = serde_json::to_string(record).map_err(|e| e.to_string())?;
    let mut f = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|e| format!("open chronicle: {e}"))?;
    writeln!(f, "{line}").map_err(|e| e.to_string())?;
    Ok(())
}

pub async fn append(phantom_root: &Path, record: ChronicleRecord) -> Result<(), String> {
    let root = phantom_root.to_path_buf();
    let rec = record;
    tokio::task::spawn_blocking(move || append_blocking(&root, &rec))
        .await
        .map_err(|e| e.to_string())?
}

/// Read last ``max_lines`` non-empty lines (newest at end of file; returned oldest-first).
pub async fn read_tail(phantom_root: &Path, max_lines: usize) -> Result<Vec<String>, String> {
    let path = chronicle_path(phantom_root);
    let raw = tokio::fs::read_to_string(&path)
        .await
        .unwrap_or_default();
    let mut lines: Vec<String> = raw.lines().map(|s| s.to_string()).filter(|s| !s.is_empty()).collect();
    if lines.len() > max_lines {
        lines = lines.split_off(lines.len() - max_lines);
    }
    Ok(lines)
}
