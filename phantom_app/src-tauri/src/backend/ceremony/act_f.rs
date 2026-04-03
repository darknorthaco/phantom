//! Act F — register primary worker with controller (Phase 11.6).

use std::path::Path;

use super::act_d;
use super::act_e;
use crate::backend::phantom_api::{PhantomApiClient, RegisterWorkerRequest};
use crate::backend::phantom_deployer::DiscoveredWorkerForCeremony;

/// Chronicle / mirror outcome when registration completes without full controller acceptance.
pub const OUTCOME_PARTIAL_REGISTRATION: &str = "PARTIAL";

/// Harness: skip HTTP approve/register (dry-run / tests without controller).
pub const ENV_SKIP_REGISTER: &str = "PHANTOM_CEREMONY_ACT_F_SKIP_REGISTER";

/// Harness: force partial outcome (registration API style failure).
pub const ENV_FORCE_PARTIAL: &str = "PHANTOM_CEREMONY_ACT_F_FORCE_PARTIAL";

/// Harness: force failed outcome.
pub const ENV_FORCE_FAILED: &str = "PHANTOM_CEREMONY_ACT_F_FORCE_FAILED";

#[derive(Debug)]
pub enum ActFRegisterOutcome {
    Success,
    Partial { detail: String },
    Failed { detail: String },
}

fn env_truthy(key: &str) -> bool {
    std::env::var(key)
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false)
}

fn is_likely_transport_err(msg: &str) -> bool {
    msg.contains("Connection failed")
        || msg.contains("error sending request")
        || msg.contains("timeout")
        || msg.contains("failed to connect")
}

/// Same gates as Act E (manifest, config, materialized engine, correlation alignment).
pub async fn validate_register_prerequisites(
    phantom_root: &Path,
    ceremony_correlation_id: &str,
) -> Result<serde_json::Value, String> {
    act_e::validate_attest_prerequisites(phantom_root, ceremony_correlation_id).await
}

fn primary_from_manifest(manifest: &serde_json::Value) -> Result<DiscoveredWorkerForCeremony, String> {
    let pw = manifest
        .get("primaryWorker")
        .ok_or_else(|| "attestation manifest: primaryWorker missing".to_string())?;
    act_d::parse_primary_worker(pw)
}

fn build_register_request(w: &DiscoveredWorkerForCeremony) -> RegisterWorkerRequest {
    RegisterWorkerRequest {
        worker_id: w.worker_id.clone(),
        host: w.host.clone(),
        port: w.port,
        gpu_info: w.gpu_info.clone(),
        status: "active".to_string(),
    }
}

/// Trust approve (when key present) + `/workers/register`.
pub async fn execute_registration(phantom_root: &Path, manifest: &serde_json::Value) -> ActFRegisterOutcome {
    if env_truthy(ENV_FORCE_FAILED) {
        return ActFRegisterOutcome::Failed {
            detail: "PHANTOM_CEREMONY_ACT_F_FORCE_FAILED set (harness)".to_string(),
        };
    }
    if env_truthy(ENV_FORCE_PARTIAL) {
        return ActFRegisterOutcome::Partial {
            detail: "PHANTOM_CEREMONY_ACT_F_FORCE_PARTIAL set (harness)".to_string(),
        };
    }
    if env_truthy(ENV_SKIP_REGISTER) {
        return ActFRegisterOutcome::Success;
    }

    let primary = match primary_from_manifest(manifest) {
        Ok(p) => p,
        Err(e) => {
            return ActFRegisterOutcome::Failed {
                detail: e,
            };
        }
    };

    let cfg_path = phantom_root.join("phantom_config.json");
    let client = match PhantomApiClient::from_phantom_config(&cfg_path) {
        Ok(c) => c,
        Err(e) => {
            return ActFRegisterOutcome::Failed {
                detail: format!("build API client: {e}"),
            };
        }
    };

    let key = primary.public_key_b64.trim();
    if !key.is_empty() {
        match client.approve_worker(&primary.worker_id, key).await {
            Ok(()) => {}
            Err(e) => {
                if is_likely_transport_err(&e) {
                    return ActFRegisterOutcome::Failed {
                        detail: format!("trust approve transport error: {e}"),
                    };
                }
                return ActFRegisterOutcome::Failed {
                    detail: format!("trust gate failure (approve_worker): {e}"),
                };
            }
        }
    }

    let req = build_register_request(&primary);
    match client.register_worker(&req).await {
        Ok(()) => ActFRegisterOutcome::Success,
        Err(e) => {
            if is_likely_transport_err(&e) {
                ActFRegisterOutcome::Failed {
                    detail: format!("registration transport error: {e}"),
                }
            } else {
                ActFRegisterOutcome::Partial {
                    detail: format!("registration incomplete: {e}"),
                }
            }
        }
    }
}
