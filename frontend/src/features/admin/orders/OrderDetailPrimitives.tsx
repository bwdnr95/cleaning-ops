import React from 'react';

import { Icon } from '../../../components/common/ui';
import { formatWon } from './OrderDetailFormat';

interface DetailStateProps {
  readonly text: string;
  readonly tone?: 'muted' | 'danger';
  readonly onBack: () => void;
}

interface SectionProps {
  readonly title: string;
  readonly icon: string;
  readonly badge?: React.ReactNode;
  readonly children: React.ReactNode;
}

interface PanelTitleProps {
  readonly children: React.ReactNode;
  readonly dirty?: boolean;
}

interface CopyLinkButtonProps {
  readonly link: string;
  readonly label?: string;
  readonly testId?: string;
}

interface KVProps {
  readonly children: React.ReactNode;
  readonly col?: number;
}

interface KVItemProps {
  readonly label: string;
  readonly value: React.ReactNode;
  readonly mono?: boolean;
  readonly span?: number;
  readonly multiline?: boolean;
}

export function DetailState({ text, tone = 'muted', onBack }: DetailStateProps) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
      <div style={{ padding: '10px 20px', background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
        <button className="btn btn--ghost btn--sm" onClick={onBack}>
          <Icon name="chevronLeft" size={13}/> 목록
        </button>
      </div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)', fontSize: 13 }}>
        {text}
      </div>
    </div>
  );
}

export function Section({ title, icon, badge = null, children }: SectionProps) {
  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon name={icon} size={13} color="var(--text-tertiary)"/>
        <span style={{ fontSize: 12.5, fontWeight: 600 }}>{title}</span>
        {badge}
      </div>
      <div style={{ padding: 14 }}>{children}</div>
    </div>
  );
}

export function PanelTitle({ children, dirty = false }: PanelTitleProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em' }}>{children}</span>
      {dirty && (
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--warn-fg)', background: 'var(--warn-bg)', borderRadius: 4, padding: '1px 5px' }}>
          변경됨
        </span>
      )}
    </div>
  );
}

export function CopyLinkButton({ link, label = '링크 복사', testId = undefined }: CopyLinkButtonProps) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <button
      type="button"
      data-testid={testId}
      className={`btn btn--block ${copied ? 'btn--primary' : 'btn--secondary'}`}
      onClick={() => void handleCopy()}
    >
      <Icon name={copied ? 'check' : 'copy'} size={13}/> {copied ? '링크가 복사되었습니다' : label}
    </button>
  );
}

export function KV({ children, col = 2 }: KVProps) {
  return <div style={{ display: 'grid', gridTemplateColumns: `repeat(${col}, 1fr)`, gap: '10px 16px' }}>{children}</div>;
}

export function KVItem({ label, value, mono = false, span = undefined, multiline = false }: KVItemProps) {
  return (
    <div style={{ gridColumn: span ? `span ${span}` : 'auto' }}>
      <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 500, marginBottom: 3 }}>{label}</div>
      <div
        className={multiline ? 'multiline-text' : undefined}
        style={{
          fontSize: 12.5,
          color: 'var(--text)',
          fontFamily: mono ? 'var(--font-mono)' : 'inherit',
          lineHeight: multiline ? 1.5 : 1.4,
        }}
      >
        {value}
      </div>
    </div>
  );
}

export function Money({ label, value }: { readonly label: string; readonly value: number | string | null | undefined }) {
  return (
    <div style={{ padding: '0 14px', borderRight: '1px solid var(--divider)' }}>
      <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 500, marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{formatWon(value)}</div>
    </div>
  );
}

export function EmptyLine({ text }: { readonly text: string }) {
  return <div style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>{text}</div>;
}
