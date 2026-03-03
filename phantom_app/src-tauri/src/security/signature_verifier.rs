use sha2::{Digest, Sha256};
use std::path::Path;

pub fn compute_sha256(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    let result = hasher.finalize();
    result.iter().map(|b| format!("{b:02x}")).collect()
}

pub async fn compute_file_sha256(file_path: &Path) -> Result<String, String> {
    let data = tokio::fs::read(file_path)
        .await
        .map_err(|e| format!("Failed to read file: {e}"))?;
    Ok(compute_sha256(&data))
}

pub async fn verify_file_signature(
    file_path: &Path,
    expected_hash: &str,
) -> Result<bool, String> {
    let actual = compute_file_sha256(file_path).await?;
    Ok(actual == expected_hash)
}
