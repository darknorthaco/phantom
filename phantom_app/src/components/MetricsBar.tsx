import { useState, useEffect } from 'react';
import { getSystemMetrics } from '../utils/tauri';

interface Props {
  health: Record<string, unknown> | null;
  onRefresh: () => void;
}

interface SysMetrics {
  cpu_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
}

export default function MetricsBar({ health, onRefresh }: Props) {
  const [sys, setSys] = useState<SysMetrics | null>(null);

  // Poll system metrics (CPU/RAM) every 10 seconds via Tauri.
  // Falls back gracefully when running outside Tauri (Vite browser preview).
  useEffect(() => {
    const fetch = () => {
      getSystemMetrics()
        .then((m) => setSys(m as unknown as SysMetrics))
        .catch(() => setSys(null));
    };
    fetch();
    const id = setInterval(fetch, 10_000);
    return () => clearInterval(id);
  }, []);

  const workersCount = (health?.workers_count as number) ?? 0;
  const activeTasks  = (health?.active_tasks  as number) ?? 0;
  const mode         = (health?.execution_mode as string) ?? 'MANUAL';
  const status       = (health?.status        as string) ?? 'unknown';

  const cpuLabel = sys ? `${sys.cpu_percent.toFixed(0)}%` : '—';
  const ramLabel = sys
    ? `${sys.memory_used_mb >= 1024
        ? (sys.memory_used_mb / 1024).toFixed(1) + ' GB'
        : sys.memory_used_mb + ' MB'} / ${
        sys.memory_total_mb >= 1024
          ? (sys.memory_total_mb / 1024).toFixed(0) + ' GB'
          : sys.memory_total_mb + ' MB'}`
    : '—';

  const cpuWarn = sys ? sys.cpu_percent > 80 : false;
  const ramWarn = sys ? sys.memory_used_mb / sys.memory_total_mb > 0.85 : false;

  return (
    <div className="metrics-bar">
      <div className="metric-item">
        <span className={`metric-dot ${status === 'healthy' ? '' : 'error'}`} />
        <span className="metric-label">Status</span>
        <span className="metric-value">{status.toUpperCase()}</span>
      </div>

      <div className="metric-item">
        <span className="metric-dot" />
        <span className="metric-label">Mode</span>
        <span className="metric-value">{mode}</span>
      </div>

      <div className="metric-item">
        <span className="metric-dot" />
        <span className="metric-label">Workers</span>
        <span className="metric-value">{workersCount}</span>
      </div>

      <div className="metric-item">
        <span className={`metric-dot ${activeTasks > 0 ? 'warn' : ''}`} />
        <span className="metric-label">Tasks</span>
        <span className="metric-value">{activeTasks}</span>
      </div>

      <div className="metric-item">
        <span className={`metric-dot ${cpuWarn ? 'warn' : ''}`} />
        <span className="metric-label">CPU</span>
        <span className="metric-value">{cpuLabel}</span>
      </div>

      <div className="metric-item">
        <span className={`metric-dot ${ramWarn ? 'warn' : ''}`} />
        <span className="metric-label">RAM</span>
        <span className="metric-value">{ramLabel}</span>
      </div>

      <div
        className="metric-item"
        style={{ marginLeft: 'auto', cursor: 'pointer' }}
        onClick={onRefresh}
      >
        <span className="metric-label" style={{ textDecoration: 'underline' }}>Refresh</span>
      </div>

      <div className="metric-item">
        <span className="metric-label">PHANTOM v1.0</span>
      </div>
    </div>
  );
}
