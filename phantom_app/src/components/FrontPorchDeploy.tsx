import { useState, useEffect } from 'react';
import { listen, UnlistenFn } from '@tauri-apps/api/event';
import { deployPhantom } from '../utils/tauri';
import '../styles/deploy.css';

interface DeployProgress {
  step: number;
  total_steps: number;
  label: string;
  fraction: number;
}

interface Props {
  onDeployComplete: () => void;
}

export default function FrontPorchDeploy({ onDeployComplete }: Props) {
  const [deploying, setDeploying] = useState(false);
  const [progress, setProgress] = useState<DeployProgress | null>(null);

  useEffect(() => {
    let unlisten: UnlistenFn | undefined;

    listen<DeployProgress>('deploy-progress', (event) => {
      setProgress(event.payload);
      if (event.payload.fraction >= 1.0) {
        setTimeout(onDeployComplete, 1200);
      }
    }).then((fn) => {
      unlisten = fn;
    });

    return () => { unlisten?.(); };
  }, [onDeployComplete]);

  const handleDeploy = async () => {
    setDeploying(true);
    try {
      await deployPhantom();
    } catch (err) {
      console.error('Deploy failed:', err);
      setDeploying(false);
    }
  };

  const pct = progress ? Math.round(progress.fraction * 100) : 0;

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
        </div>
      ) : (
        <button className="deploy-btn" onClick={handleDeploy} disabled={deploying}>
          Deploy Phantom
        </button>
      )}
    </div>
  );
}
