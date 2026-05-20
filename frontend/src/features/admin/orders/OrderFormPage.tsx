import React from 'react';

import {
  createOrderGroup,
  getAdminOrder,
  listPartners,
  listServiceCatalog,
  updateAdminOrder,
  updateAdminOrderGroup,
} from '../../../api/admin';
import { useApiResource } from '../../../api/useApiResource';
import { AddressInput } from '../../../components/AddressInput';
import { DatePicker } from '../../../components/common/DatePicker';
import { Icon } from '../../../components/common/ui';
import { ORDER_STATUSES } from '../../../domain/orderStatus';
import { PARTNER_PAYMENT_STATUSES, PAYMENT_STATUSES } from '../../../domain/paymentStatus';
import { getAppTodayValue } from '../../../domain/time';

export function OrderFormPage({ mode = 'create', orderId = null, onCancel, onSaved }) {
  const partners = useApiResource(listPartners);
  const serviceCatalog = useApiResource(listServiceCatalog);
  const [form, setForm] = React.useState(() => createEmptyGroupForm());
  const [isLoadingOrder, setIsLoadingOrder] = React.useState(mode === 'edit');
  const [isSaving, setIsSaving] = React.useState(false);
  const [error, setError] = React.useState(null);
  const activeServiceCategories = React.useMemo(
    () => (serviceCatalog.data || []).filter((category) => category.is_active),
    [serviceCatalog.data],
  );

  React.useEffect(() => {
    let isCurrent = true;

    if (mode !== 'edit' || !orderId) {
      setForm(createEmptyGroupForm());
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

  const setGroupField = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const setLineField = (lineIndex, key, value) => {
    setForm((current) => {
      const nextLines = current.lines.slice();
      nextLines[lineIndex] = { ...nextLines[lineIndex], [key]: value };
      return { ...current, lines: nextLines };
    });
  };

  const addLine = () => {
    setForm((current) => ({ ...current, lines: [...current.lines, createEmptyLineForm()] }));
  };

  const removeLine = (lineIndex) => {
    setForm((current) => {
      if (current.lines.length <= 1) {
        return current;
      }
      return { ...current, lines: current.lines.filter((_, index) => index !== lineIndex) };
    });
  };

  const handleMoneyChange = (lineIndex, key, value) => {
    const formattedValue = formatMoneyInput(value);
    setForm((current) => {
      const nextLines = current.lines.slice();
      const nextLine = { ...nextLines[lineIndex], [key]: formattedValue };

      if (key === 'total_amount' || key === 'deposit_amount') {
        nextLine.balance_amount = calculateBalanceAmount(nextLine.total_amount, nextLine.deposit_amount);
      }

      nextLines[lineIndex] = nextLine;
      return { ...current, lines: nextLines };
    });
  };

  const handlePartnerChange = (lineIndex, partnerId) => {
    const partner = (partners.data || []).find((item) => item.id === partnerId);
    setForm((current) => {
      const nextLines = current.lines.slice();
      nextLines[lineIndex] = {
        ...nextLines[lineIndex],
        partner_id: partnerId,
        team_name: partner?.name || '',
      };
      return { ...current, lines: nextLines };
    });
  };

  const handleServiceCategoryChange = (lineIndex, categoryId) => {
    setForm((current) => {
      const nextLines = current.lines.slice();
      nextLines[lineIndex] = {
        ...nextLines[lineIndex],
        service_category_id: categoryId,
        service_item_id: '',
      };
      return { ...current, lines: nextLines };
    });
  };

  const handleServiceItemChange = (lineIndex, serviceItemId) => {
    const line = form.lines[lineIndex];
    const option = getServiceItems(activeServiceCategories, line.service_category_id)
      .find((item) => item.id === serviceItemId);
    setForm((current) => {
      const nextLines = current.lines.slice();
      const currentLine = nextLines[lineIndex];
      const totalAmount = option && currentLine.total_amount === ''
        ? formatMoneyInput(Math.round(Number(option.base_price || 0)))
        : currentLine.total_amount;
      const nextLine = {
        ...currentLine,
        service_item_id: serviceItemId,
        service_name: option?.name || currentLine.service_name,
        total_amount: totalAmount,
      };
      nextLine.balance_amount = calculateBalanceAmount(nextLine.total_amount, nextLine.deposit_amount);
      nextLines[lineIndex] = nextLine;
      return { ...current, lines: nextLines };
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);

    if (!form.customer_name.trim() || !form.customer_phone.trim() || !form.customer_address.trim()) {
      setError('고객명, 연락처, 주소는 필수입니다.');
      return;
    }
    if (form.lines.some((line) => !line.service_name.trim())) {
      setError('모든 라인의 상품명은 필수입니다.');
      return;
    }

    setIsSaving(true);
    try {
      if (mode === 'edit' && orderId) {
        await updateAdminOrderGroup(form.group_id, toGroupMetadataPayload(form));
        const saved = await updateAdminOrder(orderId, toLinePayload(form.lines[0]));
        onSaved?.(saved);
      } else {
        const savedGroup = await createOrderGroup(toGroupCreatePayload(form));
        onSaved?.(savedGroup.lines?.[0] || savedGroup);
      }
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
    <form data-testid="admin-order-form" onSubmit={handleSubmit} style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}>
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
        <button type="submit" data-testid="order-save" className="btn btn--primary btn--sm" disabled={isSaving}>
          <Icon name="check" size={13}/> {isSaving ? '저장 중' : '저장'}
        </button>
      </div>

      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16, maxWidth: 1260, margin: '0 auto' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Section title="고객 정보">
              <FieldGrid>
                <TextField testId="order-customer-name" label="고객명" required value={form.customer_name} onChange={(value) => setGroupField('customer_name', value)} />
                <TextField testId="order-customer-phone" label="연락처" required value={form.customer_phone} onChange={(value) => setGroupField('customer_phone', value)} placeholder="010-0000-0000" />
                <TextField label="유입 경로" value={form.source_channel} onChange={(value) => setGroupField('source_channel', value)} />
                <div style={{ gridColumn: 'span 2' }}>
                  <AddressInput
                    baseAddress={form.customer_address}
                    detailAddress={form.customer_address_detail}
                    required
                    onChange={({ baseAddress, detailAddress }) => {
                      setGroupField('customer_address', baseAddress);
                      setGroupField('customer_address_detail', detailAddress);
                    }}
                  />
                </div>
              </FieldGrid>
            </Section>

            <Section
              title="상품 / 일정"
              action={mode === 'create' ? (
                <button type="button" data-testid="order-add-line" className="btn btn--ghost btn--sm" onClick={addLine}>
                  <Icon name="plus" size={12}/> 라인 추가
                </button>
              ) : null}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {form.lines.map((line, lineIndex) => (
                  <LineEditor
                    key={line.local_id}
                    line={line}
                    lineIndex={lineIndex}
                    canRemove={mode === 'create' && form.lines.length > 1}
                    activeServiceCategories={activeServiceCategories}
                    partners={partners.data || []}
                    onFieldChange={setLineField}
                    onMoneyChange={handleMoneyChange}
                    onPartnerChange={handlePartnerChange}
                    onServiceCategoryChange={handleServiceCategoryChange}
                    onServiceItemChange={handleServiceItemChange}
                    onRemove={removeLine}
                  />
                ))}
              </div>
            </Section>
          </div>

          <aside style={{ display: 'flex', flexDirection: 'column', gap: 12, position: 'sticky', top: 0, alignSelf: 'flex-start' }}>
            <div className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: 0, marginBottom: 8 }}>그룹 설정</div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                <input
                  type="checkbox"
                  checked={form.customer_visible_payment}
                  onChange={(event) => setGroupField('customer_visible_payment', event.target.checked)}
                />
                고객 페이지에 결제 금액 노출
              </label>
              <TextField testId="order-group-notes" label="그룹 메모" span={1} multiline value={form.notes} onChange={(value) => setGroupField('notes', value)} />
            </div>

            {error && (
              <div style={{ padding: 10, borderRadius: 6, background: 'var(--danger-bg)', color: 'var(--danger-fg)', fontSize: 12 }}>
                {error}
              </div>
            )}

            <div className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: 0, marginBottom: 8 }}>저장 시 처리</div>
              <div style={{ fontSize: 12, lineHeight: 1.55, color: 'var(--text-secondary)' }}>
                신규 주문 저장 시 고객 확인 링크가 생성됩니다. 상태와 협력사 변경은 타임라인에 함께 기록됩니다.
              </div>
            </div>
          </aside>
        </div>
      </div>
    </form>
  );
}

