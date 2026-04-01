import { invoke } from '@tauri-apps/api/core';
import type {
  DeploymentPreScanOptions,
  DeploymentPreScanResult,
  LanScanRegistrationResult,
  PreDeployReport,
  WorkerRegistrationSummary,
  WorkerSelectionForRegistration,
} from '../state/deploymentState';

// Identity (Phase 1)
export const getIdentity = () => invoke<Record<string, unknown>>('get_identity');

// §1 Controller Selection Ceremony — persist placement params before deploy
export const confirmControllerPlacement = (
  host: string,
  port: number,
  deviceLabel: string,
  identityFingerprint: string
) =>
  invoke<void>('confirm_controller_placement', {
    host,
    port,
    deviceLabel,
    identityFingerprint,
  });
export const signMessage = (message: string) => invoke<string>('sign_message', { message });
export const verifySignature = (publicKeyB64: string, message: string, signatureB64: string) =>
  invoke<boolean>('verify_signature', { publicKeyB64, message, signatureB64 });

// TLS (Phase 2)
export const generateCertificate = () => invoke<Record<string, unknown>>('generate_certificate');

/** Phase 4 — self-signed PEM (optional CN); paths under state/tls/ */
export const generateSelfSignedCert = (commonName?: string | null) =>
  invoke<Record<string, unknown>>('generate_self_signed_cert', { commonName: commonName ?? null });

export const importTlsCert = (certSource: string, keySource: string) =>
  invoke<Record<string, unknown>>('import_tls_cert', { certSource, keySource });

export const validateTlsCert = (path: string) =>
  invoke<Record<string, unknown>>('validate_tls_cert', { path });

/** Merge WAN/TLS into ~/.phantom/phantom_config.json (requires Step 4.5 done first). */
export const savePhantomTlsSettings = (
  wanMode: boolean,
  tlsEnabled: boolean,
  tlsCertPath: string,
  tlsKeyPath: string
) =>
  invoke<void>('save_phantom_tls_settings', {
    settings: {
      wanMode,
      tlsEnabled,
      tlsCertPath,
      tlsKeyPath,
    },
  });

// Trust (Phase 3)
export const getTrustLedger = () => invoke<Record<string, unknown>>('get_trust_ledger');
export const approvePeer = (peerId: string) => invoke<void>('approve_peer', { peerId });
export const rejectPeer = (peerId: string) => invoke<void>('reject_peer', { peerId });

// Audit (Phase 4)
export const getAuditLog = (limit: number) => invoke<Array<Record<string, unknown>>>('get_audit_log', { limit });

// Execution modes (Phase 5)
export const getExecutionMode = () => invoke<Record<string, unknown>>('get_execution_mode');
export const setExecutionMode = (mode: string) => invoke<Record<string, unknown>>('set_execution_mode', { mode });
export const loadLlmConfig = () => invoke<Record<string, unknown>>('load_llm_config');

// System metrics (Phase 6)
export const getSystemMetrics = () => invoke<Record<string, unknown>>('get_system_metrics');

// Integrity (Phase 7)
export const checkIntegrity = () => invoke<Record<string, unknown>>('check_integrity');

// Deployment ceremony (Phase 2 — phased deploy flow; Phase 3 optional offline options)
export const runDeploymentPreScan = (options?: DeploymentPreScanOptions | null) =>
  invoke<DeploymentPreScanResult>('run_deployment_pre_scan', { options: options ?? null });

/** Phase 4 — deterministic checklist before deploy (placement, engine, venv, TLS, /health). */
export const runPreDeployValidation = () =>
  invoke<PreDeployReport>('run_pre_deploy_validation');

export const completeDeploymentWithSelection = (
  workerPool: WorkerSelectionForRegistration[],
  runControllerLlm: boolean
) =>
  invoke<WorkerRegistrationSummary>('complete_deployment_with_selection', {
    workerPool,
    runControllerLlm,
  });

