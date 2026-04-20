import { useState, useEffect } from 'react';
import { getWorkers } from '../utils/tauri';

interface Worker {
  worker_id: string;
  host: string;
  port: number;
  gpu_info: Record<string, unknown>;
  status: string;
  signature_verified?: boolean;
  fingerprint?: string;
  key_changed?: boolean;
}

/** Signature status badge for §3 manifest verification. */
function SignatureBadge({ worker }: { worker: Worker }) {
  if (worker.key_changed) {
    return (
      <span
        className="status-badge"
        style={{ background: 'var(--accent-crimson, #dc3545)', color: '#fff' }}
        title="Public key changed — re-approval required"
      >
        ⚠ Key Changed
      </span>
    );
  }
  if (worker.signature_verified === true) {
    return (
      <span
        className="status-badge active"
        title={`Verified · ${worker.fingerprint ?? ''}`}
      >
        ✓ Verified
      </span>
    );
  }
  if (worker.signature_verified === false) {
    return (
      <span
        className="status-badge offline"
        title="Signature missing or invalid — not eligible for auto-selection"
      >
        ✗ Unverified
      </span>
    );
  }
  // undefined — legacy worker, no sig info
  return (
    <span className="status-badge" style={{ opacity: 0.6 }} title="No signature data (legacy worker)">
      — N/A
    </span>
  );
}

export default function WorkersPanel() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchWorkers = () => {
    setLoading(true);
    getWorkers()
      .then((d) => {
        const body = d as { workers?: Worker[] };
        setWorkers(body.workers ?? []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => { fetchWorkers(); }, []);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Workers</span>
        <button className="console-send-btn" onClick={fetchWorkers}>Refresh</button>
      </div>
      <div className="scan-result" style={{ fontSize: '0.85em', marginBottom: 8, opacity: 0.8 }}>
        LAN discovery and worker registration are controlled by deployment ceremony acts.
      </div>

      {loading ? (
        <div className="empty-state">Loading workers…</div>
      ) : workers.length === 0 ? (
        <div className="empty-state">No workers registered. Use LAN scan or register via API.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Host</th>
              <th>Port</th>
              <th>GPU</th>
              <th>Signature</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {workers.map((w) => (
              <tr key={w.worker_id}>
                <td style={{ fontFamily: 'var(--font-mono)' }}>{w.worker_id}</td>
                <td>{w.host}</td>
                <td>{w.port}</td>
                <td>{(w.gpu_info as Record<string, string>)?.name ?? '—'}</td>
                <td><SignatureBadge worker={w} /></td>
                <td>
                  <span className={`status-badge ${w.status === 'active' ? 'active' : 'offline'}`}>
                    {w.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
