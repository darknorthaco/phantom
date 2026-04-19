//! Phase 11 — Ceremony orchestrator: sole mutator of `S_ceremony` (in-memory mirror + disk).

use std::path::{Path, PathBuf};
use std::sync::Mutex;

use uuid::Uuid;

use super::act_a;
use super::act_b;
use super::act_c::{self, ActCDiscoveryOutcome};
use super::act_d;
use super::act_e::{self, ActEAttestationOutcome, OUTCOME_SUCCEEDED_WITH_WARNINGS};
use super::act_f::{self, ActFRegisterOutcome, OUTCOME_PARTIAL_REGISTRATION};
use super::ceremony_chronicle::{
    append_ceremony_line, append_recovery_target, append_recovery_target_for_phase,
    CeremonyChronicleLine,
};
use super::dto::{CeremonyStatusDto, OperationalEvaluation};
use super::phase::{
    can_run_act_b, can_run_act_c, can_run_act_d, can_run_act_e, can_run_act_f, CeremonyPhase,
};
use super::state_file::{atomic_write, load, CeremonyStateFile};

use crate::backend::phantom_state::AppPhase;

/// Scoped `PHANTOM_CEREMONY_ACT_E_SKIP_CONTROLLER_HEALTH` + `PHANTOM_CEREMONY_ACT_F_SKIP_REGISTER` for dry-run only.
struct DryRunCeremonyNetworkStubGuard {
    e_prior: Option<std::ffi::OsString>,
    f_prior: Option<std::ffi::OsString>,
}

impl DryRunCeremonyNetworkStubGuard {
    fn arm() -> Self {
        let e_prior = std::env::var_os(act_e::ENV_SKIP_CONTROLLER_HEALTH);
        let f_prior = std::env::var_os(act_f::ENV_SKIP_REGISTER);
        std::env::set_var(act_e::ENV_SKIP_CONTROLLER_HEALTH, "1");
        std::env::set_var(act_f::ENV_SKIP_REGISTER, "1");
        Self { e_prior, f_prior }
    }
}

impl Drop for DryRunCeremonyNetworkStubGuard {
    fn drop(&mut self) {
        match &self.e_prior {
            Some(v) => std::env::set_var(act_e::ENV_SKIP_CONTROLLER_HEALTH, v),
            None => std::env::remove_var(act_e::ENV_SKIP_CONTROLLER_HEALTH),
        }
        match &self.f_prior {
            Some(v) => std::env::set_var(act_f::ENV_SKIP_REGISTER, v),
            None => std::env::remove_var(act_f::ENV_SKIP_REGISTER),
        }
    }
}

const DRY_RUN_PLACEMENT_HOST: &str = "127.0.0.1";
const DRY_RUN_PLACEMENT_PORT: u16 = 8080;
const DRY_RUN_DEVICE_LABEL: &str = "dry-run";
const DRY_RUN_IDENTITY_FP: &str = "dry-run-fp";

/// In-memory mirror of ceremony state; only this type writes `ceremony_state.json` for the unified ceremony.
pub struct CeremonyOrchestrator {
    phantom_root: PathBuf,
    mirror: Mutex<CeremonyStateFile>,
}

impl CeremonyOrchestrator {
    pub fn new(phantom_root: PathBuf) -> Self {
        let disk = load(&phantom_root);
        Self {
            phantom_root,
            mirror: Mutex::new(disk),
        }
    }

    /// Replace the in-memory mirror from disk (tests / external writers).
    pub fn reload_from_disk(&self) -> Result<(), String> {
        let disk = load(&self.phantom_root);
        let mut g = self.mirror.lock().map_err(|e| e.to_string())?;
        *g = disk;
        Ok(())
    }

    fn with_mirror_mut<T>(&self, f: impl FnOnce(&mut CeremonyStateFile) -> Result<T, String>) -> Result<T, String> {
        let mut g = self.mirror.lock().map_err(|e| e.to_string())?;
        f(&mut g)
    }

    fn persist_locked(state: &CeremonyStateFile, root: &Path) -> Result<(), String> {
        atomic_write(root, state)
    }

    fn chronicle(
        root: &Path,
        event_type: &str,
        correlation_id: Option<&str>,
        act: Option<&str>,
        before: &str,
        after: &str,
        outcome: Option<&str>,
        summary: &str,
    ) -> Result<(), String> {
        append_ceremony_line(
            root,
            &CeremonyChronicleLine::new(
                event_type,
                correlation_id.map(String::from),
                act.map(String::from),
                before,
                after,
                outcome.map(String::from),
                summary,
            ),
        )
    }

    /// New correlation ID (UUID v4).
    pub fn new_correlation_id() -> String {
        Uuid::new_v4().to_string()
    }

