import { useState, useEffect, useRef } from 'react';
import { listen, UnlistenFn } from '@tauri-apps/api/event';
import { scanAndRegisterWorkers } from '../utils/tauri';

interface Worker {
  worker_id: string;
  host: string;
  port: number;
  gpu_info: Record<string, unknown>;
  status: string;
  signature_verified?: boolean;
  fingerprint?: string;
  key_changed?: boolean;
}

/** Signature status badge for §3 manifest verification. */
function SignatureBadge({ worker }: { worker: Worker }) {
  if (worker.key_changed) {
    return (
      <span
        className="status-badge"
        style={{ background: 'var(--accent-crimson, #dc3545)', color: '#fff' }}
        title="Public key changed — re-approval required"
      >
        ⚠ Key Changed
      </span>
    );
  }
  if (worker.signature_verified === true) {
    return (
      <span
        className="status-badge active"
        title={`Verified · ${worker.fingerprint ?? ''}`}
      >
        ✓ Verified
      </span>
    );
  }
  if (worker.signature_verified === false) {
    return (
      <span
        className="status-badge offline"
        title="Signature missing or invalid — not eligible for auto-selection"
      >
        ✗ Unverified
      </span>
    );
  }
  // undefined — legacy worker, no sig info
  return (
    <span className="status-badge" style={{ opacity: 0.6 }} title="No signature data (legacy worker)">
      — N/A
    </span>
  );
}

export default function WorkersPanel() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [scanLog, setScanLog] = useState<string[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

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
    setScanLog([]);
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

  useEffect(() => {
    let unlisten: UnlistenFn | undefined;
    listen<string>('scan-log', (event) => {
      setScanLog((prev) => [...prev, event.payload]);
    }).then((fn) => {
      unlisten = fn;
    });
    return () => { unlisten?.(); };
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [scanLog]);

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
      {scanning && (
        <div
          className="scan-log"
          style={{
            marginBottom: 12,
            maxHeight: 180,
            overflow: 'auto',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            padding: 8,
            background: 'rgba(0,0,0,0.2)',
            borderRadius: 4,
            textAlign: 'left',
          }}
        >
          {scanLog.length > 0 ? (
            scanLog.map((line, i) => (
              <div key={i} style={{ marginBottom: 2 }}>
                {line}
              </div>
            ))
          ) : (
            <div style={{ opacity: 0.7 }}>Scanning…</div>
          )}
          <div ref={logEndRef} />
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
              <th>Signature</th>
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
                <td><SignatureBadge worker={w} /></td>
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
