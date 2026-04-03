//! Act D — configure controller from discovery snapshot (Phase 11.4).

use std::path::Path;

use serde_json::json;

use super::dto::DiscoverySnapshot;
use super::act_c;
use crate::backend::phantom_deployer::DiscoveredWorkerForCeremony;

fn snapshot_path(phantom_root: &Path) -> std::path::PathBuf {
    phantom_root.join("state").join("discovery_snapshot.json")
}

fn attestation_manifest_path(phantom_root: &Path) -> std::path::PathBuf {
    phantom_root.join("state").join("ceremony_attestation_manifest.json")
}

/// Load and parse `state/discovery_snapshot.json`.
pub async fn load_discovery_snapshot(phantom_root: &Path) -> Result<DiscoverySnapshot, String> {
    let p = snapshot_path(phantom_root);
    if !p.is_file() {
        return Err("discovery_snapshot.json missing — complete Act C (discovery) first.".to_string());
    }
    let raw = tokio::fs::read_to_string(&p)
        .await
        .map_err(|e| format!("read discovery_snapshot.json: {e}"))?;
    serde_json::from_str(&raw).map_err(|e| format!("invalid discovery_snapshot.json: {e}"))
}

fn discovery_partial_flag(policy: &serde_json::Value) -> bool {
    policy
        .get("discovery_partial")
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
}

/// Reject empty candidates when snapshot is explicitly partial (doctrine error path).
pub fn validate_candidate_count(snapshot: &DiscoverySnapshot) -> Result<(), String> {
    if snapshot.candidates.is_empty() {
        if discovery_partial_flag(&snapshot.policy_flags) {
            return Err(
                "discovery snapshot is PARTIAL with zero candidates — cannot select primary worker."
                    .to_string(),
            );
        }
        return Err("discovery snapshot has no candidates — cannot configure controller.".to_string());
    }
    Ok(())
}

/// Validate correlation and optional `snapshot_id` from ceremony mirror against the snapshot file.
pub fn validate_snapshot_identity(
    snapshot: &DiscoverySnapshot,
    ceremony_correlation_id: &str,
    ceremony_snapshot_id: Option<&str>,
) -> Result<(), String> {
    if snapshot.correlation_id != ceremony_correlation_id {
        return Err(format!(
            "discovery snapshot correlation_id mismatch (snapshot vs ceremony state)"
        ));
    }
    if let Some(expected) = ceremony_snapshot_id {
        if !expected.is_empty() && snapshot.snapshot_id != expected {
            return Err("discovery snapshot_id mismatch (snapshot vs ceremony state)".to_string());
        }
    }
    Ok(())
}

/// Parse and validate primary worker fields (camelCase JSON from Act C).
pub fn parse_primary_worker(v: &serde_json::Value) -> Result<DiscoveredWorkerForCeremony, String> {
    let w: DiscoveredWorkerForCeremony =
        serde_json::from_value(v.clone()).map_err(|e| format!("invalid worker candidate: {e}"))?;
    if w.worker_id.trim().is_empty() {
        return Err("primary worker: workerId empty".to_string());
    }
    if w.host.trim().is_empty() {
        return Err("primary worker: host empty".to_string());
    }
    if w.port == 0 {
        return Err("primary worker: port invalid".to_string());
    }
    Ok(w)
}

/// LAN-first: non-loopback `sourceIp` before `127.0.0.1` / localhost; stable within buckets.
pub fn order_candidates_lan_first(candidates: &[serde_json::Value]) -> Vec<serde_json::Value> {
    let mut parsed: Vec<(bool, usize, serde_json::Value)> = candidates
        .iter()
        .cloned()
        .enumerate()
        .map(|(i, v)| {
            let ip = v
                .get("sourceIp")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_lowercase();
            let is_lan = ip != "127.0.0.1" && ip != "::1" && ip != "localhost";
            (is_lan, i, v)
        })
        .collect();
    parsed.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.cmp(&b.1)));
    parsed.into_iter().map(|(_, _, v)| v).collect()
}

