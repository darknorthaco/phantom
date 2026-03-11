/**
 * Deployment Ceremony — React Context
 *
 * Provides ceremony state to Screen 4 components (Controller Select,
 * Worker Select, Diagnostics). State is populated from run_deployment_pre_scan
 * and updated by user choices before complete_deployment_with_selection.
 */

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react';
import type {
  ControllerConfig,
  DeploymentCeremonyState,
  DiscoveredWorker,
} from './deploymentState';
import {
  initialDeploymentCeremonyState,
  type DeploymentPreScanResult,
} from './deploymentState';

interface DeploymentCeremonyContextValue {
  state: DeploymentCeremonyState;
  applyPreScanResult: (result: DeploymentPreScanResult) => void;
  setControllerConfig: (config: ControllerConfig | null) => void;
  setWorkerPool: (workers: DiscoveredWorker[]) => void;
  reset: () => void;
}

const DeploymentCeremonyContext = createContext<
  DeploymentCeremonyContextValue | undefined
>(undefined);

export function DeploymentCeremonyProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DeploymentCeremonyState>(
    initialDeploymentCeremonyState
  );

  const applyPreScanResult = useCallback((result: DeploymentPreScanResult) => {
    // §2 — Only pre-select workers with verified signatures. Unverified default unchecked.
    const preSelected = result.discoveryFailed
      ? []
      : result.discoveredWorkers.filter((w) => w.signatureVerified);
    setState({
      discoveredWorkers: result.discoveredWorkers,
      discoveryLog: result.discoveryLog,
      discoveryFailed: result.discoveryFailed,
      controllerConfig: null,
      workerPool: preSelected,
    });
  }, []);

  const setControllerConfig = useCallback((config: ControllerConfig | null) => {
    setState((prev) => ({ ...prev, controllerConfig: config }));
  }, []);

  const setWorkerPool = useCallback((workers: DiscoveredWorker[]) => {
    setState((prev) => ({ ...prev, workerPool: workers }));
  }, []);

  const reset = useCallback(() => {
    setState(initialDeploymentCeremonyState);
  }, []);

  const value: DeploymentCeremonyContextValue = {
    state,
    applyPreScanResult,
    setControllerConfig,
    setWorkerPool,
    reset,
  };

  return (
    <DeploymentCeremonyContext.Provider value={value}>
      {children}
    </DeploymentCeremonyContext.Provider>
  );
}

export function useDeploymentCeremony() {
  const ctx = useContext(DeploymentCeremonyContext);
  if (ctx === undefined) {
    throw new Error(
      'useDeploymentCeremony must be used within DeploymentCeremonyProvider'
    );
  }
  return ctx;
}
