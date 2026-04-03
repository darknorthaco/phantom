//! Act C — discovery (LAN UDP + offline synthetic) per Phase 2–3; aggregates `DiscoverySnapshot`.

use std::collections::HashSet;
use std::path::{Path, PathBuf};

use tauri::Emitter;
use uuid::Uuid;

use super::dto::DiscoverySnapshot;
use crate::backend::discovery::{base_to_broadcast, discover_workers_with_log};
use crate::backend::discovery_log::{DependencyInitEntry, DiscoveryLogBuilder, FullDeployLogEntry};
use crate::backend::phantom_deployer::{
    local_ip_bases, read_runtime_tcp_endpoints, DiscoveredWorkerForCeremony,
};

use crate::backend::discovery::DEFAULT_DISCOVERY_TOTAL_TIMEOUT_MS;

/// Outcome of discovery work (internal; orchestrator maps to state + `outcome_class`).
#[derive(Debug)]
pub enum ActCDiscoveryOutcome {
    /// At least one candidate manifest.
    Success {
        snapshot: DiscoverySnapshot,
    },
    /// Window completed with zero usable candidates (timeout / empty LAN / offline edge).
    Partial {
        snapshot: DiscoverySnapshot,
    },
    /// Hard failure (task panic, I/O, or manifest parse errors with no successful candidates).
    Failed {
        detail: String,
    },
}

fn read_nested_config(path: &Path, keys: &[&str]) -> Option<String> {
    let content = std::fs::read_to_string(path).ok()?;
    let mut node: serde_json::Value = serde_json::from_str(&content).ok()?;
    for key in keys {
        node = node.get(key)?.clone();
    }
    match &node {
        serde_json::Value::String(s) => Some(s.clone()),
        serde_json::Value::Number(n) => Some(n.to_string()),
        serde_json::Value::Bool(b) => Some(b.to_string()),
        _ => None,
    }
}

fn read_discovery_window(phantom_root: &Path) -> (u64, bool) {
    let config_path = phantom_root.join("phantom_config.json");
    let total_timeout_ms = read_nested_config(&config_path, &["discovery", "total_timeout_ms"])
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(DEFAULT_DISCOVERY_TOTAL_TIMEOUT_MS);
    let early_exit = read_nested_config(&config_path, &["discovery", "early_exit_on_first_worker"])
        .and_then(|s| s.parse::<bool>().ok())
        .unwrap_or(true);
    (total_timeout_ms, early_exit)
}

/// Venv + engine layout expected after Act B.
pub fn validate_materialized_environment(phantom_root: &Path) -> Result<(), String> {
    let venv = phantom_root.join("venv");
    if !venv.is_dir() {
        return Err("phantom venv missing — complete Act B (materialize) first.".to_string());
    }
    let venv_ok = venv.join("pyvenv.cfg").is_file()
        || venv.join("bin").join("python").is_file()
        || venv.join("bin").join("python3").is_file()
        || venv.join("Scripts").join("python.exe").is_file();
    if !venv_ok {
        return Err("phantom venv incomplete (no pyvenv.cfg / python) — re-run Act B.".to_string());
    }

    let engine = phantom_root.join("engine");
    let run_py = engine.join("run.py");
    let phantom_core_dir = engine.join("phantom_core");
    if !run_py.is_file() && !phantom_core_dir.is_dir() {
        return Err("phantom engine missing (no engine/run.py or engine/phantom_core) — re-run Act B.".to_string());
    }
    Ok(())
}

fn manifests_to_candidates(workers: &[DiscoveredWorkerForCeremony]) -> Vec<serde_json::Value> {
    workers
        .iter()
        .filter_map(|w| serde_json::to_value(w).ok())
        .collect()
}

fn build_snapshot(correlation_id: &str, candidates: Vec<serde_json::Value>, policy: serde_json::Value) -> DiscoverySnapshot {
    DiscoverySnapshot {
        snapshot_id: Uuid::new_v4().to_string(),
        correlation_id: correlation_id.to_string(),
        created_at: chrono::Utc::now().to_rfc3339(),
        candidates,
        policy_flags: policy,
    }
}

/// Persist snapshot for later acts; orchestrator sets `snapshot_id` on ceremony state.
pub fn persist_discovery_snapshot(phantom_root: &Path, snapshot: &DiscoverySnapshot) -> Result<(), String> {
    let state_dir = phantom_root.join("state");
    std::fs::create_dir_all(&state_dir).map_err(|e| format!("create state dir: {e}"))?;
    let path = state_dir.join("discovery_snapshot.json");
    let body = serde_json::to_string_pretty(snapshot).map_err(|e| e.to_string())?;
    let tmp = path.with_extension("json.tmp");
    std::fs::write(&tmp, &body).map_err(|e| format!("write discovery snapshot: {e}"))?;
    std::fs::rename(&tmp, &path).map_err(|e| format!("finalize discovery snapshot: {e}"))?;
    Ok(())
}

fn emit_line(app: Option<&tauri::AppHandle>, line: &str) {
    if let Some(app) = app {
        let _ = app.emit("scan-log", line);
    }
}

