import { invoke } from '@tauri-apps/api/core';

// Identity (Phase 1)
export const getIdentity = () => invoke<Record<string, unknown>>('get_identity');
export const signMessage = (message: string) => invoke<string>('sign_message', { message });
export const verifySignature = (publicKeyB64: string, message: string, signatureB64: string) =>
  invoke<boolean>('verify_signature', { publicKeyB64, message, signatureB64 });

// TLS (Phase 2)
export const generateCertificate = () => invoke<Record<string, unknown>>('generate_certificate');

// Trust (Phase 3)
export const getTrustLedger = () => invoke<Record<string, unknown>>('get_trust_ledger');
export const approvePeer = (peerId: string) => invoke<void>('approve_peer', { peerId });
export const rejectPeer = (peerId: string) => invoke<void>('reject_peer', { peerId });

// Audit (Phase 4)
export const getAuditLog = (limit: number) => invoke<Array<Record<string, unknown>>>('get_audit_log', { limit });

// Execution modes (Phase 5)
export const setExecutionMode = (mode: string) => invoke<Record<string, unknown>>('set_execution_mode', { mode });
export const loadLlmConfig = () => invoke<Record<string, unknown>>('load_llm_config');

// System metrics (Phase 6)
export const getSystemMetrics = () => invoke<Record<string, unknown>>('get_system_metrics');

// Integrity (Phase 7)
export const checkIntegrity = () => invoke<Record<string, unknown>>('check_integrity');

// Original commands
export const getDeploymentStatus = () => invoke<string>('get_deployment_status');
export const deployPhantom = () => invoke<void>('deploy_phantom');
export const getPhantomHealth = () => invoke<Record<string, unknown>>('get_phantom_health');
export const getWorkers = () => invoke<Record<string, unknown>>('get_workers');
export const getStats = () => invoke<Record<string, unknown>>('get_stats');
export const submitTask = (taskType: string, parameters: Record<string, unknown>, priority: number) =>
  invoke<Record<string, unknown>>('submit_task', { taskType, parameters, priority });
export const scanAndRegisterWorkers = () =>
  invoke<{ scanned: number; registered: number; nodes: Array<[string, number]> }>('scan_and_register_workers');
