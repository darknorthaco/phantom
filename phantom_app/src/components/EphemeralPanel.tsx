import { useState, useEffect } from 'react';

interface EphemeralSession {
  id: string;
  name: string;
  token: string;
  expires_at: number;
  scope: string;
  created_at: number;
}

function generateToken(): string {
  const arr = new Uint8Array(16);
  crypto.getRandomValues(arr);
  return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('');
}

function formatTimeRemaining(expiresAt: number): string {
  const remaining = expiresAt - Date.now();
  if (remaining <= 0) return 'Expired';
  const hours = Math.floor(remaining / 3_600_000);
  const minutes = Math.floor((remaining % 3_600_000) / 60_000);
  const seconds = Math.floor((remaining % 60_000) / 1_000);
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

const DURATION_OPTIONS = [
  { label: '1 hour',   ms: 3_600_000 },
  { label: '6 hours',  ms: 21_600_000 },
  { label: '24 hours', ms: 86_400_000 },
];

const SCOPE_OPTIONS = ['read-only', 'task-submit', 'full-access'];

export default function EphemeralPanel() {
  const [sessions, setSessions] = useState<EphemeralSession[]>([]);
  const [sessionName, setSessionName] = useState('');
  const [duration, setDuration] = useState(DURATION_OPTIONS[0].ms);
  const [scope, setScope] = useState('read-only');
  const [, setTick] = useState(0);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setTick(t => t + 1);
      setSessions(s => s.filter(sess => sess.expires_at > Date.now()));
    }, 1_000);
    return () => clearInterval(interval);
  }, []);

  const createSession = () => {
    if (!sessionName.trim()) return;
    const session: EphemeralSession = {
      id: crypto.randomUUID(),
      name: sessionName.trim(),
      token: generateToken(),
      expires_at: Date.now() + duration,
      scope,
      created_at: Date.now(),
    };
    setSessions(s => [session, ...s]);
    setSessionName('');
  };

  const revokeSession = (id: string) => {
    setSessions(s => s.filter(sess => sess.id !== id));
  };

  const copyToken = (id: string, token: string) => {
    navigator.clipboard.writeText(token).catch(() => {});
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2_000);
  };

  const inputStyle: React.CSSProperties = {
    background: 'var(--bg-tertiary)',
    border: '1px solid var(--border-dim)',
    color: 'var(--text-primary)',
    padding: '6px 10px',
    borderRadius: 4,
    fontSize: 12,
    fontFamily: 'var(--font-mono)',
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Ephemeral Access</span>
      </div>

      <div className="card">
        <div className="card-title">Create Temporary Session</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6, marginBottom: 12 }}>
          Grant time-limited, scope-restricted access to workers for guests or temporary
          workloads. Sessions auto-expire and are removed from this panel when they do.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input
            type="text"
            placeholder="Session name (e.g. Alice's workload)"
            value={sessionName}
            onChange={e => setSessionName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && createSession()}
            style={inputStyle}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <select
              value={duration}
              onChange={e => setDuration(Number(e.target.value))}
              style={{ ...inputStyle, flex: 1 }}
            >
              {DURATION_OPTIONS.map(opt => (
                <option key={opt.ms} value={opt.ms}>{opt.label}</option>
              ))}
            </select>
            <select
              value={scope}
              onChange={e => setScope(e.target.value)}
              style={{ ...inputStyle, flex: 1 }}
            >
              {SCOPE_OPTIONS.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <button
            className="console-send-btn"
            onClick={createSession}
            disabled={!sessionName.trim()}
            style={{ alignSelf: 'flex-start' }}
          >
            Create Session
          </button>
        </div>
      </div>

      {sessions.length === 0 ? (
        <div className="empty-state">No active ephemeral sessions.</div>
      ) : (
        <div className="card">
          <div className="card-title">Active Sessions ({sessions.length})</div>
          {sessions.map(sess => (
            <div
              key={sess.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '8px 0',
                borderBottom: '1px solid var(--border-dim)',
              }}
            >
              <div>
                <div style={{ fontSize: 12 }}>{sess.name}</div>
                <div style={{ display: 'flex', gap: 8, marginTop: 4, alignItems: 'center' }}>
                  <span className="status-badge active">{sess.scope}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                    {formatTimeRemaining(sess.expires_at)}
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  className="console-send-btn"
                  style={{ fontSize: 10, padding: '3px 10px' }}
                  onClick={() => copyToken(sess.id, sess.token)}
                >
                  {copiedId === sess.id ? 'Copied!' : 'Copy Token'}
                </button>
                <button
                  className="console-send-btn"
                  style={{ fontSize: 10, padding: '3px 10px', background: 'var(--accent-crimson)' }}
                  onClick={() => revokeSession(sess.id)}
                >
                  Revoke
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
