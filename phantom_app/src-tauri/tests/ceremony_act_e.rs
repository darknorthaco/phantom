//! Phase 11.5 — Act E (attest) integration tests.

use phantom_app_lib::ceremony::{
    atomic_write, load, CeremonyOrchestrator, CeremonyPhase, CeremonyStateFile,
    ENV_FORCE_DEGRADED, ENV_SKIP_CONTROLLER_HEALTH, OUTCOME_SUCCEEDED_WITH_WARNINGS,
};
use serde_json::json;
use std::path::Path;

fn stub_materialize_layout(root: &Path) {
    std::fs::create_dir_all(root.join("venv")).unwrap();
    std::fs::write(root.join("venv/pyvenv.cfg"), "home = .\n").unwrap();
    std::fs::create_dir_all(root.join("engine")).unwrap();
    std::fs::write(root.join("engine/run.py"), "# stub\n").unwrap();
}

fn write_attestation_manifest(root: &Path, correlation_id: &str) {
    std::fs::create_dir_all(root.join("state")).unwrap();
    let body = json!({
        "schemaVersion": "1",
        "snapshotId": "snap-e",
        "correlationId": correlation_id,
        "snapshotCreatedAt": "2026-01-01T00:00:00Z",
        "primaryWorker": {
            "workerId": "w-e",
            "host": "127.0.0.1",
            "port": 8090,
            "gpuInfo": {},
            "sourceIp": "127.0.0.1",
            "signatureVerified": true,
            "fingerprint": "ab",
            "publicKeyB64": ""
        },
        "preparedAt": "2026-01-01T00:00:01Z"
    });
    std::fs::write(
        root.join("state").join("ceremony_attestation_manifest.json"),
        serde_json::to_string_pretty(&body).unwrap(),
    )
    .unwrap();
}

fn write_phantom_config(root: &Path, host: &str, port: u16) {
    let cfg = json!({
        "controller": {
            "host": host,
            "port": port,
            "security": "disabled",
            "identity_fingerprint": "fp",
            "socket_integrated": true
        },
        "ports": {
            "controller_api": { "port": port, "protocol": "tcp", "required": true },
            "worker_http": { "port": 8090, "protocol": "tcp", "required": true },
            "discovery_udp": { "port": 8095, "protocol": "udp", "required": true },
            "socket_infra": { "port": 8081, "protocol": "tcp", "required": false }
        },
        "worker": {
            "readiness_probe_interval_ms": 500,
            "readiness_max_attempts": 20,
            "readiness_attempt_timeout_ms": 1000
        },
        "discovery": {
            "total_timeout_ms": 10000,
            "early_exit_on_first_worker": true
        },
        "execution_modes": { "default_mode": "manual" },
        "wan_mode": false,
        "tls_enabled": false,
        "tls_cert_path": "",
        "tls_key_path": "",
        "config_version": "1.0",
        "written_at": "2026-01-01T00:00:00Z",
        "written_by_step": "act_d_configure"
    });
    std::fs::write(
        root.join("phantom_config.json"),
        serde_json::to_string_pretty(&cfg).unwrap(),
    )
    .unwrap();
}

fn seed_configure_state(root: &Path, correlation_id: &str, ctrl_host: &str, ctrl_port: u16) {
    stub_materialize_layout(root);
    std::fs::write(
        root.join("controller_placement.json"),
        json!({
            "host": ctrl_host,
            "port": ctrl_port,
            "device_label": "t",
            "identity_fingerprint": "fp"
        })
        .to_string(),
    )
    .unwrap();
    write_phantom_config(root, ctrl_host, ctrl_port);
    write_attestation_manifest(root, correlation_id);

    let mut s = CeremonyStateFile::default();
    s.s_ceremony = CeremonyPhase::Configure.as_str().to_string();
    s.correlation_id = Some(correlation_id.to_string());
    s.snapshot_id = Some("snap-e".into());
    s.last_completed_act = Some("D".into());
    atomic_write(root, &s).unwrap();
}

