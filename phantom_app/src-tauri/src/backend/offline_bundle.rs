//! Offline bundle verification and model catalogue loading (Phase 3).
//!
//! Schema must stay aligned with ``installer/offline_bundle.py`` / ``offline_bundle_lib.py``.

use serde::Deserialize;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::time::Duration;
use tokio::fs;
use tokio::net::TcpStream;

/// Short TCP probe — used to auto-select offline deploy when isolated.
///
/// - `PHANTOM_FORCE_OFFLINE=1` → always false (treat as offline upstream).
/// - `PHANTOM_ASSUME_ONLINE=1` → always true (CI / tests without real WAN).
pub async fn network_reachable_for_deploy() -> bool {
    if std::env::var("PHANTOM_FORCE_OFFLINE").as_deref() == Ok("1") {
        return false;
    }
    if std::env::var("PHANTOM_ASSUME_ONLINE").as_deref() == Ok("1") {
        return true;
    }
    for (host, port) in [("1.1.1.1", 443_u16), ("9.9.9.9", 443_u16)] {
        if tokio::time::timeout(Duration::from_millis(800), TcpStream::connect((host, port)))
            .await
            .ok()
            .and_then(|r| r.ok())
            .is_some()
        {
            return true;
        }
    }
    false
}

/// Resolve first valid bundle directory (contains ``manifest.json``).
pub fn resolve_offline_bundle_candidate(
    phantom_root: &Path,
    invoke_path: Option<String>,
    state_path: Option<PathBuf>,
) -> Option<PathBuf> {
    let env_path = std::env::var("PHANTOM_OFFLINE_BUNDLE")
        .ok()
        .map(PathBuf::from);
    let mut candidates: Vec<Option<PathBuf>> = Vec::new();
    if let Some(s) = invoke_path {
        candidates.push(Some(PathBuf::from(s)));
    }
    candidates.push(state_path);
    candidates.push(env_path);
    candidates.push(Some(phantom_root.join("offline_bundle")));
    let pending = phantom_root.join("state/pending_offline_bundle_path.txt");
    if let Ok(s) = std::fs::read_to_string(&pending) {
        let p = PathBuf::from(s.trim());
        candidates.push(Some(p));
    }
    for p in candidates.into_iter().flatten() {
        if p.join("manifest.json").is_file() {
            return Some(p);
        }
    }
    None
}

#[derive(Debug, Deserialize)]
struct ManifestFileEntry {
    relative_path: String,
    sha256: String,
}

#[derive(Debug, Deserialize)]
struct BundleManifest {
    schema_version: u32,
    files: Vec<ManifestFileEntry>,
}

/// Outcome of verifying ``manifest.json`` against on-disk files.
#[derive(Debug, serde::Serialize)]
pub struct OfflineVerifyReport {
    pub ok: bool,
    pub checked_files: usize,
    pub errors: Vec<String>,
}

/// Verify every hashed file under *bundle_root* matches ``manifest.json``.
pub async fn verify_offline_bundle_root(bundle_root: &Path) -> Result<OfflineVerifyReport, String> {
    let manifest_path = bundle_root.join("manifest.json");
    let raw = fs::read_to_string(&manifest_path)
        .await
        .map_err(|e| format!("Failed to read manifest.json: {e}"))?;
    let manifest: BundleManifest =
        serde_json::from_str(&raw).map_err(|e| format!("Invalid manifest.json: {e}"))?;
    if manifest.schema_version != 1 {
        return Err(format!(
            "Unsupported manifest schema_version {} (expected 1)",
            manifest.schema_version
        ));
    }

    let mut errors: Vec<String> = Vec::new();
    let mut checked = 0usize;
    for ent in &manifest.files {
        let fp = bundle_root.join(&ent.relative_path);
        if !fp.is_file() {
            errors.push(format!("Missing file: {}", ent.relative_path));
            continue;
        }
        let bytes = fs::read(&fp)
            .await
            .map_err(|e| format!("Read {}: {e}", ent.relative_path))?;
        let mut hasher = Sha256::new();
        hasher.update(&bytes);
        let hex = format!("{:x}", hasher.finalize());
        if hex.to_lowercase() != ent.sha256.to_lowercase() {
            errors.push(format!("SHA-256 mismatch: {}", ent.relative_path));
        }
        checked += 1;
    }

    Ok(OfflineVerifyReport {
        ok: errors.is_empty(),
        checked_files: checked,
        errors,
    })
}

/// Load ``models/model_catalogue.json`` from a bundle directory.
pub async fn load_offline_catalogue_value(bundle_root: &Path) -> Result<Value, String> {
    let p = bundle_root.join("models/model_catalogue.json");
    let s = fs::read_to_string(&p)
        .await
        .map_err(|e| format!("Failed to read model catalogue: {e}"))?;
    serde_json::from_str(&s).map_err(|e| format!("Invalid model catalogue JSON: {e}"))
}
