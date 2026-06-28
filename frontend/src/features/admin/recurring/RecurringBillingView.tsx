import React from 'react';

import {
  exportRecurringBilling,
  getRecurringBilling,
  markRecurringMonthPaid,
  settleRecurringMonth,
  type RecurringBillingRow,
} from '../../../api/recurringBilling';
import { formatAmount } from '../../../domain/recurrence';

// 정기계약 페이지와 표 스타일을 맞춘다(형제 컴포넌트 RecurringContractsPage 참고).
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

// KST 기준 이번 달 "YYYY-MM" (브라우저 로컬이 KST 타깃).
function thisMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export function RecurringBillingView() {
  const [month, setMonth] = React.useState(thisMonth());
  const [rows, setRows] = React.useState<RecurringBillingRow[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      setRows(await getRecurringBilling(month));
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기에 실패했습니다.');
      setRows([]);
    }
  }, [month]);

  React.useEffect(() => {
    void load();
  }, [load]);

  // 월을 바꾸면 이전 달 데이터가 잠깐 남지 않도록 로딩 상태로 되돌린다.
  const changeMonth = (value: string) => {
    setRows(null);
    setMonth(value);
  };

  // confirm → 액션 → 재조회. 실패 시 인라인 에러. (형제 페이지와 동일 패턴)
  const act = async (run: () => Promise<unknown>, confirmMsg: string) => {
    if (!window.confirm(confirmMsg)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await run();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '처리에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <label style={{ fontSize: 12.5, color: 'var(--text-tertiary)' }}>
          청구 월
          <input
            type="month"
            value={month}
            onChange={(e) => changeMonth(e.target.value)}
            data-testid="billing-month"
            // iOS 줌 방지: 입력 폰트 16px 이상.
            style={{ fontSize: 16, padding: '6px 8px', marginLeft: 8 }}
          />
        </label>
        <button
          className="btn btn--ghost btn--sm"
          style={{ marginLeft: 'auto' }}
          data-testid="billing-export"
          disabled={busy || !rows || rows.length === 0}
          onClick={() => void exportRecurringBilling(month)}
        >
          CSV 내보내기
        </button>
      </div>

      {error && (
        <div
          role="alert"
          data-testid="billing-error"
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

      {rows === null ? (
        <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>불러오는 중…</div>
      ) : rows.length === 0 ? (
        <div data-testid="billing-empty" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
          이 달에 집계할 정기 주문이 없습니다.
        </div>
      ) : (
        <div
          style={{
            overflowX: 'auto',
            border: '1px solid var(--border)',
            borderRadius: 8,
            background: 'var(--surface)',
          }}
        >
          <table style={{ width: '100%', minWidth: 760, fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={headStyle}>계약</th>
                <th style={headStyle}>고객</th>
                <th style={headStyle}>방문</th>
                <th style={headStyle}>청구합</th>
                <th style={headStyle}>확정매출</th>
                <th style={headStyle}>미입금</th>
                <th style={headStyle}>정산합</th>
                <th style={headStyle}>미정산</th>
                <th style={headStyle}>액션</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.contract_id} data-testid={`billing-row-${r.contract_id}`}>
                  <td style={{ ...cellStyle, fontWeight: 600 }}>{r.label}</td>
                  <td style={cellStyle}>{r.customer_name}</td>
                  <td style={cellStyle}>{r.visit_count}건</td>
                  <td style={cellStyle}>{formatAmount(r.billed_total)}</td>
                  <td style={cellStyle}>{formatAmount(r.confirmed_revenue)}</td>
                  <td
                    style={{
                      ...cellStyle,
                      color: r.unpaid_customer_count ? 'var(--danger-fg, #c0392b)' : undefined,
                    }}
                  >
                    {r.unpaid_customer_count}건
                  </td>
                  <td style={cellStyle}>{formatAmount(r.partner_total)}</td>
                  <td
                    style={{
                      ...cellStyle,
                      color: r.unpaid_partner_count ? 'var(--danger-fg, #c0392b)' : undefined,
                    }}
                  >
                    {r.unpaid_partner_count}건 / {formatAmount(r.unpaid_partner_total)}
                  </td>
                  <td style={cellStyle}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        className="btn btn--ghost btn--sm"
                        disabled={busy || r.unpaid_customer_count === 0}
                        data-testid={`billing-markpaid-${r.contract_id}`}
                        onClick={() =>
                          void act(
                            () => markRecurringMonthPaid(r.contract_id, month),
                            `${r.label} · ${month} 미입금 ${r.unpaid_customer_count}건을 입금완료로 표시할까요?`,
                          )
                        }
                      >
                        입금완료
                      </button>
                      <button
                        className="btn btn--ghost btn--sm"
                        disabled={busy || r.unpaid_partner_count === 0}
                        data-testid={`billing-settle-${r.contract_id}`}
                        onClick={() =>
                          void act(
                            () => settleRecurringMonth(r.contract_id, month),
                            `${r.label} · ${month} 정산 가능 ${r.unpaid_partner_count}건을 정산완료로 표시할까요?`,
                          )
                        }
                      >
                        정산완료
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
