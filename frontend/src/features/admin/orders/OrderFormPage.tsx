import React from 'react';

import { createAdminOrder, getAdminOrder, listPartners, updateAdminOrder } from '../../../api/admin';
import { Icon } from '../../../components/common/ui';
import { ORDER_STATUSES } from '../../../domain/orderStatus';
import { useApiResource } from '../../../api/useApiResource';

export function OrderFormPage({ mode = 'create', orderId = null, onCancel, onSaved }) {
  const partners = useApiResource(listPartners);
  const [form, setForm] = React.useState(() => createEmptyForm());
  const [isLoadingOrder, setIsLoadingOrder] = React.useState(mode === 'edit');
  const [isSaving, setIsSaving] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    let isCurrent = true;

    if (mode !== 'edit' || !orderId) {
      setForm(createEmptyForm());
      setIsLoadingOrder(false);
      return () => {
        isCurrent = false;
      };
    }

    setIsLoadingOrder(true);
    getAdminOrder(orderId)
      .then((order) => {
        if (isCurrent) {
          setForm(toForm(order));
        }
      })
      .catch(() => {
        if (isCurrent) {
          setError('주문 정보를 불러오지 못했습니다.');
        }
      })
      .finally(() => {
        if (isCurrent) {
          setIsLoadingOrder(false);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [mode, orderId]);

  const setField = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const handlePartnerChange = (partnerId) => {
    const partner = (partners.data || []).find((item) => item.id === partnerId);
    setForm((current) => ({
      ...current,
      partner_id: partnerId,
      team_name: partner?.name || '',
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);

    if (!form.customer_name.trim() || !form.customer_phone.trim() || !form.customer_address.trim() || !form.service_name.trim()) {
      setError('고객명, 연락처, 주소, 상품명은 필수입니다.');
      return;
    }

    setIsSaving(true);
    try {
      const payload = toPayload(form);
      const saved = mode === 'edit' && orderId
        ? await updateAdminOrder(orderId, payload)
        : await createAdminOrder(payload);
      onSaved?.(saved);
    } catch (requestError) {
      setError(requestError?.message || '주문을 저장하지 못했습니다.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoadingOrder) {
    return <FormState text="주문 입력 정보를 불러오는 중입니다." onCancel={onCancel} />;
  }

  return (
    <form onSubmit={handleSubmit} style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}>
      <div style={{
        padding: '10px 20px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
      }}>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onCancel}>
          <Icon name="chevronLeft" size={13}/> 취소
        </button>
        <span style={{ width: 1, height: 16, background: 'var(--border)' }}/>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
          {mode === 'edit' ? '주문 수정' : '신규 주문 등록'}
        </h2>
        <div style={{ flex: 1 }}/>
        <button type="submit" className="btn btn--primary btn--sm" disabled={isSaving}>
          <Icon name="check" size={13}/> {isSaving ? '저장 중' : '저장'}
        </button>
      </div>

      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16, maxWidth: 1260, margin: '0 auto' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Section title="고객 정보">
              <FieldGrid>
                <TextField label="고객명" required value={form.customer_name} onChange={(value) => setField('customer_name', value)} />
                <TextField label="연락처" required value={form.customer_phone} onChange={(value) => setField('customer_phone', value)} placeholder="010-0000-0000" />
                <TextField label="유입 경로" value={form.source_channel} onChange={(value) => setField('source_channel', value)} />
                <TextField label="주소" required span={2} value={form.customer_address} onChange={(value) => setField('customer_address', value)} />
              </FieldGrid>
            </Section>

            <Section title="상품 / 일정">
              <FieldGrid>
                <TextField label="상품명" required value={form.service_name} onChange={(value) => setField('service_name', value)} />
                <TextField label="수량/규격" value={form.size_or_quantity} onChange={(value) => setField('size_or_quantity', value)} />
                <TextField label="접수일" type="date" value={form.received_date} onChange={(value) => setField('received_date', value)} />
                <TextField label="방문 예정일" type="date" value={form.scheduled_date} onChange={(value) => setField('scheduled_date', value)} />
                <TextField label="요청 시간" value={form.requested_time} onChange={(value) => setField('requested_time', value)} placeholder="14:00 또는 오후 2-5시" />
                <TextField label="상품 상세" span={2} multiline value={form.service_detail} onChange={(value) => setField('service_detail', value)} />
                <TextField label="요청사항" span={2} multiline value={form.special_request} onChange={(value) => setField('special_request', value)} />
              </FieldGrid>
            </Section>

            <Section title="금액 / 결제">
              <FieldGrid>
                <TextField label="총 금액" type="number" value={form.total_amount} onChange={(value) => setField('total_amount', value)} />
                <TextField label="계약금" type="number" value={form.deposit_amount} onChange={(value) => setField('deposit_amount', value)} />
                <TextField label="잔금" type="number" value={form.balance_amount} onChange={(value) => setField('balance_amount', value)} />
                <TextField label="현장 추가" type="number" value={form.onsite_extra_amount} onChange={(value) => setField('onsite_extra_amount', value)} />
                <TextField label="결제 상태" value={form.payment_status} onChange={(value) => setField('payment_status', value)} />
                <TextField label="VAT" value={form.vat_type} onChange={(value) => setField('vat_type', value)} />
                <TextField label="결제 메모" span={2} multiline value={form.payment_memo} onChange={(value) => setField('payment_memo', value)} />
                <TextField label="증빙 메모" span={2} multiline value={form.evidence_memo} onChange={(value) => setField('evidence_memo', value)} />
              </FieldGrid>
            </Section>

            <Section title="협력사 / 정산">
              <FieldGrid>
                <Field label="협력사">
                  <select className="input" value={form.partner_id} onChange={(event) => handlePartnerChange(event.target.value)}>
                    <option value="">미배정</option>
                    {(partners.data || []).map((partner) => (
                      <option key={partner.id} value={partner.id}>{partner.name}</option>
                    ))}
                  </select>
                </Field>
                <TextField label="팀명" value={form.team_name} onChange={(value) => setField('team_name', value)} />
                <TextField label="협력사 지급액" type="number" value={form.partner_payment_amount} onChange={(value) => setField('partner_payment_amount', value)} />
                <TextField label="협력사 정산 상태" value={form.partner_payment_status} onChange={(value) => setField('partner_payment_status', value)} />
              </FieldGrid>
            </Section>
          </div>

          <aside style={{ display: 'flex', flexDirection: 'column', gap: 12, position: 'sticky', top: 0, alignSelf: 'flex-start' }}>
            <div className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 8 }}>운영 상태</div>
              <Field label="주문 상태">
                <select className="input" value={form.status} onChange={(event) => setField('status', event.target.value)}>
                  {ORDER_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
                </select>
              </Field>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
                <input
                  type="checkbox"
                  checked={form.customer_visible_payment}
                  onChange={(event) => setField('customer_visible_payment', event.target.checked)}
                />
                고객 페이지에 결제 금액 노출
              </label>
            </div>

            {error && (
              <div style={{ padding: 10, borderRadius: 6, background: 'var(--danger-bg)', color: 'var(--danger-fg)', fontSize: 12 }}>
                {error}
              </div>
            )}

            <div className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 8 }}>저장 시 처리</div>
              <div style={{ fontSize: 12, lineHeight: 1.55, color: 'var(--text-secondary)' }}>
                신규 주문은 고객 토큰이 생성되고 `created` 타임라인이 남습니다. 상태와 협력사 변경은 각각 타임라인에 기록됩니다.
              </div>
            </div>
          </aside>
        </div>
      </div>
    </form>
  );
}

function FormState({ text, onCancel }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
      <div style={{ padding: '10px 20px', background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onCancel}>
          <Icon name="chevronLeft" size={13}/> 취소
        </button>
      </div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
        {text}
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', fontSize: 12.5, fontWeight: 600 }}>
        {title}
      </div>
      <div style={{ padding: 14 }}>{children}</div>
    </div>
  );
}

function FieldGrid({ children }) {
  return <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '12px 14px' }}>{children}</div>;
}

