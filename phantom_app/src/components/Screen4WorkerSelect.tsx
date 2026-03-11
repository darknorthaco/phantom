/**
 * Screen 4 Part 2 — Worker Pool Admission
 *
 * Each worker has a checkbox "Include in worker pool".
 * User must select at least one worker.
 */

import { useDeploymentCeremony } from '../state/DeploymentCeremonyContext';
import type { DiscoveredWorker } from '../state/deploymentState';

function formatHardware(w: DiscoveredWorker): string {
  const g = w.gpuInfo as Record<string, unknown>;
  const parts: string[] = [];
  if (g?.gpu) parts.push(String(g.gpu));
  if (g?.vram) parts.push(`${g.vram} MB`);
  return parts.length > 0 ? parts.join(' · ') : 'Hardware unknown';
}

export default function Screen4WorkerSelect() {
  const { state, setWorkerPool } = useDeploymentCeremony();
  const { discoveredWorkers, workerPool } = state;

  const isInPool = (w: DiscoveredWorker) =>
    workerPool.some((p) => p.workerId === w.workerId);

  const handleToggle = (w: DiscoveredWorker, include: boolean) => {
    if (include) {
      setWorkerPool([...workerPool, w]);
    } else {
      const next = workerPool.filter((p) => p.workerId !== w.workerId);
      setWorkerPool(next);
    }
  };

  return (
    <div className="ceremony-part">
      <h3 className="ceremony-heading">Worker Pool Admission</h3>
      <p className="ceremony-subtext">
        Select at least one worker to include in the Phantom worker pool.
      </p>

      <div className="ceremony-worker-list">
        {discoveredWorkers.map((w) => {
          const included = isInPool(w);
          return (
            <label key={w.workerId} className="ceremony-worker-card ceremony-worker-card-checkbox">
              <input
                type="checkbox"
                checked={included}
                onChange={(e) => handleToggle(w, e.target.checked)}
              />
              <div className="ceremony-worker-body">
                <div className="ceremony-worker-header">
                  <span className="ceremony-worker-id">{w.workerId}</span>
                  <span
                    className={`ceremony-badge ${w.signatureVerified ? 'ceremony-badge-verified' : 'ceremony-badge-unverified'}`}
                  >
                    {w.signatureVerified ? '✓' : '✗'}
                  </span>
                </div>
                <div className="ceremony-worker-meta">
                  {w.host}:{w.port}
                </div>
                <div className="ceremony-worker-hardware">{formatHardware(w)}</div>
              </div>
            </label>
          );
        })}
      </div>

      {workerPool.length === 0 && (
        <p className="ceremony-warning">
          You must select at least one worker to continue.
        </p>
      )}
    </div>
  );
}
