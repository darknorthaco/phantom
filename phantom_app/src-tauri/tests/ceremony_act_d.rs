//! Phase 11.4 — Act D (configure) integration tests.

use phantom_app_lib::ceremony::{
    atomic_write, load, CeremonyOrchestrator, CeremonyPhase, CeremonyStateFile, DiscoverySnapshot,
    ENV_SKIP_CONTROLLER_HEALTH, ENV_SKIP_REGISTER,
};
use serde_json::json;
use std::path::{Path, PathBuf};
use tokio::process::Command;

fn python_cmd() -> &'static str {
    #[cfg(target_os = "windows")]
    {
        "python"
    }
    #[cfg(not(target_os = "windows"))]
    {
        "python3"
    }
}

async fn python_available() -> bool {
    Command::new(python_cmd())
        .arg("-c")
        .arg("import sys; sys.exit(0)")
        .output()
        .await
        .map(|o| o.status.success())
        .unwrap_or(false)
}

fn workspace_phantom_core() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("phantom_core")
}

struct SkipActEAndFDryRun {
    e_prior: Option<std::ffi::OsString>,
    f_prior: Option<std::ffi::OsString>,
}
impl SkipActEAndFDryRun {
    fn arm() -> Self {
        let e_prior = std::env::var_os(ENV_SKIP_CONTROLLER_HEALTH);
        let f_prior = std::env::var_os(ENV_SKIP_REGISTER);
        std::env::set_var(ENV_SKIP_CONTROLLER_HEALTH, "1");
        std::env::set_var(ENV_SKIP_REGISTER, "1");
        Self { e_prior, f_prior }
    }
}
impl Drop for SkipActEAndFDryRun {
    fn drop(&mut self) {
        match &self.e_prior {
            Some(v) => std::env::set_var(ENV_SKIP_CONTROLLER_HEALTH, v),
            None => std::env::remove_var(ENV_SKIP_CONTROLLER_HEALTH),
        }
        match &self.f_prior {
            Some(v) => std::env::set_var(ENV_SKIP_REGISTER, v),
            None => std::env::remove_var(ENV_SKIP_REGISTER),
        }
    }
}

fn stub_materialize_layout(root: &Path) {
    std::fs::create_dir_all(root.join("venv")).unwrap();
    std::fs::write(root.join("venv/pyvenv.cfg"), "home = .\n").unwrap();
    std::fs::create_dir_all(root.join("engine")).unwrap();
    std::fs::write(root.join("engine/run.py"), "# stub\n").unwrap();
}

fn worker_json(worker_id: &str, host: &str, port: u16, source_ip: &str) -> serde_json::Value {
    json!({
        "workerId": worker_id,
        "host": host,
        "port": port,
        "gpuInfo": {},
        "sourceIp": source_ip,
        "signatureVerified": true,
        "fingerprint": "aa",
        "publicKeyB64": ""
    })
}

fn write_snapshot(
    root: &Path,
    correlation_id: &str,
    snapshot_id: &str,
    candidates: Vec<serde_json::Value>,
    policy: serde_json::Value,
) {
    std::fs::create_dir_all(root.join("state")).unwrap();
    let snap = DiscoverySnapshot {
        snapshot_id: snapshot_id.to_string(),
        correlation_id: correlation_id.to_string(),
        created_at: "2026-01-01T00:00:00Z".to_string(),
        candidates,
        policy_flags: policy,
    };
    let body = serde_json::to_string_pretty(&snap).unwrap();
    std::fs::write(root.join("state").join("discovery_snapshot.json"), body).unwrap();
}

/// Discover-shaped ceremony state + placement + snapshot (no Acts B/C required for D-only tests).
fn seed_discover_ready(
    root: &Path,
    correlation_id: &str,
    snapshot_id: &str,
    candidates: Vec<serde_json::Value>,
    policy: serde_json::Value,
) {
    stub_materialize_layout(root);
    std::fs::write(
        root.join("controller_placement.json"),
        json!({
            "host": "127.0.0.1",
            "port": 8080,
            "device_label": "t",
            "identity_fingerprint": "fp"
        })
        .to_string(),
    )
    .unwrap();
    write_snapshot(root, correlation_id, snapshot_id, candidates, policy);

    let mut s = CeremonyStateFile::default();
    s.s_ceremony = CeremonyPhase::Discover.as_str().to_string();
    s.correlation_id = Some(correlation_id.to_string());
    s.snapshot_id = Some(snapshot_id.to_string());
    s.last_completed_act = Some("C".into());
    atomic_write(root, &s).unwrap();
}

#[tokio::test]
async fn act_d_rejects_wrong_phase() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let o = CeremonyOrchestrator::new(root);
    let err = o.run_act_d().await.unwrap_err();
    assert!(err.contains("CS_DISCOVER"), "{err}");
}

#[tokio::test]
async fn act_d_prerequisite_fails_before_chronicle_when_snapshot_missing() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    stub_materialize_layout(&root);
    std::fs::write(
        root.join("controller_placement.json"),
        json!({"host": "127.0.0.1", "port": 8080, "identity_fingerprint": "x"}).to_string(),
    )
    .unwrap();

    let mut s = CeremonyStateFile::default();
    s.s_ceremony = CeremonyPhase::Discover.as_str().to_string();
    s.correlation_id = Some("corr-miss".into());
    s.snapshot_id = Some("sid1".into());
    atomic_write(&root, &s).unwrap();

    let o = CeremonyOrchestrator::new(root.clone());
    let err = o.run_act_d().await.unwrap_err();
    assert!(err.contains("discovery_snapshot") || err.contains("Act C"), "{err}");

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl"))
        .unwrap_or_default();
    assert!(
        !chron.contains("Act D entry"),
        "must not chronicle D when prerequisites fail: {chron}"
    );
}

