use std::path::Path;
use tokio::process::Command;

pub async fn install_service(
    service_name: &str,
    display_name: &str,
    python_path: &Path,
    run_py: &Path,
    state_dir: &Path,
) -> Result<(), String> {
    let bin_path = format!(
        "{} {} --host 127.0.0.1 --port 8080 --security basic",
        python_path.to_string_lossy(),
        run_py.to_string_lossy()
    );

    let output = Command::new("sc")
        .args([
            "create",
            service_name,
            &format!("binPath={bin_path}"),
            &format!("DisplayName={display_name}"),
            "start=demand",
        ])
        .output()
        .await
        .map_err(|e| format!("sc create failed: {e}"))?;

    if !output.status.success() {
        return Err(format!(
            "sc create failed: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    Ok(())
}

pub async fn uninstall_service(service_name: &str) -> Result<(), String> {
    let output = Command::new("sc")
        .args(["delete", service_name])
        .output()
        .await
        .map_err(|e| format!("sc delete failed: {e}"))?;

    if !output.status.success() {
        return Err(format!(
            "sc delete failed: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    Ok(())
}
