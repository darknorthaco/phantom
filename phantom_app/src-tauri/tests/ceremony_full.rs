//! Phase 11 — full ceremony A → F integration (no live controller).

use phantom_app_lib::ceremony::{load, CeremonyOrchestrator, CeremonyPhase, CeremonyStateFile};
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

fn count_chronicle_events(chron: &str, event_type: &str) -> usize {
    chron
        .lines()
        .filter(|l| !l.is_empty())
        .filter(|l| {
            serde_json::from_str::<serde_json::Value>(l)
                .ok()
                .and_then(|v| {
                    v.get("eventType")
                        .and_then(|x| x.as_str())
                        .map(|t| t == event_type)
                })
                .unwrap_or(false)
        })
        .count()
}

#[tokio::test]
async fn full_ceremony_a_through_f_operational() {
    if !python_available().await {
        return;
    }
    let engine = workspace_phantom_core();
    if !engine.join("run.py").is_file() {
        return;
    }

    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let bundle = root.join("offline_bundle");
    std::fs::create_dir_all(&bundle).unwrap();

    let o = CeremonyOrchestrator::new(root.clone());
    let st = o
        .dry_run_stub_graph(engine, Some(bundle), None)
        .await
        .expect("full ceremony dry-run");

    assert_eq!(st.s_ceremony, CeremonyPhase::Operational.as_str());
    assert_eq!(st.outcome_class, None);

    let disk: CeremonyStateFile = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Operational.as_str());
    assert_eq!(disk.last_completed_act.as_deref(), Some("F"));
    assert_eq!(disk.outcome_class, None);
    assert_eq!(disk.recovery_target_act, None);

    assert!(root.join("state").join("discovery_snapshot.json").is_file());
    assert!(root.join("phantom_config.json").is_file());
    assert!(
        root.join("state")
            .join("ceremony_attestation_manifest.json")
            .is_file()
    );

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert_eq!(count_chronicle_events(&chron, "act_entry"), 6);
    assert_eq!(count_chronicle_events(&chron, "act_exit"), 6);
}
