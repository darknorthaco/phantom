import { useState, useEffect } from 'react';
import { scanAndRegisterWorkers } from '../utils/tauri';

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
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);

  const fetchWorkers = () => {
    setLoading(true);
    setScanResult(null);
    fetch('http://127.0.0.1:8080/workers')
      .then((r) => r.json())
      .then((d) => { setWorkers(d.workers || []); setLoading(false); })
      .catch(() => setLoading(false));
  };

  const runScan = () => {
    setScanning(true);
    setScanResult(null);
    scanAndRegisterWorkers()
      .then((r) => {
        setScanning(false);
        setScanResult(
          `Scanned ${r.scanned} node(s), registered ${r.registered} worker(s)`
        );
        fetchWorkers();
      })
      .catch((e) => {
        setScanning(false);
        setScanResult(`Scan failed: ${e}`);
      });
  };

  useEffect(() => { fetchWorkers(); }, []);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Workers</span>
        <button
          className="console-send-btn"
          onClick={runScan}
          disabled={scanning}
          title="Scan LAN for Phantom workers on port 8090 and register with controller"
        >
          {scanning ? 'Scanning…' : 'Scan LAN'}
        </button>
        <button className="console-send-btn" onClick={fetchWorkers}>Refresh</button>
      </div>
      {scanResult && (
        <div className="scan-result" style={{ fontSize: '0.85em', marginBottom: 8 }}>
          {scanResult}
        </div>
      )}

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
