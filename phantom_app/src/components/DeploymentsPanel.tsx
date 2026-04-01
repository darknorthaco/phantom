import { useState, useEffect } from 'react';
import { getPhantomHealth, loadLlmConfig, uninstallPhantom } from '../utils/tauri';
import { tauriInvokeErrorMessage } from '../state/deploymentState';

type ComponentStatus = 'running' | 'stopped' | 'error' | 'unknown';

interface ComponentEntry {
  name: string;
  version: string;
  status: ComponentStatus;
  detail?: string;
}

function badgeClass(status: ComponentStatus): string {
  return status === 'running' ? 'active' : 'offline';
}

function badgeLabel(entry: ComponentEntry): string {
  if (entry.status === 'unknown') return 'Checking…';
  return entry.detail ?? (entry.status === 'running' ? 'Running' : 'Stopped');
}

export default function DeploymentsPanel() {
  const [components, setComponents] = useState<ComponentEntry[]>([
    { name: 'Phantom Controller',    version: '—', status: 'unknown' },
    { name: 'Socket Infrastructure', version: '—', status: 'unknown' },
    { name: 'LLM Task Master',       version: '—', status: 'unknown' },
  ]);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState<string>('');
  const [uninstallBusy, setUninstallBusy] = useState(false);

  const refresh = async () => {
    setLoading(true);
    const updated: ComponentEntry[] = [
      { name: 'Phantom Controller',    version: '2.0.0', status: 'unknown' },
      { name: 'Socket Infrastructure', version: '1.0.0', status: 'unknown' },
      { name: 'LLM Task Master',       version: '1.0.0', status: 'unknown' },
    ];

    // Controller health via Tauri → REST
    try {
      const health = await getPhantomHealth() as Record<string, unknown>;
      const h = health.status === 'healthy' || health.status === 'degraded';
      updated[0] = {
        name: 'Phantom Controller',
        version: typeof health.version === 'string' ? health.version : '2.0.0',
        status: h ? 'running' : 'error',
        detail: typeof health.execution_mode === 'string'
          ? `${health.status} / mode: ${health.execution_mode}`
          : String(health.status ?? 'unknown'),
      };
    } catch {
      updated[0] = { ...updated[0], status: 'stopped', detail: 'Not reachable' };
    }

    // Socket infrastructure — optional standalone listener (not the controller API URL from config).
    try {
      const resp = await fetch('http://127.0.0.1:8081/health', { signal: AbortSignal.timeout(1_500) });
      updated[1] = {
        ...updated[1],
        status: resp.ok ? 'running' : 'stopped',
        detail: resp.ok ? 'Running' : 'Standalone mode',
      };
    } catch {
      updated[1] = { ...updated[1], status: 'stopped', detail: 'Standalone mode' };
    }

    // LLM Task Master — derived from llm_config.json execution mode
    try {
      const cfg = await loadLlmConfig() as Record<string, unknown>;
      const model  = typeof cfg.model === 'string' ? cfg.model : 'phi-3.5-mini';
      const mode   = typeof cfg.execution_mode === 'string' ? cfg.execution_mode : 'manual';
      updated[2] = {
        name: 'LLM Task Master',
        version: '1.0.0',
        status: mode !== 'manual' ? 'running' : 'stopped',
        detail: `${model} / ${mode}`,
      };
    } catch {
      updated[2] = { ...updated[2], status: 'stopped', detail: 'Not configured' };
    }

    setComponents(updated);
    setLastChecked(new Date().toLocaleTimeString());
    setLoading(false);
  };

  useEffect(() => { refresh(); }, []);

  const handleUninstall = async () => {
    const ok = window.confirm(
      'Uninstall Phantom completely? This runs the surgical teardown: services, firewall rules, Phantom-related Python processes, your .phantom directory, Windows LocalAppData/AppData Phantom folders, shortcuts, and user uninstall registry keys. A report is appended to the Deployment Chronicle first. You may need to restart the app afterward.',
    );
    if (!ok) return;
    setUninstallBusy(true);
    try {
      await uninstallPhantom();
      window.alert('Uninstall finished. Close and reopen Phantom if the UI still shows old deployment state.');
    } catch (e) {
      window.alert(tauriInvokeErrorMessage(e));
    } finally {
      setUninstallBusy(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Deployments</span>
        <button className="console-send-btn" onClick={refresh} disabled={loading}>
          {loading ? 'Checking…' : 'Refresh'}
        </button>
      </div>

      <div className="card">
        <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Active Deployment</span>
          {lastChecked && (
            <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 'normal' }}>
              Last checked: {lastChecked}
            </span>
          )}
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Component</th>
              <th>Version</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {components.map(c => (
              <tr key={c.name}>
                <td>{c.name}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{c.version}</td>
                <td>
                  <span className={`status-badge ${badgeClass(c.status)}`}>
                    {badgeLabel(c)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title">Remove Phantom from this machine</div>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 12 }}>
          Same operation as Troubleshooter <strong>Full Reset</strong> and the{' '}
          <code style={{ fontSize: 11 }}>scripts/uninstall.ps1</code> /{' '}
          <code style={{ fontSize: 11 }}>phantom_uninstall.py</code> tools. See{' '}
          <strong>UNINSTALLATION.md</strong> in the repository.
        </p>
        <button
          type="button"
          className="console-send-btn"
          style={{ borderColor: 'rgba(220,90,90,0.5)', color: '#e8a0a0' }}
          disabled={uninstallBusy}
          onClick={() => void handleUninstall()}
        >
          {uninstallBusy ? 'Uninstalling…' : 'Uninstall Phantom (surgical)'}
        </button>
      </div>
    </div>
  );
}
