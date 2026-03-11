//! Phantom Discovery Log — structured log for deployment ceremony diagnostics.
//!
//! Built during LAN scan; provides sanitized, copy/paste-ready output when
//! zero workers are detected.

use serde::Serialize;

/// Single entry in the Full Deployment Initialization Log (Phase 4).
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FullDeployLogEntry {
    pub timestamp: String,
    pub step_index: u32,
    pub step_name: String,
    pub success: bool,
    pub duration_ms: u64,
    pub metadata: Option<serde_json::Value>,
    pub error_message: Option<String>,
}

/// Single entry in the Dependency Initialization Log (Phase 3).
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DependencyInitEntry {
    pub timestamp: String,
    pub item: String,
    pub success: bool,
    pub duration_ms: u64,
}

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
    /// Number of readiness probe attempts made before the LAN scan.
    pub readiness_probe_attempts: u32,
    /// Whether the readiness probe received a response from the local worker.
    pub readiness_probe_success: bool,
    /// Actionable hints shown when worker_count == 0.
    pub diagnostic_hints: Vec<String>,
    /// Discovery window start timestamp (RFC3339). For Phase 3 "Discovery Timing Breakdown".
    pub discovery_start_timestamp: String,
    /// Discovery window end timestamp (RFC3339). Dependency Initialization Log.
    pub discovery_end_timestamp: String,
    /// Total discovery duration in milliseconds.
    pub discovery_duration_ms: u64,
    /// Dependency Initialization Log — each dependency load before discovery.
    pub dependency_init_log: Vec<DependencyInitEntry>,
    /// Total timeout (ms) configured for the discovery window.
    pub discovery_total_timeout_ms: u64,
    /// Number of recv poll cycles in the discovery loop.
    pub discovery_poll_cycles: u32,
    /// Full Deployment Initialization Log — every step from Deploy click to discovery (Phase 4).
    pub full_deploy_log: Vec<FullDeployLogEntry>,
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
        if self.readiness_probe_attempts > 0 {
            lines.push(format!(
                "Readiness probe: {} (attempts: {})",
                if self.readiness_probe_success {
                    "succeeded"
                } else {
                    "timed out"
                },
                self.readiness_probe_attempts,
            ));
        }
        lines.push("--- Full Deployment Initialization Log ---".to_string());
        for entry in &self.full_deploy_log {
            let meta = entry
                .metadata
                .as_ref()
                .map(|v| format!(" | {:?}", v))
                .unwrap_or_default();
            let err = entry
                .error_message
                .as_ref()
                .map(|e| format!(" | error: {e}"))
                .unwrap_or_default();
            lines.push(format!(
                "{} | #{} | {} | {} | {} ms{}{}",
                entry.timestamp,
                entry.step_index,
                entry.step_name,
                if entry.success { "ok" } else { "FAIL" },
                entry.duration_ms,
                meta,
                err
            ));
        }
        lines.push("--- Discovery Timing Breakdown ---".to_string());
        lines.push(format!("Start: {}", self.discovery_start_timestamp));
        lines.push(format!("End: {}", self.discovery_end_timestamp));
        lines.push(format!("Duration: {} ms", self.discovery_duration_ms));
        lines.push(format!("Total timeout used: {} ms", self.discovery_total_timeout_ms));
        lines.push(format!("Responses received: {}", self.responses_received));
        lines.push(format!("Poll cycles: {}", self.discovery_poll_cycles));
        lines.push("--- Dependency Initialization Log ---".to_string());
        for entry in &self.dependency_init_log {
            lines.push(format!(
                "{} | {} | {} | {} ms",
                entry.timestamp,
                entry.item,
                if entry.success { "ok" } else { "FAIL" },
                entry.duration_ms
            ));
        }
        lines.push("--- Raw entries ---".to_string());
        for entry in &self.raw_entries {
            lines.push(entry.clone());
        }
        if self.worker_count == 0 && !self.diagnostic_hints.is_empty() {
            lines.push("--- Possible causes ---".to_string());
            for hint in &self.diagnostic_hints {
                lines.push(format!("  • {hint}"));
            }
        }
        lines.join("\n")
    }

    /// Set readiness probe result (post-build enrichment).
    pub fn set_readiness_result(&mut self, attempts: u32, success: bool) {
        self.readiness_probe_attempts = attempts;
        self.readiness_probe_success = success;
    }

    /// Append a diagnostic hint (shown when worker_count == 0).
    pub fn add_diagnostic_hint(&mut self, hint: impl AsRef<str>) {
        self.diagnostic_hints.push(hint.as_ref().to_string());
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
    readiness_probe_attempts: u32,
    readiness_probe_success: bool,
    diagnostic_hints: Vec<String>,
    discovery_start_timestamp: String,
    discovery_end_timestamp: String,
    discovery_duration_ms: u64,
    dependency_init_log: Vec<DependencyInitEntry>,
    discovery_total_timeout_ms: u64,
    discovery_poll_cycles: u32,
    full_deploy_log: Vec<FullDeployLogEntry>,
    step_index_counter: u32,
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
            readiness_probe_attempts: 0,
            readiness_probe_success: false,
            diagnostic_hints: Vec::new(),
            discovery_start_timestamp: String::new(),
            discovery_end_timestamp: String::new(),
            discovery_duration_ms: 0,
            dependency_init_log: Vec::new(),
            discovery_total_timeout_ms: 0,
            discovery_poll_cycles: 0,
            full_deploy_log: Vec::new(),
            step_index_counter: 0,
        }
    }

    /// Add a Full Deployment Initialization Log entry. Step index auto-increments.
    pub fn add_full_deploy_entry(
        &mut self,
        step_name: impl Into<String>,
        success: bool,
        duration_ms: u64,
        metadata: Option<serde_json::Value>,
        error_message: Option<String>,
    ) {
        self.step_index_counter += 1;
        self.full_deploy_log.push(FullDeployLogEntry {
            timestamp: chrono::Utc::now().to_rfc3339(),
            step_index: self.step_index_counter,
            step_name: step_name.into(),
            success,
            duration_ms,
            metadata,
            error_message,
        });
    }

    /// Add pre-built Full Deployment entries (e.g. from deployer). Preserves step_index.
    pub fn add_full_deploy_entries(&mut self, entries: impl IntoIterator<Item = FullDeployLogEntry>) {
        for e in entries {
            if e.step_index > self.step_index_counter {
                self.step_index_counter = e.step_index;
            }
            self.full_deploy_log.push(e);
        }
    }

    /// Record discovery window timing (for Phase 3 "Discovery Timing Breakdown").
    pub fn set_discovery_timing(
        &mut self,
        start: &str,
        end: &str,
        duration_ms: u64,
        total_timeout_ms: u64,
        poll_cycles: u32,
    ) {
        self.discovery_start_timestamp = start.to_string();
        self.discovery_end_timestamp = end.to_string();
        self.discovery_duration_ms = duration_ms;
        self.discovery_total_timeout_ms = total_timeout_ms;
        self.discovery_poll_cycles = poll_cycles;
    }

    /// Add a Dependency Initialization Log entry.
    pub fn add_dependency_init_entry(&mut self, entry: DependencyInitEntry) {
        self.dependency_init_log.push(entry);
    }

    /// Add multiple Dependency Initialization Log entries.
    pub fn add_dependency_init_entries(&mut self, entries: Vec<DependencyInitEntry>) {
        self.dependency_init_log.extend(entries);
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

    /// Record the outcome of the worker readiness probe.
    pub fn set_readiness_result(&mut self, attempts: u32, success: bool) {
        self.readiness_probe_attempts = attempts;
        self.readiness_probe_success = success;
    }

    /// Append a diagnostic hint (shown when worker_count == 0).
    pub fn add_diagnostic_hint(&mut self, hint: impl AsRef<str>) {
        self.diagnostic_hints.push(hint.as_ref().to_string());
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
            readiness_probe_attempts: self.readiness_probe_attempts,
            readiness_probe_success: self.readiness_probe_success,
            diagnostic_hints: self.diagnostic_hints,
            discovery_start_timestamp: self.discovery_start_timestamp,
            discovery_end_timestamp: self.discovery_end_timestamp,
            discovery_duration_ms: self.discovery_duration_ms,
            dependency_init_log: self.dependency_init_log,
            discovery_total_timeout_ms: self.discovery_total_timeout_ms,
            discovery_poll_cycles: self.discovery_poll_cycles,
            full_deploy_log: self.full_deploy_log,
        }
    }
}