/// Same `phantom_config.json` shape as deploy bootstrap step 4.5 (no schema drift).
async fn write_phantom_config_from_placement(phantom_root: &Path) -> Result<(), String> {
    let config_path = phantom_root.join("phantom_config.json");
    let placement_path = phantom_root.join("controller_placement.json");
    if !placement_path.is_file() {
        return Err("controller_placement.json missing — complete Act A first.".to_string());
    }
    let placement_raw = tokio::fs::read_to_string(&placement_path)
        .await
        .map_err(|e| format!("read controller_placement.json: {e}"))?;
    let placement: serde_json::Value =
        serde_json::from_str(&placement_raw).map_err(|e| format!("invalid controller_placement.json: {e}"))?;
    let host = placement
        .get("host")
        .and_then(|v| v.as_str())
        .unwrap_or("127.0.0.1")
        .to_string();
    let port = placement.get("port").and_then(|v| v.as_u64()).unwrap_or(8080) as u16;
    let identity_fingerprint = placement
        .get("identity_fingerprint")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    if config_path.exists() {
        let ts = chrono::Utc::now().format("%Y%m%dT%H%M%SZ").to_string();
        let backup = phantom_root.join(format!("phantom_config.json.bak.{ts}"));
        tokio::fs::rename(&config_path, &backup)
            .await
            .map_err(|e| format!("back up phantom_config.json: {e}"))?;
    }

    let now = chrono::Utc::now().to_rfc3339();
    let config = json!({
        "controller": {
            "host": host,
            "port": port,
            "security": "disabled",
            "identity_fingerprint": identity_fingerprint,
            "socket_integrated": true
        },
        "ports": {
            "controller_api": { "port": port, "protocol": "tcp", "required": true  },
            "worker_http":    { "port": 8090, "protocol": "tcp", "required": true  },
            "discovery_udp":  { "port": 8095, "protocol": "udp", "required": true  },
            "socket_infra":   { "port": 8081, "protocol": "tcp", "required": false }
        },
        "worker": {
            "readiness_probe_interval_ms":  500,
            "readiness_max_attempts":       20,
            "readiness_attempt_timeout_ms": 1000
        },
        "discovery": {
            "total_timeout_ms":            10000,
            "early_exit_on_first_worker":  true
        },
        "execution_modes": {
            "default_mode": "manual"
        },
        "wan_mode": false,
        "tls_enabled": false,
        "tls_cert_path": "",
        "tls_key_path": "",
        "config_version":  "1.0",
        "written_at":      now,
        "written_by_step": "act_d_configure"
    });

    let tmp_path = phantom_root.join("phantom_config.json.tmp");
    tokio::fs::write(
        &tmp_path,
        serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?,
    )
    .await
    .map_err(|e| format!("write phantom_config.json.tmp: {e}"))?;
    tokio::fs::rename(&tmp_path, &config_path)
        .await
        .map_err(|e| format!("rename phantom_config.json: {e}"))?;
    Ok(())
}

/// Persist attestation input for Act E (JSON only; not a new public DTO).
async fn write_attestation_manifest(
    phantom_root: &Path,
    snapshot: &DiscoverySnapshot,
    primary: &DiscoveredWorkerForCeremony,
) -> Result<(), String> {
    let state_dir = phantom_root.join("state");
    tokio::fs::create_dir_all(&state_dir)
        .await
        .map_err(|e| format!("create state dir: {e}"))?;
    let primary_json = serde_json::to_value(primary).map_err(|e| e.to_string())?;
    let body = json!({
        "schemaVersion": "1",
        "snapshotId": snapshot.snapshot_id,
        "correlationId": snapshot.correlation_id,
        "snapshotCreatedAt": snapshot.created_at,
        "primaryWorker": primary_json,
        "preparedAt": chrono::Utc::now().to_rfc3339(),
    });
    let path = attestation_manifest_path(phantom_root);
    let tmp = path.with_extension("json.tmp");
    let pretty = serde_json::to_string_pretty(&body).map_err(|e| e.to_string())?;
    tokio::fs::write(&tmp, pretty)
        .await
        .map_err(|e| format!("write attestation manifest tmp: {e}"))?;
    tokio::fs::rename(&tmp, &path)
        .await
        .map_err(|e| format!("finalize attestation manifest: {e}"))?;
    Ok(())
}

/// Prerequisites only (before Act D chronicle): env, snapshot file, identity, candidate rules.
pub async fn validate_configure_prerequisites(
    phantom_root: &Path,
    ceremony_correlation_id: &str,
    ceremony_snapshot_id: Option<&str>,
) -> Result<DiscoverySnapshot, String> {
    act_c::validate_materialized_environment(phantom_root)?;
    let snapshot = load_discovery_snapshot(phantom_root).await?;
    validate_snapshot_identity(&snapshot, ceremony_correlation_id, ceremony_snapshot_id)?;
    validate_candidate_count(&snapshot)?;
    Ok(snapshot)
}

/// Write controller config + attestation manifest from an already-validated snapshot.
pub async fn execute_configure_writes(
    phantom_root: &Path,
    snapshot: &DiscoverySnapshot,
) -> Result<(), String> {
    let ordered = order_candidates_lan_first(&snapshot.candidates);
    let primary_val = ordered
        .first()
        .ok_or_else(|| "no ordered candidates".to_string())?;
    let primary = parse_primary_worker(primary_val)?;

    write_phantom_config_from_placement(phantom_root).await?;
    write_attestation_manifest(phantom_root, snapshot, &primary).await?;
    Ok(())
}
