/**
 * Screen 4 — Deployment Ceremony (multi-part container)
 *
 * Tabs: [ Controller | Workers | Diagnostics ]
 * Diagnostics only visible when worker_count === 0.
 * Continue enabled when controller chosen + ≥1 worker + !discovery_failed.
 */

import { useEffect, useState } from 'react';
import { useDeploymentCeremony } from '../state/DeploymentCeremonyContext';
import { toWorkerSelection, type DeploymentPreScanResult } from '../state/deploymentState';
import { completeDeploymentWithSelection } from '../utils/tauri';
import Screen4ControllerSelect from './Screen4ControllerSelect';
import Screen4WorkerSelect from './Screen4WorkerSelect';
import Screen4Diagnostics from './Screen4Diagnostics';

type TabId = 'controller' | 'workers' | 'diagnostics';

interface Props {
  preScanResult: DeploymentPreScanResult;
  onComplete: () => void;
  onBack?: () => void;
  onError?: (err: string) => void;
}

export default function DeploymentCeremony({ preScanResult, onComplete, onBack, onError }: Props) {
  const { state, applyPreScanResult } = useDeploymentCeremony();

  useEffect(() => {
    applyPreScanResult(preScanResult);
  }, [preScanResult, applyPreScanResult]);

  const {
    discoveredWorkers,
    discoveryFailed,
    controllerConfig,
    workerPool,
  } = state;

  const showDiagnostics = discoveryFailed;

  const tabs: { id: TabId; label: string; visible: boolean }[] = [
    { id: 'controller', label: 'Controller', visible: !discoveryFailed },
    { id: 'workers', label: 'Workers', visible: !discoveryFailed },
    { id: 'diagnostics', label: 'Diagnostics', visible: showDiagnostics },
  ].filter((t) => t.visible);

  const [activeTab, setActiveTab] = useState<TabId>(
    discoveryFailed ? 'diagnostics' : 'controller'
  );

  const canContinue =
    !discoveryFailed &&
    controllerConfig !== null &&
    workerPool.length >= 1;

  const [completing, setCompleting] = useState(false);

  const handleContinue = async () => {
    if (!canContinue || !controllerConfig) return;
    setCompleting(true);
    try {
      const workerSelections = workerPool.map(toWorkerSelection);
      await completeDeploymentWithSelection(
        workerSelections,
        controllerConfig.runControllerLlm
      );
      onComplete();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      onError?.(msg);
    } finally {
      setCompleting(false);
    }
  };

  return (
    <div className="deploy-screen ceremony-screen">
      <div className="phantom-mask-container">
        <img src="/phantom.svg" alt="Phantom" className="phantom-mask-svg" />
      </div>

      <div className="deploy-title">Deployment Ceremony</div>

      <div className="ceremony-body">
        <div className="ceremony-tabs">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`ceremony-tab ${activeTab === t.id ? 'ceremony-tab-active' : ''}`}
              onClick={() => setActiveTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="ceremony-content">
          {activeTab === 'controller' && <Screen4ControllerSelect />}
          {activeTab === 'workers' && <Screen4WorkerSelect />}
          {activeTab === 'diagnostics' && <Screen4Diagnostics />}
        </div>

        <div className="ceremony-actions">
          {discoveryFailed ? (
            <>
              <p className="ceremony-error-text">
                No workers detected. Cannot proceed to TOC.
              </p>
              {onBack && (
                <button
                  type="button"
                  className="deploy-btn ceremony-btn-secondary"
                  style={{ marginTop: 12 }}
                  onClick={onBack}
                >
                  Back — Retry Scan
                </button>
              )}
            </>
          ) : (
            <div className="ceremony-actions-row">
              {onBack && (
                <button
                  type="button"
                  className="deploy-btn ceremony-btn-secondary"
                  onClick={onBack}
                >
                  Back
                </button>
              )}
              <button
                type="button"
                className="deploy-btn"
                onClick={handleContinue}
                disabled={!canContinue || completing}
              >
                {completing ? 'Completing…' : 'Continue'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
