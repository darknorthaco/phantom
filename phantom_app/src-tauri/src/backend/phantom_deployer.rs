use std::collections::HashSet;
use std::path::{Path, PathBuf};
use tokio::process::Command;

use super::lan_scanner::DiscoveredNode;
use super::phantom_api::{PhantomApiClient, RegisterWorkerRequest};

#[derive(Debug, Clone, serde::Serialize)]
pub struct DeployStep {
    pub index: usize,
    pub label: String,
    pub status: String,
}

pub struct PhantomDeployer {
    phantom_root: PathBuf,
    engine_source: PathBuf,
}

impl PhantomDeployer {
    pub fn new(phantom_root: &Path, engine_source: &Path) -> Self {
        Self {
            phantom_root: phantom_root.to_path_buf(),
            engine_source: engine_source.to_path_buf(),
        }
    }

    pub fn steps() -> Vec<&'static str> {
        vec![
            "Creating Phantom virtual environment",
            "Installing Python runtime",
            "Installing Phantom Core",
            "Verifying GPU plugins",
            "Installing Phantom service",
            "Starting controller",
            "Opening ports",
            "Initializing state",
            "Scanning LAN",
            "Loading execution modes",
        ]
    }

    pub async fn run_step(&self, index: usize) -> Result<(), String> {
        match index {
            0 => self.create_venv().await,
            1 => self.install_python_deps().await,
            2 => self.install_phantom_core().await,
            3 => self.verify_gpu_plugins().await,
            4 => self.install_service().await,
            5 => self.start_controller().await,
            6 => self.open_ports().await,
            7 => self.initialize_state().await,
            8 => self.scan_lan().await,
            9 => self.load_execution_modes().await,
            _ => Err("Unknown deployment step".to_string()),
        }
    }

    async fn create_venv(&self) -> Result<(), String> {
        let venv_path = self.phantom_root.join("venv");
        tokio::fs::create_dir_all(&self.phantom_root)
            .await
            .map_err(|e| format!("Failed to create phantom root: {e}"))?;

        // On Windows the launcher is "python", on Unix "python3"
        #[cfg(target_os = "windows")]
        let py_cmd = "python";
        #[cfg(not(target_os = "windows"))]
        let py_cmd = "python3";

        let output = Command::new(py_cmd)
            .args(["-m", "venv", &venv_path.to_string_lossy()])
            .output()
            .await
            .map_err(|e| format!("Failed to create venv: {e}"))?;

        if !output.status.success() {
            return Err(format!(
                "venv creation failed: {}",
                String::from_utf8_lossy(&output.stderr)
            ));
        }
        Ok(())
    }

    async fn install_python_deps(&self) -> Result<(), String> {
        let pip = venv_pip(&self.phantom_root);
        let req = self.engine_source.join("requirements.txt");

        if !req.exists() {
            return Err(format!("requirements.txt not found at {:?}", req));
        }

        let output = Command::new(pip.to_string_lossy().as_ref())
            .args(["install", "--no-cache-dir",
                   "fastapi", "uvicorn[standard]", "pydantic", "httpx",
                   "requests", "websockets", "psutil", "numpy", "pyyaml",
                   "cryptography", "pyjwt"])
            .output()
            .await
            .map_err(|e| format!("pip install failed: {e}"))?;

        if !output.status.success() {
            return Err(format!(
                "pip install failed: {}",
                String::from_utf8_lossy(&output.stderr)
            ));
        }
        Ok(())
    }

    async fn install_phantom_core(&self) -> Result<(), String> {
        let dest = self.phantom_root.join("engine");

        // If engine is already deployed and run.py is present, skip the copy.
        if dest.join("run.py").exists() {
            log::info!("Phantom engine already present at {:?} — skipping copy", dest);
            return Ok(());
        }

        // If engine_source is the same path as the destination, nothing to do.
        if self.engine_source == dest {
            return Ok(());
        }

        log::info!(
            "Copying Phantom engine from {:?} → {:?}",
            self.engine_source,
            dest
        );

        copy_dir_all(&self.engine_source, &dest)
            .await
            .map_err(|e| format!("Failed to install Phantom engine: {e}"))?;

        log::info!("Phantom engine installed successfully");
        Ok(())
    }

    async fn verify_gpu_plugins(&self) -> Result<(), String> {
        #[cfg(target_os = "linux")]
        {
            let gpus = super::linux::gpu_detection::detect_nvidia_gpus().await;
            if gpus.is_empty() {
                log::info!("No NVIDIA GPUs detected — GPU plugins inactive (CPU-only mode)");
            } else {
                log::info!("Detected {} NVIDIA GPU(s): {}", gpus.len(), gpus[0].name);
            }
        }
        #[cfg(target_os = "windows")]
        {
            let gpus = super::windows::gpu_detection::detect_gpus().await;
            if gpus.is_empty() {
                log::info!("No GPUs detected — GPU plugins inactive (CPU-only mode)");
            } else {
                log::info!("Detected {} GPU(s): {}", gpus.len(), gpus[0].name);
            }
        }
        Ok(())
    }

    async fn install_service(&self) -> Result<(), String> {
        let python    = venv_python(&self.phantom_root);
        let run_py    = self.engine_source.join("run.py");
        let state_dir = self.phantom_root.join("state");

        #[cfg(target_os = "linux")]
        {
            let unit = super::linux::systemd_installer::generate_unit_file(
                &whoami_or_root(),
                &python,
                &run_py,
                &self.engine_source,
                &state_dir,
            );

            // Try user-level systemd (no root required) first
            let user_systemd = home_dir().join(".config/systemd/user");
            tokio::fs::create_dir_all(&user_systemd)
                .await
                .map_err(|e| format!("Failed to create systemd user dir: {e}"))?;

            let unit_path = user_systemd.join("phantom.service");
            tokio::fs::write(&unit_path, &unit)
                .await
                .map_err(|e| format!("Failed to write unit file: {e}"))?;

            log::info!("Written systemd unit to {:?}", unit_path);

            // daemon-reload for user session
            let reload = Command::new("systemctl")
                .args(["--user", "daemon-reload"])
                .output()
                .await;

            match reload {
                Ok(out) if out.status.success() => {
                    // Enable the user service (don't fail if this errors — not all environments support it)
                    let _ = Command::new("systemctl")
                        .args(["--user", "enable", "phantom"])
                        .output()
                        .await;
                    log::info!("Phantom systemd user service enabled");
                }
                _ => {
                    log::warn!("systemctl --user daemon-reload unavailable; service file written but not enabled");
                }
            }
        }

        #[cfg(target_os = "windows")]
        {
            let python_win = self.phantom_root.join("venv\\Scripts\\python.exe");
            match super::windows::service_installer::install_service(
                "phantom",
                "Phantom Distributed Compute Controller",
                &python_win,
                &run_py,
                &state_dir,
            ).await {
                Ok(()) => log::info!("Phantom Windows service installed"),
                Err(e) => log::warn!("Windows service install failed (may already exist): {e}"),
            }
        }

        #[cfg(not(any(target_os = "linux", target_os = "windows")))]
        {
            log::info!("Service installation skipped on this platform");
            let _ = (&python, &run_py, &state_dir); // suppress unused warnings
        }

        Ok(())
    }

    async fn start_controller(&self) -> Result<(), String> {
        let python = venv_python(&self.phantom_root);
        // Prefer the deployed copy; fall back to engine_source (dev mode).
        let deployed_run_py = self.phantom_root.join("engine/run.py");
        let run_py = if deployed_run_py.exists() {
            deployed_run_py
        } else {
            self.engine_source.join("run.py")
        };

        // Read security level from phantom_config.json (written by step 9).
        // Falls back to "disabled" for first-launch and dev environments.
        let security_level = read_controller_config(&self.phantom_root, "security_level")
            .unwrap_or_else(|| "disabled".to_string());

        if !run_py.exists() {
            return Err(format!("run.py not found at {:?}", run_py));
        }

        let state_dir = self.phantom_root.join("state");
        tokio::fs::create_dir_all(&state_dir)
            .await
            .map_err(|e| format!("mkdir state: {e}"))?;

        Command::new(python.to_string_lossy().as_ref())
            .args([
                run_py.to_string_lossy().as_ref(),
                "--host", "127.0.0.1",
                "--port", "8080",
                "--security", &security_level,
            ])
            .env("PHANTOM_STATE_DIR", state_dir.to_string_lossy().as_ref())
            .spawn()
            .map_err(|e| format!("Failed to start controller: {e}"))?;

        tokio::time::sleep(std::time::Duration::from_secs(3)).await;
        Ok(())
    }

    async fn open_ports(&self) -> Result<(), String> {
        #[cfg(target_os = "linux")]
        {
            // Try ufw first (Ubuntu/Debian)
            let ufw = Command::new("ufw")
                .args(["allow", "8080/tcp"])
                .output()
                .await;

            match ufw {
                Ok(out) if out.status.success() => {
                    log::info!("ufw: allowed port 8080/tcp");
                    return Ok(());
                }
                _ => {
                    log::info!("ufw not available, trying iptables");
                }
            }

            // Fall back to iptables
            let ipt = Command::new("iptables")
                .args(["-C", "INPUT", "-p", "tcp", "--dport", "8080", "-j", "ACCEPT"])
                .output()
                .await;

            let already_open = matches!(ipt, Ok(ref o) if o.status.success());

            if !already_open {
                let add = Command::new("iptables")
                    .args(["-A", "INPUT", "-p", "tcp", "--dport", "8080", "-j", "ACCEPT"])
                    .output()
                    .await;

                match add {
                    Ok(out) if out.status.success() => {
                        log::info!("iptables: opened port 8080/tcp");
                    }
                    Ok(out) => {
                        log::warn!(
                            "iptables failed: {}",
                            String::from_utf8_lossy(&out.stderr)
                        );
                    }
                    Err(e) => {
                        log::warn!("iptables not available: {e}");
                    }
                }
            } else {
                log::info!("Port 8080/tcp already open in iptables");
            }
        }

        #[cfg(target_os = "windows")]
        {
            let result = Command::new("netsh")
                .args([
                    "advfirewall", "firewall", "add", "rule",
                    "name=PhantomController",
                    "dir=in",
                    "action=allow",
                    "protocol=TCP",
                    "localport=8080",
                ])
                .output()
                .await;

            match result {
                Ok(out) if out.status.success() => {
                    log::info!("Windows firewall: allowed port 8080/TCP");
                }
                Ok(out) => {
                    log::warn!(
                        "netsh firewall rule failed: {}",
                        String::from_utf8_lossy(&out.stderr)
                    );
                }
                Err(e) => {
                    log::warn!("netsh not available: {e}");
                }
            }
        }

        Ok(())
    }

    async fn initialize_state(&self) -> Result<(), String> {
        let marker = self.phantom_root.join("deployed.marker");
        tokio::fs::write(&marker, "deployed")
            .await
            .map_err(|e| format!("Failed to write marker: {e}"))?;
        Ok(())
    }

    async fn scan_lan(&self) -> Result<(), String> {
        // Determine the local IP to use as the scan base; try fallback subnets if primary fails.
        let base_ips = local_ip_bases();
        log::info!(
            "Scanning LAN from base(s) {:?} on worker port 8090",
            base_ips
        );

        // Scan only worker port 8090 — controllers use 8080 and do not expose worker_id.
        let worker_port = 8090_u16;
        let mut nodes: Vec<DiscoveredNode> = Vec::new();

        // Always check localhost for same-machine worker+controller setups.
        let local_nodes = tokio::task::spawn_blocking(move || {
            super::lan_scanner::scan_localhost(worker_port)
        })
        .await
        .map_err(|e| format!("LAN scan task panicked: {e}"))?;
        nodes.extend(local_nodes);

        // Scan each candidate subnet (primary from UDP trick + fallbacks).
        for base_ip in &base_ips {
            let scan_base = base_ip.clone();
            let mut port_nodes = tokio::task::spawn_blocking(move || {
                super::lan_scanner::scan_subnet(&scan_base, worker_port)
            })
            .await
            .map_err(|e| format!("LAN scan task panicked: {e}"))?;
            nodes.append(&mut port_nodes);
        }

        // De-dupe in case the same endpoint was discovered multiple times.
        let mut seen = HashSet::new();
        nodes.retain(|n| seen.insert(format!("{}:{}", n.ip, n.port)));

        log::info!("LAN scan complete: {} Phantom node(s) found", nodes.len());

        if !nodes.is_empty() {
            let scan_path = self.phantom_root.join("lan_scan.json");
            let json = serde_json::to_string_pretty(&nodes)
                .unwrap_or_else(|_| "[]".to_string());
            tokio::fs::write(&scan_path, json)
                .await
                .map_err(|e| format!("Failed to write LAN scan results: {e}"))?;
            log::info!("LAN scan results written to {:?}", scan_path);
        }

        // Best effort: auto-register discovered workers in the local controller.
        // This makes the TOC Workers panel reflect scan results immediately.
        let controller = PhantomApiClient::new("http://127.0.0.1:8080");
        let mut registered = 0usize;
        for node in nodes {
            if let Some(worker) = discover_worker(node).await {
                match controller.register_worker(&worker).await {
                    Ok(()) => {
                        registered += 1;
                    }
                    Err(e) => {
                        log::warn!("Failed to register discovered worker {}: {e}", worker.host);
                    }
                }
            }
        }
        log::info!("LAN worker auto-registration complete: {registered} worker(s) registered");

        Ok(())
    }
}

