import { useState, useCallback, useEffect } from 'react';
import WizardWelcome from './components/WizardWelcome';
import ControllerSelectionScreen from './components/ControllerSelectionScreen';
import FrontPorchDeploy from './components/FrontPorchDeploy';
import DeploymentCeremony from './components/DeploymentCeremony';
import { DeploymentCeremonyProvider } from './state/DeploymentCeremonyContext';
import type { DeploymentPreScanResult, WorkerRegistrationSummary } from './state/deploymentState';
import { poolFullyRegistered } from './state/deploymentState';
import ConsentModal from './components/ConsentModal';
import MetricsBar from './components/MetricsBar';
import SidebarNavigator from './components/SidebarNavigator';
import PhantomConsole from './components/PhantomConsole';
import WorkersPanel from './components/WorkersPanel';
import RoutingPanel from './components/RoutingPanel';
import ModelsPanel from './components/ModelsPanel';
import EphemeralPanel from './components/EphemeralPanel';
import DeploymentsPanel from './components/DeploymentsPanel';
import AuditLogPanel from './components/AuditLogPanel';
import ExperimentalAOL from './components/ExperimentalAOL';
import ChatPanel from './components/ChatPanel';
import { getControllerBaseUrl, getPhantomHealth } from './utils/tauri';
import './styles/theme.css';
import './styles/deploy.css';
import './styles/toc.css';

type Phase = 'wizard' | 'controller_selection' | 'front_porch' | 'deploying' | 'deployment_ceremony' | 'consent_toc' | 'toc';

export default function App() {
  const [phase, setPhase] = useState<Phase>('wizard');
  const [preScanResult, setPreScanResult] = useState<DeploymentPreScanResult | null>(null);
  const [registrationSummary, setRegistrationSummary] = useState<WorkerRegistrationSummary | null>(null);
  const [activeView, setActiveView] = useState('console');
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [controllerBaseUrl, setControllerBaseUrl] = useState('');

  const checkHealth = useCallback(() => {
    getPhantomHealth()
      .then((d) => setHealth(d as Record<string, unknown>))
      .catch(() => setHealth(null));
  }, []);

  // Auto-detect deployed controller on mount; skip wizard if already running.
  useEffect(() => {
    getPhantomHealth()
      .then((d) => {
        const body = d as Record<string, unknown>;
        const s = body.status as string | undefined;
        if (s === 'healthy' || s === 'degraded') {
          setHealth(body);
          setPhase('toc');
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (phase !== 'toc') return;
    getControllerBaseUrl()
      .then(setControllerBaseUrl)
      .catch(() => setControllerBaseUrl(''));
  }, [phase]);

  // Live health polling while in TOC — keeps MetricsBar current.
  useEffect(() => {
    if (phase !== 'toc') return;
    const id = setInterval(checkHealth, 15_000);
    return () => clearInterval(id);
  }, [phase, checkHealth]);

  const handleWizardConsent = () => {
    setPhase('controller_selection');
  };

  const handleControllerConfirm = () => {
    setPhase('front_porch');
  };

  const handleControllerCancel = () => {
    setPhase('wizard');
  };

  const handlePreScanComplete = (result: DeploymentPreScanResult) => {
    setPreScanResult(result);
    setPhase('deployment_ceremony');
  };

  const handleCeremonyComplete = (summary: WorkerRegistrationSummary) => {
    setRegistrationSummary(summary);
    setPhase('consent_toc');
    checkHealth();
  };

  const handleCeremonyBack = () => {
    setPreScanResult(null);
    setRegistrationSummary(null);
    setPhase('front_porch');
  };

  const handleEnterToc = () => {
    checkHealth();
    setPhase('toc');
  };

  // Wizard Step 1: Welcome + Consent
  if (phase === 'wizard') {
    return <WizardWelcome onConsent={handleWizardConsent} />;
  }

  // §1 Pre-0: Controller Selection Ceremony (placement + identity)
  if (phase === 'controller_selection') {
    return (
      <ControllerSelectionScreen
        onConfirm={handleControllerConfirm}
        onCancel={handleControllerCancel}
      />
    );
  }

  // Wizard Step 2: Deploy Phantom (pre-scan)
  if (phase === 'front_porch' || phase === 'deploying') {
    return <FrontPorchDeploy onPreScanComplete={handlePreScanComplete} />;
  }

  // Screen 4: Deployment Ceremony (controller + worker selection)
  if (phase === 'deployment_ceremony' && preScanResult) {
    return (
      <DeploymentCeremonyProvider>
        <DeploymentCeremony
          preScanResult={preScanResult}
          onComplete={handleCeremonyComplete}
          onBack={handleCeremonyBack}
        />
      </DeploymentCeremonyProvider>
    );
  }

  // Consent gate before entering TOC
  if (phase === 'consent_toc') {
    const consentBase =
      'Deployment complete. You are about to enter the Phantom Tactical Operations Center. The controller is active and awaiting your commands.';
    const consentMessage =
      registrationSummary && !poolFullyRegistered(registrationSummary)
        ? `${consentBase}\n\nPartial registration: ${registrationSummary.registeredCount} of ${registrationSummary.selectedCount} selected workers are registered with the controller. Trust failures: ${registrationSummary.trustFailedCount}. Register API failures: ${registrationSummary.registrationFailedCount}. Review Workers and trust before routing tasks.`
        : consentBase;
    return (
      <div className="deploy-screen">
        <ConsentModal
          title="Enter Command Center"
          message={consentMessage}
          onConfirm={() => {
            setRegistrationSummary(null);
            handleEnterToc();
          }}
          onCancel={() => {
            setRegistrationSummary(null);
            setPhase('front_porch');
          }}
        />
      </div>
    );
  }

  // TOC Interface
  const renderPanel = () => {
    switch (activeView) {
      case 'chat':         return <ChatPanel />;
      case 'console':      return <PhantomConsole />;
      case 'workers':      return <WorkersPanel />;
      case 'routing':      return <RoutingPanel />;
      case 'models':       return <ModelsPanel />;
      case 'ephemeral':    return <EphemeralPanel />;
      case 'deployments':  return <DeploymentsPanel />;
      case 'logs':         return <AuditLogPanel />;
      case 'experimental': return <ExperimentalAOL />;
      case 'tasks':
        return (
          <div className="panel">
            <div className="panel-header"><span className="panel-title">Tasks</span></div>
            <div className="empty-state">No active tasks. Submit tasks via the Console or API.</div>
          </div>
        );
      case 'settings':
        return (
          <div className="panel">
            <div className="panel-header"><span className="panel-title">Settings</span></div>
            <div className="card">
              <div className="card-title">Controller Endpoint</div>
              <p
                style={{
                  color: 'var(--text-secondary)',
                  fontSize: 12,
                  fontFamily: 'var(--font-mono)',
                  wordBreak: 'break-all',
                }}
              >
                {controllerBaseUrl || '—'}
              </p>
            </div>
            <div className="card">
              <div className="card-title">Default Execution Mode</div>
              <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>MANUAL (sacred default per doctrine)</p>
            </div>
          </div>
        );
      default: return <PhantomConsole />;
    }
  };

  return (
    <div className="toc-layout">
      <MetricsBar health={health} onRefresh={checkHealth} />
      <SidebarNavigator active={activeView} onNavigate={setActiveView} />
      <div className="main-content">
        {renderPanel()}
      </div>
    </div>
  );
}
