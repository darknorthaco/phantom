/**
 * Screen 4 Part 1 — Controller Hardware Selection
 *
 * Display discovered workers, user selects exactly one controller host
 * and optionally enables "Run Controller LLM (Phi-Lite) on selected hardware".
 */

import { useDeploymentCeremony } from '../state/DeploymentCeremonyContext';
import type { DiscoveredWorker } from '../state/deploymentState';

function formatHardware(w: DiscoveredWorker): string {
  const g = w.gpuInfo as Record<string, unknown>;
  const parts: string[] = [];
  if (g?.gpu) parts.push(String(g.gpu));
  if (g?.vram) parts.push(`${g.vram} MB`);
  if (g?.cpu) parts.push(String(g.cpu));
  if (g?.os) parts.push(String(g.os));
  return parts.length > 0 ? parts.join(' · ') : 'Hardware unknown';
}

function SignatureBadge({ verified }: { verified: boolean }) {
  if (verified) {
    return (
      <span className="ceremony-badge ceremony-badge-verified" title="Signature verified">
        ✓ Verified
      </span>
    );
  }
  return (
    <span className="ceremony-badge ceremony-badge-unverified" title="Signature unverified">
      ✗ Unverified
    </span>
  );
}

export default function Screen4ControllerSelect() {
  const { state, setControllerConfig } = useDeploymentCeremony();
  const { discoveredWorkers, controllerConfig } = state;

  const handleSelect = (w: DiscoveredWorker) => {
    const runLlm = controllerConfig?.workerId === w.workerId ? controllerConfig.runControllerLlm : false;
    setControllerConfig({
      host: w.host,
      workerId: w.workerId,
      runControllerLlm: runLlm,
    });
  };

  const handleLlmToggle = () => {
    if (!controllerConfig) return;
    setControllerConfig({
      ...controllerConfig,
      runControllerLlm: !controllerConfig.runControllerLlm,
    });
  };

  return (
    <div className="ceremony-part">
      <h3 className="ceremony-heading">Controller Hardware Selection</h3>
      <p className="ceremony-subtext">
        Select the host that will run the Phantom controller. All discovered workers are shown, including this machine.
      </p>

      <div className="ceremony-worker-list">
        {discoveredWorkers.map((w) => {
          const isSelected = controllerConfig?.workerId === w.workerId;
          return (
            <div
              key={w.workerId}
              className={`ceremony-worker-card ${isSelected ? 'ceremony-worker-card-selected' : ''}`}
              onClick={() => handleSelect(w)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && handleSelect(w)}
            >
              <div className="ceremony-worker-radio">
                <span className={`ceremony-radio-dot ${isSelected ? 'ceremony-radio-dot-selected' : ''}`} />
              </div>
              <div className="ceremony-worker-body">
                <div className="ceremony-worker-header">
                  <span className="ceremony-worker-id">{w.workerId}</span>
                  <SignatureBadge verified={w.signatureVerified} />
                </div>
                <div className="ceremony-worker-meta">
                  {w.host}:{w.port}
                  {w.sourceIp && w.sourceIp !== w.host && ` (from ${w.sourceIp})`}
                </div>
                <div className="ceremony-worker-hardware">{formatHardware(w)}</div>
              </div>
            </div>
          );
        })}
      </div>

      {controllerConfig && (
        <label className="ceremony-toggle-row">
          <input
            type="checkbox"
            checked={controllerConfig.runControllerLlm}
            onChange={handleLlmToggle}
          />
          <span>Run Controller LLM (Phi-Lite) on selected hardware</span>
        </label>
      )}
    </div>
  );
}
