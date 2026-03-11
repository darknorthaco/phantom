use std::path::{Path, PathBuf};
use tauri::Emitter;
use tokio::process::Command;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

use super::discovery::{
    self, base_to_broadcast, discover_workers_with_log, DEFAULT_DISCOVERY_TOTAL_TIMEOUT_MS,
};
use super::discovery_log::{DependencyInitEntry, DiscoveryLog, FullDeployLogEntry};
use super::phantom_api::{PhantomApiClient, RegisterWorkerRequest};

#[derive(Debug, Clone, serde::Serialize)]
pub struct DeployStep {
    pub index: usize,
    pub label: String,
    pub status: String,
}

/// Worker representation for deployment ceremony (frontend display).
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiscoveredWorkerForCeremony {
    pub worker_id: String,
    pub host: String,
    pub port: u16,
    pub gpu_info: serde_json::Value,
    pub source_ip: String,
    pub signature_verified: bool,
    pub fingerprint: String,
    /// Base64 Ed25519 public key — required for §5 TrustRecord(approved).
    pub public_key_b64: String,
}

/// Result of pre-scan deployment (steps 0–9 + discovery, no registration).
#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DeploymentPreScanResult {
    pub discovered_workers: Vec<DiscoveredWorkerForCeremony>,
    pub discovery_log: DiscoveryLog,
    /// True when worker_count == 0; blocks progression to TOC.
    pub discovery_failed: bool,
}

/// Worker selection for registration (from frontend).
#[derive(Debug, Clone, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkerSelectionForRegistration {
    pub worker_id: String,
    pub host: String,
    pub port: u16,
    pub gpu_info: serde_json::Value,
    /// Base64 Ed25519 public key — required for §5 TrustRecord(approved).
    #[serde(default)]
    pub public_key_b64: String,
}

/// Request payload for complete_deployment_with_selection (camelCase for frontend).
#[derive(Debug, Clone, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompleteDeploymentRequest {
    pub worker_pool: Vec<WorkerSelectionForRegistration>,
    pub run_controller_llm: bool,
}

pub struct PhantomDeployer {
    phantom_root: PathBuf,
    engine_source: PathBuf,
    /// When set, scan_lan emits "scan-log" events for in-app display.
    scan_log_emitter: Option<tauri::AppHandle>,
    /// Result of the local worker readiness probe: (attempts, success).
    /// Written by start_local_worker(), read by run_pre_scan_deployment().
    readiness_result: std::sync::Mutex<(u32, bool)>,
}

impl PhantomDeployer {
    pub fn new(
        phantom_root: &Path,
        engine_source: &Path,
        scan_log_emitter: Option<tauri::AppHandle>,
    ) -> Self {
        Self {
            phantom_root: phantom_root.to_path_buf(),
            engine_source: engine_source.to_path_buf(),
            scan_log_emitter,
            readiness_result: std::sync::Mutex::new((0, false)),
        }
    }

    fn emit_scan_log(&self, line: &str) {
        if let Some(ref app) = self.scan_log_emitter {
            let _ = app.emit("scan-log", line);
        }
    }

    /// Read discovery config from phantom_config.json.
    /// Falls back to DEFAULT_DISCOVERY_TOTAL_TIMEOUT_MS and true if unavailable.
    fn read_discovery_config(&self) -> (u64, bool) {
        let config_path = self.phantom_root.join("phantom_config.json");
        let total_timeout_ms = read_nested_config(&config_path, &["discovery", "total_timeout_ms"])
            .and_then(|s| s.parse::<u64>().ok())
            .unwrap_or(DEFAULT_DISCOVERY_TOTAL_TIMEOUT_MS);
        let early_exit = read_nested_config(&config_path, &["discovery", "early_exit_on_first_worker"])
            .and_then(|s| s.parse::<bool>().ok())
            .unwrap_or(true);
        (total_timeout_ms, early_exit)
    }

    fn emit_deploy_progress(&self, step: usize, total: usize, label: &str, fraction: f64) {
        if let Some(ref app) = self.scan_log_emitter {
            let progress = super::phantom_state::DeploymentProgress {
                step,
                total_steps: total,
                label: label.to_string(),
                fraction,
            };
            let _ = app.emit("deploy-progress", &progress);
        }
    }

