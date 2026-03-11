//! Phantom discovery: broadcast DISCOVER_WORKERS, workers self-identify with signed manifests.
//! No host probing, ARP, or port scanning. Subnets from NIC enumeration only.
//!
//! §3 integration: incoming manifests are parsed as SignedManifest, signature is
//! verified, and the `signature_verified` flag is set before returning results.

use super::discovery_log::DiscoveryLogBuilder;
use super::worker_info::{RawWireManifest, SignedManifest};
use std::collections::HashSet;
use std::net::UdpSocket;
use std::time::Duration;

/// Well-known discovery port. Workers listen here for DISCOVER_WORKERS.
pub const DISCOVERY_PORT: u16 = 8095;

/// Discovery request sent via UDP broadcast.
const DISCOVER_PAYLOAD: &[u8] = b"PHANTOM_DISCOVER_WORKERS";

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
fn parse_manifest(raw: &str, source_ip: String) -> Option<DiscoveredManifest> {
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
        source_ip,
        signature_verified,
        fingerprint,
    })
}

/// Broadcast DISCOVER_WORKERS and collect manifests.
fn broadcast_and_collect(
    broadcast_addr: &str,
    listen_timeout_ms: u64,
) -> Vec<DiscoveredManifest> {
    let socket = match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => s,
        Err(_) => return vec![],
    };
    socket.set_broadcast(true).ok();
    socket
        .set_read_timeout(Some(Duration::from_millis(listen_timeout_ms)))
        .ok();

    let target = format!("{}:{}", broadcast_addr, DISCOVERY_PORT);
    if socket.send_to(DISCOVER_PAYLOAD, &target).is_err() {
        return vec![];
    }

    let mut manifests = Vec::new();
    let mut buf = [0u8; 4096];
    loop {
        match socket.recv_from(&mut buf) {
            Ok((n, src)) => {
                let source_ip = src.ip().to_string();
                if let Ok(s) = std::str::from_utf8(&buf[..n]) {
                    if let Some(dm) = parse_manifest(s, source_ip) {
                        manifests.push(dm);
                    }
                }
            }
            Err(_) => break,
        }
    }
    manifests
}

/// Send DISCOVER_WORKERS to unicast (e.g. 127.0.0.1 for local worker).
fn unicast_and_collect(addr: &str, listen_timeout_ms: u64) -> Vec<DiscoveredManifest> {
    let socket = match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => s,
        Err(_) => return vec![],
    };
    socket
        .set_read_timeout(Some(Duration::from_millis(listen_timeout_ms)))
        .ok();

    let target = format!("{}:{}", addr, DISCOVERY_PORT);
    if socket.send_to(DISCOVER_PAYLOAD, &target).is_err() {
        return vec![];
    }

    let mut manifests = Vec::new();
    let mut buf = [0u8; 4096];
    loop {
        match socket.recv_from(&mut buf) {
            Ok((n, src)) => {
                let source_ip = src.ip().to_string();
                if let Ok(s) = std::str::from_utf8(&buf[..n]) {
                    if let Some(dm) = parse_manifest(s, source_ip) {
                        manifests.push(dm);
                    }
                }
            }
            Err(_) => break,
        }
    }
    manifests
}

/// Run discovery: unicast to localhost, then broadcast on each subnet.
/// Deduplicate by worker_id.  Each manifest has `signature_verified` set.
pub fn discover_workers(broadcast_addrs: &[String]) -> Vec<DiscoveredManifest> {
    const TIMEOUT_MS: u64 = 1500;
    let mut seen = HashSet::new();
    let mut all = Vec::new();

    for m in unicast_and_collect("127.0.0.1", TIMEOUT_MS) {
        if seen.insert(m.manifest.worker_id.clone()) {
            all.push(m);
        }
    }

    for addr in broadcast_addrs {
        for m in broadcast_and_collect(addr, TIMEOUT_MS) {
            if seen.insert(m.manifest.worker_id.clone()) {
                all.push(m);
            }
        }
    }
    all
}

