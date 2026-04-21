# phantom_next

Ground-up Phantom reboot scaffold.

## Purpose

`phantom_next` is a clean-slate runtime foundation that preserves Phantom's
best architecture:

- Ceremony-first governance
- Security-first runtime policy
- Deterministic, GPU-aware orchestration

while intentionally excluding legacy deployment and installer pathways.

## Layout

- `phantom_next/ceremony.py` - phase model + transition validation + chronicle.
- `phantom_next/orchestrator.py` - worker selection and queue orchestration.
- `phantom_next/security.py` - strict deployment policy checks.
- `tests/` - baseline invariant tests.

## Run Tests

From repository root:

`python -m unittest discover -s phantom_next/tests -v`
