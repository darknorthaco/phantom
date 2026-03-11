import { useState, useCallback, useEffect } from 'react';
import WizardWelcome from './components/WizardWelcome';
import FrontPorchDeploy from './components/FrontPorchDeploy';
import DeploymentCeremony from './components/DeploymentCeremony';
import { DeploymentCeremonyProvider } from './state/DeploymentCeremonyContext';
import type { DeploymentPreScanResult } from './state/deploymentState';
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
import './styles/theme.css';
import './styles/deploy.css';
import './styles/toc.css';

type Phase = 'wizard' | 'front_porch' | 'deploying' | 'deployment_ceremony' | 'consent_toc' | 'toc';

export default function App() {
  const [phase, setPhase] = useState<Phase>('wizard');
  const [preScanResult, setPreScanResult] = useState<DeploymentPreScanResult | null>(null);
  const [activeView, setActiveView] = useState('console');
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);

  const checkHealth = useCallback(() => {
    fetch('http://127.0.0.1:8080/health')
      .then((r) => r.json())
      .then((d) => setHealth(d))
      .catch(() => setHealth(null));
  }, []);

  // Auto-detect deployed controller on mount; skip wizard if already running.
  useEffect(() => {
    fetch('http://127.0.0.1:8080/health')
      .then((r) => r.json())
      .then((d) => {
        if (d && d.status === 'healthy') {
          setHealth(d);
          setPhase('toc');
        }
      })
      .catch(() => {});
  }, []);

  // Live health polling while in TOC — keeps MetricsBar current.
  useEffect(() => {
    if (phase !== 'toc') return;
    const id = setInterval(checkHealth, 15_000);
    return () => clearInterval(id);
  }, [phase, checkHealth]);

  const handleWizardConsent = () => {
    setPhase('front_porch');
  };

  const handlePreScanComplete = (result: DeploymentPreScanResult) => {
    setPreScanResult(result);
    setPhase('deployment_ceremony');
  };

  const handleCeremonyComplete = () => {
    setPhase('consent_toc');
    checkHealth();
  };

  const handleCeremonyBack = () => {
    setPreScanResult(null);
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
    return (
      <div className="deploy-screen">
        <ConsentModal
          title="Enter Command Center"
          message="Deployment complete. You are about to enter the Phantom Tactical Operations Center. The controller is active and awaiting your commands."
          onConfirm={handleEnterToc}
          onCancel={() => setPhase('front_porch')}
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
              <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>http://127.0.0.1:8080</p>
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
