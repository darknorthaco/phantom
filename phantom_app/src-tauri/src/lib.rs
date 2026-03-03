mod backend;
mod security;

use backend::phantom_api::PhantomApiClient;
use backend::phantom_deployer::PhantomDeployer;
use backend::phantom_state::{AppPhase, AppState, DeploymentProgress, PhantomMetrics};
use std::path::PathBuf;
use tauri::Emitter;

#[tauri::command]
async fn get_deployment_status(state: tauri::State<'_, AppState>) -> Result<String, String> {
    if state.is_deployed() {
        return Ok("deployed".to_string());
    }
    let phase = state.phase.lock().map_err(|e| e.to_string())?;
    match &*phase {
        AppPhase::FrontPorch => Ok("front_porch".to_string()),
        AppPhase::Deploying => Ok("deploying".to_string()),
        AppPhase::Deployed => Ok("deployed".to_string()),
        AppPhase::Error(msg) => Ok(format!("error:{msg}")),
    }
}

#[tauri::command]
async fn deploy_phantom(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<(), String> {
    {
        let mut phase = state.phase.lock().map_err(|e| e.to_string())?;
        *phase = AppPhase::Deploying;
    }

    let engine_source = find_engine_source();
    let phantom_root = state.phantom_root.clone();
    let deployer = PhantomDeployer::new(&phantom_root, &engine_source);
    let steps = PhantomDeployer::steps();
    let total = steps.len();

    for (i, label) in steps.iter().enumerate() {
        let progress = DeploymentProgress {
            step: i,
            total_steps: total,
            label: label.to_string(),
            fraction: (i as f64) / (total as f64),
        };
        let _ = app.emit("deploy-progress", &progress);

        if let Err(e) = deployer.run_step(i).await {
            log::warn!("Deployment step {} ({}) failed: {}", i, label, e);
        }
    }

    let done = DeploymentProgress {
        step: total,
        total_steps: total,
        label: "Deployment complete".to_string(),
        fraction: 1.0,
    };
    let _ = app.emit("deploy-progress", &done);

    {
        let mut phase = state.phase.lock().map_err(|e| e.to_string())?;
        *phase = AppPhase::Deployed;
    }

    Ok(())
}

#[tauri::command]
async fn get_phantom_health(
    state: tauri::State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let url = {
        state
            .controller_url
            .lock()
            .map_err(|e| e.to_string())?
            .clone()
    };
    let client = PhantomApiClient::new(&url);
    let health = client.health().await?;
    serde_json::to_value(health).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_workers(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let url = {
        state
            .controller_url
            .lock()
            .map_err(|e| e.to_string())?
            .clone()
    };
    let client = PhantomApiClient::new(&url);
    let workers = client.list_workers().await?;
    serde_json::to_value(workers).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_stats(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let url = {
        state
            .controller_url
            .lock()
            .map_err(|e| e.to_string())?
            .clone()
    };
    let client = PhantomApiClient::new(&url);
    let stats = client.get_stats().await?;
    serde_json::to_value(stats).map_err(|e| e.to_string())
}

#[tauri::command]
async fn submit_task(
    state: tauri::State<'_, AppState>,
    task_type: String,
    parameters: serde_json::Value,
    priority: u32,
) -> Result<serde_json::Value, String> {
    let url = {
        state
            .controller_url
            .lock()
            .map_err(|e| e.to_string())?
            .clone()
    };
    let client = PhantomApiClient::new(&url);
    let task = backend::phantom_api::TaskSubmission {
        task_type,
        parameters,
        priority,
        target_worker: None,
    };
    let result = client.submit_task(&task).await?;
    serde_json::to_value(result).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_system_metrics() -> PhantomMetrics {
    PhantomMetrics {
        cpu_percent: 0.0,
        memory_used_mb: 0,
        memory_total_mb: 0,
        worker_count: 0,
        active_tasks: 0,
        throughput: 0.0,
    }
}

#[tauri::command]
fn scan_lan(base_ip: String, port: u16) -> Vec<backend::lan_scanner::DiscoveredNode> {
    backend::lan_scanner::scan_subnet(&base_ip, port)
}

fn find_engine_source() -> PathBuf {
    let candidates = [
        PathBuf::from("/workspace/phantom_core"),
        PathBuf::from("../phantom_core"),
        PathBuf::from("../../phantom_core"),
    ];
    for c in &candidates {
        if c.join("run.py").exists() {
            return c.clone();
        }
    }
    candidates[0].clone()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(AppState::new())
        .invoke_handler(tauri::generate_handler![
            get_deployment_status,
            deploy_phantom,
            get_phantom_health,
            get_workers,
            get_stats,
            submit_task,
            get_system_metrics,
            scan_lan,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Phantom application");
}
