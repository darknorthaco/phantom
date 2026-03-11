//! Phantom Discovery Log — structured log for deployment ceremony diagnostics.
//!
//! Built during LAN scan; provides sanitized, copy/paste-ready output when
//! zero workers are detected.

use serde::Serialize;

/// Structured discovery log emitted on every scan.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DiscoveryLog {
    pub timestamp: String,
    pub interfaces_scanned: Vec<String>,
    pub broadcast_port: u16,
    pub packets_sent: u32,
    pub responses_received: u32,
    pub signature_failures: u32,
    pub manifest_errors: u32,
    pub worker_count: usize,
    pub raw_entries: Vec<String>,
}

impl DiscoveryLog {
    /// Produce a sanitized, copy/paste-ready string for diagnostic sharing.
    pub fn to_sanitized_string(&self) -> String {
        let mut lines = Vec::new();
        lines.push(format!("Phantom Discovery Log — {}", self.timestamp));
        lines.push(format!("Interfaces scanned: {:?}", self.interfaces_scanned));
        lines.push(format!("Broadcast port: {}", self.broadcast_port));
        lines.push(format!("Packets sent: {}", self.packets_sent));
        lines.push(format!("Responses received: {}", self.responses_received));
        lines.push(format!("Signature failures: {}", self.signature_failures));
        lines.push(format!("Manifest parse errors: {}", self.manifest_errors));
        lines.push(format!("Worker count: {}", self.worker_count));
        lines.push("--- Raw entries ---".to_string());
        for entry in &self.raw_entries {
            lines.push(entry.clone());
        }
        lines.join("\n")
    }
}

/// Builder for DiscoveryLog, used during scanning.
pub struct DiscoveryLogBuilder {
    timestamp: String,
    interfaces_scanned: Vec<String>,
    broadcast_port: u16,
    packets_sent: u32,
    responses_received: u32,
    signature_failures: u32,
    manifest_errors: u32,
    raw_entries: Vec<String>,
}

impl DiscoveryLogBuilder {
    pub fn new(interfaces_scanned: Vec<String>, broadcast_port: u16) -> Self {
        Self {
            timestamp: chrono::Utc::now().to_rfc3339(),
            interfaces_scanned,
            broadcast_port,
            packets_sent: 0,
            responses_received: 0,
            signature_failures: 0,
            manifest_errors: 0,
            raw_entries: Vec::new(),
        }
    }

    pub fn push_raw(&mut self, entry: impl AsRef<str>) {
        let s = entry.as_ref().to_string();
        self.raw_entries.push(s);
    }

    pub fn inc_packets_sent(&mut self) {
        self.packets_sent += 1;
    }

    pub fn inc_responses_received(&mut self, signature_verified: bool) {
        self.responses_received += 1;
        if !signature_verified {
            self.signature_failures += 1;
        }
    }

    pub fn inc_manifest_error(&mut self) {
        self.manifest_errors += 1;
    }

    pub fn build(self, worker_count: usize) -> DiscoveryLog {
        DiscoveryLog {
            timestamp: self.timestamp,
            interfaces_scanned: self.interfaces_scanned,
            broadcast_port: self.broadcast_port,
            packets_sent: self.packets_sent,
            responses_received: self.responses_received,
            signature_failures: self.signature_failures,
            manifest_errors: self.manifest_errors,
            worker_count,
            raw_entries: self.raw_entries,
        }
    }
}
