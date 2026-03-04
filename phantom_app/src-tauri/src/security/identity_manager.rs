use ed25519_dalek::{Signer, SigningKey, Verifier, VerifyingKey};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

const PRIVATE_KEY_FILE: &str = "private.key";
const PUBLIC_KEY_FILE: &str = "public.key";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IdentityInfo {
    pub public_key_b64: String,
    pub fingerprint: String,
    pub identity_dir: String,
}

pub struct IdentityManager {
    identity_dir: PathBuf,
    signing_key: Option<SigningKey>,
}

impl IdentityManager {
    pub fn new(state_dir: &Path) -> Self {
        Self {
            identity_dir: state_dir.join("identity"),
            signing_key: None,
        }
    }

    pub async fn load_or_create(&mut self) -> Result<IdentityInfo, String> {
        tokio::fs::create_dir_all(&self.identity_dir)
            .await
            .map_err(|e| format!("Failed to create identity dir: {e}"))?;

        let priv_path = self.identity_dir.join(PRIVATE_KEY_FILE);
        let pub_path = self.identity_dir.join(PUBLIC_KEY_FILE);

        if priv_path.exists() {
            self.load_existing(&priv_path, &pub_path).await
        } else {
            self.generate_new(&priv_path, &pub_path).await
        }
    }

    async fn load_existing(
        &mut self,
        priv_path: &Path,
        _pub_path: &Path,
    ) -> Result<IdentityInfo, String> {
        let priv_bytes = tokio::fs::read(priv_path)
            .await
            .map_err(|e| format!("Failed to read private key: {e}"))?;

        let decoded = base64::Engine::decode(
            &base64::engine::general_purpose::STANDARD,
            priv_bytes.as_slice(),
        )
        .map_err(|e| format!("Failed to decode private key: {e}"))?;

        let key_bytes: [u8; 32] = decoded
            .try_into()
            .map_err(|_| "Invalid private key length".to_string())?;

        let signing_key = SigningKey::from_bytes(&key_bytes);
        let verifying_key = signing_key.verifying_key();
        let info = self.build_info(&verifying_key);
        self.signing_key = Some(signing_key);
        Ok(info)
    }

    async fn generate_new(
        &mut self,
        priv_path: &Path,
        pub_path: &Path,
    ) -> Result<IdentityInfo, String> {
        let mut csprng = OsRng;
        let signing_key = SigningKey::generate(&mut csprng);
        let verifying_key = signing_key.verifying_key();

        use base64::Engine;
        let priv_b64 =
            base64::engine::general_purpose::STANDARD.encode(signing_key.to_bytes());
        let pub_b64 =
            base64::engine::general_purpose::STANDARD.encode(verifying_key.to_bytes());

        tokio::fs::write(priv_path, priv_b64.as_bytes())
            .await
            .map_err(|e| format!("Failed to write private key: {e}"))?;
        tokio::fs::write(pub_path, pub_b64.as_bytes())
            .await
            .map_err(|e| format!("Failed to write public key: {e}"))?;

        let info = self.build_info(&verifying_key);
        self.signing_key = Some(signing_key);
        Ok(info)
    }

    fn build_info(&self, verifying_key: &VerifyingKey) -> IdentityInfo {
        use base64::Engine;
        use sha2::{Digest, Sha256};

        let pub_bytes = verifying_key.to_bytes();
        let pub_b64 = base64::engine::general_purpose::STANDARD.encode(pub_bytes);

        let mut hasher = Sha256::new();
        hasher.update(pub_bytes);
        let hash = hasher.finalize();
        let fingerprint = hex::encode(&hash[..8]);

        IdentityInfo {
            public_key_b64: pub_b64,
            fingerprint,
            identity_dir: self.identity_dir.to_string_lossy().to_string(),
        }
    }

    pub fn sign_message(&self, message: &[u8]) -> Result<String, String> {
        let key = self
            .signing_key
            .as_ref()
            .ok_or("Identity not loaded")?;
        let signature = key.sign(message);
        use base64::Engine;
        Ok(base64::engine::general_purpose::STANDARD.encode(signature.to_bytes()))
    }

    pub fn verify_signature(
        public_key_b64: &str,
        message: &[u8],
        signature_b64: &str,
    ) -> Result<bool, String> {
        use base64::Engine;
        let pub_bytes = base64::engine::general_purpose::STANDARD
            .decode(public_key_b64)
            .map_err(|e| format!("Invalid public key: {e}"))?;
        let sig_bytes = base64::engine::general_purpose::STANDARD
            .decode(signature_b64)
            .map_err(|e| format!("Invalid signature: {e}"))?;

        let pub_array: [u8; 32] = pub_bytes
            .try_into()
            .map_err(|_| "Invalid public key length".to_string())?;
        let sig_array: [u8; 64] = sig_bytes
            .try_into()
            .map_err(|_| "Invalid signature length".to_string())?;

        let verifying_key = VerifyingKey::from_bytes(&pub_array)
            .map_err(|e| format!("Invalid public key: {e}"))?;
        let signature = ed25519_dalek::Signature::from_bytes(&sig_array);

        Ok(verifying_key.verify(message, &signature).is_ok())
    }
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

mod hex {
    pub fn encode(bytes: &[u8]) -> String {
        super::hex_encode(bytes)
    }
}