#[tokio::test]
async fn act_d_rejects_partial_snapshot_with_zero_candidates() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    seed_discover_ready(
        &root,
        "c1",
        "snap-p",
        vec![],
        json!({ "discovery_partial": true }),
    );

    let o = CeremonyOrchestrator::new(root.clone());
    let err = o.run_act_d().await.unwrap_err();
    assert!(
        err.contains("PARTIAL") || err.contains("zero candidates") || err.contains("primary"),
        "{err}"
    );

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl"))
        .unwrap_or_default();
    assert!(!chron.contains("Act D entry"), "{chron}");
}

#[tokio::test]
async fn act_d_success_writes_config_and_attestation() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let lan = worker_json("lan-w", "192.168.4.2", 8090, "192.168.4.2");
    let syn = worker_json("syn-w", "127.0.0.1", 8090, "127.0.0.1");
    seed_discover_ready(&root, "c-ok", "snap-1", vec![syn, lan], json!({ "lan_mode": "lan_udp" }));

    let o = CeremonyOrchestrator::new(root.clone());
    let out = o.run_act_d().await.expect("Act D ok");
    assert_eq!(out.s_ceremony, CeremonyPhase::Configure.as_str());

    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Configure.as_str());
    assert_eq!(disk.last_completed_act.as_deref(), Some("D"));

    assert!(root.join("phantom_config.json").is_file());
    let att = root.join("state").join("ceremony_attestation_manifest.json");
    assert!(att.is_file());
    let att_raw = std::fs::read_to_string(&att).unwrap();
    let att_v: serde_json::Value = serde_json::from_str(&att_raw).unwrap();
    assert_eq!(att_v["primaryWorker"]["workerId"], "lan-w");

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains("Act D entry"), "{chron}");
    assert!(chron.contains("Act D exit"), "{chron}");
}

#[tokio::test]
async fn act_d_synthetic_only_candidate_succeeds() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let syn = worker_json("local-worker", "127.0.0.1", 8090, "127.0.0.1");
    seed_discover_ready(&root, "c-syn", "snap-s", vec![syn], json!({ "synthetic_mode": "offline_synthetic" }));

    let o = CeremonyOrchestrator::new(root.clone());
    o.run_act_d().await.unwrap();
    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Configure.as_str());
}

#[tokio::test]
async fn act_d_correlation_mismatch_before_chronicle() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    seed_discover_ready(
        &root,
        "snap-corr",
        "snap-x",
        vec![worker_json("w", "10.0.0.1", 8090, "10.0.0.1")],
        json!({}),
    );

    let mut disk = load(&root);
    disk.correlation_id = Some("different".into());
    atomic_write(&root, &disk).unwrap();

    let o = CeremonyOrchestrator::new(root.clone());
    let err = o.run_act_d().await.unwrap_err();
    assert!(err.contains("correlation") || err.contains("mismatch"), "{err}");
}

#[tokio::test]
async fn act_d_failure_after_entry_on_config_io() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    seed_discover_ready(
        &root,
        "c-io",
        "snap-io",
        vec![worker_json("w", "10.0.0.2", 8090, "10.0.0.2")],
        json!({}),
    );

    // Block atomic config write: `phantom_config.json.tmp` must be a file, not a directory.
    std::fs::create_dir_all(root.join("phantom_config.json.tmp")).unwrap();

    let o = CeremonyOrchestrator::new(root.clone());
    let out = o.run_act_d().await.expect("returns dto");
    assert_eq!(out.outcome_class.as_deref(), Some("FAILED"));
    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Discover.as_str());
    assert_eq!(disk.recovery_target_act.as_deref(), Some("D"));

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains("Act D entry"), "{chron}");
    assert!(chron.contains("FAILED"), "{chron}");
}

#[tokio::test]
async fn act_a_through_d_chain() {
    if !python_available().await {
        return;
    }
    let engine = workspace_phantom_core();
    if !engine.join("run.py").is_file() {
        return;
    }

    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let bundle = root.join("bundle");
    std::fs::create_dir_all(&bundle).unwrap();
    std::fs::write(
        root.join("phantom_config.json"),
        r#"{"discovery":{"total_timeout_ms":80,"early_exit_on_first_worker":true}}"#,
    )
    .unwrap();

    let o = CeremonyOrchestrator::new(root.clone());
    o.commit_placement("127.0.0.1".into(), 8093, "d".into(), "fp-d".into())
        .await
        .unwrap();
    o.run_act_b(engine, None, None).await.unwrap();
    o.run_act_c(Some(bundle), None).await.unwrap();
    let out = o.run_act_d().await.unwrap();
    assert_eq!(out.s_ceremony, CeremonyPhase::Configure.as_str());

    let _skip = SkipActEAndFDryRun::arm();
    let out_e = o.run_act_e().await.unwrap();
    assert_eq!(out_e.s_ceremony, CeremonyPhase::Attest.as_str());
    let out_f = o.run_act_f().await.unwrap();
    assert_eq!(out_f.s_ceremony, CeremonyPhase::Operational.as_str());
    assert!(out_f.outcome_class.is_none());

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains("Act F entry"), "{chron}");
    assert!(chron.contains("Act F exit"), "{chron}");
}
