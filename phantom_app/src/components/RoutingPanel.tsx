import { useState, useEffect } from 'react';
import ConsentModal from './ConsentModal';
import { getExecutionMode, setExecutionMode } from '../utils/tauri';
import { tauriInvokeErrorMessage } from '../state/deploymentState';

export default function RoutingPanel() {
  const [mode, setMode] = useState<string>('MANUAL');
  const [schemas, setSchemas] = useState<Record<string, unknown>>({});
  const [pendingMode, setPendingMode] = useState<string | null>(null);
  const [modeError, setModeError] = useState<string | null>(null);

  useEffect(() => {
    getExecutionMode()
      .then((d) => {
        setMode(String(d.mode ?? 'MANUAL'));
        setSchemas((d.schemas as Record<string, unknown>) ?? {});
      })
      .catch(() => {});
  }, []);

  const requestModeSwitch = (newMode: string) => {
    if (newMode === mode) return;
    setPendingMode(newMode);
  };

  const confirmModeSwitch = () => {
    if (!pendingMode) return;
    const next = pendingMode;
    setModeError(null);
    setExecutionMode(next)
      .then((d) => {
        setMode(String((d as { mode?: string }).mode ?? next));
        setPendingMode(null);
      })
      .catch((e) => {
        setModeError(tauriInvokeErrorMessage(e));
        setPendingMode(null);
      });
  };

  const modes = ['AUTO', 'HYBRID', 'MANUAL'] as const;
  const modeDesc: Record<string, string> = {
    MANUAL: 'Full human control. You select which worker handles each task. MANUAL is the sacred default.',
    HYBRID: 'System proposes worker assignments. Human approval required before execution.',
    AUTO: 'Fully automated task routing. The engine selects the optimal worker. Withdraws on human activity.',
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Routing &amp; Execution Modes</span>
      </div>

      {modeError && (
        <div
          role="alert"
          style={{
            marginBottom: 16,
            padding: '10px 12px',
            background: 'rgba(180, 60, 60, 0.12)',
            border: '1px solid rgba(220, 90, 90, 0.4)',
            borderRadius: 6,
            fontSize: 12,
            color: '#e8a0a0',
            whiteSpace: 'pre-wrap',
          }}
        >
          {modeError}
          <button
            type="button"
            onClick={() => setModeError(null)}
            className="deploy-btn ceremony-btn-secondary"
            style={{ marginLeft: 12, fontSize: 10, padding: '4px 10px' }}
          >
            Dismiss
          </button>
        </div>
      )}

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
            onClick={() => requestModeSwitch(m)}
          >
            {m}{m === 'MANUAL' ? ' ★' : ''}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-title">Current Mode: {mode}</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6 }}>
          {modeDesc[mode] ?? ''}
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

      {pendingMode && (
        <ConsentModal
          title="Change Execution Mode"
          message={`Switch from ${mode} to ${pendingMode}? ${pendingMode === 'AUTO' ? 'AUTO mode grants the engine autonomous routing authority.' : pendingMode === 'HYBRID' ? 'HYBRID mode requires your approval for each task.' : 'MANUAL mode gives you full direct control.'}`}
          onConfirm={confirmModeSwitch}
          onCancel={() => setPendingMode(null)}
        />
      )}
    </div>
  );
}
