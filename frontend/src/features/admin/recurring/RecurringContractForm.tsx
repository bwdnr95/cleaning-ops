import React from 'react';

import { listPartners } from '../../../api/admin';
import {
  createRecurringContract,
  updateRecurringContract,
  type RecurringContractInput,
} from '../../../api/recurring';
import { WEEKDAY_LABEL } from '../../../domain/recurrence';

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
  const [form, setForm] = React.useState<RecurringContractInput>(() => {
    if (!initial) return EMPTY;
    // 레거시 단일 weekday만 가진 주간 계약을 편집할 때 토글이 비어 보이지 않도록 weekdays로 시드한다.
    if (
      initial.recurrence_mode === 'weekly' &&
      (initial.weekdays == null || initial.weekdays.length === 0) &&
      initial.weekday != null
    ) {
      return { ...initial, weekdays: [initial.weekday] };
    }
    return initial;
  });
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

  // 주간 다중요일 토글(월=0 ... 일=6). 선택/해제 후 항상 오름차순 정렬해 둔다.
  const toggleWeekday = (idx: number) => {
    const current = form.weekdays ?? [];
    const next = current.includes(idx)
      ? current.filter((w) => w !== idx)
      : [...current, idx].sort((a, b) => a - b);
    set('weekdays', next);
  };

  // weekly인데 요일을 하나도 고르지 않으면 저장 불가(백엔드는 폴백하지만 의도 명확화를 위해 막는다).
  const weeklyNeedsWeekday =
    form.recurrence_mode === 'weekly' && (form.weekdays ?? []).length === 0;

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: RecurringContractInput = {
        ...form,
        day_of_month: form.recurrence_mode === 'monthly' ? form.day_of_month ?? 1 : null,
        interval_weeks: form.recurrence_mode === 'weekly' ? form.interval_weeks ?? 1 : null,
        weekdays: form.recurrence_mode === 'weekly' ? form.weekdays ?? [] : null,
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
              <>
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
                <label style={labelStyle}>
                  요일 선택 (다중 가능)
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(7, 1fr)',
                      gap: 6,
                      marginTop: 2,
                    }}
                  >
                    {WEEKDAY_LABEL.map((lbl, idx) => {
                      const on = (form.weekdays ?? []).includes(idx);
                      return (
                        <button
                          type="button"
                          key={idx}
                          data-testid={`rc-weekday-${idx}`}
                          aria-pressed={on}
                          onClick={() => toggleWeekday(idx)}
                          style={{
                            height: 44, // 모바일 터치 타겟 최소 44px
                            borderRadius: 6,
                            fontSize: 15,
                            cursor: 'pointer',
                            border: `1px solid ${on ? 'var(--brand)' : 'var(--border)'}`,
                            background: on ? 'var(--brand-bg)' : 'var(--surface)',
                            color: on ? 'var(--brand)' : 'var(--text-secondary)',
                            fontWeight: on ? 700 : 500,
                          }}
                        >
                          {lbl}
                        </button>
                      );
                    })}
                  </div>
                  {weeklyNeedsWeekday && (
                    <span
                      data-testid="rc-weekday-warning"
                      style={{ fontSize: 11.5, color: 'var(--danger-fg, #c0392b)', fontWeight: 500 }}
                    >
                      주간 계약은 요일을 1개 이상 선택하세요.
                    </span>
                  )}
                </label>
              </>
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
              상품 상세(선택)
              <textarea
                style={{ ...inputStyle, minHeight: 60, resize: 'vertical', fontFamily: 'inherit' }}
                value={form.service_detail ?? ''}
                onChange={(e) => set('service_detail', e.target.value || null)}
                data-testid="rc-service-detail"
                placeholder="예: 3층 사무실 · 화장실 2칸 포함"
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
              특별 요청(선택)
              <input
                style={inputStyle}
                value={form.special_request ?? ''}
                onChange={(e) => set('special_request', e.target.value || null)}
                data-testid="rc-special-request"
              />
            </label>
            <label style={labelStyle}>
              청소 담당팀(선택)
              <input
                style={inputStyle}
                value={form.team_name ?? ''}
                onChange={(e) => set('team_name', e.target.value || null)}
                data-testid="rc-team-name"
                placeholder="예: 1팀 / 김반장팀"
              />
            </label>
            <label style={labelStyle}>
              청소 담당자 번호(선택)
              <input
                style={inputStyle}
                value={form.team_phone ?? ''}
                onChange={(e) => set('team_phone', e.target.value || null)}
                data-testid="rc-team-phone"
                inputMode="numeric"
                placeholder="01012345678"
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
            disabled={saving || weeklyNeedsWeekday}
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
