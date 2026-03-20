use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Mutex;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AppPhase {
    FrontPorch,
    Deploying,
    Deployed,
    Error(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeploymentProgress {
    pub step: usize,
    pub total_steps: usize,
    pub label: String,
    pub fraction: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhantomMetrics {
    pub cpu_percent: f64,
    pub memory_used_mb: u64,
    pub memory_total_mb: u64,
    pub workers_count: u32,
    pub active_tasks: u32,
    pub throughput: f64,
}

#[derive(Debug)]
pub struct AppState {
    pub phase: Mutex<AppPhase>,
    pub phantom_root: PathBuf,
    pub controller_url: Mutex<String>,
    /// Active offline bundle root for subsequent deploy / pre-scan (optional).
    pub offline_bundle_path: Mutex<Option<PathBuf>>,
}

impl AppState {
    pub fn new() -> Self {
        let home = dirs_next().unwrap_or_else(|| PathBuf::from("."));
        let phantom_root = home.join(".phantom");

        Self {
            phase: Mutex::new(AppPhase::FrontPorch),
            phantom_root,
            controller_url: Mutex::new("http://127.0.0.1:8080".to_string()),
            offline_bundle_path: Mutex::new(None),
        }
    }

    pub fn is_deployed(&self) -> bool {
        self.phantom_root.join("deployed.marker").exists()
    }
}

fn dirs_next() -> Option<PathBuf> {
    std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
}
