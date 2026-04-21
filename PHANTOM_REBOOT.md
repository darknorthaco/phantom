# Phantom Reboot Charter (vNext)

This document starts the "new Phantom" track with a clean contract:

- Keep the doctrine and constitutional ceremony model.
- Keep proven security and orchestration primitives.
- Remove legacy entrypoints from the canonical execution path.
- Rebuild runtime surfaces from small, testable modules.

## What We Preserve

1. Ceremony as canonical policy engine (Acts A-F).
2. Explicit operator consent and MANUAL-first control.
3. WAN requires TLS; no implicit plaintext fallback.
4. Chronicle-style audit events for every state transition.
5. GPU-aware worker scoring and deterministic task routing.

## What We Replace

1. Legacy installer/package entrypoints in user-facing flows.
2. Mixed ownership of deployment state across multiple modules.
3. Coupling between desktop packaging complexity and core runtime correctness.

## vNext Acceptance Gates

1. Single canonical state machine owns ceremony transitions.
2. Every transition is validated, deterministic, and auditable.
3. Controller runtime can boot from clean install without legacy flags.
4. Security policy fails closed (WAN + no TLS is rejected).
5. Adversarial regression tests can run against the state machine and scheduler.

## Initial Scaffold

`phantom_next/` contains the first executable primitives for the reboot:

- `ceremony.py` - canonical ceremony phases and transition guardrails.
- `orchestrator.py` - worker/task models and GPU-aware worker selection.
- `security.py` - strict runtime policy validation.
- `tests/` - baseline tests proving core invariants.

This scaffold is intentionally minimal. It is the starting point for rebuilding
the canonical runtime around doctrine-first guarantees while shedding legacy
surface area.
