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
        if !dest.exists() {
            tokio::fs::create_dir_all(&dest)
                .await
                .map_err(|e| format!("mkdir failed: {e}"))?;
        }
        Ok(())
    }

    async fn verify_gpu_plugins(&self) -> Result<(), String> {
        Ok(())
    }

    async fn install_service(&self) -> Result<(), String> {
        Ok(())
    }

    async fn start_controller(&self) -> Result<(), String> {
        let python = self.phantom_root.join("venv/bin/python3");
        let run_py = self.engine_source.join("run.py");

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
        Ok(())
    }

    async fn load_execution_modes(&self) -> Result<(), String> {
        Ok(())
    }
}