struct EnvGuard {
    key: &'static str,
    prior: Option<std::ffi::OsString>,
}
impl EnvGuard {
    fn set(key: &'static str, val: &str) -> Self {
        let prior = std::env::var_os(key);
        std::env::set_var(key, val);
        Self { key, prior }
    }
}
impl Drop for EnvGuard {
    fn drop(&mut self) {
        match &self.prior {
            Some(v) => std::env::set_var(self.key, v),
            None => std::env::remove_var(self.key),
        }
    }
}

#[tokio::test]
async fn act_e_rejects_wrong_phase() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let o = CeremonyOrchestrator::new(root);
    let err = o.run_act_e().await.unwrap_err();
    assert!(err.contains("CS_CONFIGURE"), "{err}");
}

#[tokio::test]
async fn act_e_prerequisite_no_manifest_before_chronicle() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    stub_materialize_layout(&root);
    write_phantom_config(&root, "127.0.0.1", 8080);
    let mut s = CeremonyStateFile::default();
    s.s_ceremony = CeremonyPhase::Configure.as_str().to_string();
    s.correlation_id = Some("c1".into());
    atomic_write(&root, &s).unwrap();

    let o = CeremonyOrchestrator::new(root.clone());
    let err = o.run_act_e().await.unwrap_err();
    assert!(
        err.contains("ceremony_attestation_manifest") || err.contains("Act D"),
        "{err}"
    );
    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl"))
        .unwrap_or_default();
    assert!(!chron.contains("Act E entry"), "{chron}");
}

#[tokio::test]
async fn act_e_success_skip_health() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    seed_configure_state(&root, "corr-ok", "127.0.0.1", 8080);
    let _g = EnvGuard::set(ENV_SKIP_CONTROLLER_HEALTH, "1");

    let o = CeremonyOrchestrator::new(root.clone());
    let out = o.run_act_e().await.unwrap();
    assert_eq!(out.s_ceremony, CeremonyPhase::Attest.as_str());
    assert!(out.outcome_class.is_none());

    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Attest.as_str());
    assert_eq!(disk.last_completed_act.as_deref(), Some("E"));

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains("Act E entry"), "{chron}");
    assert!(chron.contains("Act E exit"), "{chron}");
}

#[tokio::test]
async fn act_e_degraded_force_harness() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    seed_configure_state(&root, "corr-deg", "127.0.0.1", 8080);
    let _deg = EnvGuard::set(ENV_FORCE_DEGRADED, "1");

    let o = CeremonyOrchestrator::new(root.clone());
    let out = o.run_act_e().await.unwrap();
    assert_eq!(out.s_ceremony, CeremonyPhase::Attest.as_str());
    assert_eq!(
        out.outcome_class.as_deref(),
        Some(OUTCOME_SUCCEEDED_WITH_WARNINGS)
    );

    let disk = load(&root);
    assert_eq!(disk.outcome_class.as_deref(), Some(OUTCOME_SUCCEEDED_WITH_WARNINGS));

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains(OUTCOME_SUCCEEDED_WITH_WARNINGS), "{chron}");
}

#[tokio::test]
async fn act_e_failure_controller_unreachable() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    seed_configure_state(&root, "corr-fail", "127.0.0.1", 6);

    let o = CeremonyOrchestrator::new(root.clone());
    let out = o.run_act_e().await.unwrap();
    assert_eq!(out.s_ceremony, CeremonyPhase::Configure.as_str());
    assert_eq!(out.outcome_class.as_deref(), Some("FAILED"));
    let disk = load(&root);
    assert_eq!(disk.recovery_target_act.as_deref(), Some("E"));

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains("Act E entry"), "{chron}");
    assert!(chron.contains("FAILED"), "{chron}");
}

#[tokio::test]
async fn act_e_invalid_manifest_correlation_before_chronicle() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    seed_configure_state(&root, "corr-x", "127.0.0.1", 8080);
    let mut body: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(root.join("state").join("ceremony_attestation_manifest.json")).unwrap()).unwrap();
    *body.get_mut("correlationId").unwrap() = json!("wrong");
    std::fs::write(
        root.join("state").join("ceremony_attestation_manifest.json"),
        serde_json::to_string_pretty(&body).unwrap(),
    )
    .unwrap();

    let o = CeremonyOrchestrator::new(root.clone());
    let err = o.run_act_e().await.unwrap_err();
    assert!(err.contains("correlationId") || err.contains("mismatch"), "{err}");
}
