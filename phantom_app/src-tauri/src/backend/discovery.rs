//! Phantom discovery: broadcast DISCOVER_WORKERS, workers self-identify with signed manifests.
//! No host probing, ARP, or port scanning. Subnets from NIC enumeration only.
//!
//! §3 integration: incoming manifests are parsed as SignedManifest, signature is
//! verified, and the `signature_verified` flag is set before returning results.
//!
//! Discovery uses a single UDP socket and a configurable total window
//! (discovery_total_timeout_ms). All targets are probed up front; responses
//! are collected in one listen loop until the window expires or early exit.

use super::discovery_log::{DependencyInitEntry, DiscoveryLogBuilder};
use super::worker_info::{RawWireManifest, SignedManifest};
use std::collections::HashSet;
use std::io::ErrorKind;
use std::net::UdpSocket;
use std::time::Duration;

/// Well-known discovery port. Workers listen here for DISCOVER_WORKERS.
pub const DISCOVERY_PORT: u16 = 8095;

/// Discovery request sent via UDP broadcast.
const DISCOVER_PAYLOAD: &[u8] = b"PHANTOM_DISCOVER_WORKERS";

/// Default total discovery window when config is unavailable.
pub const DEFAULT_DISCOVERY_TOTAL_TIMEOUT_MS: u64 = 10000;

/// Discovered worker manifest with source IP and verification status.
#[derive(Debug, Clone)]
pub struct DiscoveredManifest {
    pub manifest: SignedManifest,
    /// Port from legacy manifests (kept for backward compat).
    pub port: u16,
    /// IP the manifest was received from (UDP source).
    pub source_ip: String,
    /// Whether the Ed25519 signature was verified.
    pub signature_verified: bool,
    /// Short hex fingerprint of the public key.
    pub fingerprint: String,
}

impl DiscoveredManifest {
    /// The host to use for registration — prefer manifest address, fall back to source IP.
    pub fn registration_host(&self) -> String {
        if self.manifest.address == "0.0.0.0" || self.manifest.address.is_empty() {
            self.source_ip.clone()
        } else {
            self.manifest.address.clone()
        }
    }

    /// Convenience accessor — worker_id.
    pub fn worker_id(&self) -> &str {
        &self.manifest.worker_id
    }
}

// Backward-compat type alias used by phantom_deployer.
pub type WorkerManifest = DiscoveredManifest;

impl WorkerManifest {
    // Legacy field accessors for backward compatibility with phantom_deployer.
    pub fn host(&self) -> &str {
        &self.manifest.address
    }
    pub fn gpu_info(&self) -> &serde_json::Value {
        &self.manifest.capabilities
    }
}

/// Convert subnet base (e.g. "192.168.1.1") to broadcast address (e.g. "192.168.1.255").
pub fn base_to_broadcast(base_ip: &str) -> Option<String> {
    let parts: Vec<&str> = base_ip.split('.').collect();
    if parts.len() != 4 {
        return None;
    }
    Some(format!("{}.{}.{}.255", parts[0], parts[1], parts[2]))
}

/// Parse a raw UDP payload into a DiscoveredManifest. Handles both legacy
/// unsigned manifests and new SignedManifest format.
fn parse_manifest(raw: &str, source_ip: &str) -> Option<DiscoveredManifest> {
    let wire: RawWireManifest = serde_json::from_str(raw).ok()?;
    if wire.effective_msg_type() != "WORKER_MANIFEST" || wire.worker_id.is_empty() {
        return None;
    }
    let port = wire.port;
    let signed = wire.into_signed_manifest();
    let signature_verified = signed.verify_signature();
    let fingerprint = signed.fingerprint();

    Some(DiscoveredManifest {
        manifest: signed,
        port,
        source_ip: source_ip.to_string(),
        signature_verified,
        fingerprint,
    })
}

