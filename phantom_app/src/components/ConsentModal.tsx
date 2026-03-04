interface Props {
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConsentModal({ title, message, onConfirm, onCancel }: Props) {
  return (
    <div style={{
      position: 'fixed', inset: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,0.7)', zIndex: 1000,
    }}>
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border-color)',
        borderRadius: 8, padding: 28, maxWidth: 440, width: '90%',
      }}>
        <div style={{
          fontFamily: 'var(--font-mono)', fontSize: 13,
          letterSpacing: 2, textTransform: 'uppercase',
          color: 'var(--accent-blue)', marginBottom: 16,
        }}>
          {title}
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6, marginBottom: 24 }}>
          {message}
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <button className="deploy-btn" style={{ padding: '8px 20px', fontSize: 11, borderColor: 'var(--border-color)' }} onClick={onCancel}>
            Cancel
          </button>
          <button className="deploy-btn" style={{ padding: '8px 20px', fontSize: 11 }} onClick={onConfirm}>
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
