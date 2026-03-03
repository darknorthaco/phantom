import { useState, useEffect } from 'react';

export default function RoutingPanel() {
  const [mode, setMode] = useState<string>('AUTO');
  const [schemas, setSchemas] = useState<Record<string, unknown>>({});

  useEffect(() => {
    fetch('http://127.0.0.1:8080/mode')
      .then((r) => r.json())
      .then((d) => { setMode(d.mode); setSchemas(d.schemas || {}); })
      .catch(() => {});
  }, []);

  const switchMode = (newMode: string) => {
    fetch('http://127.0.0.1:8080/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: newMode }),
    })
      .then((r) => r.json())
      .then((d) => setMode(d.mode))
      .catch(() => {});
  };

  const modes = ['AUTO', 'HYBRID', 'MANUAL'] as const;

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Routing &amp; Execution Modes</span>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        {modes.map((m) => (
          <button
            key={m}
            className="deploy-btn"
            style={{
              padding: '10px 24px',
              fontSize: 12,
              borderColor: mode === m ? 'var(--accent-blue)' : 'var(--border-color)',
              background: mode === m ? 'var(--accent-blue-dim)' : 'transparent',
              color: mode === m ? 'var(--accent-blue)' : 'var(--text-secondary)',
            }}
            onClick={() => switchMode(m)}
          >
            {m}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-title">Current Mode: {mode}</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6 }}>
          {mode === 'AUTO' && 'Fully automated task routing. The engine selects the optimal worker.'}
          {mode === 'HYBRID' && 'System proposes worker assignments. Human approval required before execution.'}
          {mode === 'MANUAL' && 'Full human control. You select which worker handles each task.'}
        </p>
      </div>

      {Object.keys(schemas).length > 0 && (
        <div className="card">
          <div className="card-title">Socket Schemas</div>
          <pre style={{ color: 'var(--text-secondary)', fontSize: 11, fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(schemas, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
