"""
Tests for §3 Manifest Signing Model — discovery.py and trust_store.py.

Covers:
  - Canonical payload determinism
  - Signature creation and verification (valid, invalid, missing)
  - TrustStore append-only behaviour
  - TrustStore key-change detection
  - SignedManifest round-trip (dict → SignedManifest → dict)
  - parse_and_verify for valid/invalid/unsigned JSON
"""

import json
import os
import shutil
import tempfile
import time
import unittest

from phantom_core.discovery import (
    ManifestSigner,
    ManifestVerifier,
    SignedManifest,
    build_canonical_payload,
    parse_and_verify,
)
from phantom_core.trust_store import (
    TrustEventType,
    TrustLevel,
    TrustRecord,
    TrustStore,
)

# ---------------------------------------------------------------------------
# Canonical payload tests
# ---------------------------------------------------------------------------


class TestCanonicalPayload(unittest.TestCase):
    """§3 — deterministic canonical payload builder."""

    def test_sorted_keys(self):
        payload = build_canonical_payload(
            worker_id="w1",
            address="10.0.0.1",
            capabilities={"gpu": "RTX3090", "vram": 24576},
            msg_type="WORKER_MANIFEST",
            signed_at=1700000000.0,
        )
        obj = json.loads(payload)
        keys = list(obj.keys())
        self.assertEqual(keys, sorted(keys))

    def test_no_whitespace(self):
        payload = build_canonical_payload(
            worker_id="w1",
            address="10.0.0.1",
            capabilities={},
            msg_type="WORKER_MANIFEST",
            signed_at=0.0,
        )
        # No spaces after separators
        self.assertNotIn(": ", payload)
        self.assertNotIn(", ", payload)

    def test_deterministic(self):
        args = dict(
            worker_id="w1",
            address="10.0.0.1",
            capabilities={"z": 1, "a": 2},
            msg_type="WORKER_MANIFEST",
            signed_at=1700000000.0,
        )
        p1 = build_canonical_payload(**args)
        p2 = build_canonical_payload(**args)
        self.assertEqual(p1, p2)

    def test_nested_capabilities_sorted(self):
        payload = build_canonical_payload(
            worker_id="w1",
            address="10.0.0.1",
            capabilities={"z": {"b": 2, "a": 1}, "a": 0},
            msg_type="WORKER_MANIFEST",
            signed_at=0.0,
        )
        obj = json.loads(payload)
        cap_keys = list(obj["capabilities"].keys())
        self.assertEqual(cap_keys, ["a", "z"])
        inner_keys = list(obj["capabilities"]["z"].keys())
        self.assertEqual(inner_keys, ["a", "b"])


# ---------------------------------------------------------------------------
# SignedManifest model tests
# ---------------------------------------------------------------------------


class TestSignedManifest(unittest.TestCase):
    """§3 — SignedManifest data model."""

    def test_from_dict_legacy(self):
        """Legacy unsigned JSON (type/host/gpu_info) → SignedManifest."""
        data = {
            "type": "WORKER_MANIFEST",
            "worker_id": "w1",
            "host": "10.0.0.1",
            "port": 8090,
            "gpu_info": {"name": "RTX3090"},
        }
        m = SignedManifest.from_dict(data)
        self.assertEqual(m.worker_id, "w1")
        self.assertEqual(m.address, "10.0.0.1")
        self.assertEqual(m.msg_type, "WORKER_MANIFEST")
        self.assertEqual(m.public_key_b64, "")
        self.assertIsNone(m.signature_verified)

    def test_to_wire_dict_includes_legacy(self):
        m = SignedManifest(
            worker_id="w1",
            address="10.0.0.1",
            capabilities={"name": "RTX3090"},
        )
        wire = m.to_wire_dict()
        self.assertIn("type", wire)
        self.assertIn("host", wire)
        self.assertIn("gpu_info", wire)

    def test_round_trip(self):
        m = SignedManifest(
            worker_id="w1",
            address="10.0.0.1",
            capabilities={"vram": 24576},
        )
        d = m.to_dict()
        m2 = SignedManifest.from_dict(d)
        self.assertEqual(m.worker_id, m2.worker_id)
        self.assertEqual(m.address, m2.address)


