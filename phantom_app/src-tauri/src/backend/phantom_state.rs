use super::phantom_api::PhantomApiClient;
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

/// Emitted as ``deploy-failed`` when a deploy step or registration fails (human-facing diagnostics).
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DeployFailureInfo {
    pub message: String,
    pub step_index: Option<usize>,
    pub step_label: Option<String>,
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
        let cfg_path = phantom_root.join("phantom_config.json");
        let initial_controller_url =
            PhantomApiClient::controller_base_url_from_config(&cfg_path)
                .map(|(url, _)| url)
                .unwrap_or_else(|_| "http://127.0.0.1:8080".to_string());

        Self {
            phase: Mutex::new(AppPhase::FrontPorch),
            phantom_root,
            controller_url: Mutex::new(initial_controller_url),
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
