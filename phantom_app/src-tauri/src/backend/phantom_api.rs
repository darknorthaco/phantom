use serde::{Deserialize, Serialize};
use std::path::Path;
use std::time::Duration;

fn build_http_client(allow_insecure_tls: bool, request_timeout: Duration) -> Result<reqwest::Client, String> {
    let mut builder = reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(10))
        .timeout(request_timeout);
    if allow_insecure_tls {
        builder = builder.danger_accept_invalid_certs(true);
    }
    builder
        .build()
        .map_err(|e| format!("HTTP client build failed: {e}"))
}

fn json_scalar_to_string(v: Option<&serde_json::Value>) -> Option<String> {
    let v = v?;
    match v {
        serde_json::Value::String(s) => Some(s.clone()),
        serde_json::Value::Number(n) => Some(n.to_string()),
        serde_json::Value::Bool(b) => Some(b.to_string()),
        _ => None,
    }
}

fn default_orchestrator_ready_missing() -> bool {
    true
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub timestamp: String,
    pub execution_mode: String,
    pub queue_paused: bool,
    pub workers_count: u32,
    pub active_tasks: u32,
    /// Absent on older controllers — assume ready (legacy).
    #[serde(default = "default_orchestrator_ready_missing")]
    pub orchestrator_ready: bool,
    #[serde(default)]
    pub orchestrator_error: Option<String>,
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
    /// Plain-HTTP client (pre-bootstrap fallback). Uses the same timeouts as config-backed clients;
    /// does **not** disable certificate verification (no TLS on this path).
    pub fn new(base_url: &str) -> Self {
        let client = build_http_client(false, Duration::from_secs(120))
            .unwrap_or_else(|e| {
                log::error!("PhantomApiClient::new: HTTP client build failed ({e}); using reqwest default");
                reqwest::Client::new()
            });
        Self {
            base_url: base_url.to_string(),
            client,
        }
    }

    /// Read ``controller.host``, ``controller.port``, and ``tls_enabled`` from ``phantom_config.json``.
    /// Returns ``(base_url, tls_active)`` where ``tls_active`` selects self-signed acceptance for local clients.
    pub fn controller_base_url_from_config(config_path: &Path) -> Result<(String, bool), String> {
        if !config_path.is_file() {
            return Err(format!(
                "phantom_config.json not found: {}",
                config_path.display()
            ));
        }
        let raw = std::fs::read_to_string(config_path).map_err(|e| e.to_string())?;
        let v: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
        let ctrl = v
            .get("controller")
            .ok_or_else(|| "phantom_config.json: missing controller block".to_string())?;
        let host = json_scalar_to_string(ctrl.get("host"))
            .unwrap_or_else(|| "127.0.0.1".to_string());
        let port_str = json_scalar_to_string(ctrl.get("port")).ok_or_else(|| {
            "phantom_config.json: controller.port missing or invalid type".to_string()
        })?;
        let port: u16 = port_str
            .parse()
            .map_err(|_| format!("invalid controller.port: {port_str}"))?;
        let tls = v
            .get("tls_enabled")
            .map(|x| {
                x.as_bool()
                    .unwrap_or_else(|| x.as_str().is_some_and(|s| s == "true" || s == "1"))
            })
            .unwrap_or(false);
        let scheme = if tls { "https" } else { "http" };
        Ok((format!("{scheme}://{host}:{port}"), tls))
    }

    /// Full API client for the controller profile (TLS + port from config). Self-signed PEM is accepted
    /// only when ``tls_enabled`` is true (local sovereign deploy).
    pub fn from_phantom_config(config_path: &Path) -> Result<Self, String> {
        let (base_url, tls) = Self::controller_base_url_from_config(config_path)?;
        let client = build_http_client(tls, Duration::from_secs(120))?;
        Ok(Self { base_url, client })
    }

    /// When ``phantom_config.json`` is absent (pre-deploy), use ``fallback_base_url`` with a default client.
    /// If the config file exists but is unreadable, logs **warn** — fallback ignores ``tls_enabled`` and may be wrong.
    pub fn from_phantom_root_or_fallback(phantom_root: &Path, fallback_base_url: &str) -> Self {
        let cfg = phantom_root.join("phantom_config.json");
        match Self::from_phantom_config(&cfg) {
            Ok(c) => c,
            Err(e) => {
                if cfg.is_file() {
                    log::warn!(
                        "PhantomApiClient: {} present but controller profile could not be loaded ({e}); \
                         using fallback {fallback_base_url} (HTTPS / tls_enabled not applied)",
                        cfg.display()
                    );
                } else {
                    log::debug!("PhantomApiClient: using fallback URL {fallback_base_url} ({e})");
                }
                Self::new(fallback_base_url)
            }
        }
    }

    /// Build a client for **local deploy-time** health polling only (short timeouts).
    /// When `allow_insecure_tls` is true, self-signed controller certificates are accepted
    /// (same host the deployer just started — not a general WAN trust bypass).
    pub fn for_local_health_check(
        base_url: &str,
        allow_insecure_tls: bool,
    ) -> Result<Self, String> {
        let client = build_http_client(allow_insecure_tls, Duration::from_secs(15))?;
        Ok(Self {
            base_url: base_url.to_string(),
            client,
        })
    }

    /// GET ``/mode`` — current execution mode and socket schemas.
    pub async fn get_execution_mode(&self) -> Result<serde_json::Value, String> {
        let resp = self
            .client
            .get(format!("{}/mode", self.base_url))
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?;
        if !resp.status().is_success() {
            return Err(format!("HTTP {}", resp.status()));
        }
        resp.json::<serde_json::Value>()
            .await
            .map_err(|e| format!("Parse error: {e}"))
    }

    /// POST ``/mode`` — execution mode change (same transport as other API calls).
    pub async fn post_execution_mode(&self, mode: String) -> Result<serde_json::Value, String> {
        let resp = self
            .client
            .post(format!("{}/mode", self.base_url))
            .json(&serde_json::json!({ "mode": mode }))
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?;
        if !resp.status().is_success() {
            return Err(format!("HTTP {}", resp.status()));
        }
        resp.json::<serde_json::Value>()
            .await
            .map_err(|e| format!("Parse error: {e}"))
    }

    pub async fn health(&self) -> Result<HealthResponse, String> {
        let resp = self
            .client
            .get(format!("{}/health", self.base_url))
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?;
        if !resp.status().is_success() {
            return Err(format!("HTTP {}", resp.status()));
        }
        resp.json::<HealthResponse>()
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

    /// GET ``/tasks/{task_id}`` — task status and result (for chat / task polling).
    pub async fn get_task(&self, task_id: &str) -> Result<serde_json::Value, String> {
        let resp = self
            .client
            .get(format!("{}/tasks/{}", self.base_url, task_id))
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?;
        if !resp.status().is_success() {
            return Err(format!("HTTP {}", resp.status()));
        }
        resp.json::<serde_json::Value>()
            .await
            .map_err(|e| format!("Parse error: {e}"))
    }
}
