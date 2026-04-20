/**
 * PR-B — Deploy Mode Badge (I-ModeVisible).
 *
 * Doctrine: the operator MUST always see which deploy engine this binary
 * ships. `mode` is sourced from the backend `deploy_mode()` command and
 * cannot be spoofed by frontend environment flags.
 *
 * Release builds show a green `CEREMONY-FIRST` badge.
 * Transitional compat builds show a loud amber `LEGACY-COMPAT` badge so
 * doctrine drift is never silent.
 */

import { useEffect, useState, type CSSProperties } from 'react';
import { deployMode, type DeployModeInfo } from '../utils/tauri';

interface Props {
  compact?: boolean;
}

export default function DeployModeBadge({ compact = false }: Props) {
  const [info, setInfo] = useState<DeployModeInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    deployMode()
      .then(setInfo)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  if (err) {
    return (
      <div
        style={badgeStyle('rgba(220, 90, 90, 0.2)', '#e88')}
        title={`deploy_mode() failed: ${err}`}
      >
        MODE: UNKNOWN
      </div>
    );
  }
  if (!info) {
    return (
      <div style={badgeStyle('rgba(120, 120, 120, 0.15)', '#999')}>MODE: …</div>
    );
  }

  const isLegacy = info.mode === 'legacy';
  const bg = isLegacy ? 'rgba(220, 140, 60, 0.18)' : 'rgba(80, 160, 120, 0.18)';
  const fg = isLegacy ? '#e6a56a' : '#6fcf97';
  const label = isLegacy ? 'LEGACY-COMPAT' : 'CEREMONY-FIRST';
  const title = [
    `Deploy mode: ${info.mode}`,
    `Build features: ${info.buildFeatures.join(', ') || '(none)'}`,
    `Chronicle schema v${info.chronicleSchemaVersion}`,
    isLegacy
      ? 'WARNING: this is a transitional compat build. Doctrine drift events will be recorded.'
      : 'Ceremony-first canonical path. Legacy deployer is not compiled into this binary.',
  ].join('\n');

  return (
    <div style={badgeStyle(bg, fg, compact)} title={title} role="status">
      MODE: {label}
      {!compact && info.buildFeatures.length > 0 && (
        <span style={{ opacity: 0.75, marginLeft: 6, fontSize: 9 }}>
          [{info.buildFeatures.join(',')}]
        </span>
      )}
    </div>
  );
}

function badgeStyle(bg: string, fg: string, compact: boolean = false): CSSProperties {
  return {
    display: 'inline-block',
    padding: compact ? '2px 6px' : '3px 10px',
    fontFamily: 'var(--font-mono)',
    fontSize: compact ? 9 : 10,
    fontWeight: 700,
    letterSpacing: 1,
    color: fg,
    background: bg,
    border: `1px solid ${fg}`,
    borderRadius: 3,
  };
}