    /// Read-only status for `ceremony_status()` invoke.
    pub fn ceremony_status(&self) -> Result<CeremonyStatusDto, String> {
        let g = self.mirror.lock().map_err(|e| e.to_string())?;
        Ok(CeremonyStatusDto::from_mirror(
            &g.s_ceremony,
            g.correlation_id.as_deref(),
            g.outcome_class.as_deref(),
            &[],
            g.last_completed_act.as_deref(),
        ))
    }

    /// Phase 12 — real operational predicate evaluation.
    ///
    /// Doctrine-aligned, side-effect free, never depends on WAN. Inspects on-disk
    /// ceremony artifacts and the in-memory mirror; returns a structured
    /// `OperationalEvaluation` with per-clause detail.
    pub fn operational_evaluate(&self) -> OperationalEvaluation {
        match self.mirror.lock() {
            Ok(g) => super::predicate::evaluate_operational(&self.phantom_root, &g),
            Err(_) => OperationalEvaluation::default(),
        }
    }

    /// Backwards-compatible alias retained so callers built against the Phase 11
    /// surface continue to compile. Now delegates to the real predicate engine.
    pub fn operational_evaluate_stub(&self) -> OperationalEvaluation {
        self.operational_evaluate()
    }

    /// Project `S_ceremony` to legacy `AppPhase` (Phase 3 §2.2).
    pub fn project_to_app_phase(s: &str) -> AppPhase {
        match CeremonyPhase::parse(s) {
            Some(CeremonyPhase::Operational) => AppPhase::Deployed,
            Some(
                CeremonyPhase::Materialize
                | CeremonyPhase::Configure
                | CeremonyPhase::Attest
                | CeremonyPhase::Discover
                | CeremonyPhase::Register
                | CeremonyPhase::Recovery
                | CeremonyPhase::Teardown,
            ) => AppPhase::Deploying,
            Some(CeremonyPhase::Idle) | Some(CeremonyPhase::Placement) | None => AppPhase::FrontPorch,
        }
    }

    /// Act A only: validate placement, write placement file, set `CS_PLACEMENT`, chronicle entry/exit, persist.
    /// Does not advance beyond `CS_PLACEMENT` (no Act B–F).
    pub async fn commit_placement(
        &self,
        host: String,
        port: u16,
        device_label: String,
        identity_fingerprint: String,
    ) -> Result<CeremonyStatusDto, String> {
        act_a::write_placement_file(
            &self.phantom_root,
            &host,
            port,
            &device_label,
            &identity_fingerprint,
        )
        .await?;

        self.with_mirror_mut(|m| {
            let before = m.s_ceremony.clone();
            let corr = m
                .correlation_id
                .clone()
                .unwrap_or_else(CeremonyOrchestrator::new_correlation_id);
            m.correlation_id = Some(corr.clone());

            Self::chronicle(
                &self.phantom_root,
                "act_entry",
                Some(&corr),
                Some("A"),
                &before,
                &before,
                None,
                "Act A entry (placement)",
            )?;

            m.s_ceremony = CeremonyPhase::Placement.as_str().to_string();
            m.last_completed_act = Some("A".to_string());
            m.outcome_class = None;
            let after = m.s_ceremony.clone();

            Self::chronicle(
                &self.phantom_root,
                "act_exit",
                Some(&corr),
                Some("A"),
                &before,
                &after,
                None,
                "Act A exit (placement committed)",
            )?;

            Self::persist_locked(m, &self.phantom_root)?;
            Ok(CeremonyStatusDto::from_mirror(
                &after,
                m.correlation_id.as_deref(),
                None,
                &[],
                m.last_completed_act.as_deref(),
            ))
        })
    }