# ---------------------------------------------------------------------------
# Signing & verification tests
# ---------------------------------------------------------------------------


class TestManifestSigning(unittest.TestCase):
    """§3 — ManifestSigner + ManifestVerifier."""

    def setUp(self):
        self.signer = ManifestSigner.generate()

    def test_sign_and_verify(self):
        m = SignedManifest(
            worker_id="w1",
            address="10.0.0.1",
            capabilities={"gpu": "RTX3090"},
        )
        self.signer.sign(m)
        self.assertNotEqual(m.signature_b64, "")
        self.assertNotEqual(m.public_key_b64, "")
        self.assertGreater(m.signed_at, 0)
        self.assertTrue(ManifestVerifier.verify(m))
        self.assertTrue(m.signature_verified)

    def test_unsigned_manifest_fails(self):
        m = SignedManifest(worker_id="w1", address="10.0.0.1", capabilities={})
        self.assertFalse(ManifestVerifier.verify(m))
        self.assertFalse(m.signature_verified)

    def test_tampered_payload_fails(self):
        m = SignedManifest(worker_id="w1", address="10.0.0.1", capabilities={})
        self.signer.sign(m)
        # Tamper with the manifest after signing
        m.worker_id = "TAMPERED"
        self.assertFalse(ManifestVerifier.verify(m))

    def test_wrong_key_fails(self):
        m = SignedManifest(worker_id="w1", address="10.0.0.1", capabilities={})
        self.signer.sign(m)
        # Replace with a different key's public key
        other = ManifestSigner.generate()
        m.public_key_b64 = other.public_key_b64
        self.assertFalse(ManifestVerifier.verify(m))

    def test_invalid_base64_fails(self):
        m = SignedManifest(
            worker_id="w1",
            address="10.0.0.1",
            capabilities={},
            public_key_b64="not-valid-base64!!!!",
            signature_b64="also-invalid!!!!",
            signed_at=time.time(),
        )
        self.assertFalse(ManifestVerifier.verify(m))


# ---------------------------------------------------------------------------
# parse_and_verify tests
# ---------------------------------------------------------------------------


class TestParseAndVerify(unittest.TestCase):
    """§3 — JSON → SignedManifest parsing with verification."""

    def test_valid_signed(self):
        signer = ManifestSigner.generate()
        m = SignedManifest(worker_id="w1", address="10.0.0.1", capabilities={"a": 1})
        signer.sign(m)
        raw = json.dumps(m.to_wire_dict())
        result = parse_and_verify(raw)
        self.assertIsNotNone(result)
        self.assertTrue(result.signature_verified)

    def test_unsigned_legacy(self):
        raw = json.dumps(
            {
                "type": "WORKER_MANIFEST",
                "worker_id": "w1",
                "host": "10.0.0.1",
                "port": 8090,
                "gpu_info": {},
            }
        )
        result = parse_and_verify(raw)
        self.assertIsNotNone(result)
        self.assertFalse(result.signature_verified)

    def test_invalid_json_returns_none(self):
        self.assertIsNone(parse_and_verify("{bad json"))

    def test_non_manifest_returns_none(self):
        raw = json.dumps({"type": "OTHER", "worker_id": "w1"})
        self.assertIsNone(parse_and_verify(raw))

    def test_missing_worker_id_returns_none(self):
        raw = json.dumps({"type": "WORKER_MANIFEST"})
        self.assertIsNone(parse_and_verify(raw))


# ---------------------------------------------------------------------------
# TrustStore tests
# ---------------------------------------------------------------------------


