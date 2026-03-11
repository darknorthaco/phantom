//! Phantom §3/§5 — Append-only TrustStore for worker identity tracking.
//!
//! Records every trust-level transition per worker.  Implements TOFU
//! (Trust On First Use) key management and key-change detection.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::sync::Mutex;

// ---------------------------------------------------------------------------
// Event types / trust levels
// ---------------------------------------------------------------------------

/// Event types that trigger a TrustRecord.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum TrustEventType {
    #[serde(rename = "first_seen")]
    FirstSeen,
    #[serde(rename = "signature_valid")]
    SignatureValid,
    #[serde(rename = "key_changed")]
    KeyChanged,
    #[serde(rename = "signature_invalid")]
    SignatureInvalid,
}

/// Current trust level of a worker.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum TrustLevel {
    #[serde(rename = "unverified")]
    Unverified,
    #[serde(rename = "sig_valid")]
    SigValid,
    #[serde(rename = "approved")]
    Approved,
    #[serde(rename = "registered")]
    Registered,
    #[serde(rename = "revoked")]
    Revoked,
}

// ---------------------------------------------------------------------------
// TrustRecord
// ---------------------------------------------------------------------------

/// Immutable record written at every trust-level transition.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrustRecord {
    pub worker_id: String,
    pub public_key: String,
    pub event_type: TrustEventType,
    pub trust_level: TrustLevel,
    pub timestamp: f64,
    #[serde(default)]
    pub reason: String,
}

// ---------------------------------------------------------------------------
// TrustStore
// ---------------------------------------------------------------------------

/// Persistent, append-only trust ledger.
///
/// Storage: `<state_dir>/trust_store.jsonl` (one JSON record per line).
pub struct TrustStore {
    path: PathBuf,
    records: Mutex<HashMap<String, Vec<TrustRecord>>>,
}

impl TrustStore {
    /// Create or open a TrustStore in the given state directory.
    pub fn new(state_dir: &std::path::Path) -> Self {
        let _ = fs::create_dir_all(state_dir);
        let path = state_dir.join("trust_store.jsonl");
        let store = Self {
            path,
            records: Mutex::new(HashMap::new()),
        };
        store.load();
        store
    }

    /// Load records from disk into memory.
    fn load(&self) {
        if !self.path.exists() {
            return;
        }
        let file = match fs::File::open(&self.path) {
            Ok(f) => f,
            Err(e) => {
                log::warn!("TrustStore load error: {e}");
                return;
            }
        };
        let reader = BufReader::new(file);
        let mut map = self.records.lock().unwrap();
        for line in reader.lines() {
            let line = match line {
                Ok(l) => l,
                Err(_) => continue,
            };
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            if let Ok(rec) = serde_json::from_str::<TrustRecord>(trimmed) {
                map.entry(rec.worker_id.clone())
                    .or_default()
                    .push(rec);
            }
        }
    }

    /// Append a TrustRecord (never modify or delete).
    pub fn write_record(&self, record: &TrustRecord) {
        // In-memory
        {
            let mut map = self.records.lock().unwrap();
            map.entry(record.worker_id.clone())
                .or_default()
                .push(record.clone());
        }
        // Persist
        if let Ok(mut f) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
        {
            if let Ok(json) = serde_json::to_string(record) {
                let _ = writeln!(f, "{json}");
            }
        }
    }

    /// Current trust level for a worker (most recent record).
    pub fn get_current_level(&self, worker_id: &str) -> Option<TrustLevel> {
        let map = self.records.lock().unwrap();
        map.get(worker_id)
            .and_then(|recs| recs.last())
            .map(|r| r.trust_level.clone())
    }

    /// Most recently recorded public key for a worker.
    pub fn get_current_key(&self, worker_id: &str) -> Option<String> {
        let map = self.records.lock().unwrap();
        map.get(worker_id)
            .and_then(|recs| recs.last())
            .map(|r| r.public_key.clone())
    }

    /// Full trust history for a worker.
    pub fn get_history(&self, worker_id: &str) -> Vec<TrustRecord> {
        let map = self.records.lock().unwrap();
        map.get(worker_id).cloned().unwrap_or_default()
    }

    /// Record a signature verification result with TOFU key-change detection.
    pub fn record_verification(
        &self,
        worker_id: &str,
        public_key: &str,
        signature_valid: bool,
    ) {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);

        let existing_key = self.get_current_key(worker_id);

        // Key-change detection
        if let Some(ref old_key) = existing_key {
            if old_key != public_key {
                self.write_record(&TrustRecord {
                    worker_id: worker_id.to_string(),
                    public_key: public_key.to_string(),
                    event_type: TrustEventType::KeyChanged,
                    trust_level: TrustLevel::Unverified,
                    timestamp: now,
                    reason: "key_change_detected".to_string(),
                });
                log::warn!("Key change detected for worker {worker_id}");
            }
        }

        // First-seen
        if existing_key.is_none() {
            self.write_record(&TrustRecord {
                worker_id: worker_id.to_string(),
                public_key: public_key.to_string(),
                event_type: TrustEventType::FirstSeen,
                trust_level: TrustLevel::Unverified,
                timestamp: now,
                reason: "first_contact".to_string(),
            });
        }

        // Signature result
        if signature_valid {
            self.write_record(&TrustRecord {
                worker_id: worker_id.to_string(),
                public_key: public_key.to_string(),
                event_type: TrustEventType::SignatureValid,
                trust_level: TrustLevel::SigValid,
                timestamp: now,
                reason: "signature_verified".to_string(),
            });
        } else {
            self.write_record(&TrustRecord {
                worker_id: worker_id.to_string(),
                public_key: public_key.to_string(),
                event_type: TrustEventType::SignatureInvalid,
                trust_level: TrustLevel::Unverified,
                timestamp: now,
                reason: "signature_verification_failed".to_string(),
            });
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    fn tmp_store(name: &str) -> TrustStore {
        let dir = std::env::temp_dir().join("phantom_test_trust").join(name);
        let _ = fs::remove_dir_all(&dir);
        TrustStore::new(&dir)
    }

    #[test]
    fn append_only_produces_multiple_records() {
        let store = tmp_store("append_only");
        store.record_verification("w1", "key_a", true);
        store.record_verification("w1", "key_a", true);
        let history = store.get_history("w1");
        // first_seen + sig_valid + sig_valid (second call only adds sig_valid)
        assert!(history.len() >= 3);
    }

    #[test]
    fn current_level_returns_most_recent() {
        let store = tmp_store("current_level");
        store.record_verification("w1", "key_a", true);
        assert_eq!(
            store.get_current_level("w1"),
            Some(TrustLevel::SigValid)
        );
        store.record_verification("w1", "key_a", false);
        assert_eq!(
            store.get_current_level("w1"),
            Some(TrustLevel::Unverified)
        );
    }

    #[test]
    fn key_change_detection() {
        let store = tmp_store("key_change");
        store.record_verification("w1", "key_a", true);
        store.record_verification("w1", "key_b", true);
        let history = store.get_history("w1");
        let key_changed = history
            .iter()
            .any(|r| r.event_type == TrustEventType::KeyChanged);
        assert!(key_changed, "Expected a key_changed event");
    }

    #[test]
    fn unknown_worker_returns_none() {
        let store = tmp_store("unknown");
        assert_eq!(store.get_current_level("unknown"), None);
        assert_eq!(store.get_current_key("unknown"), None);
    }
}
