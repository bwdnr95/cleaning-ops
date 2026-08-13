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
  billing_mode: 'per_visit',
  partner_billing_mode: 'per_visit',
  discount_amount: 0,
};

// iOS 줌 방지를 위해 입력 폰트는 16px 이상으로 둔다.
const inputStyle: React.CSSProperties = {
  fontSize: 'var(--mobile-input-font-size)',
  minHeight: 'var(--touch-target)',
  padding: 'var(--space-2) var(--space-2-5)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius)',
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

function normalizedPayload(value: RecurringContractInput): RecurringContractInput {
  return {
    ...value,
    day_of_month: value.recurrence_mode === 'monthly' ? value.day_of_month ?? 1 : null,
    interval_weeks: value.recurrence_mode === 'weekly' ? value.interval_weeks ?? 1 : null,
    weekdays: value.recurrence_mode === 'weekly' ? value.weekdays ?? [] : null,
  };
}

function changedPayload(
  current: RecurringContractInput,
  initial: RecurringContractInput,
): Partial<RecurringContractInput> {
  return Object.fromEntries(
    Object.entries(current).filter(([key, value]) => {
      const initialValue = initial[key as keyof RecurringContractInput];
      return JSON.stringify(value ?? null) !== JSON.stringify(initialValue ?? null);
    }),
  ) as Partial<RecurringContractInput>;
}

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
  const errorRef = React.useRef<HTMLDivElement>(null);
  const currentBillingMonthLabel = new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: 'long',
  }).format(new Date());

  React.useEffect(() => {
    void listPartners()
      .then((rows: PartnerOption[]) => setPartners(rows.map((p) => ({ id: p.id, name: p.name }))))
      .catch(() => setPartners([]));
  }, []);

  React.useEffect(() => {
    if (!error) return;
    errorRef.current?.focus({ preventScroll: true });
    errorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [error]);

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
      const payload = normalizedPayload(form);
      if (initial) {
        await updateRecurringContract(
          initial.id,
          changedPayload(payload, normalizedPayload(initial)),
        );
      } else {
        await createRecurringContract(payload);
      }
      onDone();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="recurring-contract-form" style={{ flex: 1, minHeight: 0, overflow: 'auto', background: 'var(--bg)' }}>
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
            ref={errorRef}
            role="alert"
            tabIndex={-1}
            data-testid="rc-form-error"
            style={{
              padding: 'var(--space-2-5)',
              borderRadius: 'var(--radius)',
              background: 'var(--danger-bg)',
              color: 'var(--danger-fg)',
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
              청구 방식
              <select
                style={inputStyle}
                value={form.billing_mode ?? 'per_visit'}
                onChange={(e) => set('billing_mode', e.target.value as RecurringContractInput['billing_mode'])}
                data-testid="rc-billing-mode"
              >
                <option value="per_visit">회당 합산 (회당 금액 × 방문 횟수)</option>
                <option value="monthly">월 고정 (방문 횟수 무관)</option>
              </select>
            </label>
            <label style={labelStyle}>
              {form.billing_mode === 'monthly' ? '월 고정 금액' : '회당 금액'}
              <input
                style={inputStyle}
                type="number"
                value={form.total_amount ?? ''}
                onChange={(e) => set('total_amount', e.target.value === '' ? null : Number(e.target.value))}
                data-testid="rc-amount"
              />
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 400 }}>
                {form.billing_mode === 'monthly'
                  ? '월 트래커에 이 금액이 매월 고정으로 청구됩니다.'
                  : '월 트래커에 회당 금액 × 그 달 방문 횟수로 합산됩니다.'}
              </span>
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
              협력사 정산 방식
              <select
                style={inputStyle}
                value={form.partner_billing_mode ?? 'per_visit'}
                onChange={(e) =>
                  set('partner_billing_mode', e.target.value as RecurringContractInput['partner_billing_mode'])
                }
                data-testid="rc-partner-billing-mode"
              >
                <option value="per_visit">회당 정산 (정기 주문별 정산)</option>
                <option value="monthly">월 정산 (월별 트래커 지급)</option>
              </select>
            </label>
            <label style={labelStyle}>
              {form.partner_billing_mode === 'monthly' ? '협력사 월 도급가' : '협력사 회당 도급가'}
              <input
                style={inputStyle}
                type="number"
                value={form.partner_payment_amount ?? ''}
                onChange={(e) =>
                  set('partner_payment_amount', e.target.value === '' ? null : Number(e.target.value))
                }
                data-testid="rc-partner-payment-amount"
              />
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 400 }}>
                {form.partner_billing_mode === 'monthly'
                  ? '월별 트래커에서 협력사 지급 여부를 체크합니다.'
                  : '생성된 정기 주문의 도급가로 내려가 정산 탭에 반영됩니다.'}
              </span>
            </label>
            {initial && (
              <div
                data-testid="rc-partner-billing-effective-note"
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  background: 'var(--bg-subtle)',
                  color: 'var(--text-secondary)',
                  fontSize: 12,
                  lineHeight: 1.55,
                  wordBreak: 'keep-all',
                }}
              >
                정산 방식과 도급가 변경은 {currentBillingMonthLabel}부터 적용됩니다. 이전 달 정산 이력과
                기존 주문·사진은 그대로 유지됩니다. 완료·사진·지급완료·보류 이력이 있는 회차는 기존
                조건을 보존하고, 변경 가능한 이번 달 이후 회차부터 새 조건을 적용합니다. 적용 월의 월
                정산 자체가 지급완료된 경우에만 지급완료를 되돌린 뒤 변경해 주세요.
              </div>
            )}
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
                {form.default_partner_id
                  && !partners.some((partner) => partner.id === form.default_partner_id) && (
                    <option value={form.default_partner_id} disabled>
                      보관된 협력사 (기존 배정)
                    </option>
                  )}
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

function errorMessage(error: unknown): string {
  if (!(error instanceof Error)) {
    return '저장에 실패했습니다.';
  }
  if (error.message === 'recurring_partner_billing_change_paid') {
    return '적용 월의 월 정산이 이미 지급완료되었습니다. 지급완료를 되돌린 뒤 다시 변경하세요.';
  }
  if (error.message === 'recurring_partner_billing_change_unscheduled') {
    return '방문일이 정해지지 않은 기존 회차가 있어 적용 월을 판단할 수 없습니다. 해당 회차의 방문일을 지정한 뒤 다시 변경하세요.';
  }
  if (error.message === 'recurring_start_date_locked') {
    return '이미 생성된 회차 또는 정산 이력이 있어 시작일을 변경할 수 없습니다. 기존 이력을 유지하고 일정만 조정하세요.';
  }
  if (error.message === 'recurring_contract_end_date_passed') {
    return '종료일이 이미 지난 계약은 재개할 수 없습니다. 종료일을 오늘 이후로 변경한 뒤 다시 시도하세요.';
  }
  if (error.message === 'recurring_partner_changed_concurrently') {
    return '다른 작업에서 협력사 또는 정산 조건이 변경되었습니다. 최신 정보를 다시 불러온 뒤 시도하세요.';
  }
  if (error.message === 'partner_not_found') {
    return '선택한 협력사가 삭제되었습니다. 사용 가능한 협력사를 다시 선택하세요.';
  }
  if (error.message === 'partner_inactive') {
    return '선택한 협력사가 비활성 상태입니다. 활성 협력사를 선택하세요.';
  }
  return error.message;
}
