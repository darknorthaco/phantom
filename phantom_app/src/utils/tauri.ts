import { invoke } from '@tauri-apps/api/core';

export async function getDeploymentStatus(): Promise<string> {
  return invoke<string>('get_deployment_status');
}

export async function deployPhantom(): Promise<void> {
  return invoke<void>('deploy_phantom');
}

export async function getPhantomHealth(): Promise<Record<string, unknown>> {
  return invoke<Record<string, unknown>>('get_phantom_health');
}

export async function getWorkers(): Promise<Record<string, unknown>> {
  return invoke<Record<string, unknown>>('get_workers');
}

export async function getStats(): Promise<Record<string, unknown>> {
  return invoke<Record<string, unknown>>('get_stats');
}

export async function submitTask(
  taskType: string,
  parameters: Record<string, unknown>,
  priority: number,
): Promise<Record<string, unknown>> {
  return invoke<Record<string, unknown>>('submit_task', {
    taskType,
    parameters,
    priority,
  });
}

export async function getSystemMetrics(): Promise<Record<string, unknown>> {
  return invoke<Record<string, unknown>>('get_system_metrics');
}

export async function scanLan(
  baseIp: string,
  port: number,
): Promise<Array<Record<string, unknown>>> {
  return invoke<Array<Record<string, unknown>>>('scan_lan', { baseIp, port });
}
