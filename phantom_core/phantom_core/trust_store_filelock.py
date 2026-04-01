"""
Cross-platform advisory lock for append-only trust ledger writes.

Doctrine (Storage & Locking — see docs/doctrine/STORAGE_AND_LOCKING.md):

- **POSIX (Linux, macOS, *BSD):** ``fcntl.flock(LOCK_EX)`` around each append.
  Coordinates **multiple processes** on the same ``trust_store.jsonl`` (e.g. rare
  double-start or tooling reading while writing).

- **Windows:** ``msvcrt.locking`` on the first byte of the file, then seek to EOF
  for append. If locking fails, we log once and fall back to **in-process**
  serialization only (``threading.Lock`` in ``TrustStore``), which matches the
  supported deployment: **one controller process per ``state_dir``**.

Environment:

- ``PHANTOM_TRUST_STORE_NO_FILELOCK=1``: skip OS-level file locking (diagnostics
  only). **Do not use in production** if multiple processes might write the ledger.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import contextmanager
from typing import Callable, Iterator, TextIO

logger = logging.getLogger(__name__)

FileLockFn = Callable[[TextIO], Iterator[None]]


def _env_disables_file_lock() -> bool:
    return os.environ.get("PHANTOM_TRUST_STORE_NO_FILELOCK", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


@contextmanager
def _noop_file_lock(_file_obj: TextIO) -> Iterator[None]:
    """No cross-process lock; TrustStore still holds threading.Lock."""
    yield


@contextmanager
def _posix_flock_lock(file_obj: TextIO) -> Iterator[None]:
    """POSIX advisory whole-file lock for the open file descriptor."""
    import fcntl

    fd = file_obj.fileno()
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        yield
        file_obj.flush()
        os.fsync(fd)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def _windows_msvcrt_lock(file_obj: TextIO) -> Iterator[None]:
    """
    Lock the first byte at file offset 0, then seek to end for append.

    If ``msvcrt.locking`` fails (e.g. unsupported handle), fall back to thread-only
    locking with a clear warning (single-writer contract on Windows).
    """
    import msvcrt

    fd = file_obj.fileno()
    file_obj.flush()
    file_obj.seek(0)
    locked = False
    try:
        try:
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            locked = True
        except OSError as exc:
            logger.warning(
                "TrustStore: msvcrt.locking failed (%s); using thread-only serialization. "
                "Only one controller process may use this state_dir on Windows.",
                exc,
            )
        file_obj.seek(0, 2)
        yield
        file_obj.flush()
        os.fsync(fd)
    finally:
        if locked:
            file_obj.seek(0)
            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass


def select_trust_store_append_lock() -> FileLockFn:
    """
    Return a context manager factory ``lock(file_obj)`` for use around append writes.

    ``fcntl`` is never imported at module load on Windows.
    """
    if _env_disables_file_lock():
        logger.warning(
            "TrustStore: PHANTOM_TRUST_STORE_NO_FILELOCK is set — OS file locking disabled"
        )
        return _noop_file_lock

    if sys.platform == "win32":
        return _windows_msvcrt_lock
    # Linux, macOS, and other POSIX platforms
    return _posix_flock_lock
