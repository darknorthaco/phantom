export default function EphemeralPanel() {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Ephemeral Access</span>
      </div>

      <div className="card">
        <div className="card-title">Temporary Worker Access</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6 }}>
          Grant time-limited, scope-restricted access to workers for guests or temporary
          workloads. All ephemeral sessions are fully audited.
        </p>
      </div>

      <div className="empty-state">
        No active ephemeral sessions.
      </div>
    </div>
  );
}
