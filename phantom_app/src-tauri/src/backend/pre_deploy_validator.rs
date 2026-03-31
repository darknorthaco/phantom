//! Deterministic pre-deploy checklist (Phase 4 Task 14).
//! Read-only / local probes only — no hidden network except optional controller /health when config exists.

use serde::Serialize;
use std::path::Path;

use super::phantom_api::PhantomApiClient;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PreDeployCheck {
    pub id: String,
    pub name: String,
    /// ``pass`` | ``fail`` | ``warn`` | ``skip``
    pub status: String,
    pub detail: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PreDeployReport {
    /// True when no check has status ``fail``.
    pub ok: bool,
    pub checks: Vec<PreDeployCheck>,
    pub phantom_root: String,
    pub engine_source: String,
}

fn check(id: &str, name: &str, status: &str, detail: impl Into<String>) -> PreDeployCheck {
    PreDeployCheck {
        id: id.to_string(),
        name: name.to_string(),
        status: status.to_string(),
        detail: detail.into(),
    }
}

#[cfg(target_os = "windows")]
fn host_python_cmd() -> &'static str {
    "python"
}

#[cfg(not(target_os = "windows"))]
fn host_python_cmd() -> &'static str {
    "python3"
}

fn venv_python_path(phantom_root: &Path) -> std::path::PathBuf {
    #[cfg(target_os = "windows")]
    {
        phantom_root.join("venv\\Scripts\\python.exe")
    }
    #[cfg(not(target_os = "windows"))]
    {
        phantom_root.join("venv/bin/python3")
    }
}

fn worker_main_relative() -> &'static str {
    #[cfg(target_os = "windows")]
    {
        "windows-worker/windows_worker/main.py"
    }
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    {
        "linux-worker/linux_worker/main.py"
    }
    #[cfg(not(any(target_os = "linux", target_os = "macos", target_os = "windows")))]
    {
        ""
    }
}

fn parse_config(path: &Path) -> Option<serde_json::Value> {
    let raw = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&raw).ok()
}

fn controller_port_from_json(ctrl: Option<&serde_json::Value>) -> Option<u16> {
    let p = ctrl?.get("port")?;
    match p {
        serde_json::Value::Number(n) => n.as_u64().and_then(|u| u16::try_from(u).ok()),
        serde_json::Value::String(s) => s.parse().ok(),
        _ => None,
    }
}

fn parse_ports_entry_port(ports: Option<&serde_json::Value>, key: &str) -> Option<u16> {
    let entry = ports?.get(key)?;
    let p = entry.get("port")?;
    match p {
        serde_json::Value::Number(n) => n.as_u64().and_then(|u| u16::try_from(u).ok()),
        serde_json::Value::String(s) => s.parse().ok(),
        _ => None,
    }
}

/// Match ``PhantomApiClient::controller_base_url_from_config`` boolean fields (bool or ``"true"`` / ``"1"``).
fn json_bool_from_config(v: Option<&serde_json::Value>, default: bool) -> bool {
    match v {
        None => default,
        Some(x) => x.as_bool().unwrap_or_else(|| {
            x.as_str()
                .is_some_and(|s| s.eq_ignore_ascii_case("true") || s == "1")
        }),
    }
}

/// TLS/WAN rules that must hold before the controller process is spawned.
fn controller_tls_wan_errors(v: &serde_json::Value) -> Vec<String> {
    let mut errs = Vec::new();
    let wan = json_bool_from_config(v.get("wan_mode"), false);
    let tls = json_bool_from_config(v.get("tls_enabled"), false);
    if wan && !tls {
        errs.push("wan_mode is true but tls_enabled is false — WAN requires TLS".to_string());
    }
    if tls {
        let cert = v
            .get("tls_cert_path")
            .and_then(|x| x.as_str())
            .unwrap_or("");
        let key = v
            .get("tls_key_path")
            .and_then(|x| x.as_str())
            .unwrap_or("");
        let cert_ok = !cert.is_empty() && Path::new(cert).is_file();
        let key_ok = !key.is_empty() && Path::new(key).is_file();
        if !cert_ok || !key_ok {
            errs.push(
                "tls_enabled but tls_cert_path or tls_key_path missing or not files".to_string(),
            );
        }
    }
    errs
}

