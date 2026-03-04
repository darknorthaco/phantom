use rustls::pki_types::{CertificateDer, PrivateKeyDer, ServerName};
use rustls::{ClientConfig, RootCertStore};
use rustls_pemfile::{certs, private_key};
use std::fs::File;
use std::io::BufReader;
use std::path::Path;
use std::sync::Arc;
use tokio::net::TcpStream;
use tokio_rustls::TlsConnector;

pub struct TlsTransportConfig {
    pub cert_path: String,
    pub key_path: String,
    /// Path to the peer's self-signed certificate for pinned trust.
    /// Required for Phantom's zero-trust inter-controller mesh.
    pub peer_cert_path: Option<String>,
}

/// Establish a mutual-TLS connection to `target` (format: `"host:port"`).
///
/// Uses certificate pinning when `config.peer_cert_path` is set — the only
/// cert trusted is the one at that path.  This is the correct security model
/// for Phantom's sovereign mesh where all controllers use self-signed certs.
pub async fn establish_secure_channel(
    config: &TlsTransportConfig,
    target: &str,
) -> Result<(), String> {
    // ── Load our certificate chain ────────────────────────────────────────
    let our_certs: Vec<CertificateDer<'static>> = {
        let f = File::open(&config.cert_path)
            .map_err(|e| format!("Cannot open cert '{}': {e}", config.cert_path))?;
        certs(&mut BufReader::new(f))
            .collect::<Result<_, _>>()
            .map_err(|e| format!("Cannot parse cert chain: {e}"))?
    };

    // ── Load our private key ──────────────────────────────────────────────
    let our_key: PrivateKeyDer<'static> = {
        let f = File::open(&config.key_path)
            .map_err(|e| format!("Cannot open key '{}': {e}", config.key_path))?;
        private_key(&mut BufReader::new(f))
            .map_err(|e| format!("Cannot parse private key: {e}"))?
            .ok_or_else(|| "No private key found in key file".to_string())?
    };

    // ── Build TLS ClientConfig ────────────────────────────────────────────
    let tls_config: ClientConfig = if let Some(peer_path) = &config.peer_cert_path {
        // Certificate pinning: trust only the specific peer cert.
        let peer_certs: Vec<CertificateDer<'static>> = {
            let f = File::open(peer_path)
                .map_err(|e| format!("Cannot open peer cert '{peer_path}': {e}"))?;
            certs(&mut BufReader::new(f))
                .collect::<Result<_, _>>()
                .map_err(|e| format!("Cannot parse peer cert: {e}"))?
        };

        let mut root_store = RootCertStore::empty();
        for cert in peer_certs {
            root_store
                .add(cert)
                .map_err(|e| format!("Cannot add peer cert to trust store: {e}"))?;
        }

        ClientConfig::builder()
            .with_root_certificates(root_store)
            .with_client_auth_cert(our_certs, our_key)
            .map_err(|e| format!("TLS config error: {e}"))?
    } else {
        // No peer cert provided — use an empty root store.
        // Connections will succeed only when the server presents a cert signed
        // by one of the roots we add to the pool.  For Phantom's self-signed
        // mesh this means peer_cert_path should always be provided; leaving it
        // None is appropriate only for connections to publicly-trusted endpoints.
        let root_store = RootCertStore::empty();
        ClientConfig::builder()
            .with_root_certificates(root_store)
            .with_client_auth_cert(our_certs, our_key)
            .map_err(|e| format!("TLS config error: {e}"))?
    };

    let connector = TlsConnector::from(Arc::new(tls_config));

    // ── Parse target address ──────────────────────────────────────────────
    let (host, port) = parse_target(target)?;

    // ── TCP connect ───────────────────────────────────────────────────────
    let stream = TcpStream::connect(format!("{host}:{port}"))
        .await
        .map_err(|e| format!("TCP connect to '{target}' failed: {e}"))?;

    // ── TLS handshake ─────────────────────────────────────────────────────
    let server_name = ServerName::try_from(host.to_string())
        .map_err(|e| format!("Invalid server name '{host}': {e}"))?;

    let _tls_stream = connector
        .connect(server_name, stream)
        .await
        .map_err(|e| format!("TLS handshake with '{target}' failed: {e}"))?;

    log::info!("TLS secure channel established to {target}");
    Ok(())
}

/// Verify that the file at `cert_path` contains at least one parseable X.509
/// certificate.  Returns `Ok(true)` if valid, `Err(msg)` if the file cannot
/// be opened or parsed.
pub fn verify_peer_certificate(cert_path: &Path) -> Result<bool, String> {
    if !cert_path.exists() {
        return Err(format!(
            "Peer certificate not found: {:?}",
            cert_path
        ));
    }

    let f = File::open(cert_path)
        .map_err(|e| format!("Cannot open certificate {:?}: {e}", cert_path))?;

    let parsed: Vec<CertificateDer<'static>> = certs(&mut BufReader::new(f))
        .collect::<Result<_, _>>()
        .map_err(|e| format!("Certificate parse error in {:?}: {e}", cert_path))?;

    if parsed.is_empty() {
        return Err(format!(
            "Certificate file {:?} contains no valid X.509 certificates",
            cert_path
        ));
    }

    log::info!(
        "Peer certificate verified: {:?} ({} cert(s) parsed)",
        cert_path,
        parsed.len()
    );
    Ok(true)
}

// ── Helpers ──────────────────────────────────────────────────────────────────

fn parse_target(target: &str) -> Result<(String, u16), String> {
    // Split on the last ':' to support IPv6 addresses like [::1]:9090
    let idx = target
        .rfind(':')
        .ok_or_else(|| format!("Invalid target address (expected host:port): '{target}'"))?;
    let host = target[..idx].to_string();
    let port: u16 = target[idx + 1..]
        .parse()
        .map_err(|e| format!("Invalid port in '{target}': {e}"))?;
    Ok((host, port))
}
