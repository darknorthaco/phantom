//! Phase 11 — Unified ceremony orchestrator, state file, DTOs, Act A (placement).

pub mod act_a;
pub mod act_b;
pub mod act_c;
pub mod act_d;
pub mod act_e;
pub mod act_f;
pub mod ceremony_chronicle;
pub mod dto;
pub mod orchestrator;
pub mod phase;
pub mod predicate;
pub mod preflight;
pub mod state_file;

pub use dto::{
    ActDetailDto, CeremonyStatusDto, DiscoverySnapshot, OperationalEvaluation,
    OperationalEvaluationClause, ProcessStatus, RegistrationAttempt,
};
pub use orchestrator::CeremonyOrchestrator;
pub use phase::CeremonyPhase;
pub use state_file::{atomic_write, load, CeremonyStateFile};
