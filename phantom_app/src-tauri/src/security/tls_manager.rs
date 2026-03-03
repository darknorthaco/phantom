use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrustedPeer {
    pub peer_id: String,
    pub address: String,
    pub certificate_fingerprint: String,
    pub trusted: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AddressBook {
    pub peers: Vec<TrustedPeer>,
}

impl AddressBook {
    pub fn new() -> Self {
        Self { peers: Vec::new() }
    }

    pub fn add_peer(&mut self, peer: TrustedPeer) {
        self.peers.push(peer);
    }

    pub fn trusted_peers(&self) -> Vec<&TrustedPeer> {
        self.peers.iter().filter(|p| p.trusted).collect()
    }
}
