import { useEffect, useState, type ReactNode } from 'react';

interface Props {
  sectionId: string;
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

/**
 * Collapsible troubleshooter block with persisted open/closed state.
 */
export default function TroubleshooterCollapsibleSection({
  sectionId,
  title,
  defaultOpen = true,
  children,
}: Props) {
  const key = `phantom-ts-section-${sectionId}`;
  const [open, setOpen] = useState(() => {
    try {
      const v = localStorage.getItem(key);
      if (v === '0') return false;
      if (v === '1') return true;
    } catch {
      /* ignore */
    }
    return defaultOpen;
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, open ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [open, key]);

  return (
    <div className="ts-collapsible">
      <button
        type="button"
        className="ts-collapsible-head"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className={`ts-collapsible-chevron ${open ? 'is-open' : ''}`} aria-hidden />
        <span className="ts-collapsible-title">{title}</span>
      </button>
      <div className={`ts-collapsible-panel ${open ? 'is-open' : ''}`} aria-hidden={!open}>
        <div className="ts-collapsible-inner">{children}</div>
      </div>
    </div>
  );
}
