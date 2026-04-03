//! Phase 11 — Ceremony DTOs (Rust ↔ TS camelCase parity; no extra public API types).

use serde::{Deserialize, Serialize};

/// `CeremonyStatusDto` — mirrors `S_ceremony` and act progress for UI/consumers.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CeremonyStatusDto {
    #[serde(rename = "sCeremony")]
    pub s_ceremony: String,
    pub correlation_id: Option<String>,
    pub outcome_class: Option<String>,
    pub warnings: Vec<String>,
    pub act_detail: ActDetailDto,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ActDetailDto {
    pub current_act: Option<String>,
    pub last_completed_act: Option<String>,
}

/// Operational predicate decomposition (Phase 2 / Phase 3).
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OperationalEvaluation {
    pub operational: bool,
    pub clauses: Vec<OperationalEvaluationClause>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OperationalEvaluationClause {
    pub id: String,
    pub name: String,
    #[serde(rename = "pass")]
    pub pass: bool,
    pub detail: String,
}

/// Immutable discovery snapshot identity (Phase 3); candidates opaque until Act E is real.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiscoverySnapshot {
    pub snapshot_id: String,
    pub correlation_id: String,
    pub created_at: String,
    pub candidates: Vec<serde_json::Value>,
    pub policy_flags: serde_json::Value,
}

/// One registration run against a snapshot (Phase 3).
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RegistrationAttempt {
    pub correlation_id: String,
    pub snapshot_id: String,
    pub rows: Vec<serde_json::Value>,
    pub aggregate_class: String,
}

/// Local process / bind observation (Phase 3 / Veil).
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessStatus {
    pub pid: Option<u32>,
    pub label: String,
    pub bind_claimed: bool,
    pub detail: String,
}

impl CeremonyStatusDto {
    pub fn from_mirror(
        phase: &str,
        correlation_id: Option<&str>,
        outcome_class: Option<&str>,
        warnings: &[String],
        last_completed_act: Option<&str>,
    ) -> Self {
        Self {
            s_ceremony: phase.to_string(),
            correlation_id: correlation_id.map(String::from),
            outcome_class: outcome_class.map(String::from),
            warnings: warnings.to_vec(),
            act_detail: ActDetailDto {
                current_act: None,
                last_completed_act: last_completed_act.map(String::from),
            },
        }
    }
}

impl Default for OperationalEvaluation {
    fn default() -> Self {
        Self {
            operational: false,
            clauses: Vec::new(),
        }
    }
}
