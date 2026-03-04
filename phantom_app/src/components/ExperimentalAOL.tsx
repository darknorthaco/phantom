import { useState, useEffect } from 'react';
import { getIdentity, getTrustLedger, approvePeer, rejectPeer, generateCertificate } from '../utils/tauri';

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
  const [identityInfo, setIdentityInfo] = useState<Record<string, unknown> | null>(null);
  const [ledger, setLedger] = useState<TrustLedger>({ pending: [], approved: [], rejected: [] });
  const [loadingIdentity, setLoadingIdentity] = useState(false);
  const [loadingLedger, setLoadingLedger] = useState(false);
  const [identityError, setIdentityError] = useState<string | null>(null);
  const [certPaths, setCertPaths] = useState<Record<string, unknown> | null>(null);
  const [generatingCert, setGeneratingCert] = useState(false);
  const [certError, setCertError] = useState<string | null>(null);

  const loadIdentity = async () => {
    setLoadingIdentity(true);
    setIdentityError(null);
    try {
      const info = await getIdentity();
      setIdentityInfo(info);
    } catch (e) {
      setIdentityError(String(e));
    } finally {
      setLoadingIdentity(false);
    }
  };

  const loadLedger = async () => {
    setLoadingLedger(true);
    try {
      const raw = await getTrustLedger();
      setLedger(raw as unknown as TrustLedger);
    } catch {
      // Trust ledger not available outside Tauri context
    } finally {
      setLoadingLedger(false);
    }
  };

  const handleApprove = async (peerId: string) => {
    try {
      await approvePeer(peerId);
      await loadLedger();
    } catch (e) {
      console.error('Failed to approve peer:', e);
    }
  };

  const handleReject = async (peerId: string) => {
    try {
      await rejectPeer(peerId);
      await loadLedger();
    } catch (e) {
      console.error('Failed to reject peer:', e);
    }
  };

  const handleGenerateCert = async () => {
    setGeneratingCert(true);
    setCertError(null);
    try {
      const paths = await generateCertificate();
      setCertPaths(paths);
    } catch (e) {
      setCertError(String(e));
    } finally {
      setGeneratingCert(false);
    }
  };

  useEffect(() => { loadLedger(); }, []);

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
          <pre style={{
            color: 'var(--text-secondary)',
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}>
            {JSON.stringify(identityInfo, null, 2)}
          </pre>
        ) : (
          <>
            {identityError && (
              <div style={{ color: 'var(--accent-crimson)', fontSize: 11, marginBottom: 8 }}>
                {identityError}
              </div>
            )}
            <button
              className="console-send-btn"
              onClick={loadIdentity}
              disabled={loadingIdentity}
            >
              {loadingIdentity ? 'Loading…' : 'Load Identity'}
            </button>
          </>
        )}
      </div>

      {/* Trust Ledger */}
      <div className="card">
        <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>Trust Ledger</span>
          <button
            className="console-send-btn"
            onClick={loadLedger}
            disabled={loadingLedger}
            style={{ fontSize: 10, padding: '2px 8px' }}
          >
            {loadingLedger ? '…' : 'Refresh'}
          </button>
        </div>
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
                  <button
                    className="console-send-btn"
                    style={{ fontSize: 10, padding: '4px 12px', background: 'var(--accent-green)' }}
                    onClick={() => handleApprove(p.peer_id)}
                  >
                    Approve
                  </button>
                  <button
                    className="console-send-btn"
                    style={{ fontSize: 10, padding: '4px 12px', background: 'var(--accent-crimson)' }}
                    onClick={() => handleReject(p.peer_id)}
                  >
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

        {ledger.rejected.length > 0 && (
          <>
            <div style={{ color: 'var(--accent-crimson)', fontSize: 11, fontFamily: 'var(--font-mono)', marginTop: 16, marginBottom: 8 }}>
              REJECTED ({ledger.rejected.length})
            </div>
            {ledger.rejected.map((p) => (
              <div key={p.peer_id} style={{ fontSize: 12, padding: '4px 0', color: 'var(--text-muted)' }}>
                {p.peer_id} — <span style={{ color: 'var(--text-muted)' }}>{p.address}</span>
              </div>
            ))}
          </>
        )}

        {ledger.pending.length === 0 && ledger.approved.length === 0 && ledger.rejected.length === 0 && (
          <div className="empty-state">No WAN peers configured. Trust relationships are created when peers connect.</div>
        )}
      </div>

      {/* TLS Section */}
      <div className="card">
        <div className="card-title">TLS / Secure Transport</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6, marginBottom: 12 }}>
          WAN communication requires QUIC/TLS. Certificates are generated locally and
          never leave your controller. Each peer must explicitly approve the other's
          certificate before a secure channel is established.
        </p>

        {certPaths ? (
          <div>
            <span className="status-badge active" style={{ marginBottom: 8, display: 'inline-block' }}>
              Certificate Generated
            </span>
            <pre style={{
              color: 'var(--text-secondary)',
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              marginTop: 8,
            }}>
              {JSON.stringify(certPaths, null, 2)}
            </pre>
          </div>
        ) : (
          <>
            {certError && (
              <div style={{ color: 'var(--accent-crimson)', fontSize: 11, marginBottom: 8 }}>
                {certError}
              </div>
            )}
            <button
              className="console-send-btn"
              onClick={handleGenerateCert}
              disabled={generatingCert}
            >
              {generatingCert ? 'Generating…' : 'Generate Certificate'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
