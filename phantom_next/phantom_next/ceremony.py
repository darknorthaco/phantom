"""Canonical ceremony state machine for Phantom vNext."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional


class CeremonyPhase(str, Enum):
    IDLE = "CS_IDLE"
    PLACEMENT = "CS_PLACEMENT"
    MATERIALIZE = "CS_MATERIALIZE"
    DISCOVER = "CS_DISCOVER"
    CONFIGURE = "CS_CONFIGURE"
    ATTEST = "CS_ATTEST"
    REGISTER = "CS_REGISTER"
    OPERATIONAL = "CS_OPERATIONAL"


_ALLOWED_TRANSITIONS = {
    CeremonyPhase.IDLE: {CeremonyPhase.PLACEMENT},
    CeremonyPhase.PLACEMENT: {CeremonyPhase.MATERIALIZE},
    CeremonyPhase.MATERIALIZE: {CeremonyPhase.DISCOVER},
    CeremonyPhase.DISCOVER: {CeremonyPhase.CONFIGURE},
    CeremonyPhase.CONFIGURE: {CeremonyPhase.ATTEST},
    CeremonyPhase.ATTEST: {CeremonyPhase.REGISTER},
    CeremonyPhase.REGISTER: {CeremonyPhase.OPERATIONAL},
    CeremonyPhase.OPERATIONAL: set(),
}


@dataclass(frozen=True)
class ChronicleEvent:
    timestamp_utc: str
    correlation_id: str
    before: CeremonyPhase
    after: CeremonyPhase
    outcome: str
    summary: str


@dataclass
class CeremonyStateMachine:
    """Single owner of ceremony transition state."""

    correlation_id: str
    phase: CeremonyPhase = CeremonyPhase.IDLE
    history: List[ChronicleEvent] = field(default_factory=list)
    last_completed_act: Optional[str] = None

    def transition(self, next_phase: CeremonyPhase, *, summary: str) -> ChronicleEvent:
        allowed = _ALLOWED_TRANSITIONS[self.phase]
        if next_phase not in allowed:
            raise ValueError(
                f"invalid ceremony transition: {self.phase.value} -> {next_phase.value}"
            )

        event = ChronicleEvent(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            correlation_id=self.correlation_id,
            before=self.phase,
            after=next_phase,
            outcome="SUCCEEDED",
            summary=summary,
        )
        self.phase = next_phase
        completed_act = _phase_to_act(next_phase)
        if completed_act is not None:
            self.last_completed_act = completed_act
        self.history.append(event)
        return event

    @property
    def operational(self) -> bool:
        return self.phase == CeremonyPhase.OPERATIONAL


def _phase_to_act(phase: CeremonyPhase) -> Optional[str]:
    if phase == CeremonyPhase.PLACEMENT:
        return "A"
    if phase == CeremonyPhase.MATERIALIZE:
        return "B"
    if phase == CeremonyPhase.DISCOVER:
        return "C"
    if phase == CeremonyPhase.CONFIGURE:
        return "D"
    if phase == CeremonyPhase.ATTEST:
        return "E"
    if phase == CeremonyPhase.REGISTER:
        return "F"
    return None
