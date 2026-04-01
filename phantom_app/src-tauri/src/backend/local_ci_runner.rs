//! Local CI runner — same checks as GitHub Actions ``test-controller`` / smoke jobs.
//! Invokes ``local_ci_check.py`` with **only** the Phantom venv interpreter (absolute path).

use std::path::{Path, PathBuf};
use std::process::Stdio;

use serde::Serialize;
use tauri::{Emitter, Manager};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LocalCiInvokeResult {
    pub ok: bool,
    pub exit_code: Option<i32>,
    pub message: String,
}

#[derive(Debug, Clone, Default, serde::Deserialize, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LocalCiOptions {
    #[serde(default)]
    pub ensure_dev_tools: bool,
    #[serde(default)]
    pub port_check: bool,
}

pub fn venv_python_for_phantom(phantom_root: &Path) -> PathBuf {
    #[cfg(target_os = "windows")]
    return phantom_root.join("venv").join("Scripts").join("python.exe");
    #[cfg(not(target_os = "windows"))]
    return phantom_root.join("venv").join("bin").join("python3");
}

/// Resolve ``local_ci_check.py``: bundled ``resource_dir/local_ci/``, repo ``scripts/``, or ``PHANTOM_REPO_ROOT``.
pub fn resolve_local_ci_script(app: &tauri::AppHandle, engine_source: &Path) -> Option<PathBuf> {
    if let Ok(res) = app.path().resource_dir() {
        let p = res.join("local_ci").join("local_ci_check.py");
        if p.is_file() {
            return Some(p);
        }
    }
    if let Some(parent) = engine_source.parent() {
        let p = parent.join("scripts").join("local_ci_check.py");
        if p.is_file() {
            return Some(p);
        }
    }
    if let Ok(root) = std::env::var("PHANTOM_REPO_ROOT") {
        let p = PathBuf::from(root).join("scripts").join("local_ci_check.py");
        if p.is_file() {
            return Some(p);
        }
    }
    None
}

pub async fn run_local_ci_check(
    app: tauri::AppHandle,
    phantom_root: PathBuf,
    phantom_core_home: PathBuf,
    options: LocalCiOptions,
) -> Result<LocalCiInvokeResult, String> {
    let py = venv_python_for_phantom(&phantom_root);
    if !py.is_file() {
        return Err(format!(
            "Phantom venv Python not found at {}. Create the deployment venv first (Deploy Phantom).",
            py.display()
        ));
    }

    let script = resolve_local_ci_script(&app, &phantom_core_home).ok_or_else(|| {
        "local_ci_check.py not found. For dev: ensure repo scripts/ exists next to phantom_core. For builds: run prepare-resources (bundles resources/local_ci).".to_string()
    })?;

    let mut cmd = Command::new(&py);
    cmd.arg("-u")
        .arg(&script)
        .arg("--phantom-core-home")
        .arg(&phantom_core_home)
        .arg("--phantom-root")
        .arg(&phantom_root)
        .arg("--json-progress");
    if options.ensure_dev_tools {
        cmd.arg("--ensure-dev-tools");
    }
    if options.port_check {
        cmd.arg("--port-check");
    }
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());
    cmd.stdin(Stdio::null());

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to spawn local CI ({py:?}): {e}"))?;

    let stdout = child.stdout.take().ok_or_else(|| "local CI: no stdout pipe".to_string())?;
    let stderr = child.stderr.take().ok_or_else(|| "local CI: no stderr pipe".to_string())?;

    let app_out = app.clone();
    let out_task = tokio::spawn(async move {
        let mut reader = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            if line.is_empty() {
                continue;
            }
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&line) {
                let _ = app_out.emit("local-ci-progress", &v);
            }
        }
    });

    let app_err = app.clone();
    let err_task = tokio::spawn(async move {
        let mut reader = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            let v = serde_json::json!({ "kind": "stderr", "detail": line });
            let _ = app_err.emit("local-ci-progress", &v);
        }
    });

    let status = child
        .wait()
        .await
        .map_err(|e| format!("local CI process error: {e}"))?;

    let _ = out_task.await;
    let _ = err_task.await;

    let code = status.code();
    let ok = code == Some(0);
    Ok(LocalCiInvokeResult {
        ok,
        exit_code: code,
        message: if ok {
            "Local CI completed — same steps as GitHub test-controller / smoke jobs.".to_string()
        } else {
            format!(
                "Local CI reported failure (exit code {:?}). See Deployment Chronicle and log lines above.",
                code
            )
        },
    })
}
