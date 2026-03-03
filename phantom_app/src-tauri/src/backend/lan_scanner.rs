use serde::{Deserialize, Serialize};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream};
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveredNode {
    pub ip: String,
    pub port: u16,
    pub reachable: bool,
    pub label: Option<String>,
}

pub fn scan_subnet(base_ip: &str, port: u16) -> Vec<DiscoveredNode> {
    let parts: Vec<&str> = base_ip.rsplitn(2, '.').collect();
    if parts.len() < 2 {
        return vec![];
    }
    let prefix = parts[1];

    let mut results = Vec::new();
    for host in 1..=254u8 {
        let ip_str = format!("{prefix}.{host}");
        if let Ok(addr) = ip_str.parse::<Ipv4Addr>() {
            let socket = SocketAddr::new(IpAddr::V4(addr), port);
            let reachable =
                TcpStream::connect_timeout(&socket, Duration::from_millis(100)).is_ok();
            if reachable {
                results.push(DiscoveredNode {
                    ip: ip_str,
                    port,
                    reachable: true,
                    label: None,
                });
            }
        }
    }
    results
}
