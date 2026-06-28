import React from 'react';

import {
  deleteRecurringContract,
  endRecurringContract,
  getRecurringContract,
  pauseRecurringContract,
  resumeRecurringContract,
  type RecurringContract,
} from '../../../api/recurring';
import { Icon } from '../../../components/common/ui';
import {
  CONTRACT_STATUS_LABEL,
  CONTRACT_STATUS_TONE,
  formatAmount,
  formatScheduleText,
} from '../../../domain/recurrence';
import { RecurringContractForm } from './RecurringContractForm';

export function RecurringContractDetail({
  contractId,
  onBack,
}: {
  contractId: string;
  onBack: () => void;
}) {
  const [contract, setContract] = React.useState<RecurringContract | null>(null);
  const [editing, setEditing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      setContract(await getRecurringContract(contractId));
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기에 실패했습니다.');
    }
  }, [contractId]);

  React.useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', background: 'var(--bg)' }}>
        <div style={{ padding: 20 }}>
          <button className="btn btn--ghost btn--sm" onClick={onBack}>
            <Icon name="chevronLeft" size={13} /> 목록
          </button>
          <div role="alert" data-testid="rc-detail-error" style={{ color: 'var(--danger-fg, #c0392b)', marginTop: 12 }}>
            {error}
          </div>
        </div>
      </div>
    );
  }

  if (!contract) {
    return (
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', background: 'var(--bg)' }}>
        <div style={{ padding: 20, color: 'var(--text-tertiary)' }}>불러오는 중…</div>
      </div>
    );
  }

  if (editing) {
    return (
      <RecurringContractForm
        initial={{ ...contract }}
        onDone={() => {
          setEditing(false);
          void load();
        }}
        onCancel={() => setEditing(false)}
      />
    );
  }

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '처리에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  };

  const handleEnd = () => {
    if (!window.confirm('이 계약을 종료할까요? 종료 후에는 새 회차가 더 이상 생성되지 않습니다.')) {
      return;
    }
    void act(() => endRecurringContract(contract.id));
  };

  const handleDelete = () => {
    if (
      !window.confirm(
        '이 정기계약을 삭제할까요?\n\n이미 생성된 주문은 주문관리에 보존되며, 계약 목록에서만 사라집니다.',
      )
    ) {
      return;
    }
    void act(async () => {
      await deleteRecurringContract(contract.id);
      onBack();
    });
  };

  return (
    <div style={{ flex: 1, minHeight: 0, overflow: 'auto', background: 'var(--bg)' }}>
      <div style={{ padding: 20, maxWidth: 720, paddingBottom: 80 }}>
        <button className="btn btn--ghost btn--sm" onClick={onBack}>
          <Icon name="chevronLeft" size={13} /> 목록
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '12px 0' }}>
          <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }} data-testid="rc-detail-label">
            {contract.label}
          </h1>
          <span
            style={{
              fontSize: 11.5,
              fontWeight: 600,
              padding: '2px 9px',
              borderRadius: 10,
              background: CONTRACT_STATUS_TONE[contract.status],
              color: 'var(--text-secondary)',
            }}
            data-testid="rc-detail-status"
          >
            {CONTRACT_STATUS_LABEL[contract.status]}
          </span>
          <button
            className="btn btn--secondary btn--sm"
            style={{ marginLeft: 'auto' }}
            onClick={() => setEditing(true)}
            data-testid="rc-detail-edit"
          >
            수정
          </button>
        </div>

        <dl
          style={{
            display: 'grid',
            gridTemplateColumns: '120px 1fr',
            gap: '8px 12px',
            fontSize: 13,
            margin: 0,
            padding: 14,
            border: '1px solid var(--border)',
            borderRadius: 8,
            background: 'var(--surface)',
          }}
        >
          <Term label="고객" value={`${contract.customer_name} (${contract.customer_phone})`} />
          <Term
            label="주소"
            value={[contract.customer_address, contract.customer_address_detail].filter(Boolean).join(' ')}
          />
          <Term label="주기" value={formatScheduleText(contract)} />
          <Term label="시작일" value={contract.start_date} />
          <Term label="서비스" value={contract.service_name} />
          <Term label="1주기 금액" value={formatAmount(contract.total_amount ?? null)} />
          <Term label="다음 회차" value={contract.next_due_date ?? '-'} />
          <Term label="고객 링크" value={`/c/${contract.customer_token}`} mono />
        </dl>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }}>
          {contract.status === 'active' && (
            <button
              className="btn btn--ghost btn--sm"
              disabled={busy}
              onClick={() => void act(() => pauseRecurringContract(contract.id))}
              data-testid="rc-detail-pause"
            >
              일시정지
            </button>
          )}
          {contract.status === 'paused' && (
            <button
              className="btn btn--ghost btn--sm"
              disabled={busy}
              onClick={() => void act(() => resumeRecurringContract(contract.id))}
              data-testid="rc-detail-resume"
            >
              재개
            </button>
          )}
          {contract.status !== 'ended' && (
            <button
              className="btn btn--ghost btn--sm"
              disabled={busy}
              onClick={handleEnd}
              data-testid="rc-detail-end"
            >
              종료
            </button>
          )}
          <button
            className="btn btn--ghost btn--sm"
            style={{ color: 'var(--danger-fg, #c0392b)' }}
            disabled={busy}
            onClick={handleDelete}
            data-testid="rc-detail-delete"
          >
            삭제
          </button>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 8 }}>
          삭제해도 이미 생성된 주문은 주문관리에 보존됩니다.
        </p>
      </div>
    </div>
  );
}

function Term({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <>
      <dt style={{ color: 'var(--text-tertiary)', fontWeight: 600 }}>{label}</dt>
      <dd
        style={{
          margin: 0,
          color: 'var(--text)',
          fontFamily: mono ? 'var(--font-mono)' : 'inherit',
          wordBreak: 'break-all',
        }}
      >
        {value}
      </dd>
    </>
  );
}
