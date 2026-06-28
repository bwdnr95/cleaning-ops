import React from 'react';

import { listPartners } from '../../../api/admin';
import {
  createRecurringContract,
  updateRecurringContract,
  type RecurringContractInput,
} from '../../../api/recurring';

type PartnerOption = { id: string; name: string };

const EMPTY: RecurringContractInput = {
  label: '',
  customer_name: '',
  customer_phone: '',
  customer_address: '',
  recurrence_mode: 'monthly',
  day_of_month: 10,
  start_date: '',
  service_name: '',
  discount_amount: 0,
};

// iOS 줌 방지를 위해 입력 폰트는 16px 이상으로 둔다.
const inputStyle: React.CSSProperties = {
  fontSize: 16,
  padding: '8px 10px',
  border: '1px solid var(--border)',
  borderRadius: 6,
  width: '100%',
  background: 'var(--surface)',
  color: 'var(--text)',
};

const labelStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  fontSize: 12.5,
  fontWeight: 600,
  color: 'var(--text-secondary)',
};

export function RecurringContractForm({
  initial = null,
  onDone,
  onCancel,
}: {
  initial?: (RecurringContractInput & { id: string }) | null;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = React.useState<RecurringContractInput>(initial ?? EMPTY);
  const [partners, setPartners] = React.useState<PartnerOption[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    void listPartners()
      .then((rows: PartnerOption[]) => setPartners(rows.map((p) => ({ id: p.id, name: p.name }))))
      .catch(() => setPartners([]));
  }, []);

  const set = <K extends keyof RecurringContractInput>(key: K, value: RecurringContractInput[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  // 주간 주기에서는 start_date의 요일을 weekday(월=0 ... 일=6)로 자동 동기화한다(설계 §10.1).
  React.useEffect(() => {
    if (form.recurrence_mode === 'weekly' && form.start_date) {
      const parsed = new Date(form.start_date);
      if (!Number.isNaN(parsed.getTime())) {
        const wd = (parsed.getDay() + 6) % 7; // JS 일=0 → 월=0 규약 변환
        if (form.weekday !== wd) set('weekday', wd);
      }
    }
  }, [form.recurrence_mode, form.start_date]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: RecurringContractInput = {
        ...form,
        day_of_month: form.recurrence_mode === 'monthly' ? form.day_of_month ?? 1 : null,
        interval_weeks: form.recurrence_mode === 'weekly' ? form.interval_weeks ?? 1 : null,
      };
      if (initial) {
        await updateRecurringContract(initial.id, payload);
      } else {
        await createRecurringContract(payload);
      }
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ flex: 1, minHeight: 0, overflow: 'auto', background: 'var(--bg)' }}>
      <div style={{ padding: 20, maxWidth: 640, paddingBottom: 80 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 4px' }}>
          {initial ? '정기계약 수정' : '정기계약 등록'}
        </h1>
        {initial && (
          <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: '0 0 12px' }}>
            고객정보 수정은 이 계약의 모든 회차(기존 주문 포함 그룹)에 반영됩니다.
          </p>
        )}
        {error && (
          <div
            role="alert"
            data-testid="rc-form-error"
            style={{
              padding: 10,
              borderRadius: 6,
              background: 'var(--danger-bg, #fdecea)',
              color: 'var(--danger-fg, #c0392b)',
              fontSize: 12.5,
              marginBottom: 12,
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: 'grid', gap: 12 }}>
          <FormSection title="고객 정보">
            <label style={labelStyle}>
              계약명
              <input
                style={inputStyle}
                value={form.label}
                onChange={(e) => set('label', e.target.value)}
                data-testid="rc-label"
                placeholder="예: 강남빌딩 정기청소"
              />
            </label>
            <label style={labelStyle}>
              고객명
              <input
                style={inputStyle}
                value={form.customer_name}
                onChange={(e) => set('customer_name', e.target.value)}
                data-testid="rc-customer-name"
              />
            </label>
            <label style={labelStyle}>
              연락처
              <input
                style={inputStyle}
                value={form.customer_phone}
                onChange={(e) => set('customer_phone', e.target.value)}
                data-testid="rc-customer-phone"
                inputMode="numeric"
                placeholder="01012345678"
              />
            </label>
            <label style={labelStyle}>
              주소
              <input
                style={inputStyle}
                value={form.customer_address}
                onChange={(e) => set('customer_address', e.target.value)}
                data-testid="rc-customer-address"
              />
            </label>
            <label style={labelStyle}>
              상세주소
              <input
                style={inputStyle}
                value={form.customer_address_detail ?? ''}
                onChange={(e) => set('customer_address_detail', e.target.value || null)}
              />
            </label>
          </FormSection>

          <FormSection title="스케줄">
            <label style={labelStyle}>
              주기
              <select
                style={inputStyle}
                value={form.recurrence_mode}
                onChange={(e) => set('recurrence_mode', e.target.value as RecurringContractInput['recurrence_mode'])}
                data-testid="rc-mode"
              >
                <option value="monthly">매월 (지정일)</option>
                <option value="weekly">주간 (N주마다)</option>
              </select>
            </label>
            {form.recurrence_mode === 'monthly' ? (
              <label style={labelStyle}>
                매월 며칠
                <input
                  style={inputStyle}
                  type="number"
                  min={1}
                  max={31}
                  value={form.day_of_month ?? 10}
                  onChange={(e) => set('day_of_month', Number(e.target.value))}
                  data-testid="rc-day-of-month"
                />
              </label>
            ) : (
              <label style={labelStyle}>
                간격(주)
                <select
                  style={inputStyle}
                  value={form.interval_weeks ?? 1}
                  onChange={(e) => set('interval_weeks', Number(e.target.value))}
                  data-testid="rc-interval-weeks"
                >
                  <option value={1}>매주</option>
                  <option value={2}>격주</option>
                  <option value={4}>4주마다</option>
                </select>
              </label>
            )}
            <label style={labelStyle}>
              시작일
              <input
                style={inputStyle}
                type="date"
                value={form.start_date}
                onChange={(e) => set('start_date', e.target.value)}
                data-testid="rc-start-date"
              />
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <label style={labelStyle}>
                종료일(선택)
                <input
                  style={inputStyle}
                  type="date"
                  value={form.end_date ?? ''}
                  onChange={(e) => set('end_date', e.target.value || null)}
                  data-testid="rc-end-date"
                />
              </label>
              <label style={labelStyle}>
                최대 회차(선택)
                <input
                  style={inputStyle}
                  type="number"
                  min={1}
                  value={form.max_occurrences ?? ''}
                  onChange={(e) =>
                    set('max_occurrences', e.target.value === '' ? null : Number(e.target.value))
                  }
                  data-testid="rc-max-occurrences"
                />
              </label>
            </div>
          </FormSection>

          <FormSection title="회차 템플릿">
            <label style={labelStyle}>
              서비스명
              <input
                style={inputStyle}
                value={form.service_name}
                onChange={(e) => set('service_name', e.target.value)}
                data-testid="rc-service-name"
              />
            </label>
            <label style={labelStyle}>
              1주기 금액
              <input
                style={inputStyle}
                type="number"
                value={form.total_amount ?? ''}
                onChange={(e) => set('total_amount', e.target.value === '' ? null : Number(e.target.value))}
                data-testid="rc-amount"
              />
            </label>
            <label style={labelStyle}>
              계약금(선택)
              <input
                style={inputStyle}
                type="number"
                value={form.deposit_amount ?? ''}
                onChange={(e) => set('deposit_amount', e.target.value === '' ? null : Number(e.target.value))}
              />
            </label>
            <label style={labelStyle}>
              요청 시간(선택)
              <input
                style={inputStyle}
                value={form.requested_time ?? ''}
                onChange={(e) => set('requested_time', e.target.value || null)}
                placeholder="예: 오전 10시 / 14:00"
              />
            </label>
            <label style={labelStyle}>
              특이사항(선택)
              <input
                style={inputStyle}
                value={form.special_request ?? ''}
                onChange={(e) => set('special_request', e.target.value || null)}
              />
            </label>
            <label style={labelStyle}>
              기본 협력사(선택)
              <select
                style={inputStyle}
                value={form.default_partner_id ?? ''}
                onChange={(e) => set('default_partner_id', e.target.value || null)}
                data-testid="rc-default-partner"
              >
                <option value="">미지정</option>
                {partners.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          </FormSection>
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button
            className="btn btn--primary"
            disabled={saving}
            onClick={() => void submit()}
            data-testid="rc-submit"
          >
            {saving ? '저장 중…' : '저장'}
          </button>
          <button className="btn btn--ghost" disabled={saving} onClick={onCancel}>
            취소
          </button>
        </div>
      </div>
    </div>
  );
}

function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      style={{
        border: '1px solid var(--border)',
        borderRadius: 8,
        padding: 14,
        display: 'grid',
        gap: 10,
        background: 'var(--surface)',
      }}
    >
      <h2 style={{ fontSize: 13, fontWeight: 700, margin: 0, color: 'var(--text-tertiary)' }}>{title}</h2>
      {children}
    </section>
  );
}
