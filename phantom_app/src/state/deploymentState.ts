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
  /** Base64 Ed25519 public key — for §5 TrustRecord(approved). */
  publicKeyB64?: string;
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
  readinessProbeAttempts: number;
  readinessProbeSuccess: boolean;
  diagnosticHints: string[];
  /** ``lan_udp`` | ``offline_synthetic`` — set by deploy backend. */
  discoveryMode?: string | null;
}

export interface DeploymentPreScanResult {
  discoveredWorkers: DiscoveredWorker[];
  discoveryLog: DiscoveryLog;
  discoveryFailed: boolean;
  /** Phase 3 — deploy used an offline bundle (no PyPI / no LAN discovery). */
  offlineMode?: boolean;
}

/** Phase 3 — optional flags for run_deployment_pre_scan / deploy_phantom. */
export interface DeploymentPreScanOptions {
  offline?: boolean | null;
  offlineBundlePath?: string | null;
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
  /** Base64 Ed25519 public key — for §5 TrustRecord(approved). */
  publicKeyB64?: string;
}

/** Returned after ceremony registration (trust approve + register). */
export interface WorkerRegistrationSummary {
  selectedCount: number;
  trustFailedCount: number;
  registeredCount: number;
  registrationFailedCount: number;
}

export function poolFullyRegistered(summary: WorkerRegistrationSummary): boolean {
  return summary.selectedCount > 0 && summary.registeredCount === summary.selectedCount;
}

/** Phase 4 — `run_pre_deploy_validation` checklist item. */
export interface PreDeployCheck {
  id: string;
  name: string;
  status: 'pass' | 'fail' | 'warn' | 'skip' | string;
  detail: string;
}

export interface PreDeployReport {
  ok: boolean;
  checks: PreDeployCheck[];
  phantomRoot: string;
  engineSource: string;
}

/** Backend ``deploy-failed`` event + invoke error context (deploy / registration). */
export interface DeployFailureInfo {
  message: string;
  stepIndex?: number | null;
  stepLabel?: string | null;
}

// ── Phase 11 — Unified ceremony DTOs (Rust serde camelCase parity) ─────

export interface ActDetailDto {
  currentAct: string | null;
  lastCompletedAct: string | null;
}

export interface CeremonyStatusDto {
  sCeremony: string;
  correlationId: string | null;
  outcomeClass: string | null;
  warnings: string[];
  actDetail: ActDetailDto;
}

export interface OperationalEvaluationClause {
  id: string;
  name: string;
  pass: boolean;
  detail: string;
}

export interface OperationalEvaluation {
  operational: boolean;
  clauses: OperationalEvaluationClause[];
}

export interface DiscoverySnapshot {
  snapshotId: string;
  correlationId: string;
  createdAt: string;
  candidates: unknown[];
  policyFlags: unknown;
}

export interface RegistrationAttempt {
  correlationId: string;
  snapshotId: string;
  rows: unknown[];
  aggregateClass: string;
}

export interface ProcessStatus {
  pid: number | null;
  label: string;
  bindClaimed: boolean;
  detail: string;
}

export function tauriInvokeErrorMessage(err: unknown): string {
  if (typeof err === 'string') return err;
  if (err instanceof Error) return err.message;
  if (err && typeof err === 'object') {
    const o = err as Record<string, unknown>;
    if (typeof o.message === 'string') return o.message;
    if (typeof o.error === 'string') return o.error;
  }
  return String(err);
}

const checkRank = (status: string): number => {
  if (status === 'fail') return 0;
  if (status === 'warn') return 1;
  if (status === 'skip') return 2;
  return 3;
};

/** Fail and warn first so operators see blockers without scrolling. */
export function sortPreDeployChecksForDisplay(checks: PreDeployCheck[]): PreDeployCheck[] {
  return [...checks].sort((a, b) => checkRank(a.status) - checkRank(b.status));
}

/** Manual LAN scan + register (Workers panel). */
export interface LanScanRegistrationResult {
  scanned: number;
  registered: number;
  registrationFailed: number;
  partialRegistration: boolean;
  /** Present when ``state/offline_install.json`` blocks Workers-panel LAN discovery. */
  lanScanSkipped?: boolean;
  lanScanSkipReason?: string | null;
  nodes: Array<[string, number]>;
}

// ── Ceremony State ─────────────────────────────────────────────────────

