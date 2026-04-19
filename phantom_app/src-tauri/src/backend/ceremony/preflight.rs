//! Phase 12 — LAN-first preflight diagnostics.
//!
//! Doctrine: WAN reachability is irrelevant. We only inspect things that
//! a LAN-only deploy actually requires:
//! - UDP egress (any ephemeral port).
//! - The discovery UDP port is bindable.
//! - The controller / worker TCP ports are bindable.
//! - A usable Python interpreter exists on PATH.
//! - Phantom-root state directories are writable.
//!
//! Each check is fast, side-effect free (binds are released immediately),
//! and never opens a network connection to anything outside the local host.

use std::net::{TcpListener, UdpSocket};
use std::path::Path;

use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PreflightCheck {
    pub id: String,
    pub name: String,
    pub pass: bool,
    pub detail: String,
    /// Optional remediation hint surfaced verbatim to the operator.
    pub hint: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PreflightReport {
    pub ok: bool,
    pub checks: Vec<PreflightCheck>,
}

fn check_udp_egress() -> PreflightCheck {
    match UdpSocket::bind("0.0.0.0:0") {
        Ok(s) => PreflightCheck {
            id: "udp.egress".into(),
            name: "UDP egress (ephemeral)".into(),
            pass: true,
            detail: format!(
                "bound {}",
                s.local_addr().map(|a| a.to_string()).unwrap_or_default()
            ),
            hint: None,
        },
        Err(e) => PreflightCheck {
            id: "udp.egress".into(),
            name: "UDP egress (ephemeral)".into(),
            pass: false,
            detail: format!("bind 0.0.0.0:0 failed: {e}"),
            hint: Some(
                "Phantom needs UDP egress on the LAN. Check host firewall / sandbox policy."
                    .into(),
            ),
        },
    }
}

fn check_udp_port(port: u16, id: &str, name: &str) -> PreflightCheck {
    let addr = format!("0.0.0.0:{port}");
    match UdpSocket::bind(&addr) {
        Ok(_) => PreflightCheck {
            id: id.into(),
            name: name.into(),
            pass: true,
            detail: format!("{addr} bindable"),
            hint: None,
        },
        Err(e) => PreflightCheck {
            id: id.into(),
            name: name.into(),
            pass: false,
            detail: format!("bind {addr} failed: {e}"),
            hint: Some(format!(
                "UDP {port} is in use by another process. Stop the conflicting process or change the port."
            )),
        },
    }
}

fn check_tcp_port(port: u16, id: &str, name: &str) -> PreflightCheck {
    let addr = format!("0.0.0.0:{port}");
    match TcpListener::bind(&addr) {
        Ok(_) => PreflightCheck {
            id: id.into(),
            name: name.into(),
            pass: true,
            detail: format!("{addr} bindable"),
            hint: None,
        },
        Err(e) => PreflightCheck {
            id: id.into(),
            name: name.into(),
            pass: false,
            detail: format!("bind {addr} failed: {e}"),
            hint: Some(format!(
                "TCP {port} is in use. The Troubleshooter can cycle controller ports if this is the controller port."
            )),
        },
    }
}

fn check_python() -> PreflightCheck {
    let candidates: &[&str] = if cfg!(windows) {
        &["python", "python3"]
    } else {
        &["python3", "python"]
    };
    for bin in candidates {
        let out = std::process::Command::new(bin)
            .arg("--version")
            .output();
        if let Ok(o) = out {
            if o.status.success() {
                let v = String::from_utf8_lossy(if !o.stdout.is_empty() {
                    &o.stdout
                } else {
                    &o.stderr
                })
                .trim()
                .to_string();
                return PreflightCheck {
                    id: "python.available".into(),
                    name: "Python interpreter".into(),
                    pass: true,
                    detail: format!("{bin}: {v}"),
                    hint: None,
                };
            }
        }
    }
    PreflightCheck {
        id: "python.available".into(),
        name: "Python interpreter".into(),
        pass: false,
        detail: "no python/python3 on PATH".into(),
        hint: Some(
            "Install Python 3.10+ or add it to PATH. Phantom Act B materializes a venv from your host Python."
                .into(),
        ),
    }
}

fn check_state_writable(root: &Path) -> PreflightCheck {
    let state = root.join("state");
    let probe = state.join(".phantom_preflight_probe");
    if let Err(e) = std::fs::create_dir_all(&state) {
        return PreflightCheck {
            id: "state.writable".into(),
            name: "Phantom state directory writable".into(),
            pass: false,
            detail: format!("mkdir {}: {e}", state.display()),
            hint: Some(format!(
                "Ensure {} is writable by the current user.",
                state.display()
            )),
        };
    }
    match std::fs::write(&probe, b"phantom-preflight") {
        Ok(_) => {
            let _ = std::fs::remove_file(&probe);
            PreflightCheck {
                id: "state.writable".into(),
                name: "Phantom state directory writable".into(),
                pass: true,
                detail: format!("wrote+removed probe in {}", state.display()),
                hint: None,
            }
        }
        Err(e) => PreflightCheck {
            id: "state.writable".into(),
            name: "Phantom state directory writable".into(),
            pass: false,
            detail: format!("write probe: {e}"),
            hint: Some(format!(
                "Ensure {} is writable by the current user.",
                state.display()
            )),
        },
    }
}

/// Run the full LAN-first preflight against `phantom_root`.
pub fn run(phantom_root: &Path) -> PreflightReport {
    let checks = vec![
        check_state_writable(phantom_root),
        check_python(),
        check_udp_egress(),
        check_udp_port(8095, "udp.discovery.port", "UDP 8095 discovery port"),
        check_tcp_port(8080, "tcp.controller.port", "TCP 8080 controller API"),
        check_tcp_port(8090, "tcp.worker.port", "TCP 8090 worker HTTP"),
    ];
    let ok = checks.iter().all(|c| c.pass);
    PreflightReport { ok, checks }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn report_runs_and_returns_all_checks() {
        let dir = tempdir().unwrap();
        let r = run(dir.path());
        assert!(!r.checks.is_empty());
        assert!(r.checks.iter().any(|c| c.id == "udp.egress"));
        assert!(r.checks.iter().any(|c| c.id == "state.writable"));
    }

    #[test]
    fn state_writable_passes_for_tempdir() {
        let dir = tempdir().unwrap();
        let c = check_state_writable(dir.path());
        assert!(c.pass, "{}", c.detail);
    }
}
