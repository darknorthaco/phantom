use serde::{Deserialize, Serialize};
use tokio::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuInfo {
    pub name: String,
    pub driver_version: String,
    pub memory_total_mb: u64,
    pub memory_free_mb: u64,
}

pub async fn detect_nvidia_gpus() -> Vec<GpuInfo> {
    let output = Command::new("nvidia-smi")
        .args([
            "--query-gpu=name,driver_version,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ])
        .output()
        .await;

    let output = match output {
        Ok(o) if o.status.success() => o,
        _ => return vec![],
    };

    let stdout = String::from_utf8_lossy(&output.stdout);
    stdout
        .lines()
        .filter_map(|line| {
            let parts: Vec<&str> = line.split(',').map(|s| s.trim()).collect();
            if parts.len() >= 4 {
                Some(GpuInfo {
                    name: parts[0].to_string(),
                    driver_version: parts[1].to_string(),
                    memory_total_mb: parts[2].parse().unwrap_or(0),
                    memory_free_mb: parts[3].parse().unwrap_or(0),
                })
            } else {
                None
            }
        })
        .collect()
}
