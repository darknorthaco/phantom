use std::path::{Path, PathBuf};
use tokio::process::Command;

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

        let output = Command::new("python3")
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
        let pip = self.phantom_root.join("venv/bin/pip");
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
        let python = self.phantom_root.join("venv/bin/python3");
        let run_py = self.engine_source.join("run.py");
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
        let python = self.phantom_root.join("venv/bin/python3");
        // Prefer the deployed copy; fall back to engine_source (dev mode).
        let deployed_run_py = self.phantom_root.join("engine/run.py");
        let run_py = if deployed_run_py.exists() {
            deployed_run_py
        } else {
            self.engine_source.join("run.py")
        };

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
                "--security", "disabled",
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
        // Determine the local IP to use as the scan base
        let base_ip = local_ip_base();
        log::info!("Scanning LAN from base {base_ip} on port 8080…");

        let nodes = tokio::task::spawn_blocking(move || {
            super::lan_scanner::scan_subnet(&base_ip, 8080)
        })
        .await
        .map_err(|e| format!("LAN scan task panicked: {e}"))?;

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

        Ok(())
    }

    async fn load_execution_modes(&self) -> Result<(), String> {
        let config_path = self.phantom_root.join("llm_config.json");
        if config_path.exists() {
            log::info!("llm_config.json already present — skipping default creation");
            return Ok(());
        }

        let default = serde_json::json!({
            "execution_mode": "manual",
            "allow_per_task_override": false,
            "model": "phi-3.5-mini",
            "auto_withdraw_on_human_activity": true,
            "confidence_threshold": 0.85
        });

        let data = serde_json::to_string_pretty(&default)
            .map_err(|e| format!("Failed to serialize default config: {e}"))?;

        tokio::fs::create_dir_all(&self.phantom_root)
            .await
            .map_err(|e| format!("Failed to create phantom root: {e}"))?;

        tokio::fs::write(&config_path, data)
            .await
            .map_err(|e| format!("Failed to write llm_config.json: {e}"))?;

        log::info!("Default llm_config.json written (execution_mode: manual)");
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

fn local_ip_base() -> String {
    use std::net::UdpSocket;
    // Probe trick: connect to a public address to discover the local outbound IP
    if let Ok(sock) = UdpSocket::bind("0.0.0.0:0") {
        let _ = sock.connect("8.8.8.8:80");
        if let Ok(addr) = sock.local_addr() {
            let ip = addr.ip().to_string();
            // Return the /24 base (first three octets + ".1")
            let parts: Vec<&str> = ip.rsplitn(2, '.').collect();
            if parts.len() == 2 {
                return format!("{}.1", parts[1]);
            }
        }
    }
    "192.168.1.1".to_string()
}
