use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub timestamp: String,
    pub execution_mode: String,
    pub queue_paused: bool,
    pub workers_count: u32,
    pub active_tasks: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerEntry {
    pub worker_id: String,
    pub host: String,
    pub port: u16,
    pub gpu_info: serde_json::Value,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisterWorkerRequest {
    pub worker_id: String,
    pub host: String,
    pub port: u16,
    pub gpu_info: serde_json::Value,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkersResponse {
    pub workers: Vec<WorkerEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StatsResponse {
    pub workers: serde_json::Value,
    pub tasks: serde_json::Value,
    pub features: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskSubmission {
    pub task_type: String,
    pub parameters: serde_json::Value,
    pub priority: u32,
    pub target_worker: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResponse {
    pub task_id: String,
    pub status: String,
    pub worker_id: Option<String>,
}

pub struct PhantomApiClient {
    base_url: String,
    client: reqwest::Client,
}

impl PhantomApiClient {
    pub fn new(base_url: &str) -> Self {
        Self {
            base_url: base_url.to_string(),
            client: reqwest::Client::new(),
        }
    }

    pub async fn health(&self) -> Result<HealthResponse, String> {
        self.client
            .get(format!("{}/health", self.base_url))
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?
            .json::<HealthResponse>()
            .await
            .map_err(|e| format!("Parse error: {e}"))
    }

    pub async fn list_workers(&self) -> Result<WorkersResponse, String> {
        self.client
            .get(format!("{}/workers", self.base_url))
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?
            .json::<WorkersResponse>()
            .await
            .map_err(|e| format!("Parse error: {e}"))
    }

    /// §5 — Record user approval before registration. Must be called first.
    pub async fn approve_worker(&self, worker_id: &str, public_key_b64: &str) -> Result<(), String> {
        let body = serde_json::json!({
            "worker_id": worker_id,
            "public_key": public_key_b64,
        });
        self.client
            .post(format!("{}/workers/approve", self.base_url))
            .json(&body)
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?
            .error_for_status()
            .map_err(|e| format!("Approve failed: {e}"))?;
        Ok(())
    }

    pub async fn register_worker(&self, worker: &RegisterWorkerRequest) -> Result<(), String> {
        self.client
            .post(format!("{}/workers/register", self.base_url))
            .json(worker)
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?
            .error_for_status()
            .map_err(|e| format!("Register failed: {e}"))?;
        Ok(())
    }

    pub async fn get_stats(&self) -> Result<StatsResponse, String> {
        self.client
            .get(format!("{}/stats", self.base_url))
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?
            .json::<StatsResponse>()
            .await
            .map_err(|e| format!("Parse error: {e}"))
    }

    pub async fn submit_task(&self, task: &TaskSubmission) -> Result<TaskResponse, String> {
        self.client
            .post(format!("{}/tasks/submit", self.base_url))
            .json(task)
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?
            .json::<TaskResponse>()
            .await
            .map_err(|e| format!("Parse error: {e}"))
    }
}