/// Single-window discovery: one socket, send to 127.0.0.1 and all broadcast
/// addresses, then listen for up to `total_timeout_ms` collecting responses.
/// When `early_exit_on_first_worker` is true, exits as soon as at least one
/// valid manifest is received.
pub(crate) fn discover_single_window(
    broadcast_addrs: &[String],
    total_timeout_ms: u64,
    early_exit_on_first_worker: bool,
    mut log: Option<&mut DiscoveryLogBuilder>,
) -> Vec<DiscoveredManifest> {
    let start = std::time::Instant::now();
    let start_rfc3339 = chrono::Utc::now().to_rfc3339();

    let bind_start = std::time::Instant::now();
    let socket = match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => {
            let dur = bind_start.elapsed().as_millis() as u64;
            if let Some(ref mut l) = log {
                l.add_dependency_init_entry(DependencyInitEntry {
                    timestamp: chrono::Utc::now().to_rfc3339(),
                    item: "socket_bind (UDP 0.0.0.0:0)".to_string(),
                    success: true,
                    duration_ms: dur,
                });
                l.add_full_deploy_entry("socket_create", true, dur, None, None);
            }
            s
        }
        Err(e) => {
            let dur = bind_start.elapsed().as_millis() as u64;
            let err_msg = e.to_string();
            log::error!(
                "discovery: cannot bind UDP socket 0.0.0.0:0 — no LAN discovery ({e})"
            );
            if let Some(ref mut l) = log {
                l.push_raw(&format!("bind error: {e}"));
                l.add_dependency_init_entry(DependencyInitEntry {
                    timestamp: chrono::Utc::now().to_rfc3339(),
                    item: "socket_bind (UDP 0.0.0.0:0)".to_string(),
                    success: false,
                    duration_ms: dur,
                });
                l.add_full_deploy_entry("socket_create", false, dur, None, Some(err_msg));
            }
            return vec![];
        }
    };
    let broadcast_ok = socket.set_broadcast(true).is_ok();
    if !broadcast_ok {
        log::warn!("discovery: UDP set_broadcast(true) failed — broadcast sends may not leave this host");
    }
    if let Some(ref mut l) = log {
        l.add_full_deploy_entry(
            "socket_set_broadcast",
            broadcast_ok,
            0,
            Some(serde_json::json!({"flag": true})),
            if broadcast_ok {
                None
            } else {
                Some("set_broadcast failed".to_string())
            },
        );
    }

    // Send to 127.0.0.1
    let target_loopback = format!("127.0.0.1:{}", DISCOVERY_PORT);
    let loopback_start = std::time::Instant::now();
    let loopback_ok = match socket.send_to(DISCOVER_PAYLOAD, &target_loopback) {
        Ok(_) => true,
        Err(e) => {
            log::warn!(
                "discovery: loopback send_to {target_loopback} failed ({} bytes): {e}",
                DISCOVER_PAYLOAD.len()
            );
            false
        }
    };
    if loopback_ok {
        if let Some(ref mut l) = log {
            l.inc_packets_sent();
            l.push_raw(&format!("Sent DISCOVER_WORKERS to {target_loopback}"));
            l.add_full_deploy_entry(
                "discovery_send_loopback",
                true,
                loopback_start.elapsed().as_millis() as u64,
                Some(serde_json::json!({"target": &target_loopback})),
                None,
            );
        }
    } else if let Some(ref mut l) = log {
        l.add_full_deploy_entry(
            "discovery_send_loopback",
            false,
            loopback_start.elapsed().as_millis() as u64,
            Some(serde_json::json!({"target": &target_loopback})),
            Some("send_to failed".to_string()),
        );
    }

    // Send to each broadcast address
    let broadcast_targets: Vec<String> = broadcast_addrs
        .iter()
        .map(|a| format!("{}:{}", a, DISCOVERY_PORT))
        .collect();
    let broadcast_start = std::time::Instant::now();
    let mut broadcast_sent_ok = 0usize;
    let mut broadcast_send_errors: Vec<String> = Vec::new();
    for target in &broadcast_targets {
        match socket.send_to(DISCOVER_PAYLOAD, target) {
            Ok(_) => {
                broadcast_sent_ok += 1;
                if let Some(ref mut l) = log {
                    l.inc_packets_sent();
                    l.push_raw(&format!("Broadcast DISCOVER_WORKERS to {target}"));
                }
            }
            Err(e) => {
                let detail = format!("{target}: {e}");
                broadcast_send_errors.push(detail.clone());
                log::warn!("discovery: broadcast send_to failed ({detail})");
            }
        }
    }
    if let Some(ref mut l) = log {
        let broadcast_phase_ok =
            broadcast_targets.is_empty() || broadcast_send_errors.is_empty();
        l.add_full_deploy_entry(
            "discovery_send_broadcast",
            broadcast_phase_ok,
            broadcast_start.elapsed().as_millis() as u64,
            Some(serde_json::json!({
                "targets": &broadcast_targets,
                "sent_ok": broadcast_sent_ok,
                "send_failures": broadcast_send_errors.len(),
            })),
            if broadcast_send_errors.is_empty() {
                None
            } else {
                Some(broadcast_send_errors.join("; "))
            },
        );
    }

    if let Some(ref mut l) = log {
        l.add_full_deploy_entry(
            "discovery_listen_loop_start",
            true,
            0,
            Some(serde_json::json!({
                "total_timeout_ms": total_timeout_ms,
                "early_exit_on_first_worker": early_exit_on_first_worker
            })),
            None,
        );
        l.push_raw(&format!(
            "Listening for up to {} ms (early_exit={})",
            total_timeout_ms, early_exit_on_first_worker
        ));
    }

    let mut seen = HashSet::new();
    let mut manifests = Vec::new();
    let mut buf = [0u8; 4096];
    let mut poll_cycles = 0u32;

    loop {
        let elapsed_ms = start.elapsed().as_millis() as u64;
        let remaining_ms = total_timeout_ms.saturating_sub(elapsed_ms);
        if remaining_ms == 0 {
            break;
        }

        if let Err(e) = socket.set_read_timeout(Some(Duration::from_millis(remaining_ms))) {
            log::warn!(
                "discovery: set_read_timeout({remaining_ms} ms) failed — stopping listen loop ({e})"
            );
            if let Some(ref mut l) = log {
                l.push_raw(&format!("set_read_timeout error: {e}"));
            }
            break;
        }

        poll_cycles += 1;
        match socket.recv_from(&mut buf) {
            Ok((n, src)) => {
                let source_ip = src.ip().to_string();
                let raw = String::from_utf8_lossy(&buf[..n]).into_owned();
                if let Some(ref mut l) = log {
                    l.push_raw(&format!("Recv from {source_ip}: {} bytes", n));
                }
                if let Ok(s) = std::str::from_utf8(&buf[..n]) {
                    if let Some(dm) = parse_manifest(s, &source_ip) {
                        if let Some(ref mut l) = log {
                            l.inc_responses_received(dm.signature_verified);
                            l.push_raw(&format!(
                                "  worker {} {}:{} sig={}",
                                dm.manifest.worker_id,
                                dm.registration_host(),
                                dm.port,
                                dm.signature_verified
                            ));
                            l.add_full_deploy_entry(
                                "discovery_recv",
                                true,
                                0,
                                Some(serde_json::json!({
                                    "source_ip": source_ip,
                                    "bytes": n,
                                    "worker_id": dm.manifest.worker_id
                                })),
                                None,
                            );
                            l.add_full_deploy_entry(
                                "discovery_manifest_parse",
                                true,
                                0,
                                Some(serde_json::json!({
                                    "worker_id": dm.manifest.worker_id,
                                    "port": dm.port
                                })),
                                None,
                            );
                            l.add_full_deploy_entry(
                                "discovery_signature_validation",
                                dm.signature_verified,
                                0,
                                Some(serde_json::json!({
                                    "worker_id": dm.manifest.worker_id,
                                    "verified": dm.signature_verified
                                })),
                                if dm.signature_verified {
                                    None
                                } else {
                                    Some("signature verification failed".to_string())
                                },
                            );
                        }
                        if !dm.signature_verified {
                            log::warn!(
                                "discovery: UDP manifest from {} worker_id={} — signature verification FAILED",
                                source_ip,
                                dm.manifest.worker_id
                            );
                        }
                        if seen.insert(dm.manifest.worker_id.clone()) {
                            manifests.push(dm);
                        }
                    } else if let Some(ref mut l) = log {
                        l.inc_manifest_error();
                        l.push_raw(&format!(
                            "  parse failed: {}",
                            raw.chars().take(80).collect::<String>()
                        ));
                        l.add_full_deploy_entry(
                            "discovery_manifest_parse",
                            false,
                            0,
                            Some(serde_json::json!({"raw_preview": raw.chars().take(80).collect::<String>()})),
                            Some("invalid manifest".to_string()),
                        );
                    } else {
                        log::debug!(
                            "discovery: UDP from {} — payload not a valid worker manifest ({} bytes, preview {:?})",
                            source_ip,
                            n,
                            raw.chars().take(60).collect::<String>()
                        );
                    }
                } else if let Some(ref mut l) = log {
                    l.inc_manifest_error();
                    l.push_raw("  invalid UTF-8");
                    l.add_full_deploy_entry(
                        "discovery_manifest_parse",
                        false,
                        0,
                        None,
                        Some("invalid UTF-8".to_string()),
                    );
                } else {
                    log::debug!(
                        "discovery: UDP from {} — invalid UTF-8 ({} bytes)",
                        source_ip,
                        n
                    );
                }

                if early_exit_on_first_worker && !manifests.is_empty() {
                    if let Some(ref mut l) = log {
                        l.push_raw(&format!(
                            "Early exit: {} worker(s) discovered",
                            manifests.len()
                        ));
                    }
                    break;
                }
            }
            Err(e) => match e.kind() {
                ErrorKind::WouldBlock | ErrorKind::TimedOut => {
                    if log.is_none() {
                        log::debug!(
                            "discovery: recv timed out with no datagram (slice up to {remaining_ms} ms; elapsed_ms={}; poll_cycle={})",
                            start.elapsed().as_millis() as u64,
                            poll_cycles
                        );
                    }
                    break;
                }
                ErrorKind::Interrupted => {
                    log::debug!("discovery: recv interrupted ({e}), ending listen loop");
                    break;
                }
                _ => {
                    log::warn!("discovery: recv_from failed: {e}");
                    if let Some(ref mut l) = log {
                        l.push_raw(&format!("recv_from error: {e}"));
                    }
                    break;
                }
            },
        }
    }

    let end_rfc3339 = chrono::Utc::now().to_rfc3339();
    let duration_ms = start.elapsed().as_millis() as u64;

    if log.is_none() {
        if manifests.is_empty() {
            log::info!(
                "discovery: window finished — 0 workers (port={}, loopback_send_ok={}, broadcast_sent_ok={}/{}, listen_ms≈{}, early_exit={})",
                DISCOVERY_PORT,
                loopback_ok,
                broadcast_sent_ok,
                broadcast_targets.len(),
                duration_ms,
                early_exit_on_first_worker
            );
        } else {
            log::info!(
                "discovery: window finished — {} unique worker(s) in {} ms (port={})",
                manifests.len(),
                duration_ms,
                DISCOVERY_PORT
            );
        }
    }

    if let Some(ref mut l) = log {
        l.add_full_deploy_entry(
            "discovery_listen_loop_end",
            true,
            duration_ms,
            Some(serde_json::json!({
                "poll_cycles": poll_cycles,
                "worker_count": manifests.len()
            })),
            None,
        );
        l.set_discovery_timing(
            &start_rfc3339,
            &end_rfc3339,
            duration_ms,
            total_timeout_ms,
            poll_cycles,
        );
    }

    manifests
}

