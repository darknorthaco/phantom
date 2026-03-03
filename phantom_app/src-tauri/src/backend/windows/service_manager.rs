use tokio::process::Command;

pub async fn start_service(service_name: &str) -> Result<(), String> {
    run_sc(&["start", service_name]).await
}

pub async fn stop_service(service_name: &str) -> Result<(), String> {
    run_sc(&["stop", service_name]).await
}

pub async fn query_service(service_name: &str) -> Result<String, String> {
    let output = Command::new("sc")
        .args(["query", service_name])
        .output()
        .await
        .map_err(|e| format!("sc query failed: {e}"))?;

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

async fn run_sc(args: &[&str]) -> Result<(), String> {
    let output = Command::new("sc")
        .args(args)
        .output()
        .await
        .map_err(|e| format!("sc failed: {e}"))?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    Ok(())
}
