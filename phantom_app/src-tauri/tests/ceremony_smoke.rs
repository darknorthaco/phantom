//! Phase 11 — integration smoke: state IO, ceremony chronicle, orchestrator (no Tauri runtime).

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

#[test]
fn state_load_save_round_trip() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path();
    let mut s = CeremonyStateFile::default();
    s.s_ceremony = CeremonyPhase::Placement.as_str().to_string();
    s.correlation_id = Some("smoke-corr".into());
    atomic_write(root, &s).unwrap();
    let s2 = load(root);
    assert_eq!(s2.s_ceremony, CeremonyPhase::Placement.as_str());
    assert_eq!(s2.correlation_id.as_deref(), Some("smoke-corr"));
}

#[test]
fn ceremony_status_and_chronicle_append_via_orchestrator() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let o = CeremonyOrchestrator::new(root.clone());
    let st = o.ceremony_status().unwrap();
    assert_eq!(st.s_ceremony, CeremonyPhase::Idle.as_str());
}

#[tokio::test]
async fn end_to_end_full_dry_run_a_through_f() {
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

    let st = o
        .dry_run_stub_graph(engine, Some(bundle), None)
        .await
        .unwrap();
    assert_eq!(st.s_ceremony, CeremonyPhase::Operational.as_str());
    assert!(st.outcome_class.is_none());

    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Operational.as_str());
    assert_eq!(disk.last_completed_act.as_deref(), Some("F"));

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    for line in chron.lines().filter(|l| !l.is_empty()) {
        let v: serde_json::Value = serde_json::from_str(line).expect("valid JSONL");
        assert_eq!(v["schema_version"], "1");
    }
}