/// Run LAN window and/or offline synthetic discovery; does not mutate ceremony files.
pub async fn execute_discovery(
    phantom_root: &Path,
    correlation_id: &str,
    offline_bundle: Option<PathBuf>,
    app_handle: Option<tauri::AppHandle>,
) -> ActCDiscoveryOutcome {
    let app_ref = app_handle.as_ref();
    let (total_timeout_ms, early_exit) = read_discovery_window(phantom_root);
    let (_, _, syn_worker_http, syn_disc_port) = read_runtime_tcp_endpoints(phantom_root);

    let mut lan_workers: Vec<DiscoveredWorkerForCeremony> = Vec::new();
    let mut lan_manifest_errors = 0u32;
    let lan_mode: Option<String> = Some("lan_udp".to_string());

    emit_line(app_ref, "Act C: LAN discovery (127.0.0.1 + subnet broadcasts)…");
    let base_ips = local_ip_bases();
    let broadcast_addrs: Vec<String> = base_ips
        .iter()
        .filter_map(|b| base_to_broadcast(b))
        .collect();
    emit_line(
        app_ref,
        &format!(
            "Act C: discovery window {} ms (early_exit={})",
            total_timeout_ms, early_exit
        ),
    );

    let deps: Vec<DependencyInitEntry> = Vec::new();
    let full: Vec<FullDeployLogEntry> = Vec::new();
    let addrs = broadcast_addrs.clone();
    let lan_res = tokio::task::spawn_blocking(move || {
        discover_workers_with_log(&addrs, total_timeout_ms, early_exit, deps, full)
    })
    .await;

    match lan_res {
        Ok((manifests, log)) => {
            lan_manifest_errors = log.manifest_errors;
            lan_workers = manifests
                .iter()
                .map(|m| DiscoveredWorkerForCeremony {
                    worker_id: m.manifest.worker_id.clone(),
                    host: m.registration_host(),
                    port: m.port,
                    gpu_info: m.manifest.capabilities.clone(),
                    source_ip: m.source_ip.clone(),
                    signature_verified: m.signature_verified,
                    fingerprint: m.fingerprint.clone(),
                    public_key_b64: m.manifest.public_key_b64.clone(),
                })
                .collect();
        }
        Err(e) => {
            return ActCDiscoveryOutcome::Failed {
                detail: format!("LAN discovery task failed: {e}"),
            };
        }
    }

    let mut synthetic_workers: Vec<DiscoveredWorkerForCeremony> = Vec::new();
    let mut synthetic_mode: Option<String> = None;

    if let Some(ref bundle) = offline_bundle {
        synthetic_mode = Some("offline_synthetic".to_string());
        emit_line(
            app_ref,
            &format!(
                "Act C: offline synthetic discovery (bundle {})",
                bundle.display()
            ),
        );
        let tt = total_timeout_ms;
        let syn_port = syn_disc_port;
        let syn_http = syn_worker_http;
        let res = tokio::task::spawn_blocking(move || {
            let mut log = DiscoveryLogBuilder::new(vec!["offline".to_string()], syn_port);
            log.set_discovery_mode(Some("offline_synthetic".to_string()));
            log.push_raw("PHANTOM OFFLINE MODE — synthetic local-worker manifest (Act C)");
            let ts = chrono::Utc::now().to_rfc3339();
            log.set_discovery_timing(&ts, &ts, 0, tt, 0);
            let _ = log.build(1);
            let w = DiscoveredWorkerForCeremony {
                worker_id: "local-worker".to_string(),
                host: "127.0.0.1".to_string(),
                port: syn_http,
                gpu_info: serde_json::json!({}),
                source_ip: "127.0.0.1".to_string(),
                signature_verified: false,
                fingerprint: String::new(),
                public_key_b64: String::new(),
            };
            w
        })
        .await;

        match res {
            Ok(w) => synthetic_workers.push(w),
            Err(e) => {
                return ActCDiscoveryOutcome::Failed {
                    detail: format!("offline synthetic discovery task failed: {e}"),
                };
            }
        }
        emit_line(app_ref, "Act C: received 1 synthetic manifest (offline local-worker)");
    }

    // Merge: dedupe by worker_id (LAN first, then synthetic).
    let mut seen: HashSet<String> = HashSet::new();
    let mut merged: Vec<DiscoveredWorkerForCeremony> = Vec::new();
    for w in lan_workers {
        if seen.insert(w.worker_id.clone()) {
            merged.push(w);
        }
    }
    for w in synthetic_workers {
        if seen.insert(w.worker_id.clone()) {
            merged.push(w);
        }
    }

    let policy = serde_json::json!({
        "lan_mode": lan_mode,
        "synthetic_mode": synthetic_mode,
        "total_timeout_ms": total_timeout_ms,
        "early_exit_on_first_worker": early_exit,
        "lan_manifest_errors": lan_manifest_errors,
    });

    let candidates = manifests_to_candidates(&merged);

    if !merged.is_empty() {
        let snapshot = build_snapshot(correlation_id, candidates, policy);
        return ActCDiscoveryOutcome::Success { snapshot };
    }

    if lan_manifest_errors > 0 && merged.is_empty() {
        return ActCDiscoveryOutcome::Failed {
            detail: format!(
                "discovery manifest parse failures ({lan_manifest_errors}) with zero usable candidates"
            ),
        };
    }

    let mut policy_partial = policy;
    if let serde_json::Value::Object(ref mut m) = policy_partial {
        m.insert("discovery_partial".to_string(), serde_json::json!(true));
    }
    let snapshot = build_snapshot(correlation_id, candidates, policy_partial);
    ActCDiscoveryOutcome::Partial { snapshot }
}
