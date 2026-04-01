/**
 * Deployment Troubleshooter — guided one-click recovery (ports, processes, env, network, chronicle).
 * Collapsible sections, scroll containment, sticky quick actions, Full Reset (surgical uninstall).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import {
  getControllerPlacementInfo,
  getDeploymentChronicle,
  runLocalCiCheck,
  runPreDeployValidation,
  troubleshooterAppendNote,
  troubleshooterCycleControllerPort,
  troubleshooterFullReset,
  troubleshooterNetworkProbes,
  troubleshooterPingController,
  troubleshooterPortCycleDefaults,
  troubleshooterProtocolHint,
  troubleshooterRestartController,
  troubleshooterRestartLocalWorker,
  troubleshooterScanPort,
  troubleshooterStopServices,
  troubleshooterVerifyArtifacts,
} from '../utils/tauri';
import {
  sortPreDeployChecksForDisplay,
  tauriInvokeErrorMessage,
  type DeployFailureInfo,
  type PreDeployReport,
} from '../state/deploymentState';
import TroubleshooterCollapsibleSection from './TroubleshooterCollapsibleSection';

interface Props {
  open: boolean;
  onClose: () => void;
  deployFailure?: DeployFailureInfo | null;
}

function formatJsonBlock(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function formatLocalCiProgress(p: Record<string, unknown>): string {
  const kind = typeof p.kind === 'string' ? p.kind : '';
  if (kind === 'stderr') {
    return typeof p.detail === 'string' ? `[log] ${p.detail}` : JSON.stringify(p);
  }
  if (kind === 'step_begin') {
    return `Starting: ${String(p.step ?? '')}`;
  }
  if (kind === 'step_end') {
    const ok = p.ok === true;
    const step = String(p.step ?? '');
    const code = p.exitCode != null ? String(p.exitCode) : '?';
    return `${ok ? '[OK]' : '[FAIL]'} ${step} (exit ${code})`;
  }
  if (kind === 'run_begin') {
    return 'Local CI run started';
  }
  if (kind === 'run_summary') {
    const ok = p.ok === true;
    const failed = Array.isArray(p.failedSteps) ? (p.failedSteps as string[]).join(', ') : '';
    return ok ? 'Summary: PASS' : `Summary: FAIL${failed ? ` — ${failed}` : ''}`;
  }
  return JSON.stringify(p);
}

function chronicleLineSummary(line: string): string {
  try {
    const o = JSON.parse(line) as Record<string, unknown>;
    const ts = typeof o.ts === 'string' ? o.ts : '';
    const src = typeof o.source === 'string' ? o.source : '';
    const sum = typeof o.summary === 'string' ? o.summary : line;
    return ts ? `[${ts}] ${src}: ${sum}` : sum;
  } catch {
    return line;
  }
}

export default function DeploymentTroubleshooter({ open, onClose, deployFailure }: Props) {
  const [chronicleLines, setChronicleLines] = useState<string[]>([]);
  const [placementPort, setPlacementPort] = useState<number | null>(null);
  const [placementHost, setPlacementHost] = useState<string>('');
  const [portCycle, setPortCycle] = useState<number[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [lastPorts, setLastPorts] = useState<string>('');
  const [lastProcesses, setLastProcesses] = useState<string>('');
  const [lastEnv, setLastEnv] = useState<string>('');
  const [lastNetwork, setLastNetwork] = useState<string>('');
  const [lastProtocol, setLastProtocol] = useState<string>('');
  const [preDeployReport, setPreDeployReport] = useState<PreDeployReport | null>(null);
  const [noteDraft, setNoteDraft] = useState('');
  const [localCiProgress, setLocalCiProgress] = useState<string[]>([]);
  const [localCiRunning, setLocalCiRunning] = useState(false);
  const [localCiOutcome, setLocalCiOutcome] = useState<{ ok: boolean; message: string } | null>(null);
  const [localCiEnsureTools, setLocalCiEnsureTools] = useState(true);
  const [localCiPortCheck, setLocalCiPortCheck] = useState(false);
  const localCiUnlistenRef = useRef<UnlistenFn | null>(null);

  const refreshChronicle = useCallback(async () => {
    try {
      const lines = await getDeploymentChronicle(200);
      setChronicleLines(lines);
    } catch (e) {
      setChronicleLines([`Could not read chronicle: ${tauriInvokeErrorMessage(e)}`]);
    }
  }, []);

  const refreshPlacement = useCallback(async () => {
    try {
      const info = await getControllerPlacementInfo();
      if (info) {
        setPlacementHost(info.host);
        setPlacementPort(info.port);
      } else {
        setPlacementHost('');
        setPlacementPort(null);
      }
    } catch {
      setPlacementPort(null);
      setPlacementHost('');
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void refreshChronicle();
    void refreshPlacement();
    void troubleshooterPortCycleDefaults().then(setPortCycle).catch(() => setPortCycle([]));
  }, [open, refreshChronicle, refreshPlacement]);

  useEffect(() => {
    return () => {
      localCiUnlistenRef.current?.();
      localCiUnlistenRef.current = null;
    };
  }, []);

  const run = useCallback(
    async (key: string, fn: () => Promise<void>) => {
      setBusy(key);
      try {
        await fn();
      } finally {
        setBusy(null);
        void refreshChronicle();
        void refreshPlacement();
      }
    },
    [refreshChronicle, refreshPlacement],
  );

  const handleRunLocalCi = async () => {
    setLocalCiRunning(true);
    setLocalCiProgress([]);
    setLocalCiOutcome(null);
    localCiUnlistenRef.current?.();
    const un = await listen<Record<string, unknown>>('local-ci-progress', (event) => {
      setLocalCiProgress((prev) => [...prev, formatLocalCiProgress(event.payload)].slice(-500));
    });
    localCiUnlistenRef.current = un;
    try {
      const result = await runLocalCiCheck({
        ensureDevTools: localCiEnsureTools,
        portCheck: localCiPortCheck,
      });
      setLocalCiOutcome({ ok: result.ok, message: result.message });
    } catch (err) {
      setLocalCiOutcome({ ok: false, message: tauriInvokeErrorMessage(err) });
    } finally {
      un();
      if (localCiUnlistenRef.current === un) {
        localCiUnlistenRef.current = null;
      }
      setLocalCiRunning(false);
      void refreshChronicle();
    }
  };

  const handleFullReset = async () => {
    const ok = window.confirm(
      'Full Reset runs a surgical uninstall: stops services, removes firewall rules, terminates Phantom-related Python processes, deletes your .phantom directory and Windows Phantom app data (LocalAppData/AppData), shortcuts, and user uninstall registry keys. A report is written to the Deployment Chronicle first (if .phantom exists). The app returns to the front porch. This cannot be undone.\n\nType OK to continue.',
    );
    if (!ok) return;
    setBusy('full_reset');
    try {
      await troubleshooterFullReset();
      window.alert(
        'Full Reset finished. If the UI still shows old state, close and reopen Phantom. Some files may remain only if the app could not remove its own running executable folder.',
      );
    } catch (e) {
      window.alert(tauriInvokeErrorMessage(e));
    } finally {
      setBusy(null);
      void refreshChronicle();
    }
  };

  if (!open) return null;

  const scanPort = placementPort ?? 8080;
  const disabled = busy !== null || localCiRunning;

  return (
    <div className="deployment-troubleshooter-shell" role="dialog" aria-label="Deployment troubleshooter">
      <div className="deployment-troubleshooter-top">
        <div className="deployment-troubleshooter-header">
          <div className="deployment-troubleshooter-header-brand">
            <img src="/phantom.png" alt="" className="deployment-troubleshooter-logo" />
            <div>
              <div className="deployment-troubleshooter-title">Deployment Troubleshooter</div>
              <p className="deployment-troubleshooter-sub">
                One-click checks and safe fixes. Phantom records everything in the Deployment Chronicle — even when
                the controller never starts.
              </p>
            </div>
          </div>
          <button type="button" className="deploy-btn ceremony-btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>

        {deployFailure && (
          <div className="deployment-troubleshooter-banner" role="status">
            <strong>Recent failure</strong>
            {deployFailure.stepLabel != null && deployFailure.stepLabel !== '' && (
              <span className="deployment-troubleshooter-banner-step">
                {deployFailure.stepIndex != null && deployFailure.stepIndex !== undefined
                  ? `Step ${deployFailure.stepIndex}: ${deployFailure.stepLabel}`
                  : deployFailure.stepLabel}
              </span>
            )}
            <pre className="deployment-troubleshooter-banner-msg">{deployFailure.message}</pre>
          </div>
        )}
      </div>

      <div className="deployment-troubleshooter-scroll">
        <TroubleshooterCollapsibleSection sectionId="ports" title="Ports and binding">
          <p className="deployment-troubleshooter-hint">
            Configured controller port:{' '}
            <strong>
              {placementPort != null ? `${placementPort}` : 'unknown (complete Controller Selection first)'}
            </strong>
            {placementHost ? ` @ ${placementHost}` : ''}
          </p>
          <p className="deployment-troubleshooter-hint">
            Fallback sequence (one step per click):{' '}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>{portCycle.join(' → ')}</span>
          </p>
          <div className="deployment-troubleshooter-actions">
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() =>
                run('scan', async () => {
                  const r = await troubleshooterScanPort(scanPort);
                  setLastPorts(
                    `Port ${scanPort}: bind probe free = ${String(r.bindProbeFree)}. ` +
                      (typeof r.netstatHint === 'string' ? r.netstatHint : ''),
                  );
                })
              }
            >
              {busy === 'scan' ? 'Scanning…' : 'Scan for port conflicts'}
            </button>
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() =>
                run('cycle', async () => {
                  const r = await troubleshooterCycleControllerPort();
                  setLastPorts(formatJsonBlock(r));
                })
              }
            >
              {busy === 'cycle' ? 'Updating…' : 'Try next port in list'}
            </button>
          </div>
          {lastPorts && <pre className="deployment-troubleshooter-result">{lastPorts}</pre>}
          <p className="deployment-troubleshooter-hint">
            If every port is taken, close other web servers or VPN software, then scan again.
          </p>
        </TroubleshooterCollapsibleSection>

        <TroubleshooterCollapsibleSection sectionId="processes" title="Processes and services">
          <p className="deployment-troubleshooter-hint">
            Best effort: stops the Phantom service if installed, then starts processes again.
          </p>
          <div className="deployment-troubleshooter-actions">
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() =>
                run('rc', async () => {
                  await troubleshooterRestartController();
                  setLastProcesses('Restart controller finished. Use Ping controller /health to confirm.');
                })
              }
            >
              {busy === 'rc' ? 'Working…' : 'Restart controller'}
            </button>
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() =>
                run('rw', async () => {
                  await troubleshooterRestartLocalWorker();
                  setLastProcesses('Restart local worker finished.');
                })
              }
            >
              {busy === 'rw' ? 'Working…' : 'Restart local worker'}
            </button>
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() =>
                run('stop', async () => {
                  await troubleshooterStopServices();
                  setLastProcesses('Stop Phantom services (no uninstall) sent.');
                })
              }
            >
              {busy === 'stop' ? 'Working…' : 'Stop Phantom services'}
            </button>
          </div>
          {lastProcesses && <pre className="deployment-troubleshooter-result">{lastProcesses}</pre>}
        </TroubleshooterCollapsibleSection>

        <TroubleshooterCollapsibleSection sectionId="env" title="Environment and prerequisites">
          <div className="deployment-troubleshooter-actions">
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() =>
                run('art', async () => {
                  const r = await troubleshooterVerifyArtifacts();
                  setLastEnv(formatJsonBlock(r));
                })
              }
            >
              {busy === 'art' ? 'Checking…' : 'Verify state, venv, and config files'}
            </button>
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() =>
                run('pre', async () => {
                  const report = await runPreDeployValidation();
                  setPreDeployReport(report);
                  setLastEnv(
                    report.ok
                      ? 'Full prerequisite checklist: all checks passed.'
                      : `Full prerequisite checklist: ${report.checks.filter((c) => c.status === 'fail').length} failure(s). See list below.`,
                  );
                })
              }
            >
              {busy === 'pre' ? 'Running…' : 'Run full prerequisite checklist'}
            </button>
          </div>
          {lastEnv && <pre className="deployment-troubleshooter-result">{lastEnv}</pre>}
          {preDeployReport && (
            <div className="deployment-troubleshooter-precheck">
              {sortPreDeployChecksForDisplay(preDeployReport.checks).map((c) => (
                <div key={`${c.id}-${c.name}`} className="deployment-troubleshooter-check-row">
                  <span
                    className={
                      c.status === 'fail'
                        ? 'deployment-troubleshooter-check-fail'
                        : c.status === 'warn'
                          ? 'deployment-troubleshooter-check-warn'
                          : 'deployment-troubleshooter-check-pass'
                    }
                  >
                    [{c.status}]
                  </span>{' '}
                  {c.name}: {c.detail}
                </div>
              ))}
            </div>
          )}
        </TroubleshooterCollapsibleSection>

        <TroubleshooterCollapsibleSection sectionId="network" title="Network and protocol">
          <div className="deployment-troubleshooter-actions">
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() =>
                run('ping', async () => {
                  const r = await troubleshooterPingController();
                  setLastNetwork(formatJsonBlock(r));
                })
              }
            >
              {busy === 'ping' ? 'Pinging…' : 'Ping controller /health'}
            </button>
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() =>
                run('tcp', async () => {
                  const r = await troubleshooterNetworkProbes();
                  setLastNetwork(formatJsonBlock(r));
                })
              }
            >
              {busy === 'tcp' ? 'Probing…' : 'Probe TCP ports (controller and worker)'}
            </button>
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() =>
                run('proto', async () => {
                  const r = await troubleshooterProtocolHint();
                  setLastProtocol(formatJsonBlock(r));
                })
              }
            >
              {busy === 'proto' ? 'Loading…' : 'Protocol compatibility hint'}
            </button>
          </div>
          {(lastNetwork || lastProtocol) && (
            <pre className="deployment-troubleshooter-result">
              {[lastNetwork, lastProtocol].filter(Boolean).join('\n---\n')}
            </pre>
          )}
        </TroubleshooterCollapsibleSection>

        <TroubleshooterCollapsibleSection sectionId="localci" title="Local CI validation">
          <p className="deployment-troubleshooter-hint">
            Same steps as GitHub <strong>test-controller</strong> (black, flake8, platform scan, import smoke,
            test_controller_import_boot). Uses Phantom venv Python only.
          </p>
          <label className="deployment-troubleshooter-check-inline">
            <input
              type="checkbox"
              checked={localCiEnsureTools}
              onChange={(e) => setLocalCiEnsureTools(e.target.checked)}
              disabled={localCiRunning}
            />
            Install/update dev tools in Phantom venv
          </label>
          <label className="deployment-troubleshooter-check-inline">
            <input
              type="checkbox"
              checked={localCiPortCheck}
              onChange={(e) => setLocalCiPortCheck(e.target.checked)}
              disabled={localCiRunning}
            />
            Also probe controller port bind
          </label>
          <div className="deployment-troubleshooter-actions">
            <button
              type="button"
              className="deploy-btn"
              disabled={disabled}
              onClick={() => void handleRunLocalCi()}
            >
              {localCiRunning ? 'Running Local CI…' : 'Run Local CI (same tests GitHub runs)'}
            </button>
          </div>
          {localCiOutcome && (
            <div
              role="status"
              className={`deployment-troubleshooter-localci-outcome ${localCiOutcome.ok ? 'is-ok' : 'is-fail'}`}
            >
              <strong>{localCiOutcome.ok ? 'PASS' : 'FAIL'}</strong> — {localCiOutcome.message}
            </div>
          )}
          {localCiProgress.length > 0 && (
            <pre className="deployment-troubleshooter-result deployment-troubleshooter-localci-log">
              {localCiProgress.join('\n')}
            </pre>
          )}
        </TroubleshooterCollapsibleSection>

        <TroubleshooterCollapsibleSection sectionId="chronicle" title="Deployment Chronicle" defaultOpen>
          <p className="deployment-troubleshooter-hint">
            Unified log (JSON lines). <strong>Full Reset</strong> writes an uninstall report here first, then removes
            data directories.
          </p>
          <div className="deployment-troubleshooter-actions">
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled}
              onClick={() => run('ch', async () => refreshChronicle())}
            >
              Refresh chronicle
            </button>
            <button
              type="button"
              className="deploy-btn"
              style={{ borderColor: 'rgba(220,90,90,0.55)', color: '#e8a0a0' }}
              disabled={disabled}
              onClick={() => void handleFullReset()}
            >
              {busy === 'full_reset' ? 'Resetting…' : 'Full Reset (surgical uninstall)'}
            </button>
          </div>
          <div className="deployment-troubleshooter-chronicle-note">
            <input
              type="text"
              className="deployment-troubleshooter-input"
              placeholder="Add a short note to the chronicle (optional)"
              value={noteDraft}
              onChange={(e) => setNoteDraft(e.target.value)}
            />
            <button
              type="button"
              className="deploy-btn ceremony-btn-secondary"
              disabled={disabled || !noteDraft.trim()}
              onClick={() =>
                run('note', async () => {
                  await troubleshooterAppendNote(noteDraft.trim());
                  setNoteDraft('');
                })
              }
            >
              Append note
            </button>
          </div>
          <div className="deployment-troubleshooter-chronicle-scroll">
            {chronicleLines.length === 0 ? (
              <div className="deployment-troubleshooter-hint">No chronicle lines yet.</div>
            ) : (
              chronicleLines.map((line, i) => (
                <div key={i} className="deployment-troubleshooter-chronicle-line" title={line}>
                  {chronicleLineSummary(line)}
                </div>
              ))
            )}
          </div>
        </TroubleshooterCollapsibleSection>
      </div>

      <div className="deployment-troubleshooter-sticky-actions" role="toolbar" aria-label="Quick actions">
        <span className="deployment-troubleshooter-sticky-label">Quick:</span>
        <button
          type="button"
          className="deploy-btn ceremony-btn-secondary ts-sticky-btn"
          disabled={disabled}
          onClick={() =>
            run('scan', async () => {
              const r = await troubleshooterScanPort(scanPort);
              setLastPorts(
                `Port ${scanPort}: bind probe free = ${String(r.bindProbeFree)}. ` +
                  (typeof r.netstatHint === 'string' ? r.netstatHint : ''),
              );
            })
          }
        >
          Scan port
        </button>
        <button
          type="button"
          className="deploy-btn ceremony-btn-secondary ts-sticky-btn"
          disabled={disabled}
          onClick={() =>
            run('cycle', async () => {
              const r = await troubleshooterCycleControllerPort();
              setLastPorts(formatJsonBlock(r));
            })
          }
        >
          Next port
        </button>
        <button
          type="button"
          className="deploy-btn ceremony-btn-secondary ts-sticky-btn"
          disabled={disabled}
          onClick={() =>
            run('rc', async () => {
              await troubleshooterRestartController();
              setLastProcesses('Restart controller finished.');
            })
          }
        >
          Restart controller
        </button>
        <button
          type="button"
          className="deploy-btn ceremony-btn-secondary ts-sticky-btn"
          disabled={disabled}
          onClick={() =>
            run('rw', async () => {
              await troubleshooterRestartLocalWorker();
              setLastProcesses('Restart local worker finished.');
            })
          }
        >
          Restart worker
        </button>
        <button
          type="button"
          className="deploy-btn ceremony-btn-secondary ts-sticky-btn"
          disabled={disabled}
          onClick={() =>
            run('stop', async () => {
              await troubleshooterStopServices();
              setLastProcesses('Stop services sent.');
            })
          }
        >
          Stop services
        </button>
        <button
          type="button"
          className="deploy-btn ceremony-btn-secondary ts-sticky-btn"
          disabled={disabled}
          onClick={() => void handleRunLocalCi()}
        >
          Run Local CI
        </button>
        <button
          type="button"
          className="deploy-btn ceremony-btn-secondary ts-sticky-btn"
          disabled={disabled}
          onClick={() => run('ch', async () => refreshChronicle())}
        >
          Refresh chronicle
        </button>
      </div>
    </div>
  );
}
