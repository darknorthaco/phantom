use chrono::Utc;
use rcgen::{CertificateParams, KeyPair};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum TrustStatus {
    Pending,
    Approved,
    Rejected,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrustedPeer {
    pub peer_id: String,
    pub address: String,
    pub public_key_b64: String,
    pub certificate_fingerprint: String,
    pub status: TrustStatus,
    pub requested_at: String,
    pub decided_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AddressBook {
    pub peers: Vec<TrustedPeer>,
}

impl AddressBook {
    pub fn new() -> Self {
        Self { peers: Vec::new() }
    }

    pub fn add_peer_request(&mut self, peer: TrustedPeer) {
        if !self.peers.iter().any(|p| p.peer_id == peer.peer_id) {
            self.peers.push(peer);
        }
    }

    pub fn approve_peer(&mut self, peer_id: &str) -> Result<(), String> {
        let peer = self
            .peers
            .iter_mut()
            .find(|p| p.peer_id == peer_id)
            .ok_or_else(|| format!("Peer not found: {peer_id}"))?;

        if peer.status != TrustStatus::Pending {
            return Err(format!("Peer is not pending: {:?}", peer.status));
        }

        peer.status = TrustStatus::Approved;
        peer.decided_at = Some(Utc::now().to_rfc3339());
        Ok(())
    }

    pub fn reject_peer(&mut self, peer_id: &str) -> Result<(), String> {
        let peer = self
            .peers
            .iter_mut()
            .find(|p| p.peer_id == peer_id)
            .ok_or_else(|| format!("Peer not found: {peer_id}"))?;

        peer.status = TrustStatus::Rejected;
        peer.decided_at = Some(Utc::now().to_rfc3339());
        Ok(())
    }

    pub fn pending_peers(&self) -> Vec<&TrustedPeer> {
        self.peers
            .iter()
            .filter(|p| p.status == TrustStatus::Pending)
            .collect()
    }

    pub fn approved_peers(&self) -> Vec<&TrustedPeer> {
        self.peers
            .iter()
            .filter(|p| p.status == TrustStatus::Approved)
            .collect()
    }

    pub fn rejected_peers(&self) -> Vec<&TrustedPeer> {
        self.peers
            .iter()
            .filter(|p| p.status == TrustStatus::Rejected)
            .collect()
    }
}

pub struct TlsManager {
    cert_dir: PathBuf,
    pub address_book: AddressBook,
}

impl TlsManager {
    pub fn new(state_dir: &Path) -> Self {
        Self {
            cert_dir: state_dir.join("tls"),
            address_book: AddressBook::new(),
        }
    }

    pub async fn init(&mut self) -> Result<(), String> {
        tokio::fs::create_dir_all(&self.cert_dir)
            .await
            .map_err(|e| format!("Failed to create tls dir: {e}"))?;

        let book_path = self.cert_dir.join("address_book.json");
        if book_path.exists() {
            let data = tokio::fs::read_to_string(&book_path)
                .await
                .map_err(|e| format!("Failed to read address book: {e}"))?;
            self.address_book =
                serde_json::from_str(&data).unwrap_or_else(|_| AddressBook::new());
        }

        Ok(())
    }

    pub async fn save_address_book(&self) -> Result<(), String> {
        let book_path = self.cert_dir.join("address_book.json");
        let data =
            serde_json::to_string_pretty(&self.address_book).map_err(|e| e.to_string())?;
        tokio::fs::write(&book_path, data)
            .await
            .map_err(|e| format!("Failed to save address book: {e}"))
    }

    pub async fn generate_self_signed_cert(
        &self,
        common_name: &str,
    ) -> Result<CertPaths, String> {
        tokio::fs::create_dir_all(&self.cert_dir)
            .await
            .map_err(|e| format!("Failed to create tls dir: {e}"))?;

        let key_pair = KeyPair::generate()
            .map_err(|e| format!("Failed to generate key pair: {e}"))?;

        let mut params = CertificateParams::new(vec![common_name.to_string()])
            .map_err(|e| format!("Failed to create cert params: {e}"))?;
        params.distinguished_name.push(
            rcgen::DnType::CommonName,
            rcgen::DnValue::Utf8String(common_name.to_string()),
        );

        let cert = params
            .self_signed(&key_pair)
            .map_err(|e| format!("Failed to self-sign: {e}"))?;

        let cert_pem = cert.pem();
        let key_pem = key_pair.serialize_pem();

        let cert_path = self.cert_dir.join("phantom.crt");
        let key_path = self.cert_dir.join("phantom.key");

        tokio::fs::write(&cert_path, cert_pem.as_bytes())
            .await
            .map_err(|e| format!("Failed to write cert: {e}"))?;
        tokio::fs::write(&key_path, key_pem.as_bytes())
            .await
            .map_err(|e| format!("Failed to write key: {e}"))?;

        Ok(CertPaths {
            cert: cert_path,
            key: key_path,
        })
    }

    /// Copy operator-supplied PEM files into the local TLS directory (sovereign import).
    pub async fn import_tls_cert_pair(
        &self,
        cert_src: &Path,
        key_src: &Path,
    ) -> Result<CertPaths, String> {
        tokio::fs::create_dir_all(&self.cert_dir)
            .await
            .map_err(|e| format!("Failed to create tls dir: {e}"))?;
        let cert_path = self.cert_dir.join("imported.crt");
        let key_path = self.cert_dir.join("imported.key");
        tokio::fs::copy(cert_src, &cert_path)
            .await
            .map_err(|e| format!("Failed to copy certificate: {e}"))?;
        tokio::fs::copy(key_src, &key_path)
            .await
            .map_err(|e| format!("Failed to copy private key: {e}"))?;
        Ok(CertPaths {
            cert: cert_path,
            key: key_path,
        })
    }

    pub fn load_certificate(&self) -> Result<CertPaths, String> {
        let cert_path = self.cert_dir.join("phantom.crt");
        let key_path = self.cert_dir.join("phantom.key");

        if !cert_path.exists() || !key_path.exists() {
            return Err("Certificate not found — generate one first".to_string());
        }

        Ok(CertPaths {
            cert: cert_path,
            key: key_path,
        })
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct CertPaths {
    pub cert: PathBuf,
    pub key: PathBuf,
}

/// Local PEM sanity check (no network, no CA).
pub fn validate_tls_cert_pem(path: &Path) -> Result<(), String> {
    let s = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    if !(s.contains("BEGIN CERTIFICATE") || s.contains("BEGIN TRUSTED CERTIFICATE")) {
        return Err(
            "File is not a PEM certificate (expected BEGIN CERTIFICATE).".to_string(),
        );
    }
    Ok(())
}

/// Local PEM private key sanity check.
pub fn validate_tls_key_pem(path: &Path) -> Result<(), String> {
    let s = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    if !s.contains("BEGIN") || !s.contains("PRIVATE KEY") {
        return Err("File is not a PEM private key.".to_string());
    }
    Ok(())
}
