//! Phase 11.2 — Act B (materialize) integration tests.

use phantom_app_lib::ceremony::{atomic_write, load, CeremonyOrchestrator, CeremonyPhase, CeremonyStateFile};
use std::path::PathBuf;
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

#[tokio::test]
async fn act_b_rejects_wrong_phase() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let o = CeremonyOrchestrator::new(root);
    let err = o
        .run_act_b(workspace_phantom_core(), None, None)
        .await
        .unwrap_err();
    assert!(err.contains("CS_PLACEMENT"), "{}", err);
}

#[tokio::test]
async fn act_b_rejects_missing_correlation() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let mut s = CeremonyStateFile::default();
    s.s_ceremony = CeremonyPhase::Placement.as_str().to_string();
    s.correlation_id = None;
    atomic_write(&root, &s).unwrap();

    let o = CeremonyOrchestrator::new(root);
    let err = o
        .run_act_b(workspace_phantom_core(), None, None)
        .await
        .unwrap_err();
    assert!(err.contains("correlation_id"), "{}", err);
}

#[tokio::test]
async fn act_b_validate_fails_before_entry_when_placement_missing() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();

    let o = CeremonyOrchestrator::new(root.clone());
    o.commit_placement(
        "127.0.0.1".into(),
        8080,
        "t".into(),
        "fp".into(),
    )
    .await
    .unwrap();

    std::fs::remove_file(root.join("controller_placement.json")).unwrap();

    let err = o
        .run_act_b(workspace_phantom_core(), None, None)
        .await
        .unwrap_err();
    assert!(
        err.contains("controller_placement.json") || err.contains("placement"),
        "{}",
        err
    );

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl"))
        .unwrap_or_default();
    assert!(
        !chron.contains("\"act\":\"B\"") && !chron.contains(r#""act":"B""#),
        "Act B chronicle must not run when validate fails first: {chron}"
    );
}

#[tokio::test]
async fn act_b_failure_engine_copy_sets_recovery_and_chronicle() {
    if !python_available().await {
        return;
    }

    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();

    let o = CeremonyOrchestrator::new(root.clone());
    o.commit_placement(
        "127.0.0.1".into(),
        8080,
        "t".into(),
        "fp".into(),
    )
    .await
    .unwrap();

    let bogus_engine = root.join("no_such_engine_source");
    let out = o
        .run_act_b(bogus_engine, None, None)
        .await
        .expect("Act B returns Ok with FAILED outcome");

    assert_eq!(out.s_ceremony, CeremonyPhase::Placement.as_str());
    assert_eq!(out.outcome_class.as_deref(), Some("FAILED"));

    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Placement.as_str());
    assert_eq!(disk.recovery_target_act.as_deref(), Some("B"));
    assert_eq!(disk.outcome_class.as_deref(), Some("FAILED"));

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains("act_entry"), "{chron}");
    assert!(chron.contains("act_exit"), "{chron}");
    assert!(chron.contains("FAILED"), "{chron}");
    assert!(chron.contains("recovery_target"), "{chron}");
}

#[tokio::test]
async fn act_b_offline_bundle_missing_wheelhouse_fails_cleanly() {
    if !python_available().await {
        return;
    }

    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let bundle = dir.path().join("bad_bundle");
    std::fs::create_dir_all(&bundle).unwrap();

    let o = CeremonyOrchestrator::new(root.clone());
    o.commit_placement(
        "127.0.0.1".into(),
        8080,
        "t".into(),
        "fp".into(),
    )
    .await
    .unwrap();

    let engine = workspace_phantom_core();
    if !engine.join("run.py").is_file() {
        return;
    }

    let out = o
        .run_act_b(engine, Some(bundle), None)
        .await
        .unwrap();
    assert_eq!(out.outcome_class.as_deref(), Some("FAILED"));
    let disk = load(&root);
    assert_eq!(disk.recovery_target_act.as_deref(), Some("B"));
}

#[tokio::test]
async fn act_b_success_advances_to_materialize() {
    if !python_available().await {
        return;
    }

    let engine = workspace_phantom_core();
    if !engine.join("run.py").is_file() {
        return;
    }

    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();

    let o = CeremonyOrchestrator::new(root.clone());
    o.commit_placement(
        "127.0.0.1".into(),
        8080,
        "t".into(),
        "fp".into(),
    )
    .await
    .unwrap();

    let out = o.run_act_b(engine, None, None).await.expect("Act B ok");
    assert_eq!(out.s_ceremony, CeremonyPhase::Materialize.as_str());
    assert!(out.outcome_class.is_none());

    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Materialize.as_str());
    assert_eq!(disk.last_completed_act.as_deref(), Some("B"));
    assert!(disk.recovery_target_act.is_none());

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains("act_entry"), "{chron}");
    assert!(chron.contains("act_exit"), "{chron}");
}

#[tokio::test]
async fn act_a_then_act_b_then_dry_run_stub() {
    if !python_available().await {
        return;
    }

    let engine = workspace_phantom_core();
    if !engine.join("run.py").is_file() {
        return;
    }

    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let o = CeremonyOrchestrator::new(root.clone());

    let bundle = root.join("bundle");
    std::fs::create_dir_all(&bundle).unwrap();

    o.dry_run_stub_graph(engine, Some(bundle), None)
        .await
        .unwrap();

    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Operational.as_str());
}