/// Send a single UDP `PHANTOM_DISCOVER_WORKERS` probe to `127.0.0.1:{discovery_port}`
/// and return `true` if any response is received within `timeout_ms`.
/// Used by the worker readiness probe loop in `start_local_worker()`.
///
/// *discovery_port* must match ``phantom_config.json`` ``ports.discovery_udp`` (default 8095).
///
/// Failures are logged (bind/send/rec unexpected I/O); timeout / no reply is ``debug!``.
pub fn probe_worker_readiness(timeout_ms: u64, discovery_port: u16) -> bool {
    let socket = match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => s,
        Err(e) => {
            log::warn!("readiness probe: UDP bind 0.0.0.0:0 failed: {e}");
            return false;
        }
    };
    if let Err(e) = socket.set_read_timeout(Some(Duration::from_millis(timeout_ms))) {
        log::warn!("readiness probe: set_read_timeout({timeout_ms}ms) failed: {e}");
        return false;
    }
    let target = format!("127.0.0.1:{discovery_port}");
    if let Err(e) = socket.send_to(DISCOVER_PAYLOAD, &target) {
        log::warn!(
            "readiness probe: send_to {target} ({} bytes) failed: {e}",
            DISCOVER_PAYLOAD.len()
        );
        return false;
    }
    let mut buf = [0u8; 4096];
    match socket.recv_from(&mut buf) {
        Ok((n, src)) => {
            log::info!(
                "readiness probe: UDP reply from {} ({} bytes); discovery port {}",
                src,
                n,
                discovery_port
            );
            true
        }
        Err(e) => {
            match e.kind() {
                ErrorKind::WouldBlock | ErrorKind::TimedOut => {
                    log::debug!(
                        "readiness probe: no UDP reply on 127.0.0.1:{discovery_port} within {timeout_ms}ms ({e})"
                    );
                }
                _ => {
                    log::warn!("readiness probe: recv_from failed: {e}");
                }
            }
            false
        }
    }
}