export interface DeploymentCeremonyState {
  discoveredWorkers: DiscoveredWorker[];
  discoveryLog: DiscoveryLog | null;
  discoveryFailed: boolean;
  /** Deploy used an offline bundle (synthetic worker, no UDP discovery). */
  offlineDeploy: boolean;
  controllerConfig: ControllerConfig | null;
  workerPool: DiscoveredWorker[];
}

export const initialDeploymentCeremonyState: DeploymentCeremonyState = {
  discoveredWorkers: [],
  discoveryLog: null,
  discoveryFailed: false,
  offlineDeploy: false,
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
    publicKeyB64: w.publicKeyB64,
  };
}

/**
 * Phase 12 — synthesize a `DeploymentPreScanResult` from a ceremony Act C
 * `DiscoverySnapshot` (read via `ceremonyGetDiscoverySnapshot`). Lets the
 * existing Screen 4 components (`Screen4ControllerSelect`, `Screen4WorkerSelect`)
 * render the ceremony candidates without a parallel implementation.
 *
 * Doctrine: read-only projection. Never mutates ceremony state.
 */
export function preScanResultFromDiscoverySnapshot(
  snapshot: Record<string, unknown> | null,
): DeploymentPreScanResult {
  const candidatesRaw = Array.isArray(snapshot?.candidates)
    ? (snapshot!.candidates as unknown[])
    : [];
  const discoveredWorkers: DiscoveredWorker[] = candidatesRaw
    .filter((c): c is Record<string, unknown> => !!c && typeof c === 'object')
    .map((c) => {
      const port = typeof c.port === 'number' ? c.port : Number(c.port ?? 0);
      return {
        workerId: String(c.workerId ?? ''),
        host: String(c.host ?? ''),
        port: Number.isFinite(port) ? port : 0,
        gpuInfo: (c.gpuInfo && typeof c.gpuInfo === 'object'
          ? (c.gpuInfo as Record<string, unknown>)
          : {}),
        sourceIp: String(c.sourceIp ?? ''),
        signatureVerified: Boolean(c.signatureVerified ?? false),
        fingerprint: String(c.fingerprint ?? ''),
        publicKeyB64: typeof c.publicKeyB64 === 'string' ? c.publicKeyB64 : undefined,
      } as DiscoveredWorker;
    });

  const policyFlags =
    snapshot?.policyFlags && typeof snapshot.policyFlags === 'object'
      ? (snapshot.policyFlags as Record<string, unknown>)
      : {};
  const offlineSynthetic = Boolean(policyFlags.offline_synthetic ?? policyFlags.offlineSynthetic);
  const partial = Boolean(policyFlags.discovery_partial ?? policyFlags.discoveryPartial);

  const discoveryLog: DiscoveryLog = {
    timestamp: typeof snapshot?.createdAt === 'string' ? snapshot.createdAt : new Date().toISOString(),
    interfacesScanned: [],
    broadcastPort: 8095,
    packetsSent: 0,
    responsesReceived: discoveredWorkers.length,
    signatureFailures: 0,
    manifestErrors: 0,
    workerCount: discoveredWorkers.length,
    rawEntries: [],
    readinessProbeAttempts: 0,
    readinessProbeSuccess: discoveredWorkers.length > 0,
    diagnosticHints:
      discoveredWorkers.length === 0
        ? ['Act C produced an empty snapshot; check LAN reachability or run preflight.']
        : [],
    discoveryMode: offlineSynthetic ? 'offline_synthetic' : 'lan_udp',
  };

  return {
    discoveredWorkers,
    discoveryLog,
    discoveryFailed: discoveredWorkers.length === 0 || partial,
    offlineMode: offlineSynthetic,
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
  ];
  if (log.discoveryMode) {
    lines.push(`Discovery mode: ${log.discoveryMode}`);
  }
  if (log.readinessProbeAttempts > 0) {
    lines.push(
      `Readiness probe: ${log.readinessProbeSuccess ? 'succeeded' : `timed out after ${log.readinessProbeAttempts} attempt(s)`}`,
    );
  }
  lines.push('--- Raw entries ---', ...(log.rawEntries ?? []));
  const hints = log.diagnosticHints ?? [];
  if (log.workerCount === 0 && hints.length > 0) {
    lines.push('--- Possible causes ---');
    hints.forEach((h) => lines.push(`  • ${h}`));
  }
  return lines.join('\n');
}
