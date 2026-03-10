use serde::{Deserialize, Serialize};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream};
use std::thread;
use std::time::Duration;

/// TCP connect timeout per host. Increased from 100ms to improve reliability on
/// WiFi and high-latency networks where workers may respond slowly.
const CONNECT_TIMEOUT_MS: u64 = 300;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveredNode {
    pub ip: String,
    pub port: u16,
    pub reachable: bool,
    pub label: Option<String>,
}

/// Scan a single IP:port for reachability.
fn probe_host(ip: &str, port: u16) -> Option<DiscoveredNode> {
    let socket = match format!("{}:{}", ip, port).parse::<SocketAddr>() {
        Ok(addr) => addr,
        Err(_) => return None,
    };
    if TcpStream::connect_timeout(&socket, Duration::from_millis(CONNECT_TIMEOUT_MS)).is_ok() {
        Some(DiscoveredNode {
            ip: ip.to_string(),
            port,
            reachable: true,
            label: None,
        })
    } else {
        None
    }
}

/// Scan a /24 subnet for hosts with an open port. Uses parallel worker threads
/// to probe hosts concurrently (chunked by octet) instead of sequential scans.
pub fn scan_subnet(base_ip: &str, port: u16) -> Vec<DiscoveredNode> {
    let parts: Vec<&str> = base_ip.rsplitn(2, '.').collect();
    if parts.len() < 2 {
        return vec![];
    }
    let prefix = parts[1].to_string();

    // Split 1..254 into chunks; each thread probes a range
    const NUM_WORKERS: usize = 16;
    let hosts_per_worker = 254 / NUM_WORKERS;
    let mut handles = Vec::new();
    for w in 0..NUM_WORKERS {
        let start = 1 + w * hosts_per_worker;
        let end = if w == NUM_WORKERS - 1 {
            254
        } else {
            (w + 1) * hosts_per_worker
        };
        let p = prefix.clone();
        handles.push(thread::spawn(move || {
            let mut nodes = Vec::new();
            for host in start..=end {
                let ip_str = format!("{}.{}", p, host);
                if let Some(n) = probe_host(&ip_str, port) {
                    nodes.push(n);
                }
            }
            nodes
        }));
    }

    let mut results = Vec::new();
    for h in handles {
        if let Ok(nodes) = h.join() {
            results.extend(nodes);
        }
    }
    results
}

/// Scan localhost for a worker (e.g. controller and worker on same machine).
pub fn scan_localhost(port: u16) -> Vec<DiscoveredNode> {
    let addrs = ["127.0.0.1", "::1"];
    let mut results = Vec::new();
    for ip in &addrs {
        if let Ok(addr) = format!("{}:{}", ip, port).parse::<SocketAddr>() {
            if TcpStream::connect_timeout(&addr, Duration::from_millis(CONNECT_TIMEOUT_MS)).is_ok()
            {
                results.push(DiscoveredNode {
                    ip: ip.to_string(),
                    port,
                    reachable: true,
                    label: Some("localhost".to_string()),
                });
            }
        }
    }
    results
}
