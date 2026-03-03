export default function DeploymentsPanel() {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Deployments</span>
      </div>

      <div className="card">
        <div className="card-title">Active Deployment</div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Component</th>
              <th>Version</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Phantom Controller</td>
              <td>2.0.0</td>
              <td><span className="status-badge active">Running</span></td>
            </tr>
            <tr>
              <td>Socket Infrastructure</td>
              <td>1.0.0</td>
              <td><span className="status-badge offline">Standalone</span></td>
            </tr>
            <tr>
              <td>LLM Task Master</td>
              <td>1.0.0</td>
              <td><span className="status-badge offline">Not Deployed</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