function Field({ label, children, span = 1 }) {
  return (
    <label style={{ gridColumn: span ? `span ${span}` : 'auto', display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>{label}</span>
      {children}
    </label>
  );
}

function TextField({ label, value, onChange, type = 'text', required = false, span = 1, multiline = false, placeholder = '' }) {
  return (
    <Field label={`${label}${required ? ' *' : ''}`} span={span}>
      {multiline ? (
        <textarea
          className="input"
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          style={{ minHeight: 70, resize: 'vertical', lineHeight: 1.45 }}
        />
      ) : (
        <input
          className="input"
          type={type}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </Field>
  );
}

function createEmptyForm() {
  return {
    status: ORDER_STATUSES[0],
    received_date: todayString(),
    scheduled_date: '',
    requested_time: '',
    partner_id: '',
    team_name: '',
    service_name: '',
    size_or_quantity: '',
    service_detail: '',
    special_request: '',
    source_channel: '',
    customer_name: '',
    customer_phone: '',
    customer_address: '',
    total_amount: '',
    deposit_amount: '',
    balance_amount: '',
    onsite_extra_amount: '',
    vat_type: '',
    payment_status: '',
    payment_memo: '',
    evidence_memo: '',
    partner_payment_amount: '',
    partner_payment_status: '',
    customer_visible_payment: false,
  };
}

function toForm(order) {
  return {
    status: order.status || ORDER_STATUSES[0],
    received_date: order.received_date || todayString(),
    scheduled_date: order.scheduled_date || '',
    requested_time: order.requested_time || '',
    partner_id: order.partner_id || '',
    team_name: order.team_name || '',
    service_name: order.service_name || '',
    size_or_quantity: order.size_or_quantity || '',
    service_detail: order.service_detail || '',
    special_request: order.special_request || '',
    source_channel: order.source_channel || '',
    customer_name: order.customer_name || '',
    customer_phone: order.customer_phone || '',
    customer_address: order.customer_address || '',
    total_amount: toInputNumber(order.total_amount),
    deposit_amount: toInputNumber(order.deposit_amount),
    balance_amount: toInputNumber(order.balance_amount),
    onsite_extra_amount: toInputNumber(order.onsite_extra_amount),
    vat_type: order.vat_type || '',
    payment_status: order.payment_status || '',
    payment_memo: order.payment_memo || '',
    evidence_memo: order.evidence_memo || '',
    partner_payment_amount: toInputNumber(order.partner_payment_amount),
    partner_payment_status: order.partner_payment_status || '',
    customer_visible_payment: Boolean(order.customer_visible_payment),
  };
}

function toPayload(form) {
  return {
    status: form.status,
    received_date: form.received_date,
    scheduled_date: emptyToNull(form.scheduled_date),
    requested_time: emptyToNull(form.requested_time),
    partner_id: emptyToNull(form.partner_id),
    team_name: emptyToNull(form.team_name),
    service_name: form.service_name.trim(),
    size_or_quantity: emptyToNull(form.size_or_quantity),
    service_detail: emptyToNull(form.service_detail),
    special_request: emptyToNull(form.special_request),
    source_channel: emptyToNull(form.source_channel),
    customer_name: form.customer_name.trim(),
    customer_phone: form.customer_phone.trim(),
    customer_address: form.customer_address.trim(),
    total_amount: numberOrNull(form.total_amount),
    deposit_amount: numberOrNull(form.deposit_amount),
    balance_amount: numberOrNull(form.balance_amount),
    onsite_extra_amount: numberOrNull(form.onsite_extra_amount),
    vat_type: emptyToNull(form.vat_type),
    payment_status: emptyToNull(form.payment_status),
    payment_memo: emptyToNull(form.payment_memo),
    evidence_memo: emptyToNull(form.evidence_memo),
    partner_payment_amount: numberOrNull(form.partner_payment_amount),
    partner_payment_status: emptyToNull(form.partner_payment_status),
    customer_visible_payment: form.customer_visible_payment,
  };
}

function todayString() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function emptyToNull(value) {
  return value === '' ? null : value;
}

function numberOrNull(value) {
  return value === '' ? null : Number(value);
}

function toInputNumber(value) {
  return value === null || value === undefined ? '' : String(value);
}
