import { useState, useEffect, useRef } from 'react';
import { listen, UnlistenFn } from '@tauri-apps/api/event';
import { runDeploymentPreScan } from '../utils/tauri';
import type { DeploymentPreScanResult } from '../state/deploymentState';
import '../styles/deploy.css';

interface DeployProgress {
  step: number;
  total_steps: number;
  label: string;
  fraction: number;
}

interface Props {
  /** Called when pre-scan completes; transitions to deployment ceremony. */
  onPreScanComplete: (result: DeploymentPreScanResult) => void;
}

export default function FrontPorchDeploy({ onPreScanComplete }: Props) {
  const [deploying, setDeploying] = useState(false);
  const [progress, setProgress] = useState<DeployProgress | null>(null);
  const [scanLog, setScanLog] = useState<string[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let unlistenProgress: UnlistenFn | undefined;
    let unlistenScan: UnlistenFn | undefined;

    listen<DeployProgress>('deploy-progress', (event) => {
      setProgress(event.payload);
      if (event.payload.label !== 'Scanning LAN' && event.payload.label !== 'Starting local worker') {
        setScanLog([]);
      }
    }).then((fn) => {
      unlistenProgress = fn;
    });

    listen<string>('scan-log', (event) => {
      setScanLog((prev) => [...prev, event.payload]);
    }).then((fn) => {
      unlistenScan = fn;
    });

    return () => {
      unlistenProgress?.();
      unlistenScan?.();
    };
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [scanLog]);

  const handleDeploy = async () => {
    setDeploying(true);
    setScanLog([]);
    try {
      const result = await runDeploymentPreScan();
      onPreScanComplete(result);
    } catch (err) {
      console.error('Pre-scan failed:', err);
      setDeploying(false);
    }
  };

  const pct = progress ? Math.round(progress.fraction * 100) : 0;
  const showScanLog =
    deploying && (progress?.label === 'Scanning LAN' || progress?.label === 'Starting local worker');

  return (
    <div className="deploy-screen">
      <div className="phantom-mask-container">
        <img src="/phantom.svg" alt="Phantom" className="phantom-mask-svg" />
      </div>

      <div className="deploy-title">
        {deploying ? 'Phantom Awakening' : 'Phantom Awaits'}
      </div>

      {deploying ? (
        <div className="loading-bar-container">
          <div className="loading-bar-track">
            <div className="loading-bar-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="micro-status">
            {progress?.label || 'Initializing…'}
          </div>
          {showScanLog && scanLog.length > 0 && (
            <div
              className="scan-log"
              style={{
                marginTop: 12,
                maxHeight: 160,
                overflow: 'auto',
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                padding: 8,
                background: 'rgba(0,0,0,0.25)',
                borderRadius: 4,
                textAlign: 'left',
              }}
            >
              {scanLog.map((line, i) => (
                <div key={i} style={{ marginBottom: 2 }}>
                  {line}
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          )}
        </div>
      ) : (
        <button className="deploy-btn" onClick={handleDeploy} disabled={deploying}>
          Deploy Phantom
        </button>
      )}
    </div>
  );
}
