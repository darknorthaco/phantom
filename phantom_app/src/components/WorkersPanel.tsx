import { useState, useEffect } from 'react';

interface Worker {
  worker_id: string;
  host: string;
  port: number;
  gpu_info: Record<string, unknown>;
  status: string;
}

export default function WorkersPanel() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchWorkers = () => {
    setLoading(true);
    fetch('http://127.0.0.1:8080/workers')
      .then((r) => r.json())
      .then((d) => { setWorkers(d.workers || []); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => { fetchWorkers(); }, []);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Workers</span>
        <button className="console-send-btn" onClick={fetchWorkers}>Refresh</button>
      </div>

      {loading ? (
        <div className="empty-state">Loading workers…</div>
      ) : workers.length === 0 ? (
        <div className="empty-state">No workers registered. Use LAN scan or register via API.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Host</th>
              <th>Port</th>
              <th>GPU</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {workers.map((w) => (
              <tr key={w.worker_id}>
                <td style={{ fontFamily: 'var(--font-mono)' }}>{w.worker_id}</td>
                <td>{w.host}</td>
                <td>{w.port}</td>
                <td>{(w.gpu_info as Record<string, string>)?.name ?? '—'}</td>
                <td>
                  <span className={`status-badge ${w.status === 'active' ? 'active' : 'offline'}`}>
                    {w.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
