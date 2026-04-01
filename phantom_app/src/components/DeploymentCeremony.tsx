/**
 * Screen 4 — Deployment Ceremony (multi-part container)
 *
 * Tabs: [ Controller | Workers | Diagnostics ]
 * Diagnostics only visible when worker_count === 0.
 * Continue enabled when controller chosen + ≥1 worker + !discovery_failed.
 */

import { useEffect, useState } from 'react';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { useDeploymentCeremony } from '../state/DeploymentCeremonyContext';
import {
  toWorkerSelection,
  tauriInvokeErrorMessage,
  type DeployFailureInfo,
  type DeploymentPreScanResult,
  type WorkerRegistrationSummary,
} from '../state/deploymentState';
import { completeDeploymentWithSelection } from '../utils/tauri';
import DeploymentTroubleshooter from './DeploymentTroubleshooter';
import Screen4ControllerSelect from './Screen4ControllerSelect';
import Screen4WorkerSelect from './Screen4WorkerSelect';
import Screen4Diagnostics from './Screen4Diagnostics';

type TabId = 'controller' | 'workers' | 'diagnostics';

interface Props {
  preScanResult: DeploymentPreScanResult;
  onComplete: (summary: WorkerRegistrationSummary) => void;
  onBack?: () => void;
  onError?: (err: string) => void;
}

export default function DeploymentCeremony({ preScanResult, onComplete, onBack, onError }: Props) {
  const { state, applyPreScanResult } = useDeploymentCeremony();

  useEffect(() => {
    applyPreScanResult(preScanResult);
  }, [preScanResult, applyPreScanResult]);

  const { discoveryFailed, offlineDeploy, controllerConfig, workerPool } = state;

  const showDiagnostics = discoveryFailed;

  const allTabs: { id: TabId; label: string; visible: boolean }[] = [
    { id: 'controller', label: 'Controller', visible: !discoveryFailed },
    { id: 'workers', label: 'Workers', visible: !discoveryFailed },
    { id: 'diagnostics', label: 'Diagnostics', visible: showDiagnostics },
  ];
  const tabs = allTabs.filter((t) => t.visible) as { id: TabId; label: string; visible: boolean }[];

  const [activeTab, setActiveTab] = useState<TabId>(
    discoveryFailed ? 'diagnostics' : 'controller'
  );

  const canContinue =
    !discoveryFailed &&
    controllerConfig !== null &&
    workerPool.length >= 1;

  const [completing, setCompleting] = useState(false);
  const [completeError, setCompleteError] = useState<string | null>(null);
  const [troubleshooterOpen, setTroubleshooterOpen] = useState(false);
  const [deployFailure, setDeployFailure] = useState<DeployFailureInfo | null>(null);

  useEffect(() => {
    let unlistenFailed: UnlistenFn | undefined;
    listen<DeployFailureInfo>('deploy-failed', (event) => {
      setDeployFailure(event.payload);
      setTroubleshooterOpen(true);
    }).then((fn) => {
      unlistenFailed = fn;
    });
    return () => {
      unlistenFailed?.();
    };
  }, []);

  const handleContinue = async () => {
    if (!canContinue || !controllerConfig) return;
    setCompleteError(null);
    setCompleting(true);
    try {
      const workerSelections = workerPool.map(toWorkerSelection);
      const summary = await completeDeploymentWithSelection(
        workerSelections,
        controllerConfig.runControllerLlm
      );
      onComplete(summary);
    } catch (err) {
      const msg = tauriInvokeErrorMessage(err);
      setCompleteError(msg);
      onError?.(msg);
    } finally {
      setCompleting(false);
    }
  };

  return (
    <div className="deploy-screen ceremony-screen">
      <div className="phantom-mask-container">
        <img src="/phantom.png" alt="Phantom" className="phantom-mask-svg" />
      </div>

      <div className="deploy-title">Deployment Ceremony</div>

      {completeError && (
        <div
          role="alert"
          style={{
            maxWidth: 520,
            margin: '0 auto 16px',
            padding: '12px 14px',
            background: 'rgba(180, 60, 60, 0.12)',
            border: '1px solid rgba(220, 90, 90, 0.45)',
            borderRadius: 6,
            textAlign: 'left',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 8, color: '#e8a0a0' }}>
            Registration or finalize step failed
          </div>
          <pre
            style={{
              margin: 0,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              lineHeight: 1.45,
              color: 'var(--text-primary)',
            }}
          >
            {completeError}
          </pre>
          <p
            style={{
              margin: '10px 0 0',
              fontSize: 11,
              lineHeight: 1.5,
              color: 'var(--text-secondary)',
            }}
          >
            Trust or register API errors are logged by the controller. Adjust worker selection or trust,
            then try <strong>Continue</strong> again. Use the troubleshooter for ports, process restarts, and the
            Deployment Chronicle.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
            <button
              type="button"
              className="deploy-btn"
              style={{ fontSize: 11, padding: '6px 12px' }}
              onClick={() => setTroubleshooterOpen(true)}
            >
              Open Deployment Troubleshooter
            </button>
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              style={{ fontSize: 11, padding: '6px 12px' }}
              onClick={() => setCompleteError(null)}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {offlineDeploy && !discoveryFailed && (
        <p
          className="ceremony-subtext"
          style={{
            maxWidth: 520,
            margin: '0 auto 16px',
            padding: '10px 14px',
            background: 'rgba(180, 140, 60, 0.12)',
            border: '1px solid rgba(180, 140, 60, 0.35)',
            borderRadius: 6,
            fontSize: 12,
            lineHeight: 1.5,
            color: 'var(--text-secondary)',
          }}
        >
          Offline bundle deploy: UDP LAN discovery was skipped. The worker list uses a synthetic
          placeholder so you can finish the ceremony; trust approval may warn until real worker keys
          are registered. Discovery mode:{' '}
          <span style={{ fontFamily: 'var(--font-mono)' }}>offline_synthetic</span>.
        </p>
      )}

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
                className="deploy-btn ceremony-btn-secondary"
                onClick={() => setTroubleshooterOpen(true)}
              >
                Troubleshoot deployment
              </button>
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

      <DeploymentTroubleshooter
        open={troubleshooterOpen}
        onClose={() => setTroubleshooterOpen(false)}
        deployFailure={deployFailure}
      />
    </div>
  );
}
