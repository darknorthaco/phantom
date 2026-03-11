//! Phantom §3 — SignedManifest model, canonical payload builder, signature verification.

use crate::security::identity_manager::IdentityManager;
use serde::{Deserialize, Serialize};

/// SignedManifest received over UDP discovery.
/// Extends the legacy RawManifest with signing fields.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignedManifest {
    /// Worker identifier.
    pub worker_id: String,
    /// Worker address (host).
    pub address: String,
    /// Worker capabilities (GPU info, etc.).
    pub capabilities: serde_json::Value,
    /// Message type — always "WORKER_MANIFEST".
    #[serde(default = "default_msg_type")]
    pub msg_type: String,
    /// Base64-encoded Ed25519 public key.
    #[serde(default)]
    pub public_key_b64: String,
    /// Base64-encoded Ed25519 signature over canonical_payload.
    #[serde(default)]
    pub signature_b64: String,
    /// Signing timestamp (seconds since epoch).
    #[serde(default)]
    pub signed_at: f64,
}

fn default_msg_type() -> String {
    "WORKER_MANIFEST".to_string()
}

impl SignedManifest {
    /// Build the deterministic canonical payload for signing/verification.
    ///
    /// Rules (§3): sorted keys, no whitespace, UTF-8 JSON, no optional fields omitted.
    pub fn canonical_payload(&self) -> String {
        // Build a sorted-key JSON object — deterministic via BTreeMap
        use std::collections::BTreeMap;
        let mut map = BTreeMap::new();
        map.insert("address", serde_json::Value::String(self.address.clone()));
        map.insert(
            "capabilities",
            sort_json_value(&self.capabilities),
        );
        map.insert("msg_type", serde_json::Value::String(self.msg_type.clone()));
        map.insert(
            "signed_at",
            serde_json::Value::Number(
                serde_json::Number::from_f64(self.signed_at).unwrap_or_else(|| {
                    serde_json::Number::from_f64(0.0).unwrap()
                }),
            ),
        );
        map.insert(
            "worker_id",
            serde_json::Value::String(self.worker_id.clone()),
        );
        // serde_json serializes BTreeMap with sorted keys by default
        serde_json::to_string(&map).unwrap_or_default()
    }

    /// Verify the Ed25519 signature on this manifest.
    ///
    /// Returns `true` if valid, `false` if missing/invalid.
    pub fn verify_signature(&self) -> bool {
        if self.public_key_b64.is_empty() || self.signature_b64.is_empty() {
            return false;
        }
        let payload = self.canonical_payload();
        match IdentityManager::verify_signature(
            &self.public_key_b64,
            payload.as_bytes(),
            &self.signature_b64,
        ) {
            Ok(valid) => valid,
            Err(_) => false,
        }
    }

    /// Compute a short hex fingerprint of the public key (first 8 bytes of SHA-256).
    pub fn fingerprint(&self) -> String {
        if self.public_key_b64.is_empty() {
            return String::new();
        }
        use base64::Engine;
        let pub_bytes = match base64::engine::general_purpose::STANDARD
            .decode(&self.public_key_b64)
        {
            Ok(b) => b,
            Err(_) => return String::new(),
        };
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(&pub_bytes);
        let hash = hasher.finalize();
        hash[..8].iter().map(|b| format!("{b:02x}")).collect()
    }
}

/// Recursively sort JSON object keys for deterministic output.
fn sort_json_value(v: &serde_json::Value) -> serde_json::Value {
    match v {
        serde_json::Value::Object(map) => {
            let sorted: serde_json::Map<String, serde_json::Value> = map
                .iter()
                .map(|(k, val)| (k.clone(), sort_json_value(val)))
                .collect();
            serde_json::Value::Object(sorted)
        }
        serde_json::Value::Array(arr) => {
            serde_json::Value::Array(arr.iter().map(sort_json_value).collect())
        }
        other => other.clone(),
    }
}

/// Holds the wire format we parse from UDP — supports both legacy and signed manifests.
#[derive(Deserialize)]
pub(crate) struct RawWireManifest {
    /// Legacy "type" field.
    #[serde(rename = "type", default)]
    pub msg_type_legacy: String,
    /// New msg_type field.
    #[serde(default)]
    pub msg_type: String,
    #[serde(default)]
    pub worker_id: String,
    /// Legacy host field.
    #[serde(default)]
    pub host: String,
    /// New address field.
    #[serde(default)]
    pub address: String,
    #[serde(default)]
    pub port: u16,
    #[serde(default)]
    pub gpu_info: serde_json::Value,
    #[serde(default)]
    pub capabilities: serde_json::Value,
    // Signing fields (may be absent for legacy unsigned manifests)
    #[serde(default)]
    pub public_key_b64: String,
    #[serde(default)]
    pub signature_b64: String,
    #[serde(default)]
    pub signed_at: f64,
}

impl RawWireManifest {
    /// Resolve the effective msg_type (prefer new field, fall back to legacy).
    pub fn effective_msg_type(&self) -> &str {
        if !self.msg_type.is_empty() {
            &self.msg_type
        } else {
            &self.msg_type_legacy
        }
    }

    /// Convert to a SignedManifest, normalizing legacy fields.
    pub fn into_signed_manifest(self) -> SignedManifest {
        let address = if !self.address.is_empty() {
            self.address
        } else {
            self.host
        };
        let capabilities = if self.capabilities.is_object()
            || self.capabilities.is_array()
        {
            self.capabilities
        } else {
            self.gpu_info
        };
        let msg_type = if !self.msg_type.is_empty() {
            self.msg_type
        } else {
            self.msg_type_legacy
        };

        SignedManifest {
            worker_id: self.worker_id,
            address,
            capabilities,
            msg_type,
            public_key_b64: self.public_key_b64,
            signature_b64: self.signature_b64,
            signed_at: self.signed_at,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_payload_deterministic() {
        let m = SignedManifest {
            worker_id: "w1".into(),
            address: "192.168.1.10".into(),
            capabilities: serde_json::json!({"gpu": "RTX3090", "vram": 24576}),
            msg_type: "WORKER_MANIFEST".into(),
            public_key_b64: String::new(),
            signature_b64: String::new(),
            signed_at: 1700000000.0,
        };
        let p1 = m.canonical_payload();
        let p2 = m.canonical_payload();
        assert_eq!(p1, p2);
        // Must contain sorted keys
        assert!(p1.contains("\"address\""));
        assert!(p1.contains("\"worker_id\""));
    }

    #[test]
    fn unsigned_manifest_fails_verification() {
        let m = SignedManifest {
            worker_id: "w1".into(),
            address: "192.168.1.10".into(),
            capabilities: serde_json::json!({}),
            msg_type: "WORKER_MANIFEST".into(),
            public_key_b64: String::new(),
            signature_b64: String::new(),
            signed_at: 0.0,
        };
        assert!(!m.verify_signature());
    }

    #[test]
    fn raw_wire_manifest_conversion() {
        let raw = RawWireManifest {
            msg_type_legacy: "WORKER_MANIFEST".into(),
            msg_type: String::new(),
            worker_id: "w1".into(),
            host: "10.0.0.1".into(),
            address: String::new(),
            port: 8090,
            gpu_info: serde_json::json!({"gpu": "RTX3090"}),
            capabilities: serde_json::Value::Null,
            public_key_b64: String::new(),
            signature_b64: String::new(),
            signed_at: 0.0,
        };
        let sm = raw.into_signed_manifest();
        assert_eq!(sm.address, "10.0.0.1");
        assert_eq!(sm.msg_type, "WORKER_MANIFEST");
    }
}
