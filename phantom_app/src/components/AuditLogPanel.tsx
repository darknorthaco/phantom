import { useState, useEffect } from 'react';
import { getAuditLog } from '../utils/tauri';

interface AuditEntry {
  timestamp: string;
  event_type: string;
  details: Record<string, unknown>;
}

export default function AuditLogPanel() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const raw = await getAuditLog(100);
      setEntries(raw as unknown as AuditEntry[]);
    } catch (e) {
      setError(String(e));
      setEntries([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLogs(); }, []);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Audit Log</span>
        <button className="console-send-btn" onClick={fetchLogs} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      <div className="card">
        <div className="card-title">Event Transparency</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6 }}>
          All deployment steps, mode changes, trust decisions, worker registrations,
          and TLS handshake events are logged locally in append-only format.
          Logs are stored under <code>~/.phantom/audit/phantom_audit.jsonl</code>.
        </p>
      </div>

      {loading ? (
        <div className="empty-state">Loading audit entries…</div>
      ) : error ? (
        <div className="empty-state" style={{ color: 'var(--accent-crimson)' }}>
          Failed to load audit log: {error}
        </div>
      ) : entries.length === 0 ? (
        <div className="empty-state">No audit entries yet. Events will appear after deployment.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Event</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, i) => (
              <tr key={i}>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>{e.timestamp}</td>
                <td>{e.event_type}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 10, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {JSON.stringify(e.details)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
