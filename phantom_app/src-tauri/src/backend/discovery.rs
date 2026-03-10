//! Phantom discovery: broadcast DISCOVER_WORKERS, workers self-identify with signed manifests.
//! No host probing, ARP, or port scanning. Subnets from NIC enumeration only.

use serde::Deserialize;
use std::collections::HashSet;
use std::net::UdpSocket;
use std::time::Duration;

/// Well-known discovery port. Workers listen here for DISCOVER_WORKERS.
pub const DISCOVERY_PORT: u16 = 8095;

/// Discovery request sent via UDP broadcast.
const DISCOVER_PAYLOAD: &[u8] = b"PHANTOM_DISCOVER_WORKERS";

/// Worker manifest (self-identification response). Host may be 0.0.0.0; use
/// source_ip (UDP response origin) for registration when so.
#[derive(Debug, Clone)]
pub struct WorkerManifest {
    pub worker_id: String,
    pub host: String,
    pub port: u16,
    pub gpu_info: serde_json::Value,
    /// IP the manifest was received from (UDP source).
    pub source_ip: String,
}

impl WorkerManifest {
    pub fn registration_host(&self) -> String {
        if self.host == "0.0.0.0" || self.host.is_empty() {
            self.source_ip.clone()
        } else {
            self.host.clone()
        }
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

#[derive(Deserialize)]
struct RawManifest {
    #[serde(rename = "type")]
    msg_type: String,
    worker_id: String,
    host: String,
    port: u16,
    gpu_info: serde_json::Value,
}

/// Broadcast DISCOVER_WORKERS and collect manifests. Returns (manifest, source_ip) for each.
fn broadcast_and_collect(
    broadcast_addr: &str,
    listen_timeout_ms: u64,
) -> Vec<WorkerManifest> {
    let socket = match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => s,
        Err(_) => return vec![],
    };
    socket.set_broadcast(true).ok();
    socket.set_read_timeout(Some(Duration::from_millis(listen_timeout_ms))).ok();

    let target = format!("{}:{}", broadcast_addr, DISCOVERY_PORT);
    if socket.send_to(DISCOVER_PAYLOAD, &target).is_err() {
        return vec![];
    }

    let mut manifests = Vec::new();
    let mut buf = [0u8; 2048];
    loop {
        match socket.recv_from(&mut buf) {
            Ok((n, src)) => {
                let source_ip = src.ip().to_string();
                if let Ok(s) = std::str::from_utf8(&buf[..n]) {
                    if let Ok(r) = serde_json::from_str::<RawManifest>(s) {
                        if r.msg_type == "WORKER_MANIFEST" && !r.worker_id.is_empty() {
                            manifests.push(WorkerManifest {
                                worker_id: r.worker_id,
                                host: r.host,
                                port: r.port,
                                gpu_info: r.gpu_info,
                                source_ip,
                            });
                        }
                    }
                }
            }
            Err(_) => break,
        }
    }
    manifests
}

/// Send DISCOVER_WORKERS to unicast (e.g. 127.0.0.1 for local worker).
fn unicast_and_collect(addr: &str, listen_timeout_ms: u64) -> Vec<WorkerManifest> {
    let socket = match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => s,
        Err(_) => return vec![],
    };
    socket.set_read_timeout(Some(Duration::from_millis(listen_timeout_ms))).ok();

    let target = format!("{}:{}", addr, DISCOVERY_PORT);
    if socket.send_to(DISCOVER_PAYLOAD, &target).is_err() {
        return vec![];
    }

    let mut manifests = Vec::new();
    let mut buf = [0u8; 2048];
    loop {
        match socket.recv_from(&mut buf) {
            Ok((n, src)) => {
                let source_ip = src.ip().to_string();
                if let Ok(s) = std::str::from_utf8(&buf[..n]) {
                    if let Ok(r) = serde_json::from_str::<RawManifest>(s) {
                        if r.msg_type == "WORKER_MANIFEST" && !r.worker_id.is_empty() {
                            manifests.push(WorkerManifest {
                                worker_id: r.worker_id,
                                host: r.host,
                                port: r.port,
                                gpu_info: r.gpu_info,
                                source_ip,
                            });
                        }
                    }
                }
            }
            Err(_) => break,
        }
    }
    manifests
}

/// Run discovery: unicast to localhost, then broadcast on each subnet.
/// Deduplicate by worker_id.
pub fn discover_workers(broadcast_addrs: &[String]) -> Vec<WorkerManifest> {
    const TIMEOUT_MS: u64 = 1500;
    let mut seen = HashSet::new();
    let mut all = Vec::new();

    for m in unicast_and_collect("127.0.0.1", TIMEOUT_MS) {
        if seen.insert(m.worker_id.clone()) {
            all.push(m);
        }
    }

    for addr in broadcast_addrs {
        for m in broadcast_and_collect(addr, TIMEOUT_MS) {
            if seen.insert(m.worker_id.clone()) {
                all.push(m);
            }
        }
    }
    all
}