/// Run a full LAN scan and register discovered workers with the controller.
/// Used by both deployment step 8 and the manual "Scan LAN" action from the UI.
pub async fn scan_and_register_workers(
    phantom_root: &std::path::Path,
    controller_url: &str,
) -> Result<ScanResult, String> {
    use std::collections::HashSet;

    let base_ips = local_ip_bases();
    let worker_port = 8090_u16;

    let mut nodes: Vec<DiscoveredNode> = Vec::new();

    // Scan localhost for same-machine workers.
    let local_nodes = tokio::task::spawn_blocking(move || {
        super::lan_scanner::scan_localhost(worker_port)
    })
    .await
    .map_err(|e| format!("LAN scan task panicked: {e}"))?;
    nodes.extend(local_nodes);

    // Scan each candidate subnet.
    for base_ip in &base_ips {
        let scan_base = base_ip.clone();
        let mut port_nodes = tokio::task::spawn_blocking(move || {
            super::lan_scanner::scan_subnet(&scan_base, worker_port)
        })
        .await
        .map_err(|e| format!("LAN scan task panicked: {e}"))?;
        nodes.append(&mut port_nodes);
    }

    let mut seen = HashSet::new();
    nodes.retain(|n| seen.insert(format!("{}:{}", n.ip, n.port)));

    let controller = PhantomApiClient::new(controller_url);
    let mut registered = 0usize;
    for node in &nodes {
        if let Some(worker) = discover_worker(node.clone()).await {
            match controller.register_worker(&worker).await {
                Ok(()) => registered += 1,
                Err(e) => log::warn!("Failed to register {}:{}: {e}", node.ip, node.port),
            }
        }
    }

    // Optionally persist scan results.
    if !nodes.is_empty() {
        let scan_path = phantom_root.join("lan_scan.json");
        let json = serde_json::to_string_pretty(&nodes).unwrap_or_else(|_| "[]".to_string());
        let _ = tokio::fs::write(&scan_path, json).await;
    }

    Ok(ScanResult {
        scanned: nodes.len(),
        registered,
        nodes: nodes
            .into_iter()
            .map(|n| (n.ip.clone(), n.port))
            .collect(),
    })
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct ScanResult {
    pub scanned: usize,
    pub registered: usize,
    pub nodes: Vec<(String, u16)>,
}

impl PhantomDeployer {
    async fn load_execution_modes(&self) -> Result<(), String> {
        tokio::fs::create_dir_all(&self.phantom_root)
            .await
            .map_err(|e| format!("Failed to create phantom root: {e}"))?;

        // LLM config
        let llm_config_path = self.phantom_root.join("llm_config.json");
        if !llm_config_path.exists() {
            let default = serde_json::json!({
                "execution_mode": "manual",
                "allow_per_task_override": false,
                "model": "phi-3.5-mini",
                "auto_withdraw_on_human_activity": true,
                "confidence_threshold": 0.85
            });
            tokio::fs::write(
                &llm_config_path,
                serde_json::to_string_pretty(&default).map_err(|e| e.to_string())?,
            )
            .await
            .map_err(|e| format!("Failed to write llm_config.json: {e}"))?;
            log::info!("Default llm_config.json written (execution_mode: manual)");
        }

        // Controller config (security level and connection settings)
        let controller_config_path = self.phantom_root.join("phantom_config.json");
        if !controller_config_path.exists() {
            let default = serde_json::json!({
                "security_level": "disabled",
                "controller_host": "127.0.0.1",
                "controller_port": 8080
            });
            tokio::fs::write(
                &controller_config_path,
                serde_json::to_string_pretty(&default).map_err(|e| e.to_string())?,
            )
            .await
            .map_err(|e| format!("Failed to write phantom_config.json: {e}"))?;
            log::info!("Default phantom_config.json written (security_level: disabled)");
        }

        Ok(())
    }
}

async fn discover_worker(node: DiscoveredNode) -> Option<RegisterWorkerRequest> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(2))
        .build()
        .ok()?;

    // Prefer the worker root endpoint because it includes gpu_info.
    let root_url = format!("http://{}:{}/", node.ip, node.port);
    if let Ok(resp) = client.get(&root_url).send().await {
        if let Ok(payload) = resp.json::<serde_json::Value>().await {
            let worker_id = payload
                .get("worker_id")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
                .unwrap_or_else(|| format!("lan-worker-{}-{}", node.ip.replace('.', "-"), node.port));

            if let Some(gpu_info) = payload.get("gpu_info") {
                return Some(RegisterWorkerRequest {
                    worker_id,
                    host: node.ip,
                    port: node.port,
                    gpu_info: gpu_info.clone(),
                    status: "active".to_string(),
                });
            }
        }
    }

    // Fallback to /health if root is unavailable; only accept responses that
    // look like worker health payloads (must include worker_id).
    let health_url = format!("http://{}:{}/health", node.ip, node.port);
    let resp = client.get(&health_url).send().await.ok()?;
    let payload = resp.json::<serde_json::Value>().await.ok()?;
    let worker_id = payload
        .get("worker_id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())?;

    Some(RegisterWorkerRequest {
        worker_id,
        host: node.ip,
        port: node.port,
        gpu_info: serde_json::json!({
            "source": "lan_scan",
            "health": payload
        }),
        status: "active".to_string(),
    })
}

