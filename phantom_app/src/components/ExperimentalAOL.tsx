import { useState } from 'react';

interface TrustedPeer {
  peer_id: string;
  address: string;
  public_key_b64: string;
  certificate_fingerprint: string;
  status: string;
  requested_at: string;
  decided_at: string | null;
}

interface TrustLedger {
  pending: TrustedPeer[];
  approved: TrustedPeer[];
  rejected: TrustedPeer[];
}

export default function ExperimentalAOL() {
  const [identityInfo, setIdentityInfo] = useState<Record<string, string> | null>(null);
  const [ledger] = useState<TrustLedger>({ pending: [], approved: [], rejected: [] });

  const loadIdentity = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8080/');
      const data = await res.json();
      setIdentityInfo({ controller: 'v' + data.version, mode: data.execution_mode });
    } catch {
      setIdentityInfo({ error: 'Controller not reachable' });
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Experimental — Identity, Trust &amp; WAN</span>
      </div>

      {/* Identity Section */}
      <div className="card">
        <div className="card-title">Controller Identity</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6, marginBottom: 12 }}>
          Each controller generates an Ed25519 keypair on first launch.
          The public key serves as the controller's sovereign identity.
        </p>
        {identityInfo ? (
          <pre style={{ color: 'var(--text-secondary)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
            {JSON.stringify(identityInfo, null, 2)}
          </pre>
        ) : (
          <button className="console-send-btn" onClick={loadIdentity}>Load Identity</button>
        )}
      </div>

      {/* Trust Ledger */}
      <div className="card">
        <div className="card-title">Trust Ledger</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 12 }}>
          All WAN peer trust relationships require explicit human approval. No auto-approve. No implicit trust.
        </p>

        {ledger.pending.length > 0 && (
          <>
            <div style={{ color: 'var(--accent-amber)', fontSize: 11, fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
              PENDING APPROVAL ({ledger.pending.length})
            </div>
            {ledger.pending.map((p) => (
              <div key={p.peer_id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: 12 }}>{p.peer_id}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{p.address}</div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="console-send-btn" style={{ fontSize: 10, padding: '4px 12px', background: 'var(--accent-green)' }}>
                    Approve
                  </button>
                  <button className="console-send-btn" style={{ fontSize: 10, padding: '4px 12px', background: 'var(--accent-crimson)' }}>
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </>
        )}

        {ledger.approved.length > 0 && (
          <>
            <div style={{ color: 'var(--accent-green)', fontSize: 11, fontFamily: 'var(--font-mono)', marginTop: 16, marginBottom: 8 }}>
              APPROVED ({ledger.approved.length})
            </div>
            {ledger.approved.map((p) => (
              <div key={p.peer_id} style={{ fontSize: 12, padding: '4px 0', color: 'var(--text-secondary)' }}>
                {p.peer_id} — <span style={{ color: 'var(--text-muted)' }}>{p.address}</span>
                <span className="status-badge active" style={{ marginLeft: 8 }}>trusted</span>
              </div>
            ))}
          </>
        )}

        {ledger.pending.length === 0 && ledger.approved.length === 0 && (
          <div className="empty-state">No WAN peers configured. Trust relationships are created when peers connect.</div>
        )}
      </div>

      {/* TLS Section */}
      <div className="card">
        <div className="card-title">TLS / Secure Transport</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6 }}>
          WAN communication requires QUIC/TLS. Certificates are generated locally.
          The routing engine receives a trusted peer list as input but does not manage
          TLS, certificates, or WAN negotiation.
        </p>
      </div>
    </div>
  );
}
