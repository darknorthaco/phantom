interface Props {
  health: Record<string, unknown> | null;
  onRefresh: () => void;
}

export default function MetricsBar({ health, onRefresh }: Props) {
  const workersCount = (health?.workers_count as number) ?? 0;
  const activeTasks = (health?.active_tasks as number) ?? 0;
  const mode = (health?.execution_mode as string) ?? 'MANUAL';
  const status = (health?.status as string) ?? 'unknown';

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
      <div className="metric-item" style={{ marginLeft: 'auto', cursor: 'pointer' }} onClick={onRefresh}>
        <span className="metric-label" style={{ textDecoration: 'underline' }}>Refresh</span>
      </div>
      <div className="metric-item">
        <span className="metric-label">PHANTOM v1.0</span>
      </div>
    </div>
  );
}
