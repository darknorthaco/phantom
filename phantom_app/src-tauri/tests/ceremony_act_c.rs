//! Phase 11.3 — Act C (discovery) integration tests.

use phantom_app_lib::ceremony::{
    atomic_write, load, CeremonyOrchestrator, CeremonyPhase, CeremonyStateFile,
};
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

fn write_discovery_config(root: &Path, timeout_ms: u64) {
    std::fs::write(
        root.join("phantom_config.json"),
        format!(
            r#"{{"discovery":{{"total_timeout_ms":{timeout_ms},"early_exit_on_first_worker":true}}}}"#
        ),
    )
    .unwrap();
}

fn stub_materialized_engine(root: &Path) {
    std::fs::create_dir_all(root.join("venv")).unwrap();
    std::fs::write(root.join("venv/pyvenv.cfg"), "home = .\n").unwrap();
    std::fs::create_dir_all(root.join("engine")).unwrap();
    std::fs::write(root.join("engine/run.py"), "# stub\n").unwrap();
}

#[tokio::test]
async fn act_c_rejects_wrong_phase() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let o = CeremonyOrchestrator::new(root);
    let err = o.run_act_c(None, None).await.unwrap_err();
    assert!(err.contains("CS_MATERIALIZE"), "{err}");
}

#[tokio::test]
async fn act_c_rejects_missing_correlation() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let mut s = CeremonyStateFile::default();
    s.s_ceremony = CeremonyPhase::Materialize.as_str().to_string();
    s.correlation_id = None;
    atomic_write(&root, &s).unwrap();
    stub_materialized_engine(&root);

    let o = CeremonyOrchestrator::new(root);
    let err = o.run_act_c(None, None).await.unwrap_err();
    assert!(err.contains("correlation_id"), "{err}");
}

#[tokio::test]
async fn act_c_validate_fails_before_chronicle_when_venv_missing() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();

    let o = CeremonyOrchestrator::new(root.clone());
    o.commit_placement("127.0.0.1".into(), 8080, "t".into(), "fp".into())
        .await
        .unwrap();

    let mut disk = load(&root);
    disk.s_ceremony = CeremonyPhase::Materialize.as_str().to_string();
    disk.last_completed_act = Some("B".into());
    atomic_write(&root, &disk).unwrap();
    o.reload_from_disk().unwrap();

    let err = o.run_act_c(None, None).await.unwrap_err();
    assert!(err.contains("venv") || err.contains("materialize"), "{err}");

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl"))
        .unwrap_or_default();
    assert!(
        !chron.contains(r#""act":"C""#) && !chron.contains("\"act\":\"C\""),
        "chronicle must not record Act C when validate fails: {chron}"
    );
}

#[tokio::test]
async fn act_c_success_advances_to_discover_with_offline_synthetic() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let bundle = root.join("bundle");
    std::fs::create_dir_all(&bundle).unwrap();
    write_discovery_config(&root, 80);
    stub_materialized_engine(&root);

    let o = CeremonyOrchestrator::new(root.clone());
    o.commit_placement("127.0.0.1".into(), 8080, "t".into(), "fp".into())
        .await
        .unwrap();

    let mut disk = load(&root);
    disk.s_ceremony = CeremonyPhase::Materialize.as_str().to_string();
    disk.last_completed_act = Some("B".into());
    atomic_write(&root, &disk).unwrap();
    o.reload_from_disk().unwrap();

    let out = o.run_act_c(Some(bundle), None).await.expect("Act C ok");
    assert_eq!(out.s_ceremony, CeremonyPhase::Discover.as_str());
    assert!(out.outcome_class.is_none());

    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Discover.as_str());
    assert_eq!(disk.last_completed_act.as_deref(), Some("C"));
    assert!(disk.snapshot_id.is_some());
    assert!(root.join("state").join("discovery_snapshot.json").is_file());

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains("Act C entry"), "{chron}");
    assert!(chron.contains("Act C exit"), "{chron}");
}

#[tokio::test]
async fn act_c_partial_when_no_candidates() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    write_discovery_config(&root, 15);
    stub_materialized_engine(&root);

    let o = CeremonyOrchestrator::new(root.clone());
    o.commit_placement("127.0.0.1".into(), 8080, "t".into(), "fp".into())
        .await
        .unwrap();

    let mut disk = load(&root);
    disk.s_ceremony = CeremonyPhase::Materialize.as_str().to_string();
    disk.last_completed_act = Some("B".into());
    atomic_write(&root, &disk).unwrap();
    o.reload_from_disk().unwrap();

    let out = o.run_act_c(None, None).await.expect("Act C returns status");
    assert_eq!(out.s_ceremony, CeremonyPhase::Materialize.as_str());
    assert_eq!(out.outcome_class.as_deref(), Some("PARTIAL"));

    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Materialize.as_str());
    assert_eq!(disk.outcome_class.as_deref(), Some("PARTIAL"));
    assert_eq!(disk.recovery_target_act, None);
    assert!(disk.snapshot_id.is_some());

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains("PARTIAL"), "{chron}");
}

#[tokio::test]
async fn act_a_then_b_then_c_success() {
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
    write_discovery_config(&root, 80);

    let o = CeremonyOrchestrator::new(root.clone());
    o.commit_placement("127.0.0.1".into(), 8092, "dev".into(), "fp-abc".into())
        .await
        .unwrap();
    o.run_act_b(engine, None, None).await.unwrap();
    let out = o.run_act_c(Some(bundle), None).await.unwrap();
    assert_eq!(out.s_ceremony, CeremonyPhase::Discover.as_str());
}
