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
  tauriInvokeErrorMessage,
  type DeployFailureInfo,
  type DeploymentPreScanResult,
  type OperationalEvaluation,
  type WorkerRegistrationSummary,
} from '../state/deploymentState';
import {
  deployModeFromBuild,
  ceremonyRunActD,
  ceremonyRunActE,
  ceremonyRunActF,
  ceremonyStatus,
  operationalEvaluate,
} from '../utils/tauri';
import DeploymentTroubleshooter from './DeploymentTroubleshooter';
import DeployModeBadge from './DeployModeBadge';
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
  const [ceremonyStage, setCeremonyStage] = useState<string | null>(null);
  const [opEval, setOpEval] = useState<OperationalEvaluation | null>(null);
  const ceremonyFirst = deployModeFromBuild() === 'ceremony';

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

  // In ceremony-first mode, surface a live operational predicate snapshot for
  // the operator (read-only). Doctrine: never used to gate Continue — the
  // backend acts (D/E/F) are themselves authoritative.
  useEffect(() => {
    if (!ceremonyFirst) return;
    let cancelled = false;
    const refresh = () => {
      operationalEvaluate()
        .then((e) => {
          if (!cancelled) setOpEval(e);
        })
        .catch(() => {
          if (!cancelled) setOpEval(null);
        });
    };
    refresh();
    const id = window.setInterval(refresh, 5_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [ceremonyFirst]);

  /**
   * Phase 12 — ceremony-first Continue. Drives Acts D→F via the orchestrator
   * and synthesizes a `WorkerRegistrationSummary` from `operational_evaluate`
   * so the existing consent / TOC flow keeps working unchanged.
   *
   * NOTE: user-selected primary worker is not yet plumbed through Act D
   * (current Act D auto-selects LAN-first from the snapshot). This is the
   * next incremental Phase 12 deliverable; for now, we honour the operator's
   * worker pool selection by surfacing it in the chronicle but do not yet
   * override Act D's primary pick.
   */
  const handleContinueCeremonyFirst = async () => {
    if (!canContinue || !controllerConfig) return;
    setCompleteError(null);
    setCompleting(true);
    try {
      setCeremonyStage('Act D — configure');
      await ceremonyRunActD();

      setCeremonyStage('Act E — attest');
      await ceremonyRunActE();

      setCeremonyStage('Act F — register');
      await ceremonyRunActF();

      setCeremonyStage('Reading ceremony status');
      const status = await ceremonyStatus().catch(() => null);
      const evaluation = await operationalEvaluate().catch(() => null);
      setOpEval(evaluation);

      const summary: WorkerRegistrationSummary = {
        selectedCount: workerPool.length,
        trustFailedCount: 0,
        registeredCount:
          status?.sCeremony === 'CS_OPERATIONAL' && evaluation?.operational
            ? workerPool.length
            : 0,
        registrationFailedCount:
          status?.sCeremony === 'CS_OPERATIONAL' && evaluation?.operational
            ? 0
            : workerPool.length,
      };
      onComplete(summary);
    } catch (err) {
      const msg = tauriInvokeErrorMessage(err);
      setCompleteError(`${ceremonyStage ?? 'Ceremony'}: ${msg}`);
      onError?.(msg);
    } finally {
      setCompleting(false);
      setCeremonyStage(null);
    }
  };

  const handleContinue = handleContinueCeremonyFirst;

  return (
    <div className="deploy-screen ceremony-screen">
      <div className="phantom-mask-container">
        <img src="/phantom.png" alt="Phantom" className="phantom-mask-svg" />
      </div>

      <div className="deploy-title">Deployment Ceremony</div>
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <DeployModeBadge />
      </div>

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

        {ceremonyFirst && opEval && (
          <div
            style={{
              maxWidth: 620,
              margin: '0 auto 12px',
              padding: '8px 12px',
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
              background: 'rgba(0,0,0,0.25)',
              border: `1px solid ${opEval.operational ? 'rgba(80,160,120,0.4)' : 'rgba(220,180,120,0.45)'}`,
              borderRadius: 4,
              textAlign: 'left',
            }}
          >
            <div style={{ marginBottom: 6, letterSpacing: 1, fontWeight: 600 }}>
              Predicate {opEval.operational ? 'OPERATIONAL' : 'NOT YET OPERATIONAL'}
            </div>
            {opEval.clauses.map((c) => (
              <div key={c.id} style={{ marginBottom: 2 }}>
                <span style={{ color: c.pass ? 'var(--accent-green, #6a8)' : '#dc8' }}>
                  [{c.pass ? 'pass' : 'fail'}]
                </span>{' '}
                {c.name}
                {!c.pass && c.detail ? `: ${c.detail}` : ''}
              </div>
            ))}
          </div>
        )}

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
                disabled={!canContinue || completing || !ceremonyFirst}
                title={
                  ceremonyFirst
                    ? 'Run Acts D→F via the ceremony orchestrator'
                    : 'Legacy build detected. Use ceremony-first build.'
                }
              >
                {completing
                  ? ceremonyFirst && ceremonyStage
                    ? ceremonyStage
                    : 'Completing…'
                  : ceremonyFirst
                    ? 'Continue (ceremony-first)'
                    : 'Continue unavailable (legacy build)'}
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