/// Unicast discovery with log building.
fn unicast_and_collect_with_log(
    addr: &str,
    listen_timeout_ms: u64,
    log: &mut DiscoveryLogBuilder,
) -> Vec<DiscoveredManifest> {
    let socket = match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => s,
        Err(e) => {
            log.push_raw(&format!("unicast bind error: {e}"));
            return vec![];
        }
    };
    socket
        .set_read_timeout(Some(Duration::from_millis(listen_timeout_ms)))
        .ok();

    let target = format!("{}:{}", addr, DISCOVERY_PORT);
    if socket.send_to(DISCOVER_PAYLOAD, &target).is_err() {
        log.push_raw(&format!("unicast send failed to {target}"));
        return vec![];
    }
    log.inc_packets_sent();
    log.push_raw(&format!("Sent DISCOVER_WORKERS to {target}"));

    let mut manifests = Vec::new();
    let mut buf = [0u8; 4096];
    loop {
        match socket.recv_from(&mut buf) {
            Ok((n, src)) => {
                let source_ip = src.ip().to_string();
                let raw = String::from_utf8_lossy(&buf[..n]).into_owned();
                log.push_raw(&format!("Recv from {source_ip}: {} bytes", n));
                if let Ok(s) = std::str::from_utf8(&buf[..n]) {
                    if let Some(dm) = parse_manifest(s, source_ip) {
                        log.inc_responses_received(dm.signature_verified);
                        log.push_raw(&format!(
                            "  worker {} {}:{} sig={}",
                            dm.manifest.worker_id,
                            dm.registration_host(),
                            dm.port,
                            dm.signature_verified
                        ));
                        manifests.push(dm);
                    } else {
                        log.inc_manifest_error();
                        log.push_raw(&format!("  parse failed: {}", raw.chars().take(80).collect::<String>()));
                    }
                } else {
                    log.inc_manifest_error();
                    log.push_raw("  invalid UTF-8");
                }
            }
            Err(_) => break,
        }
    }
    manifests
}

/// Broadcast discovery with log building.
fn broadcast_and_collect_with_log(
    broadcast_addr: &str,
    listen_timeout_ms: u64,
    log: &mut DiscoveryLogBuilder,
) -> Vec<DiscoveredManifest> {
    let socket = match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => s,
        Err(e) => {
            log.push_raw(&format!("broadcast bind error: {e}"));
            return vec![];
        }
    };
    socket.set_broadcast(true).ok();
    socket
        .set_read_timeout(Some(Duration::from_millis(listen_timeout_ms)))
        .ok();

    let target = format!("{}:{}", broadcast_addr, DISCOVERY_PORT);
    if socket.send_to(DISCOVER_PAYLOAD, &target).is_err() {
        log.push_raw(&format!("broadcast send failed to {target}"));
        return vec![];
    }
    log.inc_packets_sent();
    log.push_raw(&format!("Broadcast DISCOVER_WORKERS to {target}"));

    let mut manifests = Vec::new();
    let mut buf = [0u8; 4096];
    loop {
        match socket.recv_from(&mut buf) {
            Ok((n, src)) => {
                let source_ip = src.ip().to_string();
                let raw = String::from_utf8_lossy(&buf[..n]).into_owned();
                log.push_raw(&format!("Recv from {source_ip}: {} bytes", n));
                if let Ok(s) = std::str::from_utf8(&buf[..n]) {
                    if let Some(dm) = parse_manifest(s, source_ip) {
                        log.inc_responses_received(dm.signature_verified);
                        log.push_raw(&format!(
                            "  worker {} {}:{} sig={}",
                            dm.manifest.worker_id,
                            dm.registration_host(),
                            dm.port,
                            dm.signature_verified
                        ));
                        manifests.push(dm);
                    } else {
                        log.inc_manifest_error();
                        log.push_raw(&format!("  parse failed: {}", raw.chars().take(80).collect::<String>()));
                    }
                } else {
                    log.inc_manifest_error();
                    log.push_raw("  invalid UTF-8");
                }
            }
            Err(_) => break,
        }
    }
    manifests
}

/// Run discovery with structured log. Returns (manifests, log).
/// Use for deployment ceremony when diagnostics may be needed.
pub fn discover_workers_with_log(
    broadcast_addrs: &[String],
) -> (Vec<DiscoveredManifest>, super::discovery_log::DiscoveryLog) {
    const TIMEOUT_MS: u64 = 1500;

    let mut interfaces: Vec<String> = vec!["127.0.0.1".to_string()];
    interfaces.extend(broadcast_addrs.iter().cloned());

    let mut log = DiscoveryLogBuilder::new(interfaces, DISCOVERY_PORT);
    let mut seen = HashSet::new();
    let mut all = Vec::new();

    log.push_raw("Unicast to 127.0.0.1…");
    for m in unicast_and_collect_with_log("127.0.0.1", TIMEOUT_MS, &mut log) {
        if seen.insert(m.manifest.worker_id.clone()) {
            all.push(m);
        }
    }

    for addr in broadcast_addrs {
        log.push_raw(&format!("Broadcast to {addr}…"));
        for m in broadcast_and_collect_with_log(addr, TIMEOUT_MS, &mut log) {
            if seen.insert(m.manifest.worker_id.clone()) {
                all.push(m);
            }
        }
    }

    log.push_raw(&format!("Done: {} worker(s) discovered", all.len()));
    let discovery_log = log.build(all.len());
    (all, discovery_log)
}
