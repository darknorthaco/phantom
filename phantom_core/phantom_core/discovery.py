"""
Phantom Manifest Signing — §3 Signed Manifest Model.

Provides SignedManifest schema, canonical payload construction,
Ed25519 signature creation and verification for worker discovery.
"""

import base64
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

logger = logging.getLogger(__name__)

# Maximum age (seconds) for a signed manifest before it is considered stale.
# Receivers reject manifests older than this to limit replay window.
MAX_MANIFEST_AGE_SECONDS: float = 300.0

# Clock-skew tolerance: manifests may be this many seconds into the future.
MAX_CLOCK_SKEW_SECONDS: float = 60.0

# ---------------------------------------------------------------------------
# Canonical Payload
# ---------------------------------------------------------------------------


def build_canonical_payload(
    worker_id: str,
    address: str,
    capabilities: dict,
    msg_type: str,
    signed_at: float,
) -> str:
    """Build deterministic canonical JSON payload.

    Rules (§3):
      - Sorted keys
      - UTF-8 JSON
      - No extra whitespace
      - No optional fields omitted
    """
    obj = {
        "address": address,
        "capabilities": _sort_nested(capabilities),
        "msg_type": msg_type,
        "signed_at": signed_at,
        "worker_id": worker_id,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sort_nested(obj):
    """Recursively sort dict keys for deterministic output."""
    if isinstance(obj, dict):
        return {k: _sort_nested(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_nested(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# SignedManifest
# ---------------------------------------------------------------------------


@dataclass
class SignedManifest:
    """Manifest with Ed25519 signature per §3."""

    worker_id: str
    address: str
    capabilities: dict
    msg_type: str = "WORKER_MANIFEST"
    public_key_b64: str = ""
    signature_b64: str = ""
    signed_at: float = 0.0
    # Verification result (set by receiver, not serialised on wire)
    signature_verified: Optional[bool] = field(default=None, repr=False)

    def canonical_payload(self) -> str:
        return build_canonical_payload(
            worker_id=self.worker_id,
            address=self.address,
            capabilities=self.capabilities,
            msg_type=self.msg_type,
            signed_at=self.signed_at,
        )

    def to_dict(self) -> dict:
        """Serialise for wire / UDP response."""
        d = asdict(self)
        d.pop("signature_verified", None)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SignedManifest":
        return cls(
            worker_id=data.get("worker_id", ""),
            address=data.get("address", data.get("host", "")),
            capabilities=data.get("capabilities", data.get("gpu_info", {})),
            msg_type=data.get("msg_type", data.get("type", "WORKER_MANIFEST")),
            public_key_b64=data.get("public_key_b64", ""),
            signature_b64=data.get("signature_b64", ""),
            signed_at=data.get("signed_at", 0.0),
        )

    # Backward-compatible: also emit legacy "type" field for old receivers
    def to_wire_dict(self) -> dict:
        d = self.to_dict()
        d["type"] = d["msg_type"]
        # Legacy aliases
        d["host"] = d["address"]
        d["gpu_info"] = d["capabilities"]
        return d


# ---------------------------------------------------------------------------
# Manifest Signer (worker-side)
# ---------------------------------------------------------------------------


class ManifestSigner:
    """Worker-side: sign manifests with a per-worker Ed25519 key."""

    def __init__(self, private_key: Ed25519PrivateKey):
        self._private_key = private_key
        pub_bytes = private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        self._public_key_b64 = base64.b64encode(pub_bytes).decode("ascii")

    @classmethod
    def generate(cls) -> "ManifestSigner":
        key = Ed25519PrivateKey.generate()
        return cls(key)

    @classmethod
    def from_raw_bytes(cls, key_bytes: bytes) -> "ManifestSigner":
        key = Ed25519PrivateKey.from_private_bytes(key_bytes)
        return cls(key)

    @property
    def public_key_b64(self) -> str:
        return self._public_key_b64

    def export_private_key_bytes(self) -> bytes:
        """Export raw 32-byte Ed25519 private key for persistence."""
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PrivateFormat,
        )

        return self._private_key.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )

    def sign(self, manifest: SignedManifest) -> SignedManifest:
        """Populate public_key_b64, signed_at, and signature_b64."""
        manifest.signed_at = time.time()
        manifest.public_key_b64 = self._public_key_b64
        payload = manifest.canonical_payload().encode("utf-8")
        sig = self._private_key.sign(payload)
        manifest.signature_b64 = base64.b64encode(sig).decode("ascii")
        return manifest


# ---------------------------------------------------------------------------
# Manifest Verifier (receiver-side)
# ---------------------------------------------------------------------------


class ManifestVerifier:
    """Receiver-side: verify Ed25519 signatures on incoming manifests."""

    @staticmethod
    def verify(manifest: SignedManifest) -> bool:
        """Verify signature. Returns True if valid, False otherwise.

        Sets manifest.signature_verified as a side-effect.
        """
        if not manifest.public_key_b64 or not manifest.signature_b64:
            manifest.signature_verified = False
            logger.debug(
                "Manifest from %s: missing signature fields", manifest.worker_id
            )
            return False

        try:
            pub_bytes = base64.b64decode(manifest.public_key_b64)
            sig_bytes = base64.b64decode(manifest.signature_b64)
        except (ValueError, TypeError) as exc:
            manifest.signature_verified = False
            logger.warning(
                "Manifest from %s: base64 decode failed: %s",
                manifest.worker_id,
                type(exc).__name__,
            )
            return False

        try:
            pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
            payload = manifest.canonical_payload().encode("utf-8")
            pub_key.verify(sig_bytes, payload)
            manifest.signature_verified = True
            return True
        except InvalidSignature:
            manifest.signature_verified = False
            logger.warning("Manifest from %s: invalid signature", manifest.worker_id)
            return False
        except (ValueError, TypeError) as exc:
            manifest.signature_verified = False
            logger.warning(
                "Manifest from %s: bad key or signature format: %s",
                manifest.worker_id,
                type(exc).__name__,
            )
            return False


def parse_and_verify(raw_json: str) -> Optional[SignedManifest]:
    """Parse a JSON string into a SignedManifest and verify its signature.

    Returns the manifest with signature_verified set (True/False/None).
    Returns None if JSON is unparseable or not a WORKER_MANIFEST.

    Timestamp freshness is enforced for signed manifests: manifests older
    than ``MAX_MANIFEST_AGE_SECONDS`` or more than ``MAX_CLOCK_SKEW_SECONDS``
    in the future are rejected.
    """
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None

    msg_type = data.get("msg_type", data.get("type", ""))
    if msg_type != "WORKER_MANIFEST":
        return None

    worker_id = data.get("worker_id", "")
    if not worker_id:
        return None

    manifest = SignedManifest.from_dict(data)

    # Timestamp freshness (only enforced when a signed_at value is present)
    if manifest.signed_at > 0:
        now = time.time()
        age = now - manifest.signed_at
        if age > MAX_MANIFEST_AGE_SECONDS:
            logger.warning("Manifest from %s rejected: too old (%.0fs)", worker_id, age)
            manifest.signature_verified = False
            return manifest
        if age < -MAX_CLOCK_SKEW_SECONDS:
            logger.warning(
                "Manifest from %s rejected: timestamp in future (%.0fs)",
                worker_id,
                abs(age),
            )
            manifest.signature_verified = False
            return manifest

    ManifestVerifier.verify(manifest)
    return manifest
