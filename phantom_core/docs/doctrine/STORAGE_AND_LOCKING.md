# Storage and Locking Doctrine (Phantom Controller)

This document matches the implemented behavior of `phantom_core/phantom_core/trust_store.py` and `trust_store_filelock.py`.

## Trust ledger file

- **Path:** `<PHANTOM_STATE_DIR or default state>/trust_store.jsonl`
- **Semantics:** Append-only JSON lines; records are never mutated or deleted in place.
- **Durability:** After each append, the implementation flushes and calls `fsync` on the file descriptor where OS-level locking is used (POSIX and Windows success paths).

## Concurrency

### In-process

- All `TrustStore` public methods are serialized with `threading.Lock`.

### Cross-process (multiple writers)

- **POSIX (Linux, macOS, *BSD):** Advisory `fcntl.flock(LOCK_EX)` around each append while the file is open for append. Coordinates distinct processes that share the same ledger file.
- **Windows:** `msvcrt.locking` on byte 0, then seek-to-end for append. If locking fails, the code logs a warning and relies on **thread-only** serialization — **only one controller process per `state_dir` is supported** in that case.

### Diagnostics

- **`PHANTOM_TRUST_STORE_NO_FILELOCK=1`:** Disables OS-level file locking entirely. For troubleshooting only; do not use if multiple processes could append to the same ledger.

## Sovereignty and transparency

- Locking strategy is **explicit** in code and this document, not an implicit POSIX dependency at import time.
- Warnings are logged when Windows cannot acquire `msvcrt` locks so operators can detect unsupported multi-process scenarios.

## CI enforcement

- `scripts/ci/check_platform_assumptions.py` forbids top-level `fcntl` (and listed POSIX modules) and any `os.fork()` in `phantom_core/phantom_core/**`. `fcntl` is allowed only as a lazy import inside a function (e.g. `_posix_flock_lock`).
- Workflow: `.github/workflows/build.yml` (jobs `platform-assumptions`, `python-smoke-windows`, `python-smoke-macos`).
