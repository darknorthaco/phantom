"""
Phantom Trust Store — §3 / §5 Append-Only Trust Ledger.

Records every trust-level transition for every worker.
Implements TOFU (Trust On First Use) key management and
key-change detection per the Corrected Architecture Design.
"""

import fcntl
import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types and trust levels
# ---------------------------------------------------------------------------


class TrustEventType(str, Enum):
    FIRST_SEEN = "first_seen"
    SIGNATURE_VALID = "signature_valid"
    KEY_CHANGED = "key_changed"
    SIGNATURE_INVALID = "signature_invalid"


class TrustLevel(str, Enum):
    UNVERIFIED = "unverified"
    SIG_VALID = "sig_valid"
    APPROVED = "approved"
    REGISTERED = "registered"
    REVOKED = "revoked"


# ---------------------------------------------------------------------------
# TrustRecord — immutable log entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrustRecord:
    """Immutable record written at every trust-level transition."""

    worker_id: str
    public_key: str
    event_type: str  # TrustEventType value
    trust_level: str  # TrustLevel value
    timestamp: float
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TrustRecord":
        return cls(
            worker_id=d["worker_id"],
            public_key=d["public_key"],
            event_type=d["event_type"],
            trust_level=d["trust_level"],
            timestamp=d["timestamp"],
            reason=d.get("reason", ""),
        )


# ---------------------------------------------------------------------------
# TrustStore — append-only ledger
# ---------------------------------------------------------------------------