function LineEditor({
  line,
  lineIndex,
  canRemove,
  activeServiceCategories,
  partners,
  onFieldChange,
  onMoneyChange,
  onPartnerChange,
  onServiceCategoryChange,
  onServiceItemChange,
  onRemove,
}) {
  const serviceItems = getServiceItems(activeServiceCategories, line.service_category_id);

  return (
    <div style={{ border: '1px solid var(--divider)', borderRadius: 8, background: 'var(--surface-subtle)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 12px', borderBottom: '1px solid var(--divider)' }}>
        <div style={{ fontSize: 12, fontWeight: 700 }}>라인 {lineIndex + 1}</div>
        <div style={{ flex: 1 }}/>
        {canRemove && (
          <button
            type="button"
            data-testid={`order-remove-line-${lineIndex}`}
            className="btn btn--ghost btn--sm"
            onClick={() => onRemove(lineIndex)}
          >
            <Icon name="x" size={12}/> 삭제
          </button>
        )}
      </div>

      <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <FieldGrid>
          <Field label="주문 상태">
            <select className="input" value={line.status} onChange={(event) => onFieldChange(lineIndex, 'status', event.target.value)}>
              {ORDER_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
          </Field>
          <Field label="협력사">
            <select className="input" data-testid={`order-line-${lineIndex}-partner`} value={line.partner_id} onChange={(event) => onPartnerChange(lineIndex, event.target.value)}>
              <option value="">미배정</option>
              {partners.map((partner) => (
                <option key={partner.id} value={partner.id}>{partner.name}</option>
              ))}
            </select>
          </Field>
          <Field label="카테고리">
            <select
              className="input"
              data-testid={`order-line-${lineIndex}-service-category`}
              value={line.service_category_id}
              onChange={(event) => onServiceCategoryChange(lineIndex, event.target.value)}
            >
              <option value="">직접 입력</option>
              {activeServiceCategories.map((category) => (
                <option key={category.id} value={category.id}>{category.name}</option>
              ))}
            </select>
          </Field>
          <Field label="상세상품">
            <select
              className="input"
              data-testid={`order-line-${lineIndex}-service-item`}
              value={line.service_item_id}
              onChange={(event) => onServiceItemChange(lineIndex, event.target.value)}
              disabled={!line.service_category_id}
            >
              <option value="">직접 입력</option>
              {serviceItems.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {formatWon(item.base_price)}
                </option>
              ))}
            </select>
          </Field>
          <TextField testId={`order-line-${lineIndex}-service-name`} label="상품명" required value={line.service_name} onChange={(value) => onFieldChange(lineIndex, 'service_name', value)} />
          <TextField label="수량/규격" value={line.size_or_quantity} onChange={(value) => onFieldChange(lineIndex, 'size_or_quantity', value)} />
          <Field label="접수일">
            <DatePicker testId={`order-line-${lineIndex}-received-date`} value={line.received_date} onChange={(value) => onFieldChange(lineIndex, 'received_date', value)} />
          </Field>
          <Field label="방문 예정일">
            <DatePicker testId={`order-line-${lineIndex}-scheduled-date`} value={line.scheduled_date} onChange={(value) => onFieldChange(lineIndex, 'scheduled_date', value)} placeholder="방문일 선택" />
          </Field>
          <TextField testId={`order-line-${lineIndex}-requested-time`} label="요청 시간" value={line.requested_time} onChange={(value) => onFieldChange(lineIndex, 'requested_time', value)} placeholder="14:00 또는 오후 2-5시" />
          <TextField label="팀명" value={line.team_name} onChange={(value) => onFieldChange(lineIndex, 'team_name', value)} />
          <TextField label="상품 상세" span={2} multiline value={line.service_detail} onChange={(value) => onFieldChange(lineIndex, 'service_detail', value)} />
          <TextField label="요청사항" span={2} multiline value={line.special_request} onChange={(value) => onFieldChange(lineIndex, 'special_request', value)} />
        </FieldGrid>

        <FieldGrid>
          <TextField testId={`order-line-${lineIndex}-total-amount`} label="총 금액" inputMode="numeric" value={line.total_amount} onChange={(value) => onMoneyChange(lineIndex, 'total_amount', value)} />
          <TextField label="계약금" inputMode="numeric" value={line.deposit_amount} onChange={(value) => onMoneyChange(lineIndex, 'deposit_amount', value)} />
          <TextField label="잔금" inputMode="numeric" value={line.balance_amount} onChange={(value) => onMoneyChange(lineIndex, 'balance_amount', value)} />
          <TextField label="현장 추가" inputMode="numeric" value={line.onsite_extra_amount} onChange={(value) => onMoneyChange(lineIndex, 'onsite_extra_amount', value)} />
          <Field label="결제 상태">
            <select className="input" value={line.payment_status} onChange={(event) => onFieldChange(lineIndex, 'payment_status', event.target.value)}>
              <option value="">미입력</option>
              {PAYMENT_STATUSES.map((status) => (
                <option key={status.value} value={status.value}>{status.label}</option>
              ))}
            </select>
          </Field>
          <TextField label="VAT" value={line.vat_type} onChange={(value) => onFieldChange(lineIndex, 'vat_type', value)} />
          <TextField label="결제 메모" span={2} multiline value={line.payment_memo} onChange={(value) => onFieldChange(lineIndex, 'payment_memo', value)} />
          <TextField label="증빙 메모" span={2} multiline value={line.evidence_memo} onChange={(value) => onFieldChange(lineIndex, 'evidence_memo', value)} />
          <TextField label="협력사 지급액" inputMode="numeric" value={line.partner_payment_amount} onChange={(value) => onMoneyChange(lineIndex, 'partner_payment_amount', value)} />
          <Field label="협력사 정산 상태">
            <select className="input" value={line.partner_payment_status} onChange={(event) => onFieldChange(lineIndex, 'partner_payment_status', event.target.value)}>
              <option value="">미입력</option>
              {PARTNER_PAYMENT_STATUSES.map((status) => (
                <option key={status.value} value={status.value}>{status.label}</option>
              ))}
            </select>
          </Field>
        </FieldGrid>
      </div>
    </div>
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

function Section({ title, action = null, children }) {
  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--divider)', fontSize: 12.5, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>{title}</span>
        <div style={{ flex: 1 }}/>
        {action}
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

function TextField({ label, value, onChange, type = 'text', inputMode = undefined, required = false, span = 1, multiline = false, placeholder = '', testId = undefined }) {
  return (
    <Field label={`${label}${required ? ' *' : ''}`} span={span}>
      {multiline ? (
        <textarea
          className="input"
          data-testid={testId}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          style={{ minHeight: 70, resize: 'vertical', lineHeight: 1.45 }}
        />
      ) : (
        <input
          className="input"
          data-testid={testId}
          type={type}
          inputMode={inputMode}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </Field>
  );
}

function createEmptyGroupForm() {
  return {
    group_id: '',
    customer_name: '',
    customer_phone: '',
    customer_address: '',
    customer_address_detail: '',
    source_channel: '',
    customer_visible_payment: false,
    notes: '',
    lines: [createEmptyLineForm()],
  };
}

function createEmptyLineForm() {
  return {
    local_id: crypto.randomUUID(),
    status: ORDER_STATUSES[0],
    received_date: todayString(),
    scheduled_date: '',
    requested_time: '',
    partner_id: '',
    team_name: '',
    service_category_id: '',
    service_item_id: '',
    service_name: '',
    size_or_quantity: '',
    service_detail: '',
    special_request: '',
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
  };
}

function toForm(order) {
  return {
    group_id: order.group_id || '',
    customer_name: order.customer_name || '',
    customer_phone: order.customer_phone || '',
    customer_address: order.customer_address || '',
    customer_address_detail: order.customer_address_detail || '',
    source_channel: order.source_channel || '',
    customer_visible_payment: Boolean(order.customer_visible_payment),
    notes: order.group_notes ?? order.notes ?? '',
    lines: [toLineForm(order)],
  };
}

function toLineForm(order) {
  return {
    ...createEmptyLineForm(),
    status: order.status || ORDER_STATUSES[0],
    received_date: order.received_date || todayString(),
    scheduled_date: order.scheduled_date || '',
    requested_time: order.requested_time || '',
    partner_id: order.partner_id || '',
    team_name: order.team_name || '',
    service_category_id: order.service_category_id || '',
    service_item_id: order.service_item_id || '',
    service_name: order.service_name || '',
    size_or_quantity: order.size_or_quantity || '',
    service_detail: order.service_detail || '',
    special_request: order.special_request || '',
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
  };
}

function toGroupCreatePayload(form) {
  return {
    ...toGroupMetadataPayload(form),
    lines: form.lines.map(toLinePayload),
  };
}

function toGroupMetadataPayload(form) {
  return {
    customer_name: form.customer_name.trim(),
    customer_phone: form.customer_phone.trim(),
    customer_address: form.customer_address.trim(),
    customer_address_detail: emptyToNull(form.customer_address_detail.trim()),
    source_channel: emptyToNull(form.source_channel),
    customer_visible_payment: form.customer_visible_payment,
    notes: emptyToNull(form.notes),
  };
}

function toLinePayload(line) {
  return {
    status: line.status,
    received_date: line.received_date,
    scheduled_date: emptyToNull(line.scheduled_date),
    requested_time: emptyToNull(line.requested_time),
    partner_id: emptyToNull(line.partner_id),
    team_name: emptyToNull(line.team_name),
    service_category_id: emptyToNull(line.service_category_id),
    service_item_id: emptyToNull(line.service_item_id),
    service_name: line.service_name.trim(),
    size_or_quantity: emptyToNull(line.size_or_quantity),
    service_detail: emptyToNull(line.service_detail),
    special_request: emptyToNull(line.special_request),
    total_amount: numberOrNull(line.total_amount),
    deposit_amount: numberOrNull(line.deposit_amount),
    balance_amount: numberOrNull(line.balance_amount),
    onsite_extra_amount: numberOrNull(line.onsite_extra_amount),
    vat_type: emptyToNull(line.vat_type),
    payment_status: emptyToNull(line.payment_status),
    payment_memo: emptyToNull(line.payment_memo),
    evidence_memo: emptyToNull(line.evidence_memo),
    partner_payment_amount: numberOrNull(line.partner_payment_amount),
    partner_payment_status: emptyToNull(line.partner_payment_status),
  };
}

function getServiceItems(categories, categoryId) {
  return categories
    .filter((category) => category.id === categoryId)
    .flatMap((category) => (category.items || []).filter((item) => item.is_active));
}

function todayString() {
  return getAppTodayValue();
}

function emptyToNull(value) {
  return value === '' ? null : value;
}

function numberOrNull(value) {
  return parseMoneyInput(value);
}

function toInputNumber(value) {
  if (value === null || value === undefined) {
    return '';
  }

  return formatMoneyInput(Math.round(Number(value)));
}

function formatMoneyInput(value) {
  const digits = String(value ?? '').replace(/[^\d]/g, '');
  if (digits === '') {
    return '';
  }

  return Number(digits).toLocaleString();
}

function parseMoneyInput(value) {
  const digits = String(value ?? '').replace(/[^\d]/g, '');
  if (digits === '') {
    return null;
  }

  return Number(digits);
}

function calculateBalanceAmount(totalAmount, depositAmount) {
  const total = parseMoneyInput(totalAmount);
  const deposit = parseMoneyInput(depositAmount);

  if (total === null || deposit === null) {
    return '';
  }

  return formatMoneyInput(Math.max(total - deposit, 0));
}

function formatWon(value) {
  const amount = Number(value || 0);
  return `₩${Math.round(amount).toLocaleString()}`;
}
