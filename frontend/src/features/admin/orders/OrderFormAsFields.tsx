import { Icon } from '../../../components/common/ui';

interface OrderFormAsFieldsProps {
  readonly isOpen: boolean;
  readonly memo: string;
  readonly isRequested: boolean;
  readonly isBusy: boolean;
  readonly onToggle: (isOpen: boolean) => void;
  readonly onMemoChange: (memo: string) => void;
  readonly onSend: () => void;
}

export function OrderFormAsFields({
  isOpen,
  memo,
  isRequested,
  isBusy,
  onToggle,
  onMemoChange,
  onSend,
}: OrderFormAsFieldsProps) {
  return (
    <div
      data-testid="order-as-section"
      style={{ border: '1px solid var(--divider)', borderRadius: 8, background: 'var(--bg-subtle)', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, fontWeight: 700, color: 'var(--text)' }}>
        <input
          type="checkbox"
          data-testid="order-as-checkbox"
          checked={isOpen}
          onChange={(event) => onToggle(event.target.checked)}
        />
        AS 요청 (사후관리 · 재작업)
        {isRequested && (
          <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--warn-fg)', background: 'var(--warn-bg)', borderRadius: 999, padding: '2px 8px' }}>
            요청됨
          </span>
        )}
      </label>
      {isOpen && (
        <>
          <textarea
            className="input"
            data-testid="order-as-memo"
            rows={3}
            placeholder="재작업이 필요한 위치·증상 등 협력사에 전달할 AS 내용을 입력하세요."
            value={memo}
            onChange={(event) => onMemoChange(event.target.value)}
            style={{ resize: 'vertical', fontSize: 13 }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              data-testid="order-as-send"
              className="btn btn--primary btn--sm"
              disabled={isBusy || isRequested || !memo.trim()}
              onClick={onSend}
            >
              <Icon name="send" size={12} /> {isBusy ? '전송 중' : (isRequested ? 'AS 전달됨' : 'AS 전송')}
            </button>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              {isRequested
                ? '이미 협력사 링크에 표시된 AS 요청입니다.'
                : '배정된 협력사와 고객에게 알림을 보내고, 협력사 링크에도 AS 요청이 표시됩니다.'}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
