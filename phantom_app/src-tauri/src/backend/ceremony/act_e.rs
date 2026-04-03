//! Act E — controller attestation & readiness (Phase 11.5).

use std::path::Path;

use super::act_c;
use crate::backend::phantom_api::{HealthResponse, PhantomApiClient};

/// Chronicle / mirror outcome when `/health` is degraded or orchestrator not ready.
pub const OUTCOME_SUCCEEDED_WITH_WARNINGS: &str = "SUCCEEDED_WITH_WARNINGS";

fn attestation_manifest_path(phantom_root: &Path) -> std::path::PathBuf {
    phantom_root.join("state").join("ceremony_attestation_manifest.json")
}

/// Result of attestation probes (internal).
#[derive(Debug)]
pub enum ActEAttestationOutcome {
    Success,
    Degraded { detail: String },
    Failed { detail: String },
}

/// Harness-only: skip HTTP `/health` (integration tests without a running controller).
pub const ENV_SKIP_CONTROLLER_HEALTH: &str = "PHANTOM_CEREMONY_ACT_E_SKIP_CONTROLLER_HEALTH";

/// Harness-only: force degraded outcome without calling the controller.
pub const ENV_FORCE_DEGRADED: &str = "PHANTOM_CEREMONY_ACT_E_FORCE_DEGRADED";

fn env_truthy(key: &str) -> bool {
    std::env::var(key)
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false)
}

/// Read and validate attestation manifest + `phantom_config.json` + materialized engine (before Act E chronicle).
pub async fn validate_attest_prerequisites(
    phantom_root: &Path,
    ceremony_correlation_id: &str,
) -> Result<serde_json::Value, String> {
    act_c::validate_materialized_environment(phantom_root)?;

    let cfg_path = phantom_root.join("phantom_config.json");
    if !cfg_path.is_file() {
        return Err("phantom_config.json missing — complete Act D (configure) first.".to_string());
    }
    let cfg_raw = tokio::fs::read_to_string(&cfg_path)
        .await
        .map_err(|e| format!("read phantom_config.json: {e}"))?;
    let cfg: serde_json::Value =
        serde_json::from_str(&cfg_raw).map_err(|e| format!("invalid phantom_config.json: {e}"))?;
    cfg.get("controller")
        .ok_or_else(|| "phantom_config.json: missing controller block".to_string())?;

    let mpath = attestation_manifest_path(phantom_root);
    if !mpath.is_file() {
        return Err(
            "ceremony_attestation_manifest.json missing — complete Act D (configure) first."
                .to_string(),
        );
    }
    let mraw = tokio::fs::read_to_string(&mpath)
        .await
        .map_err(|e| format!("read ceremony_attestation_manifest.json: {e}"))?;
    let manifest: serde_json::Value =
        serde_json::from_str(&mraw).map_err(|e| format!("invalid ceremony_attestation_manifest.json: {e}"))?;

    let schema = manifest
        .get("schemaVersion")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if schema != "1" {
        return Err(format!("attestation manifest: unsupported schemaVersion={schema:?}"));
    }

    let mid = manifest
        .get("correlationId")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "attestation manifest: correlationId missing".to_string())?;
    if mid != ceremony_correlation_id {
        return Err("attestation manifest: correlationId mismatch (manifest vs ceremony state)".to_string());
    }

    let pw = manifest
        .get("primaryWorker")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "attestation manifest: primaryWorker missing or not an object".to_string())?;
    if pw
        .get("workerId")
        .and_then(|v| v.as_str())
        .map(|s| s.trim().is_empty())
        .unwrap_or(true)
    {
        return Err("attestation manifest: primaryWorker.workerId missing".to_string());
    }
    if pw
        .get("host")
        .and_then(|v| v.as_str())
        .map(|s| s.trim().is_empty())
        .unwrap_or(true)
    {
        return Err("attestation manifest: primaryWorker.host missing".to_string());
    }
    pw.get("port")
        .and_then(|v| v.as_u64())
        .filter(|&p| p > 0 && p <= u64::from(u16::MAX))
        .ok_or_else(|| "attestation manifest: primaryWorker.port missing or invalid".to_string())?;

    Ok(manifest)
}

fn classify_health(h: HealthResponse) -> ActEAttestationOutcome {
    let st = h.status.as_str();
    if st != "healthy" && st != "degraded" {
        return ActEAttestationOutcome::Failed {
            detail: format!("unexpected /health status: {st:?}"),
        };
    }
    if st == "degraded" {
        return ActEAttestationOutcome::Degraded {
            detail: "controller /health reports degraded".to_string(),
        };
    }
    if !h.orchestrator_ready {
        return ActEAttestationOutcome::Degraded {
            detail: format!(
                "controller orchestrator_ready=false: {:?}",
                h.orchestrator_error
            ),
        };
    }
    ActEAttestationOutcome::Success
}

/// Controller `/health`, engine layout already validated in prerequisites.
pub async fn execute_attestation(phantom_root: &Path) -> ActEAttestationOutcome {
    if env_truthy(ENV_FORCE_DEGRADED) {
        return ActEAttestationOutcome::Degraded {
            detail: "PHANTOM_CEREMONY_ACT_E_FORCE_DEGRADED set (harness)".to_string(),
        };
    }
    if env_truthy(ENV_SKIP_CONTROLLER_HEALTH) {
        return ActEAttestationOutcome::Success;
    }

    let cfg_path = phantom_root.join("phantom_config.json");
    let client = match PhantomApiClient::from_phantom_config(&cfg_path) {
        Ok(c) => c,
        Err(e) => {
            return ActEAttestationOutcome::Failed {
                detail: format!("build API client: {e}"),
            };
        }
    };

    match client.health().await {
        Ok(h) => classify_health(h),
        Err(e) => ActEAttestationOutcome::Failed {
            detail: format!("controller unresponsive: {e}"),
        },
    }
}
