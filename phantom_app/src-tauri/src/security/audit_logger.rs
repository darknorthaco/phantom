use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use tokio::io::AsyncWriteExt;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub timestamp: String,
    pub event_type: String,
    pub details: serde_json::Value,
}

pub struct AuditLogger {
    log_dir: PathBuf,
}

impl AuditLogger {
    pub fn new(state_dir: &Path) -> Self {
        Self {
            log_dir: state_dir.join("audit"),
        }
    }

    pub async fn init(&self) -> Result<(), String> {
        tokio::fs::create_dir_all(&self.log_dir)
            .await
            .map_err(|e| format!("Failed to create audit dir: {e}"))
    }

    pub async fn log_event(
        &self,
        event_type: &str,
        details: serde_json::Value,
    ) -> Result<(), String> {
        let entry = AuditEntry {
            timestamp: Utc::now().to_rfc3339(),
            event_type: event_type.to_string(),
            details,
        };

        let line = serde_json::to_string(&entry).map_err(|e| e.to_string())?;

        let log_file = self.log_dir.join("phantom_audit.jsonl");
        let mut file = tokio::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_file)
            .await
            .map_err(|e| format!("Failed to open audit log: {e}"))?;

        file.write_all(line.as_bytes())
            .await
            .map_err(|e| format!("Failed to write audit entry: {e}"))?;
        file.write_all(b"\n")
            .await
            .map_err(|e| format!("Failed to write newline: {e}"))?;

        Ok(())
    }

    /// Append an audit line; on disk/IO failure logs **warn** (never silent).
    pub async fn log_event_best_effort(&self, event_type: &str, details: serde_json::Value) {
        if let Err(e) = self.log_event(event_type, details).await {
            log::warn!(
                target: "phantom_audit",
                "audit_write_failed event_type={} error={}",
                event_type,
                e
            );
        }
    }

    pub async fn read_entries(&self, limit: usize) -> Result<Vec<AuditEntry>, String> {
        let log_file = self.log_dir.join("phantom_audit.jsonl");
        if !log_file.exists() {
            return Ok(Vec::new());
        }

        let content = tokio::fs::read_to_string(&log_file)
            .await
            .map_err(|e| format!("Failed to read audit log: {e}"))?;

        let entries: Vec<AuditEntry> = content
            .lines()
            .rev()
            .take(limit)
            .filter_map(|line| serde_json::from_str(line).ok())
            .collect();

        Ok(entries)
    }

    pub async fn rotate_logs(&self) -> Result<(), String> {
        let log_file = self.log_dir.join("phantom_audit.jsonl");
        if !log_file.exists() {
            return Ok(());
        }

        let timestamp = Utc::now().format("%Y%m%d_%H%M%S");
        let archive = self
            .log_dir
            .join(format!("phantom_audit_{timestamp}.jsonl"));

        tokio::fs::rename(&log_file, &archive)
            .await
            .map_err(|e| format!("Failed to rotate audit log: {e}"))
    }
}