class TestTrustStore(unittest.TestCase):
    """§3/§5 — TrustStore append-only ledger."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="phantom_trust_test_")
        self.store = TrustStore(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_store(self):
        self.assertIsNone(self.store.get_current_level("w1"))
        self.assertIsNone(self.store.get_current_key("w1"))
        self.assertEqual(self.store.get_history("w1"), [])

    def test_write_and_read(self):
        rec = TrustRecord(
            worker_id="w1",
            public_key="key_a",
            event_type=TrustEventType.FIRST_SEEN.value,
            trust_level=TrustLevel.UNVERIFIED.value,
            timestamp=time.time(),
        )
        self.store.write_record(rec)
        self.assertEqual(
            self.store.get_current_level("w1"), TrustLevel.UNVERIFIED.value
        )
        self.assertEqual(self.store.get_current_key("w1"), "key_a")

    def test_append_only(self):
        """Calling write_record twice produces two records."""
        self.store.record_verification("w1", "key_a", True)
        self.store.record_verification("w1", "key_a", True)
        history = self.store.get_history("w1")
        # At minimum: first_seen + sig_valid + sig_valid
        self.assertGreaterEqual(len(history), 3)

    def test_current_level_is_most_recent(self):
        self.store.record_verification("w1", "key_a", True)
        self.assertEqual(self.store.get_current_level("w1"), TrustLevel.SIG_VALID.value)
        self.store.record_verification("w1", "key_a", False)
        self.assertEqual(
            self.store.get_current_level("w1"), TrustLevel.UNVERIFIED.value
        )

    def test_key_change_detection(self):
        self.store.record_verification("w1", "key_a", True)
        self.store.record_verification("w1", "key_b", True)
        history = self.store.get_history("w1")
        events = [r.event_type for r in history]
        self.assertIn(TrustEventType.KEY_CHANGED.value, events)

    def test_first_seen_event(self):
        self.store.record_verification("w1", "key_a", True)
        history = self.store.get_history("w1")
        self.assertEqual(history[0].event_type, TrustEventType.FIRST_SEEN.value)

    def test_approve_worker(self):
        self.store.record_verification("w1", "key_a", True)
        rec = self.store.approve_worker("w1")
        self.assertIsNotNone(rec)
        self.assertEqual(self.store.get_current_level("w1"), TrustLevel.APPROVED.value)

    def test_revoke_worker(self):
        self.store.record_verification("w1", "key_a", True)
        self.store.revoke_worker("w1")
        self.assertEqual(self.store.get_current_level("w1"), TrustLevel.REVOKED.value)

    def test_approve_unknown_returns_none(self):
        self.assertIsNone(self.store.approve_worker("unknown"))

    def test_persistence(self):
        """Records survive reload from disk."""
        self.store.record_verification("w1", "key_a", True)
        # Create a new store pointing to the same directory
        store2 = TrustStore(self.tmpdir)
        self.assertEqual(store2.get_current_level("w1"), TrustLevel.SIG_VALID.value)

    def test_get_all_workers(self):
        self.store.record_verification("w1", "key_a", True)
        self.store.record_verification("w2", "key_b", True)
        workers = self.store.get_all_workers()
        self.assertIn("w1", workers)
        self.assertIn("w2", workers)


# ---------------------------------------------------------------------------
# Replay / tamper tests (security)
# ---------------------------------------------------------------------------


class TestSecurityProperties(unittest.TestCase):
    """§3 — Security: replay prevention, tamper detection."""

    def test_timestamp_in_canonical_payload(self):
        """signed_at is part of the canonical payload — replaying with a
        different timestamp invalidates the signature."""
        signer = ManifestSigner.generate()
        m = SignedManifest(worker_id="w1", address="10.0.0.1", capabilities={})
        signer.sign(m)
        # Change timestamp
        m.signed_at = m.signed_at + 1.0
        self.assertFalse(ManifestVerifier.verify(m))

    def test_tampered_capabilities(self):
        signer = ManifestSigner.generate()
        m = SignedManifest(
            worker_id="w1",
            address="10.0.0.1",
            capabilities={"gpu": "RTX3090"},
        )
        signer.sign(m)
        m.capabilities = {"gpu": "FAKE_GPU"}
        self.assertFalse(ManifestVerifier.verify(m))

    def test_trust_store_append_only_enforcement(self):
        """Trust store file only grows — never overwrite records."""
        tmpdir = tempfile.mkdtemp(prefix="phantom_trust_append_")
        store = TrustStore(tmpdir)
        store.record_verification("w1", "key_a", True)
        path = os.path.join(tmpdir, "trust_store.jsonl")
        size1 = os.path.getsize(path)
        store.record_verification("w1", "key_a", True)
        size2 = os.path.getsize(path)
        self.assertGreater(size2, size1)
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
