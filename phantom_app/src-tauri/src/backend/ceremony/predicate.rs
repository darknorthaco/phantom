//! Phase 12 — Operational predicate engine.
//!
//! Replaces the Phase 11 stub. Evaluates a fixed set of clauses against the
//! ceremony mirror + on-disk artifacts (placement file, discovery snapshot,
//! phantom_config.json, attestation manifest). The result is doctrine-aligned
//! and side-effect free: it never mutates state, never opens network sockets,
//! and never depends on WAN reachability.
//!
//! Doctrine invariants encoded here:
//! - LAN-first ceremony is canonical; WAN reachability is irrelevant to "operational".
//! - "Operational" requires Act F to have completed (or to have been classified
//!   as PARTIAL with all upstream artifacts intact).
//! - Recovery state is never operational.
//! - Degraded outcomes (`SUCCEEDED_WITH_WARNINGS`, `PARTIAL`) keep the system
//!   operational but surface a warning clause so the UI can render the asterisk.

use std::path::Path;

use super::dto::{OperationalEvaluation, OperationalEvaluationClause};
use super::phase::CeremonyPhase;
use super::state_file::CeremonyStateFile;

/// Outcome classes considered "acceptable" for an operational system.
const OUTCOME_OK: &[&str] = &["SUCCEEDED_WITH_WARNINGS", "PARTIAL"];

fn placement_file_present(root: &Path) -> (bool, String) {
    let p = root.join("controller_placement.json");
    if !p.is_file() {
        return (false, "controller_placement.json missing (Act A not committed)".to_string());
    }
    let raw = match std::fs::read_to_string(&p) {
        Ok(s) => s,
        Err(e) => return (false, format!("read controller_placement.json: {e}")),
    };
    let v: serde_json::Value = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(e) => return (false, format!("parse controller_placement.json: {e}")),
    };
    let host_ok = v
        .get("host")
        .and_then(|x| x.as_str())
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false);
    let port_ok = v.get("port").and_then(|x| x.as_u64()).filter(|&p| p > 0).is_some();
    let fp_ok = v
        .get("identity_fingerprint")
        .and_then(|x| x.as_str())
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false);
    if host_ok && port_ok && fp_ok {
        (true, "placement host/port/fingerprint present".to_string())
    } else {
        (false, "controller_placement.json missing host/port/identity_fingerprint".to_string())
    }
}

fn discovery_snapshot_present(root: &Path) -> (bool, String) {
    let p = root.join("state").join("discovery_snapshot.json");
    if !p.is_file() {
        return (false, "discovery_snapshot.json missing (Act C not run)".to_string());
    }
    let raw = match std::fs::read_to_string(&p) {
        Ok(s) => s,
        Err(e) => return (false, format!("read discovery_snapshot.json: {e}")),
    };
    let v: serde_json::Value = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(e) => return (false, format!("parse discovery_snapshot.json: {e}")),
    };
    let count = v
        .get("candidates")
        .and_then(|c| c.as_array())
        .map(|a| a.len())
        .unwrap_or(0);
    if count == 0 {
        return (false, "discovery snapshot has zero candidates".to_string());
    }
    (true, format!("{count} discovered candidate(s)"))
}

fn controller_config_present(root: &Path) -> (bool, String) {
    let p = root.join("phantom_config.json");
    if !p.is_file() {
        return (false, "phantom_config.json missing (Act D not run)".to_string());
    }
    let raw = match std::fs::read_to_string(&p) {
        Ok(s) => s,
        Err(e) => return (false, format!("read phantom_config.json: {e}")),
    };
    let v: serde_json::Value = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(e) => return (false, format!("parse phantom_config.json: {e}")),
    };
    let ctrl = match v.get("controller").and_then(|c| c.as_object()) {
        Some(c) => c,
        None => return (false, "phantom_config.json missing controller block".to_string()),
    };
    let host_ok = ctrl
        .get("host")
        .and_then(|x| x.as_str())
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false);
    let port_ok = ctrl.get("port").and_then(|x| x.as_u64()).filter(|&p| p > 0).is_some();
    if host_ok && port_ok {
        (true, "controller host/port present".to_string())
    } else {
        (false, "controller block missing host or port".to_string())
    }
}