/// Hard gates for deploy step 6 (controller start). Fails before spawn when config,
/// TLS/WAN consistency, venv imports, controller API URL derivation, or entrypoints are not ready.
pub async fn assert_ready_for_controller_start(
    phantom_root: &Path,
    engine_source: &Path,
) -> Result<(), String> {
    let config_path = phantom_root.join("phantom_config.json");
    if !config_path.is_file() {
        return Err(format!(
            "phantom_config.json not found at {} — complete bootstrap (step 5) before starting the controller.",
            config_path.display()
        ));
    }
    let raw = std::fs::read_to_string(&config_path)
        .map_err(|e| format!("Cannot read phantom_config.json: {e}"))?;
    let v: serde_json::Value =
        serde_json::from_str(&raw).map_err(|e| format!("phantom_config.json invalid JSON: {e}"))?;

    let tls_errs = controller_tls_wan_errors(&v);
    if !tls_errs.is_empty() {
        return Err(tls_errs.join("; "));
    }

    let ctrl = v
        .get("controller")
        .ok_or_else(|| "phantom_config.json: missing controller block".to_string())?;

    if let Some(serde_json::Value::String(s)) = ctrl.get("host") {
        if s.is_empty() {
            return Err("phantom_config.json: controller.host is empty".to_string());
        }
    }

    let socket_integrated = json_bool_from_config(ctrl.get("socket_integrated"), true);

    let engine = phantom_root.join("engine");
    let deployed_run_py = engine.join("run.py");
    let deployed_integrated_py = engine.join("run_integrated_phantom.py");
    let run_py = if deployed_run_py.is_file() {
        deployed_run_py
    } else {
        engine_source.join("run.py")
    };
    let run_integrated_py = if deployed_integrated_py.is_file() {
        deployed_integrated_py
    } else {
        engine_source.join("run_integrated_phantom.py")
    };

    if socket_integrated && !run_integrated_py.is_file() {
        return Err(format!(
            "run_integrated_phantom.py not found at {} — socket integration requires this entrypoint.",
            run_integrated_py.display()
        ));
    }
    if !socket_integrated && !run_py.is_file() {
        return Err(format!(
            "run.py not found at {} — non-integrated mode requires this entrypoint.",
            run_py.display()
        ));
    }

    let vpy = venv_python_path(phantom_root);
    if !vpy.is_file() {
        return Err(format!(
            "venv interpreter missing at {} — complete venv/deps steps before starting the controller.",
            vpy.display()
        ));
    }

    let out = tokio::process::Command::new(&vpy)
        .args(["-c", "import fastapi, uvicorn, httpx, pydantic"])
        .output()
        .await
        .map_err(|e| format!("venv import probe failed to run: {e}"))?;
    if !out.status.success() {
        let stderr = String::from_utf8_lossy(&out.stderr);
        return Err(format!(
            "venv is missing controller dependencies (fastapi, uvicorn, httpx, pydantic): {stderr}"
        ));
    }

    let (base_url, tls_enabled) = PhantomApiClient::controller_base_url_from_config(&config_path)?;
    PhantomApiClient::for_local_health_check(&base_url, tls_enabled).map_err(|e| {
        format!("Cannot build health-check client for {base_url}: {e}")
    })?;

    Ok(())
}

