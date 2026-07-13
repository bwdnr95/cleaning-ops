import React from 'react';

import {
  getRecurringMonthly,
  setRecurringMonthlyStatus,
  type RecurringMonthlyRow,
} from '../../../api/recurringMonthly';
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

const textCellStyle: React.CSSProperties = {
  ...cellStyle,
  maxWidth: 150,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

const scheduleCellStyle: React.CSSProperties = {
  ...textCellStyle,
  maxWidth: 190,
};

// 체크박스 셀: 가운데 정렬 + 모바일 터치 여유.
const checkCellStyle: React.CSSProperties = {
  ...cellStyle,
  textAlign: 'center',
};

// KST 기준 이번 달 "YYYY-MM" (브라우저 로컬이 KST 타깃).
function thisMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

type ToggleField = 'tax_invoice_issued' | 'balance_paid' | 'partner_payment_paid';

export function RecurringMonthlyTracker() {
  const [month, setMonth] = React.useState(thisMonth());
  const [rows, setRows] = React.useState<RecurringMonthlyRow[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  // 토글 처리 중인 (계약,필드) 키 집합. 같은 셀 더블클릭/경합을 막는다.
  const [pendingKeys, setPendingKeys] = React.useState<Set<string>>(new Set());

  const load = React.useCallback(async () => {
    setError(null);
    try {
      setRows(await getRecurringMonthly(month));
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기에 실패했습니다.');
      // 실패 시 빈 배열로 두면 "정기계약 없음" 빈 상태가 에러 배너와 함께 떠 오해를 준다.
      // null로 되돌려 에러 배너만 노출한다(아래 로딩 분기는 !error로 가드).
      setRows(null);
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

  // 세금계산서/잔금 토글 → 서버 반영 후 재조회. 실패 시 인라인 에러.
  const toggle = async (row: RecurringMonthlyRow, field: ToggleField) => {
    const key = `${row.contract_id}:${field}`;
    setPendingKeys((prev) => new Set(prev).add(key));
    setError(null);
    try {
      await setRecurringMonthlyStatus(row.contract_id, month, { [field]: !row[field] });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '처리에 실패했습니다.');
    } finally {
      setPendingKeys((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
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
            data-testid="monthly-month"
            // iOS 줌 방지: 입력 폰트 16px 이상.
            style={{ fontSize: 16, padding: '6px 8px', marginLeft: 8 }}
          />
        </label>
      </div>

      {error && (
        <div
          role="alert"
          data-testid="monthly-error"
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
        <div data-testid="monthly-empty" style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
          진행 중인 정기계약이 없습니다.
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
          <table style={{ width: '100%', minWidth: 820, fontSize: 13, borderCollapse: 'collapse', tableLayout: 'fixed' }}>
            <thead>
              <tr>
                <th style={headStyle}>계약</th>
                <th style={headStyle}>고객</th>
                <th style={headStyle}>주기</th>
                <th style={headStyle}>고객 월금액</th>
                <th style={headStyle}>협력사 도급액</th>
                <th style={{ ...headStyle, textAlign: 'center' }}>세금계산서</th>
                <th style={{ ...headStyle, textAlign: 'center' }}>잔금입금</th>
                <th style={{ ...headStyle, textAlign: 'center' }}>협력사 지급</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.contract_id} data-testid={`monthly-row-${r.contract_id}`}>
                  <td style={{ ...textCellStyle, fontWeight: 600 }} title={r.label}>{r.label}</td>
                  <td style={textCellStyle} title={r.customer_name}>{r.customer_name}</td>
                  <td style={scheduleCellStyle} title={r.schedule_text}>{r.schedule_text}</td>
                  <td style={cellStyle}>{formatAmount(r.amount)}</td>
                  <td style={cellStyle}>{formatAmount(r.partner_amount)}</td>
                  <td style={checkCellStyle}>
                    <input
                      type="checkbox"
                      checked={r.tax_invoice_issued}
                      disabled={pendingKeys.has(`${r.contract_id}:tax_invoice_issued`)}
                      onChange={() => void toggle(r, 'tax_invoice_issued')}
                      data-testid={`monthly-tax-${r.contract_id}`}
                      aria-label={`${r.label} ${month} 세금계산서 발행`}
                      style={{ width: 18, height: 18, cursor: 'pointer' }}
                    />
                  </td>
                  <td style={checkCellStyle}>
                    <input
                      type="checkbox"
                      checked={r.balance_paid}
                      disabled={pendingKeys.has(`${r.contract_id}:balance_paid`)}
                      onChange={() => void toggle(r, 'balance_paid')}
                      data-testid={`monthly-paid-${r.contract_id}`}
                      aria-label={`${r.label} ${month} 잔금입금`}
                      style={{ width: 18, height: 18, cursor: 'pointer' }}
                    />
                  </td>
                  <td style={checkCellStyle}>
                    {r.partner_billing_mode === 'monthly' ? (
                      <input
                        type="checkbox"
                        checked={r.partner_payment_paid}
                        disabled={pendingKeys.has(`${r.contract_id}:partner_payment_paid`)}
                        onChange={() => void toggle(r, 'partner_payment_paid')}
                        data-testid={`monthly-partner-paid-${r.contract_id}`}
                        aria-label={`${r.label} ${month} 협력사 지급`}
                        style={{ width: 18, height: 18, cursor: 'pointer' }}
                      />
                    ) : (
                      <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>주문별</span>
                    )}
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
