use crate::security::signature_verifier;
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManifestEntry {
    pub file: String,
    pub sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntegrityManifest {
    pub version: String,
    pub entries: Vec<ManifestEntry>,
}

#[derive(Debug, Clone, Serialize)]
pub struct IntegrityResult {
    pub valid: bool,
    pub checked: usize,
    pub failures: Vec<String>,
}

pub async fn check_dependency_integrity(
    deps_dir: &Path,
    manifest_path: &Path,
) -> Result<IntegrityResult, String> {
    if !manifest_path.exists() {
        return Ok(IntegrityResult {
            valid: true,
            checked: 0,
            failures: vec!["manifest.json not found — skipping integrity check".to_string()],
        });
    }

    let content = tokio::fs::read_to_string(manifest_path)
        .await
        .map_err(|e| format!("Failed to read manifest: {e}"))?;

    let manifest: IntegrityManifest =
        serde_json::from_str(&content).map_err(|e| format!("Invalid manifest: {e}"))?;

    let mut failures = Vec::new();
    let mut checked = 0;

    for entry in &manifest.entries {
        let file_path = deps_dir.join(&entry.file);
        if !file_path.exists() {
            failures.push(format!("Missing: {}", entry.file));
            continue;
        }

        match signature_verifier::verify_file_signature(&file_path, &entry.sha256).await {
            Ok(true) => checked += 1,
            Ok(false) => {
                failures.push(format!("Hash mismatch: {}", entry.file));
                checked += 1;
            }
            Err(e) => failures.push(format!("Error checking {}: {e}", entry.file)),
        }
    }

    Ok(IntegrityResult {
        valid: failures.is_empty(),
        checked,
        failures,
    })
}