fn attestation_manifest_valid(root: &Path) -> (bool, String) {
    let p = root.join("state").join("ceremony_attestation_manifest.json");
    if !p.is_file() {
        return (false, "ceremony_attestation_manifest.json missing (Act D incomplete)".to_string());
    }
    let raw = match std::fs::read_to_string(&p) {
        Ok(s) => s,
        Err(e) => return (false, format!("read attestation manifest: {e}")),
    };
    let v: serde_json::Value = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(e) => return (false, format!("parse attestation manifest: {e}")),
    };
    let pw = match v.get("primaryWorker").and_then(|x| x.as_object()) {
        Some(o) => o,
        None => return (false, "primaryWorker missing".to_string()),
    };
    let id_ok = pw
        .get("workerId")
        .and_then(|x| x.as_str())
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false);
    let host_ok = pw
        .get("host")
        .and_then(|x| x.as_str())
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false);
    let port_ok = pw.get("port").and_then(|x| x.as_u64()).filter(|&p| p > 0).is_some();
    if id_ok && host_ok && port_ok {
        (true, "primaryWorker id/host/port present".to_string())
    } else {
        (false, "primaryWorker missing workerId/host/port".to_string())
    }
}

fn phase_reached_operational(mirror: &CeremonyStateFile) -> (bool, String) {
    let phase = CeremonyPhase::parse(&mirror.s_ceremony);
    let last = mirror.last_completed_act.as_deref().unwrap_or("-");
    match phase {
        Some(CeremonyPhase::Operational) if last == "F" => {
            (true, "S_ceremony=CS_OPERATIONAL, last_completed_act=F".to_string())
        }
        Some(p) => (
            false,
            format!("S_ceremony={} (need CS_OPERATIONAL with last_completed_act=F)", p.as_str()),
        ),
        None => (false, format!("unknown S_ceremony={}", mirror.s_ceremony)),
    }
}

fn not_in_recovery(mirror: &CeremonyStateFile) -> (bool, String) {
    let in_recovery_phase =
        CeremonyPhase::parse(&mirror.s_ceremony) == Some(CeremonyPhase::Recovery);
    let target = mirror.recovery_target_act.as_deref();
    if in_recovery_phase {
        return (false, "S_ceremony=CS_RECOVERY".to_string());
    }
    match target {
        Some(act) => (false, format!("recovery_target_act={act} still set")),
        None => (true, "no recovery target pending".to_string()),
    }
}

fn outcome_class_acceptable(mirror: &CeremonyStateFile) -> (bool, String) {
    match mirror.outcome_class.as_deref() {
        None => (true, "clean outcome".to_string()),
        Some("FAILED") => (false, "outcome_class=FAILED".to_string()),
        Some(other) if OUTCOME_OK.contains(&other) => (true, format!("outcome_class={other} (degraded but operational)")),
        Some(other) => (false, format!("outcome_class={other} (unrecognized)")),
    }
}

fn clause(id: &str, name: &str, pass: bool, detail: String) -> OperationalEvaluationClause {
    OperationalEvaluationClause {
        id: id.to_string(),
        name: name.to_string(),
        pass,
        detail,
    }
}

