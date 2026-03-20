import { useState, useEffect } from 'react';
import {
  getIdentity,
  getTrustLedger,
  approvePeer,
  rejectPeer,
  generateSelfSignedCert,
  importTlsCert,
  validateTlsCert,
  savePhantomTlsSettings,
} from '../utils/tauri';

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
  const [tlsCertPath, setTlsCertPath] = useState('');
  const [tlsKeyPath, setTlsKeyPath] = useState('');
  const [importCertPath, setImportCertPath] = useState('');
  const [importKeyPath, setImportKeyPath] = useState('');
  const [tlsCommonName, setTlsCommonName] = useState('phantom-controller.local');
  const [wanMode, setWanMode] = useState(false);
  const [tlsEnabled, setTlsEnabled] = useState(false);
  const [tlsBusy, setTlsBusy] = useState(false);
  const [tlsStatus, setTlsStatus] = useState<string | null>(null);
  const [tlsError, setTlsError] = useState<string | null>(null);

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

  const applyPathsFromResult = (paths: Record<string, unknown>) => {
    const c = paths.cert;
    const k = paths.key;
    const certStr = typeof c === 'string' ? c : c != null ? String(c) : '';
    const keyStr = typeof k === 'string' ? k : k != null ? String(k) : '';
    if (certStr) setTlsCertPath(certStr);
    if (keyStr) setTlsKeyPath(keyStr);
  };

  const handleGenerateSelfSigned = async () => {
    setTlsBusy(true);
    setTlsError(null);
    setTlsStatus(null);
    try {
      const cn = tlsCommonName.trim() || null;
      const paths = await generateSelfSignedCert(cn);
      applyPathsFromResult(paths);
      setTlsStatus('Self-signed PEM written under app state/tls/. Paths filled below.');
    } catch (e) {
      setTlsError(String(e));
    } finally {
      setTlsBusy(false);
    }
  };

  const handleImportTls = async () => {
    setTlsBusy(true);
    setTlsError(null);
    setTlsStatus(null);
    try {
      const paths = await importTlsCert(importCertPath.trim(), importKeyPath.trim());
      applyPathsFromResult(paths);
      setImportCertPath('');
      setImportKeyPath('');
      setTlsStatus('Certificate and key copied to state/tls/ (imported.crt / imported.key).');
    } catch (e) {
      setTlsError(String(e));
    } finally {
      setTlsBusy(false);
    }
  };

  const handleValidateCert = async () => {
    setTlsBusy(true);
    setTlsError(null);
    setTlsStatus(null);
    try {
      await validateTlsCert(tlsCertPath.trim());
      setTlsStatus('Certificate PEM validated (local read).');
    } catch (e) {
      setTlsError(String(e));
    } finally {
      setTlsBusy(false);
    }
  };

  const handleSaveTlsSettings = async () => {
    setTlsBusy(true);
    setTlsError(null);
    setTlsStatus(null);
    try {
      await savePhantomTlsSettings(
        wanMode,
        tlsEnabled,
        tlsCertPath.trim(),
        tlsKeyPath.trim()
      );
      setTlsStatus('phantom_config.json updated (WAN/TLS fields). Restart controller to apply HTTPS.');
    } catch (e) {
      setTlsError(String(e));
    } finally {
      setTlsBusy(false);
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

      {/* TLS Section — Phase 4 controller API (WAN requires TLS; LAN may stay HTTP) */}
      <div className="card">
        <div className="card-title">TLS — Controller API (Phase 4)</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6, marginBottom: 12 }}>
          <strong>LAN default:</strong> plaintext HTTP unchanged. <strong>WAN / cross-household:</strong>{' '}
          <code>wan_mode</code> requires <code>tls_enabled</code> and valid PEM paths — no silent HTTPS→HTTP
          fallback. Certs are local/self-signed or imported; nothing is sent to a public CA.
        </p>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: 12 }}>
          <input
            type="checkbox"
            checked={wanMode}
            onChange={(e) => {
              const v = e.target.checked;
              setWanMode(v);
              if (v) setTlsEnabled(true);
            }}
          />
          WAN mode (requires TLS)
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, fontSize: 12 }}>
          <input
            type="checkbox"
            checked={tlsEnabled}
            onChange={(e) => setTlsEnabled(e.target.checked)}
            disabled={wanMode}
          />
          Enable TLS (HTTPS on controller API)
          {wanMode ? (
            <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>(forced on for WAN)</span>
          ) : null}
        </label>

        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Controller cert path</div>
          <input
            className="console-input"
            style={{ width: '100%', marginBottom: 8 }}
            value={tlsCertPath}
            onChange={(e) => setTlsCertPath(e.target.value)}
            placeholder="e.g. .../state/tls/phantom.crt"
          />
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Controller key path</div>
          <input
            className="console-input"
            style={{ width: '100%' }}
            value={tlsKeyPath}
            onChange={(e) => setTlsKeyPath(e.target.value)}
            placeholder="e.g. .../state/tls/phantom.key"
          />
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
          <input
            className="console-input"
            style={{ minWidth: 200, flex: 1 }}
            value={tlsCommonName}
            onChange={(e) => setTlsCommonName(e.target.value)}
            placeholder="Common name / SAN hint"
          />
          <button
            className="console-send-btn"
            onClick={handleGenerateSelfSigned}
            disabled={tlsBusy}
          >
            Generate certificate
          </button>
          <button
            className="console-send-btn"
            onClick={handleValidateCert}
            disabled={tlsBusy || !tlsCertPath.trim()}
          >
            Validate cert PEM
          </button>
        </div>

        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Import PEM (absolute paths)</div>
        <input
          className="console-input"
          style={{ width: '100%', marginBottom: 6 }}
          value={importCertPath}
          onChange={(e) => setImportCertPath(e.target.value)}
          placeholder="Source .crt / .pem"
        />
        <input
          className="console-input"
          style={{ width: '100%', marginBottom: 8 }}
          value={importKeyPath}
          onChange={(e) => setImportKeyPath(e.target.value)}
          placeholder="Source .key"
        />
        <button
          className="console-send-btn"
          onClick={handleImportTls}
          disabled={tlsBusy || !importCertPath.trim() || !importKeyPath.trim()}
          style={{ marginBottom: 12 }}
        >
          Import certificate
        </button>

        <button
          className="console-send-btn"
          onClick={handleSaveTlsSettings}
          disabled={tlsBusy}
          style={{ background: 'var(--accent-amber)', color: '#111' }}
        >
          Save to phantom_config.json
        </button>

        {tlsError && (
          <div style={{ color: 'var(--accent-crimson)', fontSize: 11, marginTop: 10 }}>
            {tlsError}
          </div>
        )}
        {tlsStatus && (
          <div style={{ color: 'var(--accent-green)', fontSize: 11, marginTop: 10, fontFamily: 'var(--font-mono)' }}>
            {tlsStatus}
          </div>
        )}
      </div>
    </div>
  );
}