class TrustStore:
    """Persistent, append-only trust ledger local to the controller.

    Storage: ``<state_dir>/trust_store.jsonl`` (one JSON record per line).
    Thread-safe via a reentrant lock.
    """

    def __init__(self, state_dir: str):
        self._dir = Path(state_dir).resolve()
        if not self._dir.is_absolute():
            raise ValueError(f"state_dir must resolve to an absolute path: {state_dir}")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "trust_store.jsonl"
        self._lock = threading.Lock()
        # In-memory index: worker_id -> list of records (append-only)
        self._records: dict[str, List[TrustRecord]] = {}
        self._load()

    # ---- persistence -------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = TrustRecord.from_dict(json.loads(line))
                        self._records.setdefault(rec.worker_id, []).append(rec)
                    except (json.JSONDecodeError, KeyError, TypeError) as exc:
                        logger.warning(
                            "TrustStore: skipping corrupt record on line %d: %s",
                            line_num,
                            type(exc).__name__,
                        )
        except OSError as exc:
            logger.warning("TrustStore load error: %s", type(exc).__name__)

    def _append_to_file(self, record: TrustRecord) -> None:
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            logger.error("TrustStore write error: %s", type(exc).__name__)

    # ---- public API --------------------------------------------------

    def write_record(self, record: TrustRecord) -> None:
        """Append a TrustRecord. Records are never modified or deleted."""
        with self._lock:
            self._records.setdefault(record.worker_id, []).append(record)
            self._append_to_file(record)

    def get_current_level(self, worker_id: str) -> Optional[str]:
        """Return the trust level of the most recent record, or None."""
        with self._lock:
            recs = self._records.get(worker_id)
            if not recs:
                return None
            return recs[-1].trust_level

    def get_current_key(self, worker_id: str) -> Optional[str]:
        """Return the most recently recorded public key for a worker."""
        with self._lock:
            recs = self._records.get(worker_id)
            if not recs:
                return None
            return recs[-1].public_key

    def get_history(self, worker_id: str) -> List[TrustRecord]:
        """Return the full trust history for a worker (oldest first)."""
        with self._lock:
            return list(self._records.get(worker_id, []))

    def get_all_workers(self) -> List[str]:
        """Return all worker IDs that have at least one record."""
        with self._lock:
            return list(self._records.keys())

    # ---- high-level operations --------------------------------------

    def record_verification(
        self, worker_id: str, public_key: str, signature_valid: bool
    ) -> TrustRecord:
        """Record a signature verification result.

        Implements TOFU key-change detection:
        - First contact → first_seen + unverified (then optionally sig_valid)
        - Key change   → key_changed + unverified
        - Valid sig     → signature_valid + sig_valid
        - Invalid sig   → signature_invalid + unverified
        """
        now = time.time()
        existing_key = self.get_current_key(worker_id)

        # Key-change detection
        if existing_key is not None and public_key != existing_key:
            change_rec = TrustRecord(
                worker_id=worker_id,
                public_key=public_key,
                event_type=TrustEventType.KEY_CHANGED.value,
                trust_level=TrustLevel.UNVERIFIED.value,
                timestamp=now,
                reason="key_change_detected",
            )
            self.write_record(change_rec)
            logger.warning("Key change detected for worker %s", worker_id)
            # After key change, still record the sig result below

        # First-seen
        if existing_key is None:
            first_rec = TrustRecord(
                worker_id=worker_id,
                public_key=public_key,
                event_type=TrustEventType.FIRST_SEEN.value,
                trust_level=TrustLevel.UNVERIFIED.value,
                timestamp=now,
                reason="first_contact",
            )
            self.write_record(first_rec)

        # Signature result
        if signature_valid:
            rec = TrustRecord(
                worker_id=worker_id,
                public_key=public_key,
                event_type=TrustEventType.SIGNATURE_VALID.value,
                trust_level=TrustLevel.SIG_VALID.value,
                timestamp=now,
                reason="signature_verified",
            )
        else:
            rec = TrustRecord(
                worker_id=worker_id,
                public_key=public_key,
                event_type=TrustEventType.SIGNATURE_INVALID.value,
                trust_level=TrustLevel.UNVERIFIED.value,
                timestamp=now,
                reason="signature_verification_failed",
            )

        self.write_record(rec)
        return rec

    def approve_worker(self, worker_id: str) -> Optional[TrustRecord]:
        """Promote a worker to approved (user decision)."""
        current = self.get_current_level(worker_id)
        key = self.get_current_key(worker_id) or ""
        if current is None:
            return None
        rec = TrustRecord(
            worker_id=worker_id,
            public_key=key,
            event_type="user_approved",
            trust_level=TrustLevel.APPROVED.value,
            timestamp=time.time(),
            reason="user_approved_worker",
        )
        self.write_record(rec)
        return rec

    def approve_worker_with_key(
        self, worker_id: str, public_key: str
    ) -> TrustRecord:
        """§5 — Record user approval for a worker (possibly first contact).

        Used when the deployment ceremony approves a worker. Creates TrustRecord(approved)
        so the registration endpoint will accept the worker. For new workers (no prior
        record), this establishes the approved trust level.
        """
        key = public_key or ""
        rec = TrustRecord(
            worker_id=worker_id,
            public_key=key,
            event_type="user_approved",
            trust_level=TrustLevel.APPROVED.value,
            timestamp=time.time(),
            reason="user_approved_via_ceremony",
        )
        self.write_record(rec)
        return rec

    def record_registration(self, worker_id: str) -> TrustRecord:
        """§5 — Record that a worker was successfully registered."""
        key = self.get_current_key(worker_id) or ""
        rec = TrustRecord(
            worker_id=worker_id,
            public_key=key,
            event_type="worker_registered",
            trust_level=TrustLevel.REGISTERED.value,
            timestamp=time.time(),
            reason="registration_complete",
        )
        self.write_record(rec)
        return rec

    def revoke_worker(self, worker_id: str) -> Optional[TrustRecord]:
        """Revoke trust for a worker."""
        key = self.get_current_key(worker_id) or ""
        rec = TrustRecord(
            worker_id=worker_id,
            public_key=key,
            event_type="user_revoked",
            trust_level=TrustLevel.REVOKED.value,
            timestamp=time.time(),
            reason="user_revoked_worker",
        )
        self.write_record(rec)
        return rec