// Original commands
export const getDeploymentStatus = () => invoke<string>('get_deployment_status');
export const deployPhantom = (options?: DeploymentPreScanOptions | null) =>
  invoke<void>('deploy_phantom', { options: options ?? null });
export const getPhantomHealth = () => invoke<Record<string, unknown>>('get_phantom_health');
export const getControllerBaseUrl = () => invoke<string>('get_controller_base_url');
export const getWorkers = () => invoke<Record<string, unknown>>('get_workers');
export const getStats = () => invoke<Record<string, unknown>>('get_stats');
export const getTaskStatus = (taskId: string) =>
  invoke<Record<string, unknown>>('get_task_status', { taskId });
export const submitTask = (taskType: string, parameters: Record<string, unknown>, priority: number) =>
  invoke<Record<string, unknown>>('submit_task', { taskType, parameters, priority });
export const scanAndRegisterWorkers = () =>
  invoke<LanScanRegistrationResult>('scan_and_register_workers');

// Phase 3 — offline bundle
export const verifyOfflineBundle = (path: string) =>
  invoke<Record<string, unknown>>('verify_offline_bundle', { path });
export const loadOfflineModelCatalogue = (path: string) =>
  invoke<Record<string, unknown>>('load_offline_model_catalogue', { path });
export const installOfflineBundle = (path: string) =>
  invoke<Record<string, unknown>>('install_offline_bundle', { path });

// Deployment Troubleshooter + chronicle
export const getDeploymentChronicle = (limit: number) =>
  invoke<string[]>('get_deployment_chronicle', { limit });

export const troubleshooterAppendNote = (note: string) =>
  invoke<void>('troubleshooter_append_note', { note });

export const troubleshooterScanPort = (port: number) =>
  invoke<Record<string, unknown>>('troubleshooter_scan_port', { port });

export const troubleshooterCycleControllerPort = () =>
  invoke<Record<string, unknown>>('troubleshooter_cycle_controller_port');

export const troubleshooterPingController = () =>
  invoke<Record<string, unknown>>('troubleshooter_ping_controller');

export const troubleshooterProtocolHint = () =>
  invoke<Record<string, unknown>>('troubleshooter_protocol_hint');

export const troubleshooterStopServices = () => invoke<void>('troubleshooter_stop_services');

export const troubleshooterPortCycleDefaults = () =>
  invoke<number[]>('troubleshooter_port_cycle_defaults');

export interface ControllerPlacementInfo {
  host: string;
  port: number;
  deviceLabel?: string | null;
}

export const getControllerPlacementInfo = () =>
  invoke<ControllerPlacementInfo | null>('get_controller_placement_info');

export const troubleshooterNetworkProbes = () =>
  invoke<Record<string, unknown>>('troubleshooter_network_probes');

export const troubleshooterVerifyArtifacts = () =>
  invoke<Record<string, unknown>>('troubleshooter_verify_artifacts');

export const troubleshooterRestartController = () =>
  invoke<void>('troubleshooter_restart_controller');

export const troubleshooterRestartLocalWorker = () =>
  invoke<void>('troubleshooter_restart_local_worker');

/** Same checks as GitHub ``test-controller`` / Python smoke (via Phantom venv only). */
export interface LocalCiInvokeOptions {
  ensureDevTools?: boolean;
  portCheck?: boolean;
}

export interface LocalCiInvokeResult {
  ok: boolean;
  exit_code: number | null;
  message: string;
}

export const runLocalCiCheck = (options?: LocalCiInvokeOptions | null) =>
  invoke<LocalCiInvokeResult>('run_local_ci_check', { options: options ?? null });

/** Surgical uninstall (same as Deployments panel). */
export const uninstallPhantom = () => invoke<Record<string, unknown>>('uninstall_phantom');

/** Troubleshooter Full Reset — identical teardown + chronicle pre-report. */
export const troubleshooterFullReset = () =>
  invoke<Record<string, unknown>>('troubleshooter_full_reset');
