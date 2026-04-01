# Doctrine Drift Checklist (per release)

Run before tagging a release. Tick each item or record waiver with owner + date.

## Platform parity

- [ ] `python scripts/ci/check_platform_assumptions.py` passes locally.
- [ ] Windows CI job `python-smoke-windows` green on default branch.
- [ ] macOS CI job `python-smoke-macos` green (if enabled for this release).
- [ ] Controller `pytest tests/test_controller_import_boot.py` run on Windows agent for this tag (or PR merge commit).

## Bundling (Stone-Home)

- [ ] `prepare-resources.mjs` completes without FATAL; staged tree includes `windows-worker/windows_worker/main.py`.
- [ ] Tauri `bundle.resources` maps `resources/phantom_core/` → `phantom_core/`.

## Security and transparency

- [ ] No new optional dependency imported at **module top level** in `phantom_core/phantom_core/` without review.
- [ ] New network listeners or subprocess spawns documented in **Port and Binding Contract** or module docstrings.

## Storage and locking

- [ ] Any change to `trust_store` persistence reviewed against **STORAGE_AND_LOCKING.md**.
- [ ] If multi-process controller is introduced on Windows, locking design updated and tested.

## Human-first operations

- [ ] Deploy / wizard surfaces **actionable** errors for controller start failure (stderr or log path), not only HTTP timeouts.

## Sign-off

- Release owner: _________________  
- Date: _________________