/// Run all gates. ``offline_bundle_root`` when set adds bundle layout checks.
pub async fn validate_pre_deploy(
    phantom_root: &Path,
    engine_source: &Path,
    offline_bundle_root: Option<&Path>,
) -> PreDeployReport {
    let mut checks = Vec::new();

    // 1 — Phantom root writable
    match tokio::fs::create_dir_all(phantom_root).await {
        Ok(()) => {}
        Err(e) => {
            checks.push(check(
                "phantom_root_writable",
                "Phantom root directory",
                "fail",
                format!("Cannot create or access {}: {e}", phantom_root.display()),
            ));
            return finalize(phantom_root, engine_source, checks);
        }
    }
    let probe = phantom_root.join(".phantom_pre_deploy_probe");
    match tokio::fs::write(&probe, b"ok").await {
        Ok(()) => {
            let _ = tokio::fs::remove_file(&probe).await;
            checks.push(check(
                "phantom_root_writable",
                "Phantom root directory",
                "pass",
                format!("Writable: {}", phantom_root.display()),
            ));
        }
        Err(e) => {
            checks.push(check(
                "phantom_root_writable",
                "Phantom root directory",
                "fail",
                format!("Cannot write probe file under {}: {e}", phantom_root.display()),
            ));
            return finalize(phantom_root, engine_source, checks);
        }
    }

    // 2 — Host Python (venv creation)
    let py = host_python_cmd();
    let py_ok = tokio::process::Command::new(py)
        .arg("--version")
        .output()
        .await
        .map(|o| o.status.success())
        .unwrap_or(false);
    checks.push(if py_ok {
        check(
            "host_python",
            "Host Python interpreter",
            "pass",
            format!("`{py}` responds to --version"),
        )
    } else {
        check(
            "host_python",
            "Host Python interpreter",
            "fail",
            format!(
                "Cannot run `{py} --version` — install Python 3 before creating the venv"
            ),
        )
    });

    // 3 — Bundled engine entrypoint (distribution / dev tree)
    let run_py = engine_source.join("run.py");
    checks.push(if run_py.is_file() {
        check(
            "engine_entrypoint",
            "Controller entrypoint (bundled engine)",
            "pass",
            format!("run.py present at {}", engine_source.display()),
        )
    } else {
        check(
            "engine_entrypoint",
            "Controller entrypoint (bundled engine)",
            "fail",
            format!(
                "Missing run.py under engine source {} — reinstall app or set dev layout",
                engine_source.display()
            ),
        )
    });

    // 4 — Controller placement (Pre-0 ceremony)
    let placement_path = phantom_root.join("controller_placement.json");
    if !placement_path.is_file() {
        checks.push(check(
            "controller_placement",
            "Controller placement (ceremony)",
            "fail",
            "controller_placement.json missing — complete Controller Selection before deploy",
        ));
    } else if let Ok(raw) = std::fs::read_to_string(&placement_path) {
        if let Ok(v) = serde_json::from_str::<serde_json::Value>(&raw) {
            let host_ok = v
                .get("host")
                .and_then(|x| x.as_str())
                .map(|s| !s.trim().is_empty())
                .unwrap_or(false);
            let port_ok = v
                .get("port")
                .and_then(|x| x.as_u64())
                .map(|p| (1..=65535).contains(&p))
                .unwrap_or(false);
            if host_ok && port_ok {
                checks.push(check(
                    "controller_placement",
                    "Controller placement (ceremony)",
                    "pass",
                    "controller_placement.json contains host and port",
                ));
            } else {
                checks.push(check(
                    "controller_placement",
                    "Controller placement (ceremony)",
                    "fail",
                    "controller_placement.json must include non-empty host and valid port",
                ));
            }
        } else {
            checks.push(check(
                "controller_placement",
                "Controller placement (ceremony)",
                "fail",
                "controller_placement.json is not valid JSON",
            ));
        }
    } else {
        checks.push(check(
            "controller_placement",
            "Controller placement (ceremony)",
            "fail",
            format!("Cannot read {}", placement_path.display()),
        ));
    }

    // 5 — Offline bundle (optional)
    if let Some(bundle) = offline_bundle_root {
        let manifest = bundle.join("manifest.json");
        let wheelhouse = bundle.join("wheelhouse");
        if manifest.is_file() && wheelhouse.is_dir() {
            checks.push(check(
                "offline_bundle_layout",
                "Offline bundle layout",
                "pass",
                format!("manifest.json and wheelhouse/ present under {}", bundle.display()),
            ));
        } else {
            checks.push(check(
                "offline_bundle_layout",
                "Offline bundle layout",
                "fail",
                format!(
                    "Bundle at {} must contain manifest.json and wheelhouse/",
                    bundle.display()
                ),
            ));
        }
    } else {
        checks.push(check(
            "offline_bundle_layout",
            "Offline bundle layout",
            "skip",
            "No offline bundle path in app state (online deploy)",
        ));
    }

    let config_path = phantom_root.join("phantom_config.json");
    let config_val = parse_config(&config_path);

    // 6 — phantom_config.json (after bootstrap)
    if config_val.is_none() {
        checks.push(check(
            "phantom_config",
            "phantom_config.json",
            "skip",
            "Not created yet — produced at deploy step 5 (bootstrap_config)",
        ));
    } else {
        let v = config_val.as_ref().unwrap();
        let ctrl = v.get("controller");
        let has_host = ctrl
            .and_then(|c| c.get("host"))
            .and_then(|x| x.as_str())
            .map(|s| !s.is_empty())
            .unwrap_or(false);
        let has_port = controller_port_from_json(ctrl).is_some();
        if has_host && has_port {
            checks.push(check(
                "phantom_config",
                "phantom_config.json",
                "pass",
                "controller host and port present",
            ));
        } else {
            checks.push(check(
                "phantom_config",
                "phantom_config.json",
                "warn",
                "controller block incomplete — re-run bootstrap or fix JSON",
            ));
        }

        // 7 — Port parity controller vs ports.controller_api
        let ctrl_p = controller_port_from_json(ctrl);
        let ports = v.get("ports");
        let api_p = parse_ports_entry_port(ports, "controller_api");
        match (ctrl_p, api_p) {
            (Some(a), Some(b)) if a == b => {
                checks.push(check(
                    "firewall_port_parity",
                    "Controller port parity (controller vs ports.controller_api)",
                    "pass",
                    format!("Both use TCP {a}"),
                ));
            }
            (Some(a), Some(b)) => {
                checks.push(check(
                    "firewall_port_parity",
                    "Controller port parity (controller vs ports.controller_api)",
                    "warn",
                    format!("Mismatch: controller.port={a} vs ports.controller_api.port={b}"),
                ));
            }
            _ => {
                checks.push(check(
                    "firewall_port_parity",
                    "Controller port parity (controller vs ports.controller_api)",
                    "warn",
                    "Could not compare — missing port fields",
                ));
            }
        }

        // 8 — TLS consistency (aligned with ``PhantomApiClient`` boolean parsing)
        let tls_errs = controller_tls_wan_errors(v);
        if !tls_errs.is_empty() {
            checks.push(check(
                "tls_consistency",
                "TLS / WAN consistency",
                "fail",
                tls_errs.join("; "),
            ));
        } else {
            let tls_on = json_bool_from_config(v.get("tls_enabled"), false);
            if tls_on {
                checks.push(check(
                    "tls_consistency",
                    "TLS / WAN consistency",
                    "pass",
                    "tls_enabled and cert/key paths exist on disk",
                ));
            } else {
                checks.push(check(
                    "tls_consistency",
                    "TLS / WAN consistency",
                    "pass",
                    "TLS off (local HTTP profile)",
                ));
            }
        }
    }

    // 9 — Installed engine under ~/.phantom/engine
    let installed_run = phantom_root.join("engine/run.py");
    checks.push(if installed_run.is_file() {
        check(
            "engine_installed",
            "Installed engine (phantom root)",
            "pass",
            format!("{}", installed_run.display()),
        )
    } else {
        check(
            "engine_installed",
            "Installed engine (phantom root)",
            "skip",
            "engine/run.py not yet copied — normal before first deploy completes",
        )
    });

    // 10 — Venv interpreter
    let vpy = venv_python_path(phantom_root);
    checks.push(if vpy.is_file() {
        check(
            "venv_interpreter",
            "Virtualenv Python",
            "pass",
            vpy.display().to_string(),
        )
    } else {
        check(
            "venv_interpreter",
            "Virtualenv Python",
            "skip",
            "venv not created yet — deploy step 0",
        )
    });

    // 11 — Venv imports (controller deps)
    if vpy.is_file() {
        let out = tokio::process::Command::new(&vpy)
            .args([
                "-c",
                "import fastapi, uvicorn, httpx, pydantic; print('ok')",
            ])
            .output()
            .await;
        match out {
            Ok(o) if o.status.success() => {
                checks.push(check(
                    "venv_imports",
                    "Venv imports (core deps)",
                    "pass",
                    "fastapi, uvicorn, httpx, pydantic import OK",
                ));
            }
            Ok(o) => {
                let err = String::from_utf8_lossy(&o.stderr);
                checks.push(check(
                    "venv_imports",
                    "Venv imports (core deps)",
                    "warn",
                    format!("Import check failed: {err}"),
                ));
            }
            Err(e) => {
                checks.push(check(
                    "venv_imports",
                    "Venv imports (core deps)",
                    "warn",
                    format!("Could not run venv python: {e}"),
                ));
            }
        }
    } else {
        checks.push(check(
            "venv_imports",
            "Venv imports (core deps)",
            "skip",
            "No venv interpreter to test",
        ));
    }

    // 12 — Local worker bundle
    let wr = worker_main_relative();
    if wr.is_empty() {
        checks.push(check(
            "worker_entrypoint",
            "Bundled local worker",
            "skip",
            "No bundled worker path for this OS",
        ));
    } else {
        let in_source = engine_source.join("engine").join(wr);
        let in_source_alt = engine_source.join(wr);
        let in_phantom = phantom_root.join("engine").join(wr);
        let found = in_source.is_file() || in_source_alt.is_file() || in_phantom.is_file();
        checks.push(if found {
            check(
                "worker_entrypoint",
                "Bundled local worker",
                "pass",
                format!("Found {wr} under engine source or installed engine"),
            )
        } else {
            check(
                "worker_entrypoint",
                "Bundled local worker",
                "warn",
                format!("Expected {wr} under {} or {}", engine_source.display(), phantom_root.join("engine").display()),
            )
        });
    }

    // 13 — Controller /health (optional)
    if config_path.is_file() {
        match PhantomApiClient::from_phantom_config(&config_path) {
            Ok(client) => match client.health().await {
                Ok(h) => {
                    checks.push(check(
                        "controller_health",
                        "Controller GET /health",
                        "pass",
                        format!(
                            "status={} workers={}",
                            h.status, h.workers_count
                        ),
                    ));
                }
                Err(e) => {
                    checks.push(check(
                        "controller_health",
                        "Controller GET /health",
                        "warn",
                        format!("Not reachable or error (expected if controller not started): {e}"),
                    ));
                }
            },
            Err(e) => {
                checks.push(check(
                    "controller_health",
                    "Controller GET /health",
                    "warn",
                    format!("Could not build API client from config: {e}"),
                ));
            }
        }
    } else {
        checks.push(check(
            "controller_health",
            "Controller GET /health",
            "skip",
            "No phantom_config.json — cannot derive API URL",
        ));
    }

    finalize(phantom_root, engine_source, checks)
}

fn finalize(
    phantom_root: &Path,
    engine_source: &Path,
    checks: Vec<PreDeployCheck>,
) -> PreDeployReport {
    let ok = !checks.iter().any(|c| c.status == "fail");
    PreDeployReport {
        ok,
        checks,
        phantom_root: phantom_root.display().to_string(),
        engine_source: engine_source.display().to_string(),
    }
}
