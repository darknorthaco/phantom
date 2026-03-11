import '../styles/deploy.css';

interface Props {
  onConsent: () => void;
}

export default function WizardWelcome({ onConsent }: Props) {
  return (
    <div className="deploy-screen">
      <div className="phantom-mask-container">
        <img src="/phantom.png" alt="Phantom" className="phantom-mask-svg" />
      </div>

      <div className="deploy-title">Welcome to Phantom</div>

      <div style={{
        maxWidth: 520,
        textAlign: 'center',
        color: 'var(--text-secondary)',
        fontSize: 13,
        lineHeight: 1.7,
        marginBottom: 24,
        animation: 'fadeInUp 0.6s ease-out 0.3s both',
      }}>
        <p>
          Phantom is a sovereign distributed compute fabric.
          Your hardware, your models, your data — computed locally
          with no cloud dependencies.
        </p>
        <p style={{ marginTop: 12, color: 'var(--text-muted)', fontSize: 11 }}>
          By proceeding, you authorize Phantom to create a local environment,
          install its engine, and configure your system as a compute controller.
          No data leaves your network without explicit approval.
        </p>
      </div>

      <button className="deploy-btn" onClick={onConsent}>
        I Understand — Proceed
      </button>
    </div>
  );
}
