//! Phase 11 — Act C failure, recovery, then D → E → F (no live controller).

use phantom_app_lib::ceremony::{
    load, CeremonyOrchestrator, CeremonyPhase, ENV_SKIP_CONTROLLER_HEALTH, ENV_SKIP_REGISTER,
};
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

struct SkipActEAndF {
    e_prior: Option<std::ffi::OsString>,
    f_prior: Option<std::ffi::OsString>,
}
impl SkipActEAndF {
    fn arm() -> Self {
        let e_prior = std::env::var_os(ENV_SKIP_CONTROLLER_HEALTH);
        let f_prior = std::env::var_os(ENV_SKIP_REGISTER);
        std::env::set_var(ENV_SKIP_CONTROLLER_HEALTH, "1");
        std::env::set_var(ENV_SKIP_REGISTER, "1");
        Self { e_prior, f_prior }
    }
}
impl Drop for SkipActEAndF {
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

/// Block `discovery_snapshot.json` persistence by occupying the target path as a directory.
fn block_discovery_snapshot_path(root: &std::path::Path) {
    let p = root.join("state").join("discovery_snapshot.json");
    std::fs::create_dir_all(&p).unwrap();
}

#[tokio::test]
async fn act_c_failure_then_recover_through_f() {
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

    let o = CeremonyOrchestrator::new(root.clone());
    o.commit_placement("127.0.0.1".into(), 8094, "rec".into(), "fp-rec".into())
        .await
        .unwrap();
    o.run_act_b(engine, None, None).await.unwrap();

    block_discovery_snapshot_path(&root);

    let out_fail = o.run_act_c(Some(bundle.clone()), None).await.unwrap();
    assert_eq!(out_fail.s_ceremony, CeremonyPhase::Materialize.as_str());
    assert_eq!(out_fail.outcome_class.as_deref(), Some("FAILED"));
    let disk = load(&root);
    assert_eq!(disk.recovery_target_act.as_deref(), Some("C"));

    let chron_mid = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron_mid.contains("Act C entry"), "{chron_mid}");
    assert!(chron_mid.contains("FAILED"), "{chron_mid}");
    assert!(chron_mid.contains("recovery_target"), "{chron_mid}");

    let snap_block = root.join("state").join("discovery_snapshot.json");
    std::fs::remove_dir_all(&snap_block).unwrap();

    let out_c2 = o.run_act_c(Some(bundle), None).await.unwrap();
    assert_eq!(out_c2.s_ceremony, CeremonyPhase::Discover.as_str());
    assert!(out_c2.outcome_class.is_none());

    let _skip = SkipActEAndF::arm();
    o.run_act_d().await.unwrap();
    o.run_act_e().await.unwrap();
    let st_f = o.run_act_f().await.unwrap();

    assert_eq!(st_f.s_ceremony, CeremonyPhase::Operational.as_str());
    assert_eq!(st_f.outcome_class, None);

    let disk = load(&root);
    assert_eq!(disk.s_ceremony, CeremonyPhase::Operational.as_str());
    assert_eq!(disk.last_completed_act.as_deref(), Some("F"));
    assert_eq!(disk.outcome_class, None);
    assert_eq!(disk.recovery_target_act, None);

    let chron = std::fs::read_to_string(root.join("state").join("ceremony_chronicle.jsonl")).unwrap();
    assert!(chron.contains("FAILED"), "{chron}");
    assert!(chron.contains("recovery_target"), "{chron}");
    let n_c_entry = chron.matches("Act C entry").count();
    assert!(n_c_entry >= 2, "expected retry Act C chronicle, got {n_c_entry}: {chron}");
}