/// Run discovery: single window, unicast to localhost + broadcast on each subnet.
/// Deduplicate by worker_id. Uses DEFAULT_DISCOVERY_TOTAL_TIMEOUT_MS and
/// early exit on first worker. Each manifest has `signature_verified` set.
///
/// Public API preserved for backward compatibility with scan_lan and
/// scan_and_register_workers.
pub fn discover_workers(broadcast_addrs: &[String]) -> Vec<DiscoveredManifest> {
    discover_single_window(
        broadcast_addrs,
        DEFAULT_DISCOVERY_TOTAL_TIMEOUT_MS,
        true,
        None,
    )
}

/// Run discovery with structured log. Returns (manifests, log).
/// Use for deployment ceremony when diagnostics may be needed.
///
/// Uses configurable `total_timeout_ms` and `early_exit_on_first_worker`.
/// Timing data is recorded in the log for Phase 3 "Discovery Timing Breakdown".
/// `dependency_init_entries` are prepended to the Dependency Initialization Log.
/// `full_deploy_entries` (steps 1–22 from deployer) are prepended to the Full Deployment Log.
pub fn discover_workers_with_log(
    broadcast_addrs: &[String],
    total_timeout_ms: u64,
    early_exit_on_first_worker: bool,
    dependency_init_entries: impl IntoIterator<Item = super::discovery_log::DependencyInitEntry>,
    full_deploy_entries: impl IntoIterator<Item = super::discovery_log::FullDeployLogEntry>,
) -> (Vec<DiscoveredManifest>, super::discovery_log::DiscoveryLog) {
    let mut interfaces: Vec<String> = vec!["127.0.0.1".to_string()];
    interfaces.extend(broadcast_addrs.iter().cloned());

    let mut log = DiscoveryLogBuilder::new(interfaces, DISCOVERY_PORT);
    log.set_discovery_mode(Some("lan_udp".to_string()));
    for entry in dependency_init_entries {
        log.add_dependency_init_entry(entry);
    }
    log.add_full_deploy_entries(full_deploy_entries);
    log.push_raw("Single-window discovery (127.0.0.1 + broadcast)…");

    let manifests =
        discover_single_window(broadcast_addrs, total_timeout_ms, early_exit_on_first_worker, Some(&mut log));

    log.push_raw(&format!("Done: {} worker(s) discovered", manifests.len()));
    let discovery_log = log.build(manifests.len());
    (manifests, discovery_log)
}
