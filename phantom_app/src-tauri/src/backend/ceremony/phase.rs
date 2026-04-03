//! Canonical `S_ceremony` phases (Phase 2). On-disk / DTO values are `CS_*` strings.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CeremonyPhase {
    Idle,
    Placement,
    Materialize,
    Configure,
    Attest,
    Discover,
    Register,
    Operational,
    Recovery,
    Teardown,
}

impl CeremonyPhase {
    pub fn as_str(self) -> &'static str {
        match self {
            CeremonyPhase::Idle => "CS_IDLE",
            CeremonyPhase::Placement => "CS_PLACEMENT",
            CeremonyPhase::Materialize => "CS_MATERIALIZE",
            CeremonyPhase::Configure => "CS_CONFIGURE",
            CeremonyPhase::Attest => "CS_ATTEST",
            CeremonyPhase::Discover => "CS_DISCOVER",
            CeremonyPhase::Register => "CS_REGISTER",
            CeremonyPhase::Operational => "CS_OPERATIONAL",
            CeremonyPhase::Recovery => "CS_RECOVERY",
            CeremonyPhase::Teardown => "CS_TEARDOWN",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "CS_IDLE" => CeremonyPhase::Idle,
            "CS_PLACEMENT" => CeremonyPhase::Placement,
            "CS_MATERIALIZE" => CeremonyPhase::Materialize,
            "CS_CONFIGURE" => CeremonyPhase::Configure,
            "CS_ATTEST" => CeremonyPhase::Attest,
            "CS_DISCOVER" => CeremonyPhase::Discover,
            "CS_REGISTER" => CeremonyPhase::Register,
            "CS_OPERATIONAL" => CeremonyPhase::Operational,
            "CS_RECOVERY" => CeremonyPhase::Recovery,
            "CS_TEARDOWN" => CeremonyPhase::Teardown,
            _ => return None,
        })
    }
}

/// True when Act B (materialize) may run per doctrine.
pub fn can_run_act_b(current: CeremonyPhase) -> bool {
    current == CeremonyPhase::Placement
}

/// True when Act C (discovery) may run per doctrine.
pub fn can_run_act_c(current: CeremonyPhase) -> bool {
    current == CeremonyPhase::Materialize
}

/// True when Act D (configure) may run per doctrine.
pub fn can_run_act_d(current: CeremonyPhase) -> bool {
    current == CeremonyPhase::Discover
}

/// True when Act E (attest) may run per doctrine.
pub fn can_run_act_e(current: CeremonyPhase) -> bool {
    current == CeremonyPhase::Configure
}

/// True when Act F (register) may run per doctrine (`CS_ATTEST` only).
pub fn can_run_act_f(current: CeremonyPhase) -> bool {
    current == CeremonyPhase::Attest
}
