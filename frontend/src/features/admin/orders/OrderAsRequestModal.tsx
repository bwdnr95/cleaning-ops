import React from 'react';

import { Badge, Icon } from '../../../components/common/ui';

const AS_MEMO_TEMPLATES = [
  {
    key: 'revisit',
    label: '재방문 일정 요청',
    memo: 'AS 요청드립니다. 고객님과 재방문 가능 일정을 확인한 뒤 작업 가능 여부를 회신해주세요.',
  },
  {
    key: 'partial',
    label: '부분 보완 요청',
    memo: 'AS 요청드립니다. 고객님이 말씀하신 보완 위치를 확인하고, 현장에서 비포/애프터 사진과 고객 서명을 다시 받아 완료 처리해주세요.',
  },
  {
    key: 'customer_check',
    label: '고객 확인 필요',
    memo: '고객 확인이 필요한 AS 요청입니다. 현장 상황을 확인한 뒤 처리 가능 범위와 방문 가능 일정을 운영팀에 회신해주세요.',
  },
] as const;

type AsTemplateKey = (typeof AS_MEMO_TEMPLATES)[number]['key'];

type OrderAsRequestModalProps = {
  readonly open: boolean;
  readonly defaultMemo: string;
  readonly customerName: string;
  readonly serviceName: string;
  readonly partnerName: string;
  readonly isSaving: boolean;
  readonly onClose: () => void;
  readonly onSubmit: (memo: string) => void | Promise<void>;
};

export function OrderAsRequestModal({
  open,
  defaultMemo,
  customerName,
  serviceName,
  partnerName,
  isSaving,
  onClose,
  onSubmit,
}: OrderAsRequestModalProps) {
  const [memo, setMemo] = React.useState(defaultMemo);
  const [error, setError] = React.useState('');
  const [activeTemplateKey, setActiveTemplateKey] = React.useState<AsTemplateKey | null>(findTemplateKey(defaultMemo));
  const formRef = React.useRef<HTMLFormElement | null>(null);
  const memoRef = React.useRef<HTMLTextAreaElement | null>(null);
  const isSavingRef = React.useRef(isSaving);
  const onCloseRef = React.useRef(onClose);

  isSavingRef.current = isSaving;
  onCloseRef.current = onClose;

  React.useEffect(() => {
    if (open) {
      setMemo(defaultMemo);
      setError('');
      setActiveTemplateKey(findTemplateKey(defaultMemo));
    }
  }, [defaultMemo, open]);

  React.useEffect(() => {
    if (!open) {
      return undefined;
    }
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const frameId = window.requestAnimationFrame(() => memoRef.current?.focus());
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isSavingRef.current) {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab' || !formRef.current) {
        return;
      }
      const focusable = Array.from(formRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      ));
      if (focusable.length === 0) {
        event.preventDefault();
        formRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.cancelAnimationFrame(frameId);
      document.removeEventListener('keydown', handleKeyDown);
      previousFocus?.focus();
    };
  }, [open]);

  if (!open) {
    return null;
  }

  const trimmedMemo = memo.trim();
  const canSubmit = trimmedMemo.length > 0 && !isSaving;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!trimmedMemo) {
      setError('AS 요청 내용을 입력해주세요.');
      return;
    }
    setError('');
    await onSubmit(trimmedMemo);
  };

  return (
    <div
      data-testid="as-request-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="as-request-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 55,
        background: 'var(--overlay-scrim)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
    >
      <form
        ref={formRef}
        tabIndex={-1}
        className="card"
        onSubmit={(event) => void handleSubmit(event)}
        style={{
          width: 'min(620px, 100%)',
          maxHeight: 'min(720px, calc(100vh - 40px))',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--divider)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div id="as-request-title" style={{ fontSize: 14, fontWeight: 700 }}>AS 요청 처리</div>
            <div style={{ marginTop: 3, fontSize: 11.5, color: 'var(--text-tertiary)' }}>
              {customerName} · {serviceName}
            </div>
          </div>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onClose} disabled={isSaving} aria-label="닫기" style={{ padding: '0 6px' }}>
            <Icon name="x" size={14}/>
          </button>
        </div>

        <div className="scroll" style={{ padding: 16, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <AsImpactItem label="협력사" value={partnerName} tone="warn" />
            <AsImpactItem label="고객" value={customerName} tone="purple" />
          </div>

          <div style={{ padding: 10, borderRadius: 8, border: '1px solid var(--warn-bg)', background: 'var(--warn-bg)', color: 'var(--warn-fg)', fontSize: 11.5, lineHeight: 1.55, wordBreak: 'keep-all' }}>
            <div>전송하면 주문 상태가 고객확인필요로 바뀝니다.</div>
            <div>협력사와 고객에게 AS 안내 발송을 시도하고, 요청 내용은 협력사 링크에 표시합니다. 최종 발송 결과는 이력에서 확인합니다.</div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 700, marginBottom: 8 }}>빠른 문안</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {AS_MEMO_TEMPLATES.map((template) => {
                const isActive = activeTemplateKey === template.key;
                return (
                  <button
                    key={template.key}
                    type="button"
                    data-testid={`as-request-template-${template.key}`}
                    className={`btn ${isActive ? 'btn--primary' : 'btn--secondary'} btn--sm`}
                    disabled={isSaving}
                    aria-pressed={isActive}
                    onClick={() => {
                      setMemo(template.memo);
                      setActiveTemplateKey(template.key);
                      if (error) setError('');
                    }}
                  >
                    {template.label}
                  </button>
                );
              })}
            </div>
          </div>

          <label style={{ display: 'grid', gap: 8 }}>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 700 }}>AS 요청 내용</span>
            <textarea
              ref={memoRef}
              data-testid="as-request-memo"
              className="input"
              rows={5}
              value={memo}
              disabled={isSaving}
              placeholder="재작업이 필요한 위치, 고객 요청 내용, 협력사 확인 사항을 입력하세요."
              onChange={(event) => {
                const nextMemo = event.target.value;
                setMemo(nextMemo);
                setActiveTemplateKey(findTemplateKey(nextMemo));
                if (error) setError('');
              }}
              style={{ resize: 'vertical', minHeight: 112, fontSize: 13, lineHeight: 1.55 }}
            />
          </label>

          {error && (
            <div data-testid="as-request-error" style={{ padding: 10, borderRadius: 6, background: 'var(--danger-bg)', color: 'var(--danger-fg)', fontSize: 12 }}>
              {error}
            </div>
          )}
        </div>

        <div style={{ padding: 14, borderTop: '1px solid var(--divider)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" data-testid="as-request-cancel" className="btn btn--ghost" onClick={onClose} disabled={isSaving}>취소</button>
          <button type="submit" data-testid="as-request-submit" className="btn btn--primary" disabled={!canSubmit}>
            <Icon name="send" size={13}/> {isSaving ? '전송 중' : 'AS 요청 전송'}
          </button>
        </div>
      </form>
    </div>
  );
}

function findTemplateKey(memo: string): AsTemplateKey | null {
  return AS_MEMO_TEMPLATES.find((template) => template.memo === memo)?.key ?? null;
}

function AsImpactItem({ label, value, tone }: { readonly label: string; readonly value: string; readonly tone: 'warn' | 'purple' }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 10, background: 'var(--surface)' }}>
      <Badge tone={tone}>{label}</Badge>
      <div style={{ marginTop: 6, fontSize: 12.5, fontWeight: 700, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {value || '-'}
      </div>
    </div>
  );
}
