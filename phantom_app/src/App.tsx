import { useState, useEffect, useCallback } from 'react';
import FrontPorchDeploy from './components/FrontPorchDeploy';
import MetricsBar from './components/MetricsBar';
import SidebarNavigator from './components/SidebarNavigator';
import PhantomConsole from './components/PhantomConsole';
import WorkersPanel from './components/WorkersPanel';
import RoutingPanel from './components/RoutingPanel';
import ModelsPanel from './components/ModelsPanel';
import EphemeralPanel from './components/EphemeralPanel';
import DeploymentsPanel from './components/DeploymentsPanel';
import ExperimentalAOL from './components/ExperimentalAOL';
import './styles/theme.css';
import './styles/deploy.css';
import './styles/toc.css';

type Phase = 'front_porch' | 'deploying' | 'toc';

export default function App() {
  const [phase, setPhase] = useState<Phase>('front_porch');
  const [activeView, setActiveView] = useState('console');
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);

  const checkHealth = useCallback(() => {
    fetch('http://127.0.0.1:8080/health')
      .then((r) => r.json())
      .then((d) => setHealth(d))
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    checkHealth();
    const controllerUp = setInterval(checkHealth, 5000);
    return () => clearInterval(controllerUp);
  }, [checkHealth]);

  useEffect(() => {
    if (health && health.status === 'healthy' && phase === 'front_porch') {
      setPhase('toc');
    }
  }, [health, phase]);

  const handleDeployComplete = () => {
    setPhase('toc');
    checkHealth();
  };

  if (phase === 'front_porch' || phase === 'deploying') {
    return <FrontPorchDeploy onDeployComplete={handleDeployComplete} />;
  }

  const renderPanel = () => {
    switch (activeView) {
      case 'console':     return <PhantomConsole />;
      case 'workers':     return <WorkersPanel />;
      case 'routing':     return <RoutingPanel />;
      case 'models':      return <ModelsPanel />;
      case 'ephemeral':   return <EphemeralPanel />;
      case 'deployments': return <DeploymentsPanel />;
      case 'experimental':return <ExperimentalAOL />;
      case 'tasks':
        return (
          <div className="panel">
            <div className="panel-header"><span className="panel-title">Tasks</span></div>
            <div className="empty-state">No active tasks. Submit tasks via the Console or API.</div>
          </div>
        );
      case 'logs':
        return (
          <div className="panel">
            <div className="panel-header"><span className="panel-title">Logs</span></div>
            <div className="empty-state">System logs will appear here.</div>
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
          </div>
        );
      default: return <PhantomConsole />;
    }
  };

  return (
    <div className="toc-layout">
      <MetricsBar health={health} />
      <SidebarNavigator active={activeView} onNavigate={setActiveView} />
      <div className="main-content">
        {renderPanel()}
      </div>
    </div>
  );
}
