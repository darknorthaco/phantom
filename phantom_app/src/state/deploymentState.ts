/**
 * Phantom Deployment Ceremony — State & Types
 *
 * Matches backend structures (camelCase from run_deployment_pre_scan,
 * complete_deployment_with_selection). Used by Screen 4 components.
 */

// ── Types (match backend serialization) ────────────────────────────────

export interface DiscoveredWorker {
  workerId: string;
  host: string;
  port: number;
  gpuInfo: Record<string, unknown>;
  sourceIp: string;
  signatureVerified: boolean;
  fingerprint: string;
}

export interface DiscoveryLog {
  timestamp: string;
  interfacesScanned: string[];
  broadcastPort: number;
  packetsSent: number;
  responsesReceived: number;
  signatureFailures: number;
  manifestErrors: number;
  workerCount: number;
  rawEntries: string[];
}

export interface DeploymentPreScanResult {
  discoveredWorkers: DiscoveredWorker[];
  discoveryLog: DiscoveryLog;
  discoveryFailed: boolean;
}

export interface ControllerConfig {
  host: string;
  workerId: string;
  runControllerLlm: boolean;
}

/** Worker selection for complete_deployment_with_selection (matches backend). */
export interface WorkerSelectionForRegistration {
  workerId: string;
  host: string;
  port: number;
  gpuInfo: Record<string, unknown>;
}

// ── Ceremony State ─────────────────────────────────────────────────────

export interface DeploymentCeremonyState {
  discoveredWorkers: DiscoveredWorker[];
  discoveryLog: DiscoveryLog | null;
  discoveryFailed: boolean;
  controllerConfig: ControllerConfig | null;
  workerPool: DiscoveredWorker[];
}

export const initialDeploymentCeremonyState: DeploymentCeremonyState = {
  discoveredWorkers: [],
  discoveryLog: null,
  discoveryFailed: false,
  controllerConfig: null,
  workerPool: [],
};

// ── Helpers ───────────────────────────────────────────────────────────

/** Convert DiscoveredWorker to WorkerSelectionForRegistration for API call. */
export function toWorkerSelection(w: DiscoveredWorker): WorkerSelectionForRegistration {
  return {
    workerId: w.workerId,
    host: w.host,
    port: w.port,
    gpuInfo: w.gpuInfo ?? {},
  };
}

/** Build sanitized discovery log string for copy/paste (mirrors backend to_sanitized_string). */
export function discoveryLogToSanitizedString(log: DiscoveryLog): string {
  const lines = [
    `Phantom Discovery Log — ${log.timestamp}`,
    `Interfaces scanned: ${JSON.stringify(log.interfacesScanned)}`,
    `Broadcast port: ${log.broadcastPort}`,
    `Packets sent: ${log.packetsSent}`,
    `Responses received: ${log.responsesReceived}`,
    `Signature failures: ${log.signatureFailures}`,
    `Manifest parse errors: ${log.manifestErrors}`,
    `Worker count: ${log.workerCount}`,
    '--- Raw entries ---',
    ...log.rawEntries,
  ];
  return lines.join('\n');
}
