import type React from 'react';

import { Icon } from '../../../components/common/ui';

export function FormState({ text, onCancel }: { readonly text: string; readonly onCancel: () => void }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
      <div style={{ padding: '10px 20px', background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onCancel}>
          <Icon name="chevronLeft" size={13}/> 취소
        </button>
      </div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
        {text}
      </div>
    </div>
  );
}

export function Section({
  title,
  action = null,
  children,
}: {
  readonly title: string;
  readonly action?: React.ReactNode;
  readonly children: React.ReactNode;
}) {
  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', fontSize: 12.5, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>{title}</span><div style={{ flex: 1 }}/>{action}
      </div>
      <div style={{ padding: 14 }}>{children}</div>
    </div>
  );
}

export function FieldGrid({ children }: { readonly children: React.ReactNode }) {
  return <div className="order-form-field-grid" style={{ display: 'grid', gap: '12px 14px' }}>{children}</div>;
}

export function Field({
  label,
  children,
  span = 1,
}: {
  readonly label: string;
  readonly children: React.ReactNode;
  readonly span?: number;
}) {
  return (
    <label className={span > 1 ? 'order-form-field--span-2' : undefined} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>{label}</span>
      {children}
    </label>
  );
}

interface TextFieldProps {
  readonly label: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly type?: React.HTMLInputTypeAttribute;
  readonly inputMode?: React.HTMLAttributes<HTMLInputElement>['inputMode'];
  readonly required?: boolean;
  readonly span?: number;
  readonly multiline?: boolean;
  readonly placeholder?: string;
  readonly testId?: string;
}

export function TextField({
  label, value, onChange, type = 'text', inputMode, required = false, span = 1,
  multiline = false, placeholder = '', testId,
}: TextFieldProps) {
  return (
    <Field label={`${label}${required ? ' *' : ''}`} span={span}>
      {multiline ? (
        <textarea
          className="input" data-testid={testId} value={value} placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          style={{ minHeight: 70, resize: 'vertical', lineHeight: 1.45 }}
        />
      ) : (
        <input
          className="input" data-testid={testId} type={type} inputMode={inputMode}
          value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)}
        />
      )}
    </Field>
  );
}