    pub fn steps() -> Vec<&'static str> {
        vec![
            "Creating Phantom virtual environment",
            "Installing Python runtime",
            "Installing Phantom Core",
            "Verifying GPU plugins",
            "Installing Phantom service",
            "Bootstrapping config",          // Step 5 (§8 Step 4.5)
            "Starting controller",
            "Opening ports",
            "Initializing state",
            "Starting local worker",
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
            5 => self.bootstrap_config().await,  // §8 Step 4.5
            6 => self.start_controller().await,
            7 => self.open_ports().await,
            8 => self.initialize_state().await,
            9 => self.start_local_worker().await,
            10 => self.scan_lan().await,
            11 => self.load_execution_modes().await,
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

    /// §8 Step 4.5 — write phantom_config.json atomically before the controller starts.
    ///
    /// Reads ControllerPlacementParams from §1 Pre-0 ceremony (controller_placement.json).
    /// Writes the full corrected schema to phantom_config.json using an atomic tmp → rename.
    /// A timestamped backup of any pre-existing phantom_config.json is preserved.
    ///
    /// This step MUST succeed before `start_controller` (Step 6) runs.
    async fn bootstrap_config(&self) -> Result<(), String> {
        let config_path = self.phantom_root.join("phantom_config.json");
        let placement_path = self.phantom_root.join("controller_placement.json");

        // §1 — ControllerPlacementParams must exist (Pre-0 ceremony completed).
        if !placement_path.exists() {
            return Err(
                "Pre-0 Controller Selection Ceremony required. \
                 Complete the controller placement screen before deploying."
                    .to_string(),
            );
        }

        let placement_raw = tokio::fs::read_to_string(&placement_path)
            .await
            .map_err(|e| format!("Failed to read controller_placement.json: {e}"))?;
        let placement: serde_json::Value =
            serde_json::from_str(&placement_raw).map_err(|e| format!("Invalid controller_placement.json: {e}"))?;
        let host = placement
            .get("host")
            .and_then(|v| v.as_str())
            .unwrap_or("127.0.0.1")
            .to_string();
        let port = placement.get("port").and_then(|v| v.as_u64()).unwrap_or(8080) as u16;
        let identity_fingerprint = placement
            .get("identity_fingerprint")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        // Preserve any existing config as a timestamped backup.
        if config_path.exists() {
            let ts = chrono::Utc::now().format("%Y%m%dT%H%M%SZ").to_string();
            let backup = self.phantom_root.join(format!("phantom_config.json.bak.{ts}"));
            tokio::fs::rename(&config_path, &backup)
                .await
                .map_err(|e| format!("Failed to back up phantom_config.json: {e}"))?;
            log::info!("Backed up phantom_config.json → {}", backup.display());
        }

        let now = chrono::Utc::now().to_rfc3339();
        let config = serde_json::json!({
            "controller": {
                "host":                 host,
                "port":                 port,
                "security":             "disabled",
                "identity_fingerprint": identity_fingerprint
            },
            "ports": {
                "controller_api": { "port": 8080, "protocol": "tcp", "required": true  },
                "worker_http":    { "port": 8090, "protocol": "tcp", "required": true  },
                "discovery_udp":  { "port": 8095, "protocol": "udp", "required": true  },
                "socket_infra":   { "port": 8081, "protocol": "tcp", "required": false }
            },
            "worker": {
                "readiness_probe_interval_ms":  500,
                "readiness_max_attempts":       20,
                "readiness_attempt_timeout_ms": 1000
            },
            "discovery": {
                "total_timeout_ms":            10000,
                "early_exit_on_first_worker":  true
            },
            "execution_modes": {
                "default_mode": "manual"
            },
            "config_version":  "1.0",
            "written_at":      now,
            "written_by_step": "4.5"
        });

        let tmp_path = self.phantom_root.join("phantom_config.json.tmp");
        tokio::fs::write(
            &tmp_path,
            serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?,
        )
        .await
        .map_err(|e| format!("Failed to write phantom_config.json.tmp: {e}"))?;

        tokio::fs::rename(&tmp_path, &config_path)
            .await
            .map_err(|e| format!("Failed to rename phantom_config.json.tmp: {e}"))?;

        log::info!("phantom_config.json written at step 4.5 ({})", config_path.display());
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

        // Read controller parameters from phantom_config.json (written at Step 4.5).
        // No fallback: if the file is absent, Step 4.5 did not complete and this
        // step must fail with a clear error rather than silently using defaults.
        let config_path = self.phantom_root.join("phantom_config.json");
        if !config_path.exists() {
            return Err(format!(
                "phantom_config.json not found at {:?}. \
                 Step 4.5 (Bootstrap config) must complete successfully before \
                 the controller can start.",
                config_path
            ));
        }

        let host = read_nested_config(&config_path, &["controller", "host"])
            .unwrap_or_else(|| "127.0.0.1".to_string());
        let port = read_nested_config(&config_path, &["controller", "port"])
            .unwrap_or_else(|| "8080".to_string());
        let security_level = read_nested_config(&config_path, &["controller", "security"])
            .unwrap_or_else(|| "disabled".to_string());

        if !run_py.exists() {
            return Err(format!("run.py not found at {:?}", run_py));
        }

        let state_dir = self.phantom_root.join("state");
        tokio::fs::create_dir_all(&state_dir)
            .await
            .map_err(|e| format!("mkdir state: {e}"))?;

        let mut cmd = Command::new(python.to_string_lossy().as_ref());
        cmd.args([
            run_py.to_string_lossy().as_ref(),
            "--host", &host,
            "--port", &port,
            "--security", &security_level,
        ])
        .env("PHANTOM_STATE_DIR", state_dir.to_string_lossy().as_ref());
        #[cfg(windows)]
        cmd.as_std_mut().creation_flags(0x0800_0000); // CREATE_NO_WINDOW
        cmd.spawn()
            .map_err(|e| format!("Failed to start controller: {e}"))?;

        tokio::time::sleep(std::time::Duration::from_secs(3)).await;
        Ok(())
    }

    async fn open_ports(&self) -> Result<(), String> {
        #[cfg(target_os = "linux")]
        {
            // Ports: 8080/tcp (controller), 8090/tcp (worker), 8095/udp (discovery)
            let port_rules: &[(&str, &str)] = &[
                ("8080", "tcp"),
                ("8090", "tcp"),
                ("8095", "udp"),
            ];

            // Try ufw first (Ubuntu/Debian)
            let ufw_available = {
                let ufw = Command::new("ufw")
                    .args(["allow", "8080/tcp"])
                    .output()
                    .await;
                matches!(ufw, Ok(ref o) if o.status.success())
            };

            if ufw_available {
                // ufw worked for 8080/tcp; open the remaining ports
                for &(port, proto) in &port_rules[1..] {
                    let rule = format!("{port}/{proto}");
                    let _ = Command::new("ufw")
                        .args(["allow", &rule])
                        .output()
                        .await;
                }
                log::info!("ufw: allowed ports 8080/tcp, 8090/tcp, 8095/udp");
                return Ok(());
            }

            log::info!("ufw not available, trying iptables");

            // Fall back to iptables
            for &(port, proto) in port_rules {
                let ipt = Command::new("iptables")
                    .args(["-C", "INPUT", "-p", proto, "--dport", port, "-j", "ACCEPT"])
                    .output()
                    .await;

                let already_open = matches!(ipt, Ok(ref o) if o.status.success());

                if !already_open {
                    let add = Command::new("iptables")
                        .args(["-A", "INPUT", "-p", proto, "--dport", port, "-j", "ACCEPT"])
                        .output()
                        .await;

                    match add {
                        Ok(out) if out.status.success() => {
                            log::info!("iptables: opened port {port}/{proto}");
                        }
                        Ok(out) => {
                            log::warn!(
                                "iptables failed for {port}/{proto}: {}",
                                String::from_utf8_lossy(&out.stderr)
                            );
                        }
                        Err(e) => {
                            log::warn!("iptables not available: {e}");
                        }
                    }
                } else {
                    log::info!("Port {port}/{proto} already open in iptables");
                }
            }
        }

        #[cfg(target_os = "windows")]
        {
            // Ports: 8080/tcp (controller), 8090/tcp (worker), 8095/udp (discovery)
            let rules: &[(&str, &str, &str)] = &[
                ("PhantomController", "TCP", "8080"),
                ("PhantomWorker", "TCP", "8090"),
                ("PhantomDiscovery", "UDP", "8095"),
            ];

            for &(name, proto, port) in rules {
                let result = Command::new("netsh")
                    .args([
                        "advfirewall", "firewall", "add", "rule",
                        &format!("name={name}"),
                        "dir=in",
                        "action=allow",
                        &format!("protocol={proto}"),
                        &format!("localport={port}"),
                    ])
                    .output()
                    .await;

                match result {
                    Ok(out) if out.status.success() => {
                        log::info!("Windows firewall: allowed port {port}/{proto} ({name})");
                    }
                    Ok(out) => {
                        log::warn!(
                            "netsh firewall rule failed for {name}: {}",
                            String::from_utf8_lossy(&out.stderr)
                        );
                    }
                    Err(e) => {
                        log::warn!("netsh not available: {e}");
                    }
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

    #[cfg(target_os = "linux")]
    async fn start_local_worker(&self) -> Result<(), String> {
        let engine = self.phantom_root.join("engine");
        let linux_worker_dir = engine.join("linux-worker");
        let main_py = linux_worker_dir.join("linux_worker").join("main.py");
        if !main_py.exists() {
            log::info!("Local worker main.py not found, skipping");
            return Ok(());
        }

        let config_path = self.phantom_root.join("local_worker_config.json");
        let config = serde_json::json!({
            "worker_id": "local-worker",
            "controller_host": "127.0.0.1",
            "controller_port": 8080,
            "worker_port": 8090,
        });
        tokio::fs::write(
            &config_path,
            serde_json::to_string_pretty(&config).unwrap_or_else(|_| "{}".to_string()),
        )
        .await
        .map_err(|e| format!("Failed to write local worker config: {e}"))?;

        let python = venv_python(&self.phantom_root);
        let mut cmd = Command::new(python.to_string_lossy().as_ref());
        cmd.args(["-m", "linux_worker.main", "--config"])
            .arg(config_path.to_string_lossy().as_ref())
            .current_dir(&linux_worker_dir)
            .env("PYTHONPATH", linux_worker_dir.to_string_lossy().as_ref());
        #[cfg(windows)]
        cmd.as_std_mut().creation_flags(0x0800_0000); // CREATE_NO_WINDOW

        match cmd.spawn() {
            Ok(_) => log::info!("Local worker started on 0.0.0.0:8090"),
            Err(e) => log::warn!("Failed to start local worker: {e}"),
        }

        self.run_readiness_probe().await;
        Ok(())
    }

    #[cfg(target_os = "windows")]
    async fn start_local_worker(&self) -> Result<(), String> {
        let engine = self.phantom_root.join("engine");
        let linux_worker_dir = engine.join("linux-worker");
        let main_py = linux_worker_dir.join("linux_worker").join("main.py");
        if !main_py.exists() {
            log::info!("Local worker main.py not found, skipping");
            return Ok(());
        }

        let config_path = self.phantom_root.join("local_worker_config.json");
        let config = serde_json::json!({
            "worker_id": "local-worker",
            "controller_host": "127.0.0.1",
            "controller_port": 8080,
            "worker_port": 8090,
        });
        tokio::fs::write(
            &config_path,
            serde_json::to_string_pretty(&config).unwrap_or_else(|_| "{}".to_string()),
        )
        .await
        .map_err(|e| format!("Failed to write local worker config: {e}"))?;

        let python = venv_python(&self.phantom_root);
        let mut cmd = Command::new(python.to_string_lossy().as_ref());
        cmd.args(["-m", "linux_worker.main", "--config"])
            .arg(config_path.to_string_lossy().as_ref())
            .current_dir(&linux_worker_dir)
            .env("PYTHONPATH", linux_worker_dir.to_string_lossy().as_ref());
        #[cfg(windows)]
        cmd.as_std_mut().creation_flags(0x0800_0000); // CREATE_NO_WINDOW

        match cmd.spawn() {
            Ok(_) => log::info!("Local worker started on 0.0.0.0:8090"),
            Err(e) => log::warn!("Failed to start local worker: {e}"),
        }

        self.run_readiness_probe().await;
        Ok(())
    }

    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    async fn start_local_worker(&self) -> Result<(), String> {
        log::info!("Local worker step skipped on this platform");
        Ok(())
    }

    /// Poll port 8095 with `PHANTOM_DISCOVER_WORKERS` UDP probes until the local
    /// worker responds or the maximum attempts (from `phantom_config.json`) are
    /// exhausted.  Stores the probe outcome in `self.readiness_result` so
    /// `run_pre_scan_deployment()` can include it in the discovery log.
    ///
    /// This is non-blocking to the deploy flow — if the probe times out the
    /// worker may still respond during the broadcast scan.
    async fn run_readiness_probe(&self) {
        let config_path = self.phantom_root.join("phantom_config.json");
        let probe_interval_ms =
            read_nested_config(&config_path, &["worker", "readiness_probe_interval_ms"])
                .and_then(|s| s.parse::<u64>().ok())
                .unwrap_or(500);
        let max_attempts =
            read_nested_config(&config_path, &["worker", "readiness_max_attempts"])
                .and_then(|s| s.parse::<u32>().ok())
                .unwrap_or(20);
        let attempt_timeout_ms =
            read_nested_config(&config_path, &["worker", "readiness_attempt_timeout_ms"])
                .and_then(|s| s.parse::<u64>().ok())
                .unwrap_or(1000);

        self.emit_scan_log(&format!(
            "Waiting for local worker (up to {} probe attempt(s))…",
            max_attempts
        ));

        let mut probe_success = false;
        let mut attempts = 0u32;

        for i in 0..max_attempts {
            attempts = i + 1;
            self.emit_scan_log(&format!(
                "Readiness probe {}/{}…",
                attempts, max_attempts
            ));

            let ready = tokio::task::spawn_blocking(move || {
                discovery::probe_worker_readiness(attempt_timeout_ms)
            })
            .await
            .unwrap_or(false);

            if ready {
                probe_success = true;
                self.emit_scan_log(&format!(
                    "Local worker ready after {} attempt(s)",
                    attempts
                ));
                log::info!(
                    "Local worker readiness probe succeeded on attempt {}",
                    attempts
                );
                break;
            }

            if i + 1 < max_attempts {
                tokio::time::sleep(std::time::Duration::from_millis(probe_interval_ms)).await;
            }
        }

        if !probe_success {
            log::warn!(
                "Local worker readiness probe timed out after {} attempt(s); proceeding",
                attempts
            );
            self.emit_scan_log(&format!(
                "Readiness probe timed out after {} attempt(s); proceeding to discovery",
                attempts
            ));
        }

        if let Ok(mut r) = self.readiness_result.lock() {
            *r = (attempts, probe_success);
        }
    }

    async fn scan_lan(&self) -> Result<(), String> {
        let base_ips = local_ip_bases();
        let broadcast_addrs: Vec<String> = base_ips
            .iter()
            .filter_map(|b| base_to_broadcast(b))
            .collect();

        self.emit_scan_log(&format!("Subnets to broadcast: {:?}", broadcast_addrs));
        self.emit_scan_log("Broadcasting DISCOVER_WORKERS on 127.0.0.1…");
        for addr in &broadcast_addrs {
            self.emit_scan_log(&format!("Broadcasting DISCOVER_WORKERS on {addr}/24…"));
        }
        self.emit_scan_log("Waiting for worker manifests…");

        let (total_timeout_ms, early_exit) = self.read_discovery_config();
        let addrs = broadcast_addrs.clone();
        let manifests = tokio::task::spawn_blocking(move || {
            discovery::discover_single_window(&addrs, total_timeout_ms, early_exit, None)
        })
        .await
        .map_err(|e| format!("Discovery task panicked: {e}"))?;

        self.emit_scan_log(&format!("Received {} manifest(s)", manifests.len()));

        let controller = PhantomApiClient::new("http://127.0.0.1:8080");
        let mut registered = 0usize;

        for m in &manifests {
            let host = m.registration_host();
            self.emit_scan_log(&format!("Received worker manifest from {}:{} (sig={})", host, m.port, m.signature_verified));
            self.emit_scan_log("Validating manifest…");
            let req = RegisterWorkerRequest {
                worker_id: m.manifest.worker_id.clone(),
                host,
                port: m.port,
                gpu_info: m.manifest.capabilities.clone(),
                status: "active".to_string(),
            };
            match controller.register_worker(&req).await {
                Ok(()) => {
                    registered += 1;
                    self.emit_scan_log(&format!("Registering worker {}…", req.worker_id));
                }
                Err(e) => {
                    self.emit_scan_log(&format!("Registration failed: {e}"));
                    log::warn!("Failed to register worker {}: {e}", req.worker_id);
                }
            }
        }

        if !manifests.is_empty() {
            let scan_path = self.phantom_root.join("lan_scan.json");
            let json_manifests: Vec<_> = manifests
                .iter()
                .map(|m| serde_json::json!({"ip": m.registration_host(), "port": m.port, "worker_id": m.worker_id()}))
                .collect();
            let json = serde_json::to_string_pretty(&json_manifests).unwrap_or_else(|_| "[]".to_string());
            tokio::fs::write(&scan_path, json)
                .await
                .map_err(|e| format!("Failed to write discovery results: {e}"))?;
        }

        self.emit_scan_log(&format!("Done: {registered} worker(s) registered"));
        if registered == 0 {
            self.emit_scan_log("No workers found. Possible causes:");
            self.emit_scan_log("  • Worker not running or still initializing");
            self.emit_scan_log("  • Port 8095/udp may be blocked by firewall");
            self.emit_scan_log("  • Worker process failed to start (check worker logs)");
        }
        log::info!("Discovery complete: {registered} worker(s) registered");
        Ok(())
    }

    /// Run steps 0–9 plus discovery (no registration). For deployment ceremony.
    /// Returns discovered workers and structured log; discovery_failed when worker_count == 0.
    pub async fn run_pre_scan_deployment(&self) -> Result<DeploymentPreScanResult, String> {
        const TOTAL_STEPS: usize = 12;

        // Full Deployment Initialization Log — collect entries 1–22
        let mut full_deploy_entries: Vec<FullDeployLogEntry> = Vec::new();
        let mut step_idx = 0u32;

        step_idx += 1;
        full_deploy_entries.push(FullDeployLogEntry {
            timestamp: chrono::Utc::now().to_rfc3339(),
            step_index: step_idx,
            step_name: "deploy_clicked".to_string(),
            success: true,
            duration_ms: 0,
            metadata: None,
            error_message: None,
        });

        for i in 0..=9 {
            let label = Self::steps().get(i).copied().unwrap_or("…");
            self.emit_deploy_progress(i, TOTAL_STEPS, label, (i as f64) / (TOTAL_STEPS as f64));

            let step_name = format!("step_{}_{}", i, match i {
                0 => "create_venv",
                1 => "install_python_deps",
                2 => "install_phantom_core",
                3 => "verify_gpu_plugins",
                4 => "install_service",
                5 => "bootstrap_config",
                6 => "start_controller",
                7 => "open_ports",
                8 => "initialize_state",
                9 => "start_local_worker",
                _ => "unknown",
            });
            let step_start = std::time::Instant::now();
            let result = self.run_step(i).await;
            let duration_ms = step_start.elapsed().as_millis() as u64;

            step_idx += 1;
            full_deploy_entries.push(FullDeployLogEntry {
                timestamp: chrono::Utc::now().to_rfc3339(),
                step_index: step_idx,
                step_name,
                success: result.is_ok(),
                duration_ms,
                metadata: Some(serde_json::json!({"step": i})),
                error_message: result.as_ref().err().map(|e| e.clone()),
            });

            result?;
        }

        self.emit_deploy_progress(10, TOTAL_STEPS, "Scanning LAN", 10_f64 / TOTAL_STEPS as f64);

        // Dependency Initialization Log — measure each dependency before discovery
        let mut dependency_init_entries = Vec::new();

        let config_start = std::time::Instant::now();
        let (total_timeout_ms, early_exit) = self.read_discovery_config();
        let config_duration = config_start.elapsed().as_millis() as u64;
        dependency_init_entries.push(DependencyInitEntry {
            timestamp: chrono::Utc::now().to_rfc3339(),
            item: "config_load (phantom_config.json discovery section)".to_string(),
            success: true,
            duration_ms: config_duration,
        });
        step_idx += 1;
        full_deploy_entries.push(FullDeployLogEntry {
            timestamp: chrono::Utc::now().to_rfc3339(),
            step_index: step_idx,
            step_name: "config_load_phantom_config".to_string(),
            success: true,
            duration_ms: config_duration,
            metadata: Some(serde_json::json!({"total_timeout_ms": total_timeout_ms, "early_exit": early_exit})),
            error_message: None,
        });

        let net_start = std::time::Instant::now();
        let base_ips = local_ip_bases();
        let broadcast_addrs: Vec<String> = base_ips
            .iter()
            .filter_map(|b| base_to_broadcast(b))
            .collect();
        let net_duration = net_start.elapsed().as_millis() as u64;
        dependency_init_entries.push(DependencyInitEntry {
            timestamp: chrono::Utc::now().to_rfc3339(),
            item: "network_interface_enumeration".to_string(),
            success: !broadcast_addrs.is_empty(),
            duration_ms: net_duration,
        });
        step_idx += 1;
        full_deploy_entries.push(FullDeployLogEntry {
            timestamp: chrono::Utc::now().to_rfc3339(),
            step_index: step_idx,
            step_name: "network_interface_enumeration".to_string(),
            success: !broadcast_addrs.is_empty(),
            duration_ms: net_duration,
            metadata: Some(serde_json::json!({"bases": base_ips, "broadcast_count": broadcast_addrs.len()})),
            error_message: None,
        });

        step_idx += 1;
        full_deploy_entries.push(FullDeployLogEntry {
            timestamp: chrono::Utc::now().to_rfc3339(),
            step_index: step_idx,
            step_name: "broadcast_address_calculation".to_string(),
            success: !broadcast_addrs.is_empty(),
            duration_ms: 0,
            metadata: Some(serde_json::json!({"broadcast_addrs": &broadcast_addrs})),
            error_message: None,
        });

        let (probe_attempts, probe_success) = self
            .readiness_result
            .lock()
            .map(|r| *r)
            .unwrap_or((0, false));
        let probe_interval = read_nested_config(&self.phantom_root.join("phantom_config.json"), &["worker", "readiness_probe_interval_ms"])
            .and_then(|s| s.parse::<u64>().ok())
            .unwrap_or(500);
        let probe_timeout = read_nested_config(&self.phantom_root.join("phantom_config.json"), &["worker", "readiness_attempt_timeout_ms"])
            .and_then(|s| s.parse::<u64>().ok())
            .unwrap_or(1000);
        let probe_duration_ms = if probe_attempts > 0 {
            (probe_attempts - 1) * probe_interval + probe_timeout
        } else {
            0
        };
        dependency_init_entries.push(DependencyInitEntry {
            timestamp: chrono::Utc::now().to_rfc3339(),
            item: "worker_readiness_probe".to_string(),
            success: probe_success,
            duration_ms: probe_duration_ms,
        });
        step_idx += 1;
        full_deploy_entries.push(FullDeployLogEntry {
            timestamp: chrono::Utc::now().to_rfc3339(),
            step_index: step_idx,
            step_name: "readiness_probe_result".to_string(),
            success: probe_success,
            duration_ms: probe_duration_ms,
            metadata: Some(serde_json::json!({"attempts": probe_attempts})),
            error_message: if probe_success { None } else { Some("readiness probe timed out".to_string()) },
        });

        self.emit_scan_log(&format!("Subnets to broadcast: {:?}", broadcast_addrs));
        self.emit_scan_log("Broadcasting DISCOVER_WORKERS on 127.0.0.1…");
        for addr in &broadcast_addrs {
            self.emit_scan_log(&format!("Broadcasting DISCOVER_WORKERS on {addr}/24…"));
        }
        self.emit_scan_log("Waiting for worker manifests…");

        self.emit_scan_log(&format!(
            "Discovery window: {} ms (early_exit={})",
            total_timeout_ms, early_exit
        ));

        let addrs = broadcast_addrs.clone();
        let (manifests, mut discovery_log) = tokio::task::spawn_blocking(move || {
            discover_workers_with_log(
                &addrs,
                total_timeout_ms,
                early_exit,
                dependency_init_entries,
                full_deploy_entries,
            )
        })
        .await
        .map_err(|e| format!("Discovery task panicked: {e}"))?;

        // Enrich the discovery log with readiness probe results (set by step 9).
        discovery_log.set_readiness_result(probe_attempts, probe_success);

        self.emit_scan_log(&format!("Received {} manifest(s)", manifests.len()));

        let discovered_workers: Vec<DiscoveredWorkerForCeremony> = manifests
            .iter()
            .map(|m| DiscoveredWorkerForCeremony {
                worker_id: m.manifest.worker_id.clone(),
                host: m.registration_host(),
                port: m.port,
                gpu_info: m.manifest.capabilities.clone(),
                source_ip: m.source_ip.clone(),
                signature_verified: m.signature_verified,
                fingerprint: m.fingerprint.clone(),
                public_key_b64: m.manifest.public_key_b64.clone(),
            })
            .collect();

        let discovery_failed = discovery_log.worker_count == 0;

        // Add actionable hints when no workers were found.
        if discovery_failed {
            if probe_attempts > 0 && !probe_success {
                discovery_log.add_diagnostic_hint(&format!(
                    "Worker not ready: readiness probe timed out after {} attempt(s)",
                    probe_attempts
                ));
            }
            discovery_log.add_diagnostic_hint("Port 8095/udp may be blocked by firewall");
            discovery_log.add_diagnostic_hint(
                "Worker process may have failed to start (check worker logs)",
            );
            discovery_log.add_diagnostic_hint(
                "Worker still initializing — try running discovery again",
            );
        }

        Ok(DeploymentPreScanResult {
            discovered_workers,
            discovery_log,
            discovery_failed,
        })
    }

    /// Register selected workers and run step 11 (load execution modes).
    /// Persists controller and LLM config from ceremony choices.
    pub async fn complete_deployment_with_selection(
        &self,
        worker_pool: Vec<WorkerSelectionForRegistration>,
        run_controller_llm: bool,
    ) -> Result<(), String> {
        let controller = PhantomApiClient::new("http://127.0.0.1:8080");

        for w in &worker_pool {
            // §5 — Record TrustRecord(approved) before registration.
            if let Err(e) = controller
                .approve_worker(&w.worker_id, &w.public_key_b64)
                .await
            {
                log::warn!("Failed to approve worker {}: {e}", w.worker_id);
                continue;
            }
            let req = RegisterWorkerRequest {
                worker_id: w.worker_id.clone(),
                host: w.host.clone(),
                port: w.port,
                gpu_info: w.gpu_info.clone(),
                status: "active".to_string(),
            };
            if let Err(e) = controller.register_worker(&req).await {
                log::warn!("Failed to register worker {}: {e}", w.worker_id);
            }
        }

        // Ensure llm_config exists (load_execution_modes creates it), then persist run_controller_llm
        self.load_execution_modes().await?;

        let llm_config_path = self.phantom_root.join("llm_config.json");
        if llm_config_path.exists() {
            let content = tokio::fs::read_to_string(&llm_config_path)
                .await
                .map_err(|e| format!("Failed to read llm_config.json: {e}"))?;
            if let Ok(mut cfg) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(obj) = cfg.as_object_mut() {
                    obj.insert(
                        "run_controller_llm".to_string(),
                        serde_json::Value::Bool(run_controller_llm),
                    );
                }
                let tmp = self.phantom_root.join("llm_config.json.tmp");
                tokio::fs::write(
                    &tmp,
                    serde_json::to_string_pretty(&cfg).map_err(|e| e.to_string())?,
                )
                .await
                .map_err(|e| format!("Failed to write llm_config.json.tmp: {e}"))?;
                tokio::fs::rename(&tmp, &llm_config_path)
                    .await
                    .map_err(|e| format!("Failed to update llm_config.json: {e}"))?;
            }
        }

        Ok(())
    }
}

/// Emit a scan log line if the app handle is provided.
fn emit_scan_log_opt(app: &Option<tauri::AppHandle>, line: &str) {
    if let Some(ref a) = app {
        let _ = a.emit("scan-log", line);
    }
}

/// Run broadcast discovery and register workers. Used by deployment step 9 and manual "Scan LAN".
pub async fn scan_and_register_workers(
    phantom_root: &std::path::Path,
    controller_url: &str,
    scan_log_emitter: Option<tauri::AppHandle>,
) -> Result<ScanResult, String> {
    let base_ips = local_ip_bases();
    let broadcast_addrs: Vec<String> = base_ips
        .iter()
        .filter_map(|b| base_to_broadcast(b))
        .collect();

    emit_scan_log_opt(&scan_log_emitter, &format!("Subnets: {:?}", broadcast_addrs));
    emit_scan_log_opt(&scan_log_emitter, "Broadcasting DISCOVER_WORKERS…");
    emit_scan_log_opt(&scan_log_emitter, "Waiting for worker manifests…");

    let config_path = phantom_root.join("phantom_config.json");
    let total_timeout_ms = read_nested_config(&config_path, &["discovery", "total_timeout_ms"])
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(DEFAULT_DISCOVERY_TOTAL_TIMEOUT_MS);
    let early_exit = read_nested_config(&config_path, &["discovery", "early_exit_on_first_worker"])
        .and_then(|s| s.parse::<bool>().ok())
        .unwrap_or(true);

    let addrs = broadcast_addrs.clone();
    let manifests = tokio::task::spawn_blocking(move || {
        discovery::discover_single_window(&addrs, total_timeout_ms, early_exit, None)
    })
    .await
    .map_err(|e| format!("Discovery task panicked: {e}"))?;

    emit_scan_log_opt(&scan_log_emitter, &format!("Received {} manifest(s)", manifests.len()));

    let controller = PhantomApiClient::new(controller_url);
    let mut registered = 0usize;
    for m in &manifests {
        let host = m.registration_host();
        emit_scan_log_opt(&scan_log_emitter, &format!("Received worker manifest from {}:{} (sig={})", host, m.port, m.signature_verified));
        emit_scan_log_opt(&scan_log_emitter, "Validating manifest…");
        let req = RegisterWorkerRequest {
            worker_id: m.manifest.worker_id.clone(),
            host,
            port: m.port,
            gpu_info: m.manifest.capabilities.clone(),
            status: "active".to_string(),
        };
        match controller.register_worker(&req).await {
            Ok(()) => {
                registered += 1;
                emit_scan_log_opt(&scan_log_emitter, &format!("Registering worker {}…", req.worker_id));
            }
            Err(e) => {
                emit_scan_log_opt(&scan_log_emitter, &format!("Registration failed: {e}"));
                log::warn!("Failed to register {}: {e}", m.worker_id());
            }
        }
    }
    emit_scan_log_opt(&scan_log_emitter, &format!("Done: {registered} worker(s) registered"));

    if !manifests.is_empty() {
        let scan_path = phantom_root.join("lan_scan.json");
        let json_manifests: Vec<_> = manifests
            .iter()
            .map(|m| serde_json::json!({"ip": m.registration_host(), "port": m.port, "worker_id": m.worker_id()}))
            .collect();
        let json = serde_json::to_string_pretty(&json_manifests).unwrap_or_else(|_| "[]".to_string());
        let _ = tokio::fs::write(&scan_path, json).await;
    }

    Ok(ScanResult {
        scanned: manifests.len(),
        registered,
        nodes: manifests
            .into_iter()
            .map(|m| (m.registration_host(), m.port))
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

        // LLM config (separate from phantom_config.json — governs LLM routing only).
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

        // phantom_config.json was written at Step 4.5 (bootstrap_config).
        // This step is idempotent: only add execution_modes.default_mode if
        // absent from the Step 4.5 write.  Never overwrite the full file here.
        let controller_config_path = self.phantom_root.join("phantom_config.json");
        if controller_config_path.exists() {
            let content = tokio::fs::read_to_string(&controller_config_path)
                .await
                .map_err(|e| format!("Failed to read phantom_config.json: {e}"))?;
            if let Ok(mut cfg) = serde_json::from_str::<serde_json::Value>(&content) {
                let needs_update = cfg
                    .get("execution_modes")
                    .and_then(|em| em.get("default_mode"))
                    .is_none();
                if needs_update {
                    if let Some(obj) = cfg.as_object_mut() {
                        obj.entry("execution_modes")
                            .or_insert(serde_json::json!({}))
                            .as_object_mut()
                            .map(|em| em.insert(
                                "default_mode".to_string(),
                                serde_json::json!("manual"),
                            ));
                    }
                    let tmp = self.phantom_root.join("phantom_config.json.tmp");
                    tokio::fs::write(
                        &tmp,
                        serde_json::to_string_pretty(&cfg).map_err(|e| e.to_string())?,
                    )
                    .await
                    .map_err(|e| format!("Failed to write phantom_config.json.tmp: {e}"))?;
                    tokio::fs::rename(&tmp, &controller_config_path)
                        .await
                        .map_err(|e| format!("Failed to update phantom_config.json: {e}"))?;
                    log::info!("phantom_config.json: execution_modes.default_mode added (idempotent step 10)");
                }
            }
        } else {
            log::warn!(
                "phantom_config.json not found at step 10 — Step 4.5 (bootstrap_config) \
                 may not have run. Execution modes will not be persisted."
            );
        }

        Ok(())
    }
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

/// Read a string field from a flat `phantom_config.json` (legacy flat schema).
/// Returns `None` if the file doesn't exist or the field is missing.
#[allow(dead_code)]
fn read_controller_config(phantom_root: &PathBuf, key: &str) -> Option<String> {
    let path = phantom_root.join("phantom_config.json");
    let content = std::fs::read_to_string(&path).ok()?;
    let json: serde_json::Value = serde_json::from_str(&content).ok()?;
    json.get(key)?.as_str().map(|s| s.to_string())
}

/// Read a string (or number coerced to string) from a **nested** path inside
/// `phantom_config.json`.  `keys` is a path of 1–N string segments, e.g.
/// `&["controller", "security"]`.  Returns `None` if the file, the path, or
/// the value is absent.
fn read_nested_config(path: &std::path::Path, keys: &[&str]) -> Option<String> {
    let content = std::fs::read_to_string(path).ok()?;
    let mut node: serde_json::Value = serde_json::from_str(&content).ok()?;
    for key in keys {
        node = node.get(key)?.clone();
    }
    match &node {
        serde_json::Value::String(s) => Some(s.clone()),
        serde_json::Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}

/// Derive /24 base (e.g. "192.168.1.1") from an IPv4 address string.
fn ip_to_base(ip: &str) -> Option<String> {
    let parts: Vec<&str> = ip.rsplitn(2, '.').collect();
    if parts.len() == 2 {
        Some(format!("{}.1", parts[1]))
    } else {
        None
    }
}

/// Check if an IPv4 address is in a private range (RFC 1918 + common LAN ranges).
fn is_private_ipv4(ip: &str) -> bool {
    if let Ok(addr) = ip.parse::<std::net::Ipv4Addr>() {
        let octets = addr.octets();
        // 10.0.0.0/8
        if octets[0] == 10 {
            return true;
        }
        // 172.16.0.0/12
        if octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31 {
            return true;
        }
        // 192.168.0.0/16
        if octets[0] == 192 && octets[1] == 168 {
            return true;
        }
    }
    false
}

/// Return candidate /24 base IPs for LAN scanning. Uses local-ip-address to
/// enumerate all network interfaces; also includes UDP probe and comprehensive
/// fallbacks so it works regardless of LAN setup (10.x, 172.16–31.x, 192.168.x,
/// VPN, multi-NIC, offline).
fn local_ip_bases() -> Vec<String> {
    use std::collections::HashSet;
    let mut bases = HashSet::new();

    // 1. Enumerate all network interfaces (handles multi-NIC, VPN, etc.)
    if let Ok(ifaces) = local_ip_address::list_afinet_netifas() {
        for (_name, ip) in ifaces {
            let ip_str = ip.to_string();
            if is_private_ipv4(&ip_str) {
                if let Some(base) = ip_to_base(&ip_str) {
                    bases.insert(base);
                }
            }
        }
    }

    // 2. UDP probe trick for primary outbound interface (when interfaces don't yield private IPs)
    if bases.is_empty() {
        if let Ok(sock) = std::net::UdpSocket::bind("0.0.0.0:0") {
            let _ = sock.connect("8.8.8.8:80");
            if let Ok(addr) = sock.local_addr() {
                let ip = addr.ip().to_string();
                if is_private_ipv4(&ip) {
                    if let Some(base) = ip_to_base(&ip) {
                        bases.insert(base);
                    }
                }
            }
        }
    }

    // 3. Fallbacks only when interface enumeration and UDP gave no private bases
    if bases.is_empty() {
        log::info!("No subnet from interfaces; using fallback subnets for common home/office LANs");
        for fb in ["192.168.1.1", "192.168.0.1", "10.0.0.1", "172.16.0.1"] {
            bases.insert(fb.to_string());
        }
    }

    let mut result: Vec<String> = bases.into_iter().collect();
    result.sort();
    result
}
