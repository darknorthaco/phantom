import { useState, useEffect, useRef, useCallback } from 'react';
import { listen, UnlistenFn } from '@tauri-apps/api/event';
import {
  ceremonyCommitPlacement,
  ceremonyGetDiscoverySnapshot,
  ceremonyPreflight,
  ceremonyReadActBLog,
  ceremonyRunActB,
  ceremonyRunActC,
  deployModeFromBuild,
  getControllerPlacementInfo,
  runPreDeployValidation,
  type PreflightCheck,
  type PreflightReport,
} from '../utils/tauri';
import {
  preScanResultFromDiscoverySnapshot,
  sortPreDeployChecksForDisplay,
  tauriInvokeErrorMessage,
  type DeployFailureInfo,
  type DeploymentPreScanResult,
  type PreDeployReport,
} from '../state/deploymentState';
import DeploymentTroubleshooter from './DeploymentTroubleshooter';
import DeployModeBadge from './DeployModeBadge';
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
  const [preDeployReport, setPreDeployReport] = useState<PreDeployReport | null>(null);
  const [preDeployBusy, setPreDeployBusy] = useState(false);
  const [deployFailure, setDeployFailure] = useState<DeployFailureInfo | null>(null);
  const [troubleshooterOpen, setTroubleshooterOpen] = useState(false);
  const [preflight, setPreflight] = useState<PreflightReport | null>(null);
  const [preflightBusy, setPreflightBusy] = useState(false);
  const [actBLog, setActBLog] = useState<string[]>([]);
  const [ceremonyStage, setCeremonyStage] = useState<string | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const deployMode = deployModeFromBuild();
  const ceremonyFirst = deployMode === 'ceremony';

  const loadPreflight = useCallback(async () => {
    setPreflightBusy(true);
    try {
      const r = await ceremonyPreflight();
      setPreflight(r);
    } catch (e) {
      setPreflight({
        ok: false,
        checks: [
          {
            id: 'preflight.invoke_error',
            name: 'Preflight invoke',
            pass: false,
            detail: tauriInvokeErrorMessage(e),
            hint: 'Backend ceremony_preflight command failed; check phantom logs.',
          },
        ],
      });
    } finally {
      setPreflightBusy(false);
    }
  }, []);

  // Always run preflight on mount — read-only, doctrine-aligned, never network egress.
  useEffect(() => {
    loadPreflight();
  }, [loadPreflight]);

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

    let unlistenFailed: UnlistenFn | undefined;
    listen<DeployFailureInfo>('deploy-failed', (event) => {
      setDeployFailure(event.payload);
      setTroubleshooterOpen(true);
    }).then((fn) => {
      unlistenFailed = fn;
    });

    return () => {
      unlistenProgress?.();
      unlistenScan?.();
      unlistenFailed?.();
    };
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [scanLog]);

  /**
   * Phase 12 ceremony-first deploy. Drives Acts A→C through the orchestrator,
   * then hands the resulting Act C snapshot to the existing DeploymentCeremony
   * UI as a synthesized DeploymentPreScanResult. Acts D→F run from the next screen.
   *
   * Doctrine: LAN-first. WAN reachability is irrelevant. Offline bundle is
   * explicit-only and is not used here unless the operator has separately set one.
   */
  const handleDeployCeremonyFirst = async () => {
    setDeployFailure(null);
    setDeploying(true);
    setScanLog([]);
    setActBLog([]);
    try {
      setCeremonyStage('Reading placement');
      const placement = await getControllerPlacementInfo();
      if (!placement) {
        throw new Error(
          'controller_placement.json missing. Complete the controller selection screen first.',
        );
      }
      const fp = placement.identityFingerprint ?? '';
      if (!fp) {
        throw new Error(
          'placement is missing identity_fingerprint. Re-confirm controller selection.',
        );
      }

      setCeremonyStage('Act A — committing placement');
      await ceremonyCommitPlacement(
        placement.host,
        placement.port,
        placement.deviceLabel ?? '',
        fp,
      );

      setCeremonyStage('Act B — materializing engine');
      try {
        await ceremonyRunActB({});
      } catch (e) {
        const tail = await ceremonyReadActBLog(50).catch(() => [] as string[]);
        setActBLog(tail);
        throw e;
      }

      setCeremonyStage('Act C — LAN discovery');
      await ceremonyRunActC({});

      setCeremonyStage('Reading discovery snapshot');
      const snap = await ceremonyGetDiscoverySnapshot();
      const result = preScanResultFromDiscoverySnapshot(snap);
      onPreScanComplete(result);
    } catch (err) {
      const msg = tauriInvokeErrorMessage(err);
      console.error('Ceremony-first deploy failed:', err);
      setDeployFailure((prev) => prev ?? { message: msg, stepLabel: ceremonyStage ?? 'Ceremony deploy' });
      setTroubleshooterOpen(true);
      setDeploying(false);
      setCeremonyStage(null);
    }
  };

  const handleDeploy = handleDeployCeremonyFirst;

  const handlePreDeployValidate = async () => {
    setPreDeployBusy(true);
    setPreDeployReport(null);
    try {
      const report = await runPreDeployValidation();
      setPreDeployReport(report);
    } catch (e) {
      setPreDeployReport({
        ok: false,
        checks: [
          {
            id: 'invoke_error',
            name: 'Validation command',
            status: 'fail',
            detail: e instanceof Error ? e.message : String(e),
          },
        ],
        phantomRoot: '',
        engineSource: '',
      });
    } finally {
      setPreDeployBusy(false);
    }
  };

  const pct = progress ? Math.round(progress.fraction * 100) : 0;
  const showScanLog =
    deploying &&
    (progress?.label === 'Scanning LAN' ||
      progress?.label === 'Starting local worker' ||
      progress?.label === 'Starting controller');

  // PR-J end-state: Deploy button is ceremony-only.
  const deployBlockedByPreflight = preflight !== null && !preflight.ok;
  const deployBlockedByMode = !ceremonyFirst;

  return (
    <div className={`deploy-screen${deploying ? ' deploy-screen--active' : ''}`}>
      <div className="deploy-screen-logo-container">
        <img src="/phantom.png" alt="Phantom" className="deploy-screen-logo" />
      </div>

      <div className="deploy-title">
        {deploying ? 'Phantom Awakening' : 'Phantom Awaits'}
      </div>
      <div style={{ marginBottom: 8 }}>
        <DeployModeBadge />
      </div>

      {deploying ? (
        <div className="loading-bar-container">
          <div className="loading-bar-track">
            <div className="loading-bar-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="micro-status">
            {ceremonyFirst && ceremonyStage ? ceremonyStage : progress?.label || 'Initializing…'}
          </div>
          {showScanLog && scanLog.length > 0 && (
            <div
              className="scan-log deploy-prescan-scroll"
              style={{
                marginTop: 12,
                maxHeight: 'min(220px, 28vh)',
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
        <div className="deploy-screen-idle-column">
          <PreflightPanel
            report={preflight}
            busy={preflightBusy}
            ceremonyFirst={ceremonyFirst}
            onRefresh={loadPreflight}
          />

          {actBLog.length > 0 && (
            <div
              className="scan-log"
              style={{
                marginTop: 4,
                maxWidth: 'min(620px, 100%)',
                maxHeight: 'min(220px, 28vh)',
                overflow: 'auto',
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                padding: 10,
                background: 'rgba(0,0,0,0.25)',
                borderRadius: 4,
                textAlign: 'left',
                border: '1px solid rgba(200,90,90,0.45)',
              }}
            >
              <div style={{ marginBottom: 8, fontWeight: 600, letterSpacing: 1 }}>
                Act B bootstrap log (tail)
              </div>
              {actBLog.map((line, i) => (
                <div key={i} style={{ marginBottom: 2, whiteSpace: 'pre-wrap' }}>
                  {line}
                </div>
              ))}
            </div>
          )}

          {deployFailure && (
            <div
              role="alert"
              style={{
                maxWidth: 540,
                padding: '12px 14px',
                background: 'rgba(180, 60, 60, 0.12)',
                border: '1px solid rgba(220, 90, 90, 0.45)',
                borderRadius: 6,
                textAlign: 'left',
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 8, color: '#e8a0a0' }}>
                Deployment could not finish
              </div>
              {deployFailure.stepLabel != null && deployFailure.stepLabel !== '' && (
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-secondary)',
                    marginBottom: 8,
                  }}
                >
                  {deployFailure.stepIndex != null && deployFailure.stepIndex !== undefined
                    ? `Step ${deployFailure.stepIndex}: ${deployFailure.stepLabel}`
                    : deployFailure.stepLabel}
                </div>
              )}
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
                {deployFailure.message}
              </pre>
              <p
                style={{
                  margin: '10px 0 0',
                  fontSize: 11,
                  lineHeight: 1.5,
                  color: 'var(--text-secondary)',
                }}
              >
                Run <strong>Validate prerequisites</strong> for a full checklist, or open the{' '}
                <strong>Deployment Troubleshooter</strong> for ports, restarts, and the Deployment Chronicle. If
                the controller failed to start, logs also live under your Phantom home directory (for example{' '}
                <span style={{ fontFamily: 'var(--font-mono)' }}>.phantom</span>).
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
                  onClick={() => setDeployFailure(null)}
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}
          <button
            className="deploy-btn"
            onClick={handleDeploy}
            disabled={deploying || deployBlockedByPreflight || deployBlockedByMode}
            title={
              deployBlockedByMode
                ? 'This build was compiled in legacy compat mode. Use a ceremony-first build.'
                : deployBlockedByPreflight
                ? 'Resolve preflight failures before deploying.'
                : 'Deploy via ceremony-first orchestrator (Acts A→F)'
            }
          >
            {deployBlockedByMode ? 'Deploy unavailable (legacy build)' : 'Deploy Phantom (ceremony-first)'}
          </button>
          <button
            type="button"
            className="deploy-btn ceremony-btn-secondary"
            onClick={handlePreDeployValidate}
            disabled={preDeployBusy}
            style={{ fontSize: 11, padding: '8px 16px' }}
          >
            {preDeployBusy ? 'Running checklist…' : 'Validate prerequisites'}
          </button>
          <button
            type="button"
            className="deploy-btn ceremony-btn-secondary"
            onClick={() => setTroubleshooterOpen(true)}
            style={{ fontSize: 11, padding: '8px 16px' }}
          >
            Troubleshoot deployment
          </button>
          <DeploymentTroubleshooter
            open={troubleshooterOpen}
            onClose={() => setTroubleshooterOpen(false)}
            deployFailure={deployFailure}
          />
          {preDeployReport && (
            <div
              className="scan-log"
              style={{
                marginTop: 4,
                maxWidth: 'min(520px, 100%)',
                maxHeight: 'min(320px, 42vh)',
                overflow: 'auto',
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                padding: 10,
                background: 'rgba(0,0,0,0.25)',
                borderRadius: 4,
                textAlign: 'left',
                border: `1px solid ${preDeployReport.ok ? 'rgba(80,160,120,0.4)' : 'rgba(200,90,90,0.45)'}`,
              }}
            >
              <div style={{ marginBottom: 8, fontWeight: 600, letterSpacing: 1 }}>
                Pre-deploy {preDeployReport.ok ? 'OK' : 'ISSUES'} — {preDeployReport.checks.length} checks
              </div>
              {!preDeployReport.ok && (
                <div
                  style={{
                    marginBottom: 10,
                    fontSize: 10,
                    lineHeight: 1.45,
                    color: 'var(--text-secondary)',
                  }}
                >
                  Fix failing items before deploying. Warnings may be acceptable depending on your setup.
                </div>
              )}
              {(preDeployReport.phantomRoot || preDeployReport.engineSource) && (
                <div
                  style={{
                    marginBottom: 10,
                    fontSize: 9,
                    lineHeight: 1.4,
                    color: '#888',
                    wordBreak: 'break-all',
                  }}
                >
                  {preDeployReport.phantomRoot && (
                    <div>
                      <span style={{ opacity: 0.85 }}>Phantom root:</span> {preDeployReport.phantomRoot}
                    </div>
                  )}
                  {preDeployReport.engineSource && (
                    <div>
                      <span style={{ opacity: 0.85 }}>Engine source:</span> {preDeployReport.engineSource}
                    </div>
                  )}
                </div>
              )}
              {sortPreDeployChecksForDisplay(preDeployReport.checks).map((c) => (
                <div key={`${c.id}-${c.name}`} style={{ marginBottom: 6 }}>
                  <span
                    style={{
                      color:
                        c.status === 'pass'
                          ? 'var(--accent-green, #6a8)'
                          : c.status === 'fail'
                            ? '#e88'
                            : c.status === 'warn'
                              ? '#dc8'
                              : '#888',
                    }}
                  >
                    [{c.status}]
                  </span>{' '}
                  {c.name}: {c.detail}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface PreflightPanelProps {
  report: PreflightReport | null;
  busy: boolean;
  ceremonyFirst: boolean;
  onRefresh: () => void;
}

function PreflightPanel({ report, busy, ceremonyFirst, onRefresh }: PreflightPanelProps) {
  if (!report && !busy) return null;
  const okBorder = 'rgba(80,160,120,0.4)';
  const failBorder = 'rgba(200,90,90,0.45)';
  return (
    <div
      className="scan-log"
      style={{
        marginTop: 4,
        maxWidth: 'min(620px, 100%)',
        maxHeight: 'min(280px, 36vh)',
        overflow: 'auto',
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        padding: 10,
        background: 'rgba(0,0,0,0.25)',
        borderRadius: 4,
        textAlign: 'left',
        border: `1px solid ${report?.ok ? okBorder : failBorder}`,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <div style={{ fontWeight: 600, letterSpacing: 1 }}>
          LAN-first preflight {busy ? '(running…)' : report?.ok ? 'OK' : 'ISSUES'}
        </div>
        <button
          type="button"
          className="deploy-btn ceremony-btn-secondary"
          style={{ fontSize: 9, padding: '4px 8px' }}
          onClick={onRefresh}
          disabled={busy}
        >
          Re-run
        </button>
      </div>
      {!report?.ok && ceremonyFirst && (
        <div
          style={{
            marginBottom: 10,
            fontSize: 10,
            lineHeight: 1.45,
            color: 'var(--text-secondary)',
          }}
        >
          Ceremony-first deploy is gated by preflight. Resolve failing items, then re-run.
        </div>
      )}
      {report?.checks?.map((c: PreflightCheck) => (
        <div key={c.id} style={{ marginBottom: 6 }}>
          <span style={{ color: c.pass ? 'var(--accent-green, #6a8)' : '#e88' }}>
            [{c.pass ? 'pass' : 'fail'}]
          </span>{' '}
          {c.name}: {c.detail}
          {!c.pass && c.hint && (
            <div style={{ marginLeft: 14, color: 'var(--text-secondary)', fontSize: 9 }}>
              hint: {c.hint}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