    /// Act B: validate placement, materialize venv / pip / engine (steps 0–2), chronicle, persist.
    /// Success → `CS_MATERIALIZE`; failure → remain `CS_PLACEMENT`, `outcome_class = FAILED`, recovery target B.
    pub async fn run_act_b(
        &self,
        engine_source: PathBuf,
        offline_bundle: Option<PathBuf>,
        app_handle: Option<tauri::AppHandle>,
    ) -> Result<CeremonyStatusDto, String> {
        let corr = {
            let g = self.mirror.lock().map_err(|e| e.to_string())?;
            let phase = CeremonyPhase::parse(&g.s_ceremony).unwrap_or(CeremonyPhase::Idle);
            if !can_run_act_b(phase) {
                return Err(format!(
                    "Act B requires CS_PLACEMENT, got {}",
                    g.s_ceremony
                ));
            }
            g.correlation_id
                .clone()
                .ok_or_else(|| "correlation_id required before Act B".to_string())?
        };

        act_b::validate_placement_prerequisites(&self.phantom_root).await?;

        let before = CeremonyPhase::Placement.as_str();

        Self::chronicle(
            &self.phantom_root,
            "act_entry",
            Some(&corr),
            Some("B"),
            before,
            before,
            None,
            "Act B entry (materialize)",
        )?;

        let phantom_root = self.phantom_root.clone();
        let mat = act_b::execute_materialize(
            &phantom_root,
            &engine_source,
            offline_bundle,
            app_handle,
        )
        .await;

        match mat {
            Ok(()) => self.with_mirror_mut(|m| {
                let after = CeremonyPhase::Materialize.as_str().to_string();
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("B"),
                    before,
                    &after,
                    None,
                    "Act B exit (materialize complete)",
                )?;
                m.s_ceremony = after.clone();
                m.last_completed_act = Some("B".to_string());
                m.outcome_class = None;
                m.recovery_target_act = None;
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &after,
                    m.correlation_id.as_deref(),
                    None,
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
            Err(e) => self.with_mirror_mut(|m| {
                let placement = CeremonyPhase::Placement.as_str();
                let summary = format!("Act B failed: {e}");
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("B"),
                    placement,
                    placement,
                    Some("FAILED"),
                    &summary,
                )?;
                append_recovery_target(&self.phantom_root, Some(&corr), "B")?;
                m.outcome_class = Some("FAILED".to_string());
                m.recovery_target_act = Some("B".to_string());
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &m.s_ceremony,
                    m.correlation_id.as_deref(),
                    m.outcome_class.as_deref(),
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
        }
    }

    /// Act C: discovery (LAN + optional offline synthetic), snapshot persist, chronicle, state.
    /// Success → `CS_DISCOVER`; empty candidates → stay `CS_MATERIALIZE` with `PARTIAL`; failure → `FAILED`, recovery C.
    pub async fn run_act_c(
        &self,
        offline_bundle: Option<PathBuf>,
        app_handle: Option<tauri::AppHandle>,
    ) -> Result<CeremonyStatusDto, String> {
        let corr = {
            let g = self.mirror.lock().map_err(|e| e.to_string())?;
            let phase = CeremonyPhase::parse(&g.s_ceremony).unwrap_or(CeremonyPhase::Idle);
            if !can_run_act_c(phase) {
                return Err(format!(
                    "Act C requires CS_MATERIALIZE, got {}",
                    g.s_ceremony
                ));
            }
            g.correlation_id
                .clone()
                .ok_or_else(|| "correlation_id required before Act C".to_string())?
        };

        act_c::validate_materialized_environment(&self.phantom_root)?;

        let before = CeremonyPhase::Materialize.as_str();

        Self::chronicle(
            &self.phantom_root,
            "act_entry",
            Some(&corr),
            Some("C"),
            before,
            before,
            None,
            "Act C entry (discovery)",
        )?;

        let phantom_root = self.phantom_root.clone();
        let discovery = act_c::execute_discovery(
            &phantom_root,
            &corr,
            offline_bundle,
            app_handle,
        )
        .await;

        let materialize = CeremonyPhase::Materialize.as_str();

        match discovery {
            ActCDiscoveryOutcome::Success { snapshot } => {
                let snap_id = snapshot.snapshot_id.clone();
                if let Err(e) = act_c::persist_discovery_snapshot(&self.phantom_root, &snapshot) {
                    let msg = format!("persist discovery snapshot: {e}");
                    return self.with_mirror_mut(|m| {
                        let summary = format!("Act C failed: {msg}");
                        Self::chronicle(
                            &self.phantom_root,
                            "act_exit",
                            Some(&corr),
                            Some("C"),
                            materialize,
                            materialize,
                            Some("FAILED"),
                            &summary,
                        )?;
                        append_recovery_target_for_phase(
                            &self.phantom_root,
                            Some(&corr),
                            "C",
                            materialize,
                        )?;
                        m.outcome_class = Some("FAILED".to_string());
                        m.recovery_target_act = Some("C".to_string());
                        Self::persist_locked(m, &self.phantom_root)?;
                        Ok(CeremonyStatusDto::from_mirror(
                            &m.s_ceremony,
                            m.correlation_id.as_deref(),
                            m.outcome_class.as_deref(),
                            &[],
                            m.last_completed_act.as_deref(),
                        ))
                    });
                }
                self.with_mirror_mut(|m| {
                    let after = CeremonyPhase::Discover.as_str().to_string();
                    Self::chronicle(
                        &self.phantom_root,
                        "act_exit",
                        Some(&corr),
                        Some("C"),
                        before,
                        &after,
                        None,
                        "Act C exit (discovery complete)",
                    )?;
                    m.s_ceremony = after.clone();
                    m.last_completed_act = Some("C".to_string());
                    m.outcome_class = None;
                    m.recovery_target_act = None;
                    m.snapshot_id = Some(snap_id);
                    Self::persist_locked(m, &self.phantom_root)?;
                    Ok(CeremonyStatusDto::from_mirror(
                        &after,
                        m.correlation_id.as_deref(),
                        None,
                        &[],
                        m.last_completed_act.as_deref(),
                    ))
                })
            }
            ActCDiscoveryOutcome::Partial { snapshot } => {
                let snap_id = snapshot.snapshot_id.clone();
                if let Err(e) = act_c::persist_discovery_snapshot(&self.phantom_root, &snapshot) {
                    let msg = format!("persist discovery snapshot: {e}");
                    return self.with_mirror_mut(|m| {
                        let summary = format!("Act C failed: {msg}");
                        Self::chronicle(
                            &self.phantom_root,
                            "act_exit",
                            Some(&corr),
                            Some("C"),
                            materialize,
                            materialize,
                            Some("FAILED"),
                            &summary,
                        )?;
                        append_recovery_target_for_phase(
                            &self.phantom_root,
                            Some(&corr),
                            "C",
                            materialize,
                        )?;
                        m.outcome_class = Some("FAILED".to_string());
                        m.recovery_target_act = Some("C".to_string());
                        Self::persist_locked(m, &self.phantom_root)?;
                        Ok(CeremonyStatusDto::from_mirror(
                            &m.s_ceremony,
                            m.correlation_id.as_deref(),
                            m.outcome_class.as_deref(),
                            &[],
                            m.last_completed_act.as_deref(),
                        ))
                    });
                }
                self.with_mirror_mut(|m| {
                    Self::chronicle(
                        &self.phantom_root,
                        "act_exit",
                        Some(&corr),
                        Some("C"),
                        materialize,
                        materialize,
                        Some("PARTIAL"),
                        "Act C exit (discovery empty / partial)",
                    )?;
                    m.s_ceremony = materialize.to_string();
                    m.last_completed_act = Some("C".to_string());
                    m.outcome_class = Some("PARTIAL".to_string());
                    m.recovery_target_act = None;
                    m.snapshot_id = Some(snap_id);
                    Self::persist_locked(m, &self.phantom_root)?;
                    Ok(CeremonyStatusDto::from_mirror(
                        materialize,
                        m.correlation_id.as_deref(),
                        m.outcome_class.as_deref(),
                        &[],
                        m.last_completed_act.as_deref(),
                    ))
                })
            }
            ActCDiscoveryOutcome::Failed { detail } => self.with_mirror_mut(|m| {
                let summary = format!("Act C failed: {detail}");
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("C"),
                    materialize,
                    materialize,
                    Some("FAILED"),
                    &summary,
                )?;
                append_recovery_target_for_phase(
                    &self.phantom_root,
                    Some(&corr),
                    "C",
                    materialize,
                )?;
                m.outcome_class = Some("FAILED".to_string());
                m.recovery_target_act = Some("C".to_string());
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &m.s_ceremony,
                    m.correlation_id.as_deref(),
                    m.outcome_class.as_deref(),
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
        }
    }

    /// Act D: validate discovery snapshot, write `phantom_config.json` + attestation manifest for Act E.
    /// Success → `CS_CONFIGURE`; failure → remain `CS_DISCOVER`, `FAILED`, recovery target D.
    pub async fn run_act_d(&self) -> Result<CeremonyStatusDto, String> {
        let corr = {
            let g = self.mirror.lock().map_err(|e| e.to_string())?;
            let phase = CeremonyPhase::parse(&g.s_ceremony).unwrap_or(CeremonyPhase::Idle);
            if !can_run_act_d(phase) {
                return Err(format!(
                    "Act D requires CS_DISCOVER, got {}",
                    g.s_ceremony
                ));
            }
            g.correlation_id
                .clone()
                .ok_or_else(|| "correlation_id required before Act D".to_string())?
        };

        let snap_id = {
            let g = self.mirror.lock().map_err(|e| e.to_string())?;
            g.snapshot_id.clone()
        };

        let snapshot = act_d::validate_configure_prerequisites(
            &self.phantom_root,
            &corr,
            snap_id.as_deref(),
        )
        .await?;

        let before = CeremonyPhase::Discover.as_str();

        Self::chronicle(
            &self.phantom_root,
            "act_entry",
            Some(&corr),
            Some("D"),
            before,
            before,
            None,
            "Act D entry (configure)",
        )?;

        let phantom_root = self.phantom_root.clone();
        let cfg = act_d::execute_configure_writes(&phantom_root, &snapshot).await;

        let discover = CeremonyPhase::Discover.as_str();

        match cfg {
            Ok(()) => self.with_mirror_mut(|m| {
                let after = CeremonyPhase::Configure.as_str().to_string();
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("D"),
                    before,
                    &after,
                    None,
                    "Act D exit (configure complete)",
                )?;
                m.s_ceremony = after.clone();
                m.last_completed_act = Some("D".to_string());
                m.outcome_class = None;
                m.recovery_target_act = None;
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &after,
                    m.correlation_id.as_deref(),
                    None,
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
            Err(e) => self.with_mirror_mut(|m| {
                let summary = format!("Act D failed: {e}");
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("D"),
                    discover,
                    discover,
                    Some("FAILED"),
                    &summary,
                )?;
                append_recovery_target_for_phase(
                    &self.phantom_root,
                    Some(&corr),
                    "D",
                    discover,
                )?;
                m.outcome_class = Some("FAILED".to_string());
                m.recovery_target_act = Some("D".to_string());
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &m.s_ceremony,
                    m.correlation_id.as_deref(),
                    m.outcome_class.as_deref(),
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
        }
    }

    /// Act E: validate manifest + config, controller `/health`, engine; success/degraded → `CS_ATTEST`.
    /// Failure → remain `CS_CONFIGURE`, `FAILED`, recovery E.
    pub async fn run_act_e(&self) -> Result<CeremonyStatusDto, String> {
        let corr = {
            let g = self.mirror.lock().map_err(|e| e.to_string())?;
            let phase = CeremonyPhase::parse(&g.s_ceremony).unwrap_or(CeremonyPhase::Idle);
            if !can_run_act_e(phase) {
                return Err(format!(
                    "Act E requires CS_CONFIGURE, got {}",
                    g.s_ceremony
                ));
            }
            g.correlation_id
                .clone()
                .ok_or_else(|| "correlation_id required before Act E".to_string())?
        };

        let _manifest =
            act_e::validate_attest_prerequisites(&self.phantom_root, &corr).await?;

        let before = CeremonyPhase::Configure.as_str();

        Self::chronicle(
            &self.phantom_root,
            "act_entry",
            Some(&corr),
            Some("E"),
            before,
            before,
            None,
            "Act E entry (attest)",
        )?;

        let phantom_root = self.phantom_root.clone();
        let attest = act_e::execute_attestation(&phantom_root).await;

        let configure = CeremonyPhase::Configure.as_str();

        match attest {
            ActEAttestationOutcome::Success => self.with_mirror_mut(|m| {
                let after = CeremonyPhase::Attest.as_str().to_string();
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("E"),
                    before,
                    &after,
                    None,
                    "Act E exit (attestation success)",
                )?;
                m.s_ceremony = after.clone();
                m.last_completed_act = Some("E".to_string());
                m.outcome_class = None;
                m.recovery_target_act = None;
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &after,
                    m.correlation_id.as_deref(),
                    None,
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
            ActEAttestationOutcome::Degraded { detail } => self.with_mirror_mut(|m| {
                let after = CeremonyPhase::Attest.as_str().to_string();
                let summary = format!("Act E exit (attestation degraded): {detail}");
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("E"),
                    before,
                    &after,
                    Some(OUTCOME_SUCCEEDED_WITH_WARNINGS),
                    &summary,
                )?;
                m.s_ceremony = after.clone();
                m.last_completed_act = Some("E".to_string());
                m.outcome_class = Some(OUTCOME_SUCCEEDED_WITH_WARNINGS.to_string());
                m.recovery_target_act = None;
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &after,
                    m.correlation_id.as_deref(),
                    m.outcome_class.as_deref(),
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
            ActEAttestationOutcome::Failed { detail } => self.with_mirror_mut(|m| {
                let summary = format!("Act E failed: {detail}");
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("E"),
                    configure,
                    configure,
                    Some("FAILED"),
                    &summary,
                )?;
                append_recovery_target_for_phase(
                    &self.phantom_root,
                    Some(&corr),
                    "E",
                    configure,
                )?;
                m.outcome_class = Some("FAILED".to_string());
                m.recovery_target_act = Some("E".to_string());
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &m.s_ceremony,
                    m.correlation_id.as_deref(),
                    m.outcome_class.as_deref(),
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
        }
    }

    /// Act F: trust + `/workers/register`; full success → `CS_OPERATIONAL`; partial → `CS_OPERATIONAL` + `PARTIAL`;
    /// failure → remain `CS_ATTEST`, `FAILED`, recovery F.
    pub async fn run_act_f(&self) -> Result<CeremonyStatusDto, String> {
        let corr = {
            let g = self.mirror.lock().map_err(|e| e.to_string())?;
            let phase = CeremonyPhase::parse(&g.s_ceremony).unwrap_or(CeremonyPhase::Idle);
            if !can_run_act_f(phase) {
                return Err(format!(
                    "Act F requires CS_ATTEST, got {}",
                    g.s_ceremony
                ));
            }
            g.correlation_id
                .clone()
                .ok_or_else(|| "correlation_id required before Act F".to_string())?
        };

        let manifest =
            act_f::validate_register_prerequisites(&self.phantom_root, &corr).await?;

        let before = CeremonyPhase::Attest.as_str();

        Self::chronicle(
            &self.phantom_root,
            "act_entry",
            Some(&corr),
            Some("F"),
            before,
            before,
            None,
            "Act F entry (register)",
        )?;

        let phantom_root = self.phantom_root.clone();
        let reg = act_f::execute_registration(&phantom_root, &manifest).await;

        let attest = CeremonyPhase::Attest.as_str();

        match reg {
            ActFRegisterOutcome::Success => self.with_mirror_mut(|m| {
                let after = CeremonyPhase::Operational.as_str().to_string();
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("F"),
                    before,
                    &after,
                    None,
                    "Act F exit (registration success)",
                )?;
                m.s_ceremony = after.clone();
                m.last_completed_act = Some("F".to_string());
                m.outcome_class = None;
                m.recovery_target_act = None;
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &after,
                    m.correlation_id.as_deref(),
                    None,
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
            ActFRegisterOutcome::Partial { detail } => self.with_mirror_mut(|m| {
                let after = CeremonyPhase::Operational.as_str().to_string();
                let summary = format!("Act F exit (partial registration): {detail}");
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("F"),
                    before,
                    &after,
                    Some(OUTCOME_PARTIAL_REGISTRATION),
                    &summary,
                )?;
                m.s_ceremony = after.clone();
                m.last_completed_act = Some("F".to_string());
                m.outcome_class = Some(OUTCOME_PARTIAL_REGISTRATION.to_string());
                m.recovery_target_act = None;
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &after,
                    m.correlation_id.as_deref(),
                    m.outcome_class.as_deref(),
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
            ActFRegisterOutcome::Failed { detail } => self.with_mirror_mut(|m| {
                let summary = format!("Act F failed: {detail}");
                Self::chronicle(
                    &self.phantom_root,
                    "act_exit",
                    Some(&corr),
                    Some("F"),
                    attest,
                    attest,
                    Some("FAILED"),
                    &summary,
                )?;
                append_recovery_target_for_phase(
                    &self.phantom_root,
                    Some(&corr),
                    "F",
                    attest,
                )?;
                m.outcome_class = Some("FAILED".to_string());
                m.recovery_target_act = Some("F".to_string());
                Self::persist_locked(m, &self.phantom_root)?;
                Ok(CeremonyStatusDto::from_mirror(
                    &m.s_ceremony,
                    m.correlation_id.as_deref(),
                    m.outcome_class.as_deref(),
                    &[],
                    m.last_completed_act.as_deref(),
                ))
            }),
        }
    }

    /// Phase 12 — explicitly enter `CS_RECOVERY`.
    ///
    /// Requires a `recovery_target_act` to have been recorded (i.e. an Act exit
    /// classified as `FAILED`). Writes a `recovery_entry` chronicle line, sets
    /// `S_ceremony=CS_RECOVERY`, and returns the new status. Does not run any Act.
    /// Idempotent: re-entering recovery from `CS_RECOVERY` is a no-op chronicle.
    pub fn enter_recovery(&self) -> Result<CeremonyStatusDto, String> {
        self.with_mirror_mut(|m| {
            let target = m
                .recovery_target_act
                .clone()
                .ok_or_else(|| "no recovery_target_act set; nothing to recover".to_string())?;
            let corr = m.correlation_id.clone();
            let before = m.s_ceremony.clone();
            Self::chronicle(
                &self.phantom_root,
                "recovery_entry",
                corr.as_deref(),
                Some(&target),
                &before,
                CeremonyPhase::Recovery.as_str(),
                None,
                &format!("entering recovery for Act {target}"),
            )?;
            m.s_ceremony = CeremonyPhase::Recovery.as_str().to_string();
            Self::persist_locked(m, &self.phantom_root)?;
            Ok(CeremonyStatusDto::from_mirror(
                &m.s_ceremony,
                m.correlation_id.as_deref(),
                m.outcome_class.as_deref(),
                &[],
                m.last_completed_act.as_deref(),
            ))
        })
    }

    /// Phase 12 — resume the ceremony from the recorded `recovery_target_act`.
    ///
    /// Behavior:
    /// - Reads `recovery_target_act` from the mirror (B–F).
    /// - Restores the appropriate "ready-to-retry" predecessor phase
    ///   (B→PLACEMENT, C→MATERIALIZE, D→DISCOVER, E→CONFIGURE, F→ATTEST).
    /// - Writes a `recovery_exit` chronicle line and clears `outcome_class`.
    /// - Re-runs the failing Act through the normal `run_act_*` path so all
    ///   invariants and chronicle semantics are preserved.
    ///
    /// Required inputs depend on the target Act:
    /// - `B` requires `engine_source` (and may take `offline_bundle`).
    /// - `C` may take `offline_bundle`.
    /// - `D`, `E`, `F` require no extra inputs.
    pub async fn resume_from_recovery_target(
        &self,
        engine_source: Option<PathBuf>,
        offline_bundle: Option<PathBuf>,
        app_handle: Option<tauri::AppHandle>,
    ) -> Result<CeremonyStatusDto, String> {
        let (target, restore_phase) = {
            let g = self.mirror.lock().map_err(|e| e.to_string())?;
            let target = g
                .recovery_target_act
                .clone()
                .ok_or_else(|| "no recovery_target_act set; nothing to resume".to_string())?;
            let restore = match target.as_str() {
                "B" => CeremonyPhase::Placement,
                "C" => CeremonyPhase::Materialize,
                "D" => CeremonyPhase::Discover,
                "E" => CeremonyPhase::Configure,
                "F" => CeremonyPhase::Attest,
                other => {
                    return Err(format!(
                        "unknown recovery target act {other:?}; expected one of B/C/D/E/F"
                    ))
                }
            };
            (target, restore)
        };

        self.with_mirror_mut(|m| {
            let corr = m.correlation_id.clone();
            let before = m.s_ceremony.clone();
            let after = restore_phase.as_str();
            Self::chronicle(
                &self.phantom_root,
                "recovery_exit",
                corr.as_deref(),
                Some(&target),
                &before,
                after,
                None,
                &format!("resuming Act {target} from {before}"),
            )?;
            m.s_ceremony = after.to_string();
            m.outcome_class = None;
            Self::persist_locked(m, &self.phantom_root)?;
            Ok(())
        })?;

        match target.as_str() {
            "B" => {
                let engine = engine_source.ok_or_else(|| {
                    "engine_source required to resume Act B from recovery".to_string()
                })?;
                self.run_act_b(engine, offline_bundle, app_handle).await
            }
            "C" => self.run_act_c(offline_bundle, app_handle).await,
            "D" => self.run_act_d().await,
            "E" => self.run_act_e().await,
            "F" => self.run_act_f().await,
            other => Err(format!("unsupported recovery target {other:?}")),
        }
    }

    /// Full ceremony dry-run on this `phantom_root`: **A → B → C → D → E → F → CS_OPERATIONAL**.
    ///
    /// Requires **`CS_IDLE`**. Uses fixed placement targets for Act A. Act C needs
    /// `offline_bundle: Some(dir)` so offline synthetic discovery yields a candidate without LAN.
    ///
    /// Temporarily sets `PHANTOM_CEREMONY_ACT_E_SKIP_CONTROLLER_HEALTH` and
    /// `PHANTOM_CEREMONY_ACT_F_SKIP_REGISTER` for the duration of this call (restored on return).
    pub async fn dry_run_stub_graph(
        &self,
        engine_source: PathBuf,
        offline_bundle: Option<PathBuf>,
        app_handle: Option<tauri::AppHandle>,
    ) -> Result<CeremonyStatusDto, String> {
        let bundle = offline_bundle.ok_or_else(|| {
            "dry_run_stub_graph: offline_bundle must be Some(empty directory) for synthetic Act C"
                .to_string()
        })?;

        {
            let g = self.mirror.lock().map_err(|e| e.to_string())?;
            let phase = CeremonyPhase::parse(&g.s_ceremony).unwrap_or(CeremonyPhase::Idle);
            if phase != CeremonyPhase::Idle {
                return Err(format!(
                    "dry_run_stub_graph requires CS_IDLE, got {}",
                    g.s_ceremony
                ));
            }
        }

        let _net_stub = DryRunCeremonyNetworkStubGuard::arm();

        self.commit_placement(
            DRY_RUN_PLACEMENT_HOST.to_string(),
            DRY_RUN_PLACEMENT_PORT,
            DRY_RUN_DEVICE_LABEL.to_string(),
            DRY_RUN_IDENTITY_FP.to_string(),
        )
        .await
        .map_err(|e| format!("dry_run Act A: {e}"))?;

        let st_b = self
            .run_act_b(engine_source, None, app_handle.clone())
            .await
            .map_err(|e| format!("dry_run Act B: {e}"))?;
        if st_b.s_ceremony != CeremonyPhase::Materialize.as_str() || st_b.outcome_class.is_some() {
            return Err(format!(
                "dry_run Act B did not complete to CS_MATERIALIZE (phase {} outcome {:?})",
                st_b.s_ceremony, st_b.outcome_class
            ));
        }

        let st_c = self
            .run_act_c(Some(bundle), app_handle)
            .await
            .map_err(|e| format!("dry_run Act C: {e}"))?;
        if st_c.s_ceremony != CeremonyPhase::Discover.as_str() || st_c.outcome_class.is_some() {
            return Err(format!(
                "dry_run Act C did not complete to CS_DISCOVER (phase {} outcome {:?})",
                st_c.s_ceremony, st_c.outcome_class
            ));
        }

        let st_d = self
            .run_act_d()
            .await
            .map_err(|e| format!("dry_run Act D: {e}"))?;
        if st_d.s_ceremony != CeremonyPhase::Configure.as_str() || st_d.outcome_class.is_some() {
            return Err(format!(
                "dry_run Act D did not complete to CS_CONFIGURE (phase {} outcome {:?})",
                st_d.s_ceremony, st_d.outcome_class
            ));
        }

        let st_e = self.run_act_e().await.map_err(|e| format!("dry_run Act E: {e}"))?;
        if st_e.s_ceremony != CeremonyPhase::Attest.as_str() {
            return Err(format!(
                "dry_run Act E did not reach {} (phase {} outcome {:?})",
                CeremonyPhase::Attest.as_str(),
                st_e.s_ceremony,
                st_e.outcome_class
            ));
        }

        let st_f = self.run_act_f().await.map_err(|e| format!("dry_run Act F: {e}"))?;
        if st_f.s_ceremony != CeremonyPhase::Operational.as_str() || st_f.outcome_class.is_some()
        {
            return Err(format!(
                "dry_run Act F did not complete cleanly to CS_OPERATIONAL (phase {} outcome {:?})",
                st_f.s_ceremony, st_f.outcome_class
            ));
        }

        Ok(st_f)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[tokio::test]
    async fn ceremony_status_loads_idle() {
        let dir = tempdir().unwrap();
        let root = dir.path().to_path_buf();
        let o = CeremonyOrchestrator::new(root);
        let s = o.ceremony_status().unwrap();
        assert_eq!(s.s_ceremony, "CS_IDLE");
    }

    #[tokio::test]
    async fn full_dry_run_a_through_f_chronicle_and_state() {
        let py = if cfg!(windows) { "python" } else { "python3" };
        let py_ok = tokio::process::Command::new(py)
            .arg("-c")
            .arg("import sys")
            .output()
            .await
            .map(|o| o.status.success())
            .unwrap_or(false);
        if !py_ok {
            return;
        }

        let dir = tempdir().unwrap();
        let root = dir.path().to_path_buf();
        let engine = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("phantom_core");
        if !engine.join("run.py").is_file() {
            return;
        }

        let o = CeremonyOrchestrator::new(root.clone());
        let bundle = root.join("offline_bundle");
        std::fs::create_dir_all(&bundle).unwrap();

        let st = o
            .dry_run_stub_graph(engine, Some(bundle), None)
            .await
            .expect("full dry-run");
        assert_eq!(st.s_ceremony, CeremonyPhase::Operational.as_str());
        assert!(st.outcome_class.is_none());

        let disk = load(&root);
        assert_eq!(disk.s_ceremony, CeremonyPhase::Operational.as_str());
        assert_eq!(disk.last_completed_act.as_deref(), Some("F"));
        assert_eq!(disk.outcome_class, None);
        assert_eq!(disk.recovery_target_act, None);

        let chron_path = root.join("state").join("ceremony_chronicle.jsonl");
        let raw = std::fs::read_to_string(&chron_path).unwrap();
        let n_entry = raw
            .lines()
            .filter(|l| !l.is_empty())
            .filter(|l| {
                serde_json::from_str::<serde_json::Value>(l)
                    .ok()
                    .and_then(|v| v.get("eventType").and_then(|x| x.as_str()).map(|t| t == "act_entry"))
                    .unwrap_or(false)
            })
            .count();
        let n_exit = raw
            .lines()
            .filter(|l| !l.is_empty())
            .filter(|l| {
                serde_json::from_str::<serde_json::Value>(l)
                    .ok()
                    .and_then(|v| v.get("eventType").and_then(|x| x.as_str()).map(|t| t == "act_exit"))
                    .unwrap_or(false)
            })
            .count();
        assert_eq!(n_entry, 6, "expected 6 act_entry (A–F): {raw}");
        assert_eq!(n_exit, 6, "expected 6 act_exit (A–F): {raw}");
        for line in raw.lines().filter(|l| !l.is_empty()) {
            let v: serde_json::Value = serde_json::from_str(line).unwrap();
            assert_eq!(v["schema_version"], "1");
        }
    }
}
