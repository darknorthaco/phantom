use tokio::process::Command;

pub async fn enable_service(unit_name: &str) -> Result<(), String> {
    run_systemctl(&["enable", unit_name]).await
}

pub async fn start_service(unit_name: &str) -> Result<(), String> {
    run_systemctl(&["start", unit_name]).await
}

pub async fn stop_service(unit_name: &str) -> Result<(), String> {
    run_systemctl(&["stop", unit_name]).await
}

pub async fn status(unit_name: &str) -> Result<String, String> {
    let output = Command::new("systemctl")
        .args(["status", unit_name])
        .output()
        .await
        .map_err(|e| format!("systemctl failed: {e}"))?;

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

async fn run_systemctl(args: &[&str]) -> Result<(), String> {
    let output = Command::new("systemctl")
        .args(args)
        .output()
        .await
        .map_err(|e| format!("systemctl failed: {e}"))?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    Ok(())
}
