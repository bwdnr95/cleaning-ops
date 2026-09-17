import React from 'react';

import { listRecurringContracts, type RecurringContractSummary } from '../../../api/recurring';
import { CONTRACT_STATUS_LABEL, CONTRACT_STATUS_TONE } from '../../../domain/recurrence';
import { RecurringContractDetail } from './RecurringContractDetail';
import { RecurringContractForm } from './RecurringContractForm';
import { RecurringMonthlyTracker } from './RecurringMonthlyTracker';
import { RecurringOrdersList, type RecurringOrdersViewProps } from './RecurringOrdersList';

type View = { mode: 'list' } | { mode: 'create' } | { mode: 'detail'; id: string };
export type RecurringPageTab = 'contracts' | 'monthly' | 'orders';

interface RecurringContractsPageProps extends RecurringOrdersViewProps {
  // 주문 상세 '정기' 배지에서 역링크로 진입할 때 전달되는 계약 id.
  readonly initialContractId?: string | null;
  readonly onInitialContractConsumed?: () => void;
  // 상단 탭(계약/월 트래커/정기 주문)은 라우트 제어형 — 값은 해시(#recurring?view=…)에서 오고,
  // 변경은 onTabChange로 올려 브라우저 뒤로가기/새로고침에도 탭이 유지되게 한다.
  readonly tab: RecurringPageTab;
  readonly onTabChange: (tab: RecurringPageTab) => void;
  readonly onOpenOrder?: (orderId: string) => void;
  readonly onEditOrder?: (orderId: string) => void;
}

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
  tab,
  onTabChange,
  onOpenOrder,
  onEditOrder,
  ...ordersViewProps
}: RecurringContractsPageProps) {
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
  // 브라우저 뒤로/앞으로로 상단 탭만 바뀌면(popstate는 리마운트 없이 tab prop만 갱신) 계약 상세/등록 폼을
  // 닫고 목록으로 돌아간다. 마운트 시점엔 실행하지 않는다(역링크 진입은 detail로 시작해야 하므로).
  const prevTabRef = React.useRef(tab);
  React.useEffect(() => {
    if (prevTabRef.current === tab) {
      return;
    }
    prevTabRef.current = tab;
    setView({ mode: 'list' });
  }, [tab]);
  const [contracts, setContracts] = React.useState<RecurringContractSummary[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      setContracts(await listRecurringContracts());
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기에 실패했습니다.');
      // 실패 시 []로 두면 에러 배너 + "정기계약 없음" 빈상태가 동시에 떠 오해를 준다.
      // null로 되돌려 에러 배너만 노출한다(아래 로딩 분기는 error로 가드). 월 트래커(2c275b3)와 동일.
      setContracts(null);
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

  return (
    <div data-testid="admin-recurring-page" style={{ flex: 1, minHeight: 0, overflow: 'auto', background: 'var(--bg)' }}>
      <div className="page-shell" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, paddingBottom: 80 }}>
        {/* 계약 관리 / 월 트래커 / 정기 주문 전환 탭 (목록 모드에서만 노출 — create/detail은 위에서 early return).
            활성 탭은 라우트가 결정하므로 여기서는 onTabChange만 올린다. */}
        <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)' }}>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            data-testid="recurring-tab-contracts"
            style={{ fontWeight: tab === 'contracts' ? 700 : 400 }}
            onClick={() => onTabChange('contracts')}
          >
            계약
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            data-testid="recurring-tab-monthly"
            style={{ fontWeight: tab === 'monthly' ? 700 : 400 }}
            onClick={() => onTabChange('monthly')}
          >
            월 트래커
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            data-testid="recurring-tab-orders"
            style={{ fontWeight: tab === 'orders' ? 700 : 400 }}
            onClick={() => onTabChange('orders')}
          >
            정기 주문
          </button>
        </div>

        {tab === 'monthly' && <RecurringMonthlyTracker />}
        {tab === 'orders' && (
          <RecurringOrdersList {...ordersViewProps} onEditOrder={onEditOrder} onOpenOrder={onOpenOrder} />
        )}
        {tab === 'contracts' && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12.5, color: 'var(--text-tertiary)' }}>
                정기계약을 등록하면 월 트래커에서 매월 세금계산서·잔금 입금을 관리합니다.
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

            {/* 계약 목록 */}
            <section>
              <h2 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 10px' }}>정기계약</h2>
              {contracts === null ? (
                error ? null : <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>불러오는 중…</div>
              ) : contracts.length === 0 ? (
                <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>등록된 정기계약이 없습니다.</div>
              ) : (
                <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface)' }}>
                  <table style={{ width: '100%', minWidth: 560, fontSize: 13, borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        <th style={headStyle}>계약명</th>
                        <th style={headStyle}>고객</th>
                        <th style={headStyle}>주기</th>
                        <th style={headStyle}>다음 회차</th>
                        <th style={headStyle}>상태</th>
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
