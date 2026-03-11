/**
 * Screen 4 Part 3 — Diagnostic Tools
 *
 * Shown only when worker_count === 0. Displays raw discovery log,
 * Copy to Clipboard, and phantomctl command instructions.
 */

import { useCallback, useState } from 'react';
import { useDeploymentCeremony } from '../state/DeploymentCeremonyContext';
import { discoveryLogToSanitizedString } from '../state/deploymentState';

const PHANTOMCTL_COMMANDS = [
  'phantomctl discovery --debug',
  'phantomctl worker-status',
  'phantomctl trust-log',
];

export default function Screen4Diagnostics() {
  const { state } = useDeploymentCeremony();
  const { discoveryLog } = state;
  const [copied, setCopied] = useState(false);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);

  const handleCopyLog = useCallback(async () => {
    if (!discoveryLog) return;
    const text = discoveryLogToSanitizedString(discoveryLog);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }, [discoveryLog]);

  const handleCopyCommand = useCallback(async (cmd: string) => {
    try {
      await navigator.clipboard.writeText(cmd);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }, []);

  if (!discoveryLog) return null;

  return (
    <div className="ceremony-part">
      <h3 className="ceremony-heading">No Workers Detected</h3>
      <p className="ceremony-subtext ceremony-error">
        Phantom cannot proceed without at least one worker. Use diagnostic tools to troubleshoot.
      </p>

      <button
        type="button"
        className="deploy-btn ceremony-diagnostics-btn"
        onClick={() => setDiagnosticsOpen(!diagnosticsOpen)}
      >
        {diagnosticsOpen ? 'Close Diagnostic Tools' : 'Open Diagnostic Tools'}
      </button>

      {diagnosticsOpen && (
        <div className="ceremony-diagnostics-panel">
          <div className="ceremony-diagnostics-header">
            <span>Discovery Log</span>
            <button
              type="button"
              className="deploy-btn ceremony-copy-btn"
              onClick={handleCopyLog}
              disabled={!discoveryLog}
            >
              {copied ? 'Copied!' : 'Copy Log to Clipboard'}
            </button>
          </div>
          <pre className="ceremony-log-pre">
            {discoveryLog.rawEntries.length > 0
              ? discoveryLog.rawEntries.join('\n')
              : 'No raw entries recorded.'}
          </pre>

          <div className="ceremony-commands-section">
            <div className="ceremony-heading" style={{ marginBottom: 8 }}>
              Diagnostic Commands
            </div>
            <p className="ceremony-subtext" style={{ marginBottom: 12 }}>
              Run these in a terminal to troubleshoot. Copy and paste as needed.
            </p>
            {PHANTOMCTL_COMMANDS.map((cmd) => (
              <div key={cmd} className="ceremony-command-row">
                <code className="ceremony-command-code">{cmd}</code>
                <button
                  type="button"
                  className="deploy-btn ceremony-copy-btn"
                  onClick={() => handleCopyCommand(cmd)}
                >
                  Copy
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
