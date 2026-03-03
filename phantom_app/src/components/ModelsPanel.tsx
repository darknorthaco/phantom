export default function ModelsPanel() {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Models</span>
      </div>

      <div className="card">
        <div className="card-title">LLM Task Master</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6 }}>
          The LLM Task Master uses a lightweight local model (e.g. Phi-3.5 Mini) to make
          intelligent routing decisions. It runs on your GPU and never contacts external servers.
        </p>
        <div style={{ marginTop: 12 }}>
          <span className="status-badge offline">Not Deployed</span>
        </div>
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
              <td>Phi-3.5 Mini</td>
              <td>3.8B</td>
              <td>Task routing</td>
              <td><span className="status-badge offline">Available</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
