import React from 'react';

import {
  approveOccurrences,
  listRecurringContracts,
  skipOccurrences,
  syncRecurringOccurrences,
  type PendingOccurrence,
  type RecurringContractSummary,
} from '../../../api/recurring';
import { CONTRACT_STATUS_LABEL, CONTRACT_STATUS_TONE, formatAmount } from '../../../domain/recurrence';
import { RecurringBillingView } from './RecurringBillingView';
import { RecurringContractDetail } from './RecurringContractDetail';
import { RecurringContractForm } from './RecurringContractForm';

type View = { mode: 'list' } | { mode: 'create' } | { mode: 'detail'; id: string };

const cellStyle: React.CSSProperties = {
  padding: '7px 8px',
  borderBottom: '1px solid var(--divider, var(--border))',
  whiteSpace: 'nowrap',
};

const headStyle: React.CSSProperties = {
  ...cellStyle,
  textAlign: 'left',
  color: 'var(--text-tertiary)',
  fontWeight: 600,
};

export function RecurringContractsPage({
  initialContractId = null,
  onInitialContractConsumed,
}: {
  // 주문 상세 '정기' 배지에서 역링크로 진입할 때 전달되는 계약 id.
  initialContractId?: string | null;
  onInitialContractConsumed?: () => void;
} = {}) {
  // 역링크 진입은 마운트 시점에 바로 상세로 들어간다(목록 깜빡임 없이).
  const [view, setView] = React.useState<View>(
    initialContractId ? { mode: 'detail', id: initialContractId } : { mode: 'list' },
  );
  // 전달받은 계약 id는 마운트 시 한 번만 소비해 부모 상태를 비운다.
  // (이후 일반 내비게이션으로 재진입할 때 지난 id로 상세가 다시 열리지 않도록.)
  const consumedRef = React.useRef(false);
  React.useEffect(() => {
    if (initialContractId && !consumedRef.current) {
      consumedRef.current = true;
      onInitialContractConsumed?.();
    }
  }, [initialContractId, onInitialContractConsumed]);
  const [contracts, setContracts] = React.useState<RecurringContractSummary[] | null>(null);
  const [pending, setPending] = React.useState<PendingOccurrence[]>([]);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  // 정기청소 영역 상단 탭: 계약 관리(기존) / 월 합산 청구·정산.
  const [tab, setTab] = React.useState<'contracts' | 'billing'>('contracts');

  const load = React.useCallback(async () => {
    setError(null);
    try {
      // 진입 시 도래분을 계산(sync)하고 계약 요약을 함께 불러온다. sync는 멱등이다.
      const [list, due] = await Promise.all([listRecurringContracts(), syncRecurringOccurrences()]);
      setContracts(list);
      setPending(due);
      setSelected(new Set(due.map((d) => d.occurrence_id)));
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기에 실패했습니다.');
      setContracts([]);
      setPending([]);
    }
  }, []);

  React.useEffect(() => {
    if (view.mode === 'list') {
      void load();
    }
  }, [view, load]);

  if (view.mode === 'create') {
    return (
      <RecurringContractForm onDone={() => setView({ mode: 'list' })} onCancel={() => setView({ mode: 'list' })} />
    );
  }
  if (view.mode === 'detail') {
    return <RecurringContractDetail contractId={view.id} onBack={() => setView({ mode: 'list' })} />;
  }

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });

  const allSelected = pending.length > 0 && selected.size === pending.length;
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(pending.map((p) => p.occurrence_id)));

  const runApprove = async () => {
    setBusy(true);
    setError(null);
    try {
      await approveOccurrences([...selected].map((occurrence_id) => ({ occurrence_id })));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '승인에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  };

  const runSkip = async () => {
    if (!window.confirm(`선택한 ${selected.size}건을 건너뛸까요? 건너뛴 회차는 주문으로 생성되지 않습니다.`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await skipOccurrences([...selected].map((occurrence_id) => ({ occurrence_id })));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '건너뛰기에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="admin-recurring-page" style={{ flex: 1, minHeight: 0, overflow: 'auto', background: 'var(--bg)' }}>
      <div className="page-shell" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, paddingBottom: 80 }}>
        {/* 계약 관리 / 월 정산 전환 탭 (목록 모드에서만 노출 — create/detail은 위에서 early return) */}
        <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)' }}>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            data-testid="recurring-tab-contracts"
            style={{ fontWeight: tab === 'contracts' ? 700 : 400 }}
            onClick={() => setTab('contracts')}
          >
            계약
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            data-testid="recurring-tab-billing"
            style={{ fontWeight: tab === 'billing' ? 700 : 400 }}
            onClick={() => setTab('billing')}
          >
            월 정산
          </button>
        </div>

        {tab === 'billing' && <RecurringBillingView />}
        {tab === 'contracts' && (
          <>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12.5, color: 'var(--text-tertiary)' }}>
            정기계약을 등록하면 주기에 맞춰 도래한 회차를 승인해 주문을 생성합니다.
          </span>
          <button
            className="btn btn--primary btn--sm"
            style={{ marginLeft: 'auto' }}
            data-testid="recurring-create"
            onClick={() => setView({ mode: 'create' })}
          >
            + 정기계약 등록
          </button>
        </div>

        {error && (
          <div
            role="alert"
            data-testid="recurring-error"
            style={{
              padding: 10,
              borderRadius: 6,
              background: 'var(--danger-bg, #fdecea)',
              color: 'var(--danger-fg, #c0392b)',
              fontSize: 12.5,
            }}
          >
            {error}
          </div>
        )}

        {/* 승인 대기 패널 */}
        <section style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14, background: 'var(--surface)' }}>
          <h2 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 10px' }}>승인 대기 회차 ({pending.length})</h2>
          {pending.length === 0 ? (
            <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>도래한 회차가 없습니다.</div>
          ) : (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', minWidth: 640, fontSize: 13, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ ...headStyle, width: 28 }}>
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={toggleAll}
                          aria-label="전체 선택"
                          data-testid="recurring-select-all"
                        />
                      </th>
                      <th style={headStyle}>계약</th>
                      <th style={headStyle}>고객</th>
                      <th style={headStyle}>방문일</th>
                      <th style={headStyle}>서비스</th>
                      <th style={headStyle}>금액</th>
                      <th style={headStyle}>협력사</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pending.map((p) => (
                      <tr key={p.occurrence_id} data-testid={`pending-${p.occurrence_id}`}>
                        <td style={cellStyle}>
                          <input
                            type="checkbox"
                            checked={selected.has(p.occurrence_id)}
                            onChange={() => toggle(p.occurrence_id)}
                            aria-label={`${p.contract_label} ${p.due_date} 선택`}
                          />
                        </td>
                        <td style={cellStyle}>{p.contract_label}</td>
                        <td style={cellStyle}>{p.customer_name}</td>
                        <td style={{ ...cellStyle, color: p.is_overdue ? 'var(--danger-fg, #c0392b)' : undefined }}>
                          {p.due_date}
                          {p.is_overdue && <span style={{ marginLeft: 6, fontSize: 11 }}>지연</span>}
                        </td>
                        <td style={cellStyle}>{p.service_name}</td>
                        <td style={cellStyle}>{formatAmount(p.total_amount)}</td>
                        <td style={cellStyle}>{p.default_partner_name ?? '미배정'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button
                  className="btn btn--primary btn--sm"
                  disabled={busy || selected.size === 0}
                  data-testid="recurring-approve"
                  onClick={() => void runApprove()}
                >
                  선택 승인 ({selected.size})
                </button>
                <button
                  className="btn btn--ghost btn--sm"
                  disabled={busy || selected.size === 0}
                  data-testid="recurring-skip"
                  onClick={() => void runSkip()}
                >
                  건너뛰기
                </button>
              </div>
            </>
          )}
        </section>

        {/* 계약 목록 */}
        <section>
          <h2 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 10px' }}>정기계약</h2>
          {contracts === null ? (
            <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>불러오는 중…</div>
          ) : contracts.length === 0 ? (
            <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>등록된 정기계약이 없습니다.</div>
          ) : (
            <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface)' }}>
              <table style={{ width: '100%', minWidth: 640, fontSize: 13, borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={headStyle}>계약명</th>
                    <th style={headStyle}>고객</th>
                    <th style={headStyle}>주기</th>
                    <th style={headStyle}>다음 회차</th>
                    <th style={headStyle}>상태</th>
                    <th style={headStyle}>이번 달</th>
                  </tr>
                </thead>
                <tbody>
                  {contracts.map((c) => (
                    <tr
                      key={c.id}
                      data-testid={`contract-${c.id}`}
                      style={{ cursor: 'pointer' }}
                      onClick={() => setView({ mode: 'detail', id: c.id })}
                    >
                      <td style={{ ...cellStyle, fontWeight: 600 }}>{c.label}</td>
                      <td style={cellStyle}>{c.customer_name}</td>
                      <td style={cellStyle}>{c.schedule_text}</td>
                      <td style={cellStyle}>{c.next_due_date ?? '-'}</td>
                      <td style={cellStyle}>
                        <span
                          style={{
                            padding: '2px 9px',
                            borderRadius: 10,
                            fontSize: 11.5,
                            fontWeight: 600,
                            background: CONTRACT_STATUS_TONE[c.status],
                            color: 'var(--text-secondary)',
                          }}
                        >
                          {CONTRACT_STATUS_LABEL[c.status]}
                        </span>
                      </td>
                      <td style={cellStyle}>
                        {c.this_month_count}건 / {formatAmount(c.this_month_amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
          </>
        )}
      </div>
    </div>
  );
}
