use serde::{Deserialize, Serialize};
use tokio::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuInfo {
    pub name: String,
    pub driver_version: String,
    pub memory_total_mb: u64,
    pub memory_free_mb: u64,
}

pub async fn detect_gpus() -> Vec<GpuInfo> {
    if let Some(gpus) = detect_nvidia().await {
        return gpus;
    }
    detect_wmi().await.unwrap_or_default()
}

async fn detect_nvidia() -> Option<Vec<GpuInfo>> {
    let output = Command::new("nvidia-smi")
        .args([
            "--query-gpu=name,driver_version,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ])
        .output()
        .await
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let gpus: Vec<GpuInfo> = stdout
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
        .collect();

    if gpus.is_empty() { None } else { Some(gpus) }
}

async fn detect_wmi() -> Option<Vec<GpuInfo>> {
    let output = Command::new("wmic")
        .args(["path", "win32_VideoController", "get", "Name,DriverVersion,AdapterRAM", "/format:csv"])
        .output()
        .await
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let gpus: Vec<GpuInfo> = stdout
        .lines()
        .skip(2)
        .filter_map(|line| {
            let parts: Vec<&str> = line.split(',').collect();
            if parts.len() >= 4 {
                let ram_bytes: u64 = parts[1].trim().parse().unwrap_or(0);
                Some(GpuInfo {
                    name: parts[3].trim().to_string(),
                    driver_version: parts[2].trim().to_string(),
                    memory_total_mb: ram_bytes / (1024 * 1024),
                    memory_free_mb: 0,
                })
            } else {
                None
            }
        })
        .collect();

    if gpus.is_empty() { None } else { Some(gpus) }
}
