import React from 'react';

import type { AdminOrder } from '../../../api/admin';
import { listRecurringOrders } from '../../../api/recurring';
import { formatAmount } from '../../../domain/recurrence';

// 정기계약 페이지와 표 스타일을 맞춘다(형제 컴포넌트 RecurringMonthlyTracker 참고).
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

// KST 기준 이번 달 "YYYY-MM".
function thisMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

// 2-3: 정기청소 메뉴 안에서 '정기 주문'만 따로 본다. 서버가 해당 월 예정일마다 주문을
// (없으면) 자동 생성하므로, 매월/매주 특정 요일 건이 이 목록에 그대로 뜬다.
export function RecurringOrdersList() {
  const [month, setMonth] = React.useState(thisMonth());
  const [rows, setRows] = React.useState<AdminOrder[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      setRows(await listRecurringOrders(month));
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기에 실패했습니다.');
      setRows(null);
    }
  }, [month]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const changeMonth = (value: string) => {
    setRows(null);
    setMonth(value);
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <label style={{ fontSize: 12.5, color: 'var(--text-tertiary)' }}>
          기준 월
          <input
            type="month"
            value={month}
            onChange={(e) => changeMonth(e.target.value)}
            data-testid="recurring-orders-month"
            // iOS 줌 방지: 입력 폰트 16px 이상.
            style={{ fontSize: 16, padding: '6px 8px', marginLeft: 8 }}
          />
        </label>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          정기계약에서 해당 월 예정일마다 자동 생성됩니다. 협력사링크에도 다른 주문과 함께 노출됩니다.
        </span>
      </div>

      {error && (
        <div
          role="alert"
          data-testid="recurring-orders-error"
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
        error ? null : <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>불러오는 중…</div>
      ) : rows.length === 0 ? (
        <div data-testid="recurring-orders-empty" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
          이 달에 생성된 정기 주문이 없습니다.
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
          <table style={{ width: '100%', minWidth: 720, fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={headStyle}>방문일</th>
                <th style={headStyle}>고객</th>
                <th style={headStyle}>서비스</th>
                <th style={headStyle}>담당</th>
                <th style={headStyle}>상태</th>
                <th style={headStyle}>고객 금액</th>
                <th style={headStyle}>도급가</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((o) => (
                <tr key={o.id} data-testid={`recurring-order-${o.id}`}>
                  <td style={{ ...cellStyle, fontWeight: 600 }}>{o.scheduled_date ?? '미정'}</td>
                  <td style={cellStyle}>{o.customer_name}</td>
                  <td style={cellStyle}>{o.service_name}</td>
                  <td style={cellStyle}>{o.team_name || '미배정'}</td>
                  <td style={cellStyle}>{o.status}</td>
                  <td style={cellStyle}>{formatAmount(o.total_amount ?? null)}</td>
                  <td style={cellStyle}>{formatAmount(o.partner_payment_amount ?? null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