/// Evaluate the operational predicate against on-disk artifacts and the ceremony mirror.
///
/// Returns `OperationalEvaluation { operational, clauses }` where `operational`
/// is the AND of all clause passes. Callers can also inspect `clauses` for UI.
pub fn evaluate_operational(root: &Path, mirror: &CeremonyStateFile) -> OperationalEvaluation {
    let (a, da) = placement_file_present(root);
    let (b, db) = discovery_snapshot_present(root);
    let (c, dc) = controller_config_present(root);
    let (d, dd) = attestation_manifest_valid(root);
    let (e, de) = phase_reached_operational(mirror);
    let (f, df) = not_in_recovery(mirror);
    let (g, dg) = outcome_class_acceptable(mirror);

    let clauses = vec![
        clause("placement.committed", "Placement committed", a, da),
        clause("discovery.snapshot.present", "Discovery snapshot present", b, db),
        clause("controller.config.present", "Controller config present", c, dc),
        clause("attestation.manifest.valid", "Attestation manifest valid", d, dd),
        clause("ceremony.reached.operational", "Ceremony reached CS_OPERATIONAL", e, de),
        clause("ceremony.not.in.recovery", "Not in recovery", f, df),
        clause("outcome.acceptable", "Outcome class acceptable", g, dg),
    ];

    let operational = clauses.iter().all(|c| c.pass);
    OperationalEvaluation { operational, clauses }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::ceremony::state_file::CeremonyStateFile;
    use tempfile::tempdir;

    fn write(p: &std::path::Path, s: &str) {
        if let Some(parent) = p.parent() {
            std::fs::create_dir_all(parent).unwrap();
        }
        std::fs::write(p, s).unwrap();
    }

    fn idle_mirror() -> CeremonyStateFile {
        CeremonyStateFile::default()
    }

    fn operational_mirror() -> CeremonyStateFile {
        let mut m = CeremonyStateFile::default();
        m.s_ceremony = CeremonyPhase::Operational.as_str().to_string();
        m.last_completed_act = Some("F".to_string());
        m.outcome_class = None;
        m.recovery_target_act = None;
        m
    }

    #[test]
    fn idle_state_is_not_operational_and_lists_failures() {
        let dir = tempdir().unwrap();
        let r = dir.path();
        let ev = evaluate_operational(r, &idle_mirror());
        assert!(!ev.operational);
        assert_eq!(ev.clauses.len(), 7);
        assert!(ev.clauses.iter().any(|c| c.id == "placement.committed" && !c.pass));
    }

    #[test]
    fn full_artifacts_with_clean_mirror_are_operational() {
        let dir = tempdir().unwrap();
        let r = dir.path();

        write(
            &r.join("controller_placement.json"),
            r#"{"host":"127.0.0.1","port":8080,"identity_fingerprint":"abc"}"#,
        );
        write(
            &r.join("state").join("discovery_snapshot.json"),
            r#"{"snapshotId":"s1","correlationId":"c1","createdAt":"now","candidates":[{"workerId":"w1","host":"127.0.0.1","port":8090}],"policyFlags":{}}"#,
        );
        write(
            &r.join("phantom_config.json"),
            r#"{"controller":{"host":"127.0.0.1","port":8080}}"#,
        );
        write(
            &r.join("state").join("ceremony_attestation_manifest.json"),
            r#"{"schemaVersion":"1","correlationId":"c1","primaryWorker":{"workerId":"w1","host":"127.0.0.1","port":8090}}"#,
        );

        let ev = evaluate_operational(r, &operational_mirror());
        assert!(ev.operational, "expected operational; clauses={:?}", ev.clauses);
    }

    #[test]
    fn recovery_state_blocks_operational() {
        let dir = tempdir().unwrap();
        let r = dir.path();
        let mut m = operational_mirror();
        m.recovery_target_act = Some("E".to_string());
        let ev = evaluate_operational(r, &m);
        assert!(!ev.operational);
        assert!(ev.clauses.iter().any(|c| c.id == "ceremony.not.in.recovery" && !c.pass));
    }

    #[test]
    fn degraded_outcome_classes_are_still_operational_when_artifacts_present() {
        let dir = tempdir().unwrap();
        let r = dir.path();
        write(
            &r.join("controller_placement.json"),
            r#"{"host":"127.0.0.1","port":8080,"identity_fingerprint":"abc"}"#,
        );
        write(
            &r.join("state").join("discovery_snapshot.json"),
            r#"{"snapshotId":"s1","correlationId":"c1","createdAt":"now","candidates":[{"workerId":"w1","host":"127.0.0.1","port":8090}],"policyFlags":{}}"#,
        );
        write(
            &r.join("phantom_config.json"),
            r#"{"controller":{"host":"127.0.0.1","port":8080}}"#,
        );
        write(
            &r.join("state").join("ceremony_attestation_manifest.json"),
            r#"{"schemaVersion":"1","correlationId":"c1","primaryWorker":{"workerId":"w1","host":"127.0.0.1","port":8090}}"#,
        );
        let mut m = operational_mirror();
        m.outcome_class = Some("PARTIAL".to_string());
        let ev = evaluate_operational(r, &m);
        assert!(ev.operational);
        assert!(ev.clauses.iter().any(|c| c.id == "outcome.acceptable" && c.pass));
    }
}
