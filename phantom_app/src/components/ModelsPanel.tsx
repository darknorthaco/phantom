import { useState, useEffect } from 'react';
import { loadLlmConfig } from '../utils/tauri';

interface LlmConfig {
  execution_mode: string;
  allow_per_task_override: boolean;
  model: string;
  auto_withdraw_on_human_activity: boolean;
  confidence_threshold: number;
}

export default function ModelsPanel() {
  const [config, setConfig] = useState<LlmConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const raw = await loadLlmConfig();
      setConfig(raw as unknown as LlmConfig);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchConfig(); }, []);

  const modeColor = config?.execution_mode === 'auto'
    ? 'var(--accent-green)'
    : config?.execution_mode === 'hybrid'
    ? 'var(--accent-amber)'
    : 'var(--accent-blue)';

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Models</span>
        <button className="console-send-btn" onClick={fetchConfig} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      <div className="card">
        <div className="card-title">LLM Task Master</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6 }}>
          The LLM Task Master uses a lightweight local model (e.g. Phi-3.5 Mini) to make
          intelligent routing decisions. It runs on your GPU and never contacts external servers.
        </p>
        {loading ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 12 }}>Loading configuration…</div>
        ) : error ? (
          <div style={{ marginTop: 12 }}>
            <span className="status-badge offline">Not Deployed</span>
            <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 4 }}>{error}</div>
          </div>
        ) : config ? (
          <div style={{ marginTop: 12 }}>
            <span className="status-badge active">Configured</span>
            <table className="data-table" style={{ marginTop: 12 }}>
              <tbody>
                <tr>
                  <td style={{ color: 'var(--text-muted)' }}>Execution Mode</td>
                  <td>
                    <span style={{
                      color: modeColor,
                      textTransform: 'uppercase',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11,
                    }}>
                      {config.execution_mode}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--text-muted)' }}>Model</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{config.model}</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--text-muted)' }}>Confidence Threshold</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    {(config.confidence_threshold * 100).toFixed(0)}%
                  </td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--text-muted)' }}>Per-Task Override</td>
                  <td>
                    <span className={`status-badge ${config.allow_per_task_override ? 'active' : 'offline'}`}>
                      {config.allow_per_task_override ? 'Allowed' : 'Disabled'}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--text-muted)' }}>Human-Priority Withdraw</td>
                  <td>
                    <span className={`status-badge ${config.auto_withdraw_on_human_activity ? 'active' : 'offline'}`}>
                      {config.auto_withdraw_on_human_activity ? 'Enabled' : 'Disabled'}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      <div className="card">
        <div className="card-title">Model Catalogue</div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Size</th>
              <th>Purpose</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                {config?.model ?? 'phi-3.5-mini'}
              </td>
              <td>3.8B</td>
              <td>Task routing</td>
              <td>
                <span className={`status-badge ${config ? 'active' : 'offline'}`}>
                  {config ? 'Configured' : 'Available'}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
