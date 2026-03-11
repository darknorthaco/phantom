/**
 * §1 Pre-0 Controller Selection Ceremony
 *
 * Mandatory gate between WizardWelcome and deploy. User selects placement,
 * reviews controller identity fingerprint, and confirms before any deploy step runs.
 */

import { useState, useEffect } from 'react';
import { getIdentity, confirmControllerPlacement } from '../utils/tauri';
import '../styles/deploy.css';

export type PlacementOption = 'local_cpu' | 'local_gpu' | 'custom';

interface ControllerPlacementParams {
  host: string;
  port: number;
  deviceLabel: string;
  identityFingerprint: string;
}

interface Props {
  onConfirm: (params: ControllerPlacementParams) => void;
  onCancel: () => void;
}

export default function ControllerSelectionScreen({ onConfirm, onCancel }: Props) {
  const [placement, setPlacement] = useState<PlacementOption>('local_cpu');
  const [customHost, setCustomHost] = useState('127.0.0.1');
  const [customPort, setCustomPort] = useState('8080');
  const [deviceLabel, setDeviceLabel] = useState('Phantom Controller');
  const [fingerprint, setFingerprint] = useState<string | null>(null);
  const [identityError, setIdentityError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    getIdentity()
      .then((info) => {
        const fp = (info as { fingerprint?: string }).fingerprint;
        if (fp) setFingerprint(fp);
        else setIdentityError('Identity loaded but no fingerprint returned');
      })
      .catch((err) => setIdentityError(String(err)));
  }, []);

  const host = placement === 'custom' ? customHost : '127.0.0.1';
  const port = placement === 'custom' ? parseInt(customPort, 10) || 8080 : 8080;

  const handleConfirm = async () => {
    if (!fingerprint) return;
    setConfirming(true);
    try {
      await confirmControllerPlacement(host, port, deviceLabel, fingerprint);
      onConfirm({ host, port, deviceLabel, identityFingerprint: fingerprint } as ControllerPlacementParams);
    } catch (err) {
      console.error('Confirm controller placement failed:', err);
      setIdentityError(String(err));
    } finally {
      setConfirming(false);
    }
  };

  const canConfirm = fingerprint != null && !identityError;
  const portValid = placement !== 'custom' || (customPort && parseInt(customPort, 10) > 0);

  return (
    <div className="deploy-screen">
      <div className="phantom-mask-container">
        <img src="/phantom.svg" alt="Phantom" className="phantom-mask-svg" />
      </div>

      <div className="deploy-title">Controller Placement</div>
      <p className="ceremony-subtext" style={{ maxWidth: 480, marginBottom: 20 }}>
        Select where this Phantom controller will run. The controller's cryptographic
        identity is shown below. No installation will occur until you confirm.
      </p>

      <div className="ceremony-part" style={{ maxWidth: 420, textAlign: 'left' }}>
        <h3 className="ceremony-heading">Placement</h3>
        <div className="controller-placement-options">
          <label className="ceremony-worker-card ceremony-worker-card-checkbox">
            <input
              type="radio"
              name="placement"
              checked={placement === 'local_cpu'}
              onChange={() => setPlacement('local_cpu')}
            />
            <span>Local CPU — 127.0.0.1:8080</span>
          </label>
          <label className="ceremony-worker-card ceremony-worker-card-checkbox">
            <input
              type="radio"
              name="placement"
              checked={placement === 'local_gpu'}
              onChange={() => setPlacement('local_gpu')}
            />
            <span>Local GPU — same host, GPU workloads</span>
          </label>
          <label className="ceremony-worker-card ceremony-worker-card-checkbox">
            <input
              type="radio"
              name="placement"
              checked={placement === 'custom'}
              onChange={() => setPlacement('custom')}
            />
            <span>Custom IP:Port</span>
          </label>
        </div>

        {placement === 'custom' && (
          <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
            <input
              type="text"
              value={customHost}
              onChange={(e) => setCustomHost(e.target.value)}
              placeholder="Host (e.g. 192.168.1.1)"
              style={{
                flex: 1,
                padding: 8,
                fontFamily: 'var(--font-mono)',
                background: 'rgba(0,0,0,0.25)',
                border: '1px solid rgba(255,255,255,0.15)',
                borderRadius: 4,
                color: 'inherit',
              }}
            />
            <input
              type="text"
              value={customPort}
              onChange={(e) => setCustomPort(e.target.value)}
              placeholder="Port"
              style={{
                width: 80,
                padding: 8,
                fontFamily: 'var(--font-mono)',
                background: 'rgba(0,0,0,0.25)',
                border: '1px solid rgba(255,255,255,0.15)',
                borderRadius: 4,
                color: 'inherit',
              }}
            />
          </div>
        )}
      </div>

      <div className="ceremony-part" style={{ maxWidth: 420, textAlign: 'left' }}>
        <h3 className="ceremony-heading">Controller address</h3>
        <p className="ceremony-worker-meta" style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          {host}:{port}
        </p>
      </div>

      <div className="ceremony-part" style={{ maxWidth: 420, textAlign: 'left' }}>
        <h3 className="ceremony-heading">Device label</h3>
        <input
          type="text"
          value={deviceLabel}
          onChange={(e) => setDeviceLabel(e.target.value)}
          placeholder="Human-readable name for this controller"
          style={{
            width: '100%',
            padding: 8,
            fontFamily: 'var(--font-mono)',
            background: 'rgba(0,0,0,0.25)',
            border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: 4,
            color: 'inherit',
          }}
        />
      </div>

      <div className="ceremony-part" style={{ maxWidth: 420, textAlign: 'left' }}>
        <h3 className="ceremony-heading">Identity fingerprint</h3>
        {identityError && (
          <p className="ceremony-warning" style={{ marginBottom: 8 }}>
            {identityError}
          </p>
        )}
        {fingerprint ? (
          <p
            className="ceremony-worker-meta"
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              wordBreak: 'break-all',
              padding: 10,
              background: 'rgba(0,0,0,0.25)',
              borderRadius: 4,
            }}
          >
            {fingerprint}
          </p>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>Loading identity…</p>
        )}
      </div>

      <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
        <button className="deploy-btn secondary" onClick={onCancel}>
          Cancel
        </button>
        <button
          className="deploy-btn"
          onClick={handleConfirm}
          disabled={!canConfirm || !portValid || confirming}
        >
          {confirming ? 'Confirming…' : 'Confirm placement'}
        </button>
      </div>
    </div>
  );
}
