export default function ExperimentalAOL() {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Experimental — Address Book &amp; WAN Trust</span>
      </div>

      <div className="card">
        <div className="card-title">WAN Address Book</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6 }}>
          Manage trusted peers for cross-WAN mesh communication. TLS certificates and
          trust relationships are managed here — never inside the routing engine.
        </p>
        <p style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 8 }}>
          This feature is experimental. The routing engine receives a trusted peer list
          as input but does not manage TLS, certificates, or WAN negotiation.
        </p>
      </div>

      <div className="empty-state">
        No trusted WAN peers configured.
      </div>
    </div>
  );
}