// ── Helpers ─────────────────────────────────────────────────────────

/// Recursively copy a directory tree from `src` to `dst`.
/// Skips `__pycache__`, `.git`, `venv`, and `*.pyc` files.
async fn copy_dir_all(src: &Path, dst: &Path) -> std::io::Result<()> {
    tokio::fs::create_dir_all(dst).await?;

    let mut read_dir = tokio::fs::read_dir(src).await?;
    while let Some(entry) = read_dir.next_entry().await? {
        let name = entry.file_name();
        let name_str = name.to_string_lossy();

        // Skip noise
        if matches!(
            name_str.as_ref(),
            "__pycache__" | ".git" | ".github" | "venv" | ".venv" | "node_modules"
        ) || name_str.ends_with(".pyc")
            || name_str.ends_with(".egg-info")
        {
            continue;
        }

        let src_path = entry.path();
        let dst_path = dst.join(&name);
        let file_type = entry.file_type().await?;

        if file_type.is_dir() {
            // Box the future to avoid infinite-size recursion
            Box::pin(copy_dir_all(&src_path, &dst_path)).await?;
        } else {
            tokio::fs::copy(&src_path, &dst_path).await?;
        }
    }
    Ok(())
}

fn home_dir() -> PathBuf {
    std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

#[allow(dead_code)]
fn whoami_or_root() -> String {
    std::env::var("USER")
        .or_else(|_| std::env::var("USERNAME"))
        .unwrap_or_else(|_| "root".to_string())
}

/// Return the correct Python executable path inside the venv.
/// Windows:  .phantom\venv\Scripts\python.exe
/// Unix:     .phantom/venv/bin/python3
fn venv_python(phantom_root: &PathBuf) -> PathBuf {
    #[cfg(target_os = "windows")]
    return phantom_root.join("venv\\Scripts\\python.exe");
    #[cfg(not(target_os = "windows"))]
    return phantom_root.join("venv/bin/python3");
}

/// Return the correct pip executable path inside the venv.
/// Windows:  .phantom\venv\Scripts\pip.exe
/// Unix:     .phantom/venv/bin/pip
fn venv_pip(phantom_root: &PathBuf) -> PathBuf {
    #[cfg(target_os = "windows")]
    return phantom_root.join("venv\\Scripts\\pip.exe");
    #[cfg(not(target_os = "windows"))]
    return phantom_root.join("venv/bin/pip");
}

/// Read a string field from `~/.phantom/phantom_config.json`.
/// Returns `None` if the file doesn't exist or the field is missing.
fn read_controller_config(phantom_root: &PathBuf, key: &str) -> Option<String> {
    let path = phantom_root.join("phantom_config.json");
    let content = std::fs::read_to_string(&path).ok()?;
    let json: serde_json::Value = serde_json::from_str(&content).ok()?;
    json.get(key)?.as_str().map(|s| s.to_string())
}

/// Return candidate /24 base IPs for LAN scanning. Uses UDP probe to 8.8.8.8 for
/// the primary; on failure (no internet, VPN, multi-NIC) uses common fallbacks so
/// at least one subnet is scanned.
fn local_ip_bases() -> Vec<String> {
    use std::net::UdpSocket;
    let mut bases = Vec::new();

    // Primary: probe trick — connect to public IP to discover local outbound interface.
    if let Ok(sock) = UdpSocket::bind("0.0.0.0:0") {
        let _ = sock.connect("8.8.8.8:80");
        if let Ok(addr) = sock.local_addr() {
            let ip = addr.ip().to_string();
            let parts: Vec<&str> = ip.rsplitn(2, '.').collect();
            if parts.len() == 2 {
                bases.push(format!("{}.1", parts[1]));
            }
        }
    }

    // Fallbacks only when primary fails (offline, VPN, or wrong interface).
    if bases.is_empty() {
        log::info!("Primary subnet detection failed; using fallback subnets");
        bases.extend([
            "192.168.1.1".to_string(),
            "192.168.0.1".to_string(),
            "10.0.0.1".to_string(),
        ]);
    }
    bases
}
