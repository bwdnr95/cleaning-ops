import React from 'react';

import {
  createOrderGroup,
  getAdminOrder,
  listBrokers,
  listPartners,
  listServiceCatalog,
  sendOrderAsRequest,
  updateAdminOrder,
  updateAdminOrderGroup,
} from '../../../api/admin';
import { useApiResource } from '../../../api/useApiResource';
import { AddressInput } from '../../../components/AddressInput';
import { DatePicker } from '../../../components/common/DatePicker';
import { Icon } from '../../../components/common/ui';
import { ORDER_STATUS_OPTIONS, ORDER_STATUSES, orderWorkflowStatusValue } from '../../../domain/orderStatus';
import { PARTNER_PAYMENT_STATUSES, PAYMENT_STATUSES } from '../../../domain/paymentStatus';
import { getAppTodayValue } from '../../../domain/time';
import { SourceChannelSelect } from './SourceChannelSelect';
import { useOrderFormDraft } from './useOrderFormDraft';

export function OrderFormPage({ mode = 'create', orderId = null, duplicateFromOrderId = null, onCancel, onSaved }) {
  // 복제: create 저장 경로를 그대로 쓰되, 기존 주문의 고객정보만 복사한다(서비스/일정/협력사는 공란).
  const isDuplicate = mode === 'create' && Boolean(duplicateFromOrderId);
  const partners = useApiResource(listPartners);
  const brokers = useApiResource(listBrokers);
  const serviceCatalog = useApiResource(listServiceCatalog);
  const [form, setForm] = React.useState(() => createEmptyGroupForm());
  const [isLoadingOrder, setIsLoadingOrder] = React.useState(mode === 'edit' || isDuplicate);
  const [isSaving, setIsSaving] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [notice, setNotice] = React.useState('');
  // AS(사후관리) 요청: 저장 페이로드가 아니라 별도 전송 액션(편집 모드 전용).
  const [asOpen, setAsOpen] = React.useState(false);
  const [asMemo, setAsMemo] = React.useState('');
  const [asRequested, setAsRequested] = React.useState(false);
  const [asBusy, setAsBusy] = React.useState(false);
  const draft = useOrderFormDraft(form, { enabled: mode === 'create' && !isDuplicate });
  const activeServiceCategories = React.useMemo(
    () => (serviceCatalog.data || []).filter((category) => category.is_active),
    [serviceCatalog.data],
  );

  React.useEffect(() => {
    let isCurrent = true;

    const loadId = mode === 'edit' ? orderId : (isDuplicate ? duplicateFromOrderId : null);
    if (!loadId) {
      setForm(createEmptyGroupForm());
      setIsLoadingOrder(false);
      return () => {
        isCurrent = false;
      };
    }

    setIsLoadingOrder(true);
    getAdminOrder(loadId)
      .then((order) => {
        if (isCurrent) {
          setForm(isDuplicate ? toDuplicateForm(order) : toForm(order));
          if (!isDuplicate) {
            setAsRequested(Boolean(order.as_requested));
            setAsMemo(order.as_memo || '');
            setAsOpen(Boolean(order.as_requested));
          }
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
  }, [mode, orderId, isDuplicate, duplicateFromOrderId]);

  React.useEffect(() => {
    if (mode !== 'create' || isDuplicate) return;
    const restored = draft.loadDraft();
    if (!restored) return;
    if (form.customer_name === '' && form.customer_phone === '' && form.lines.every((line) => !line.scheduled_date)) {
      if (window.confirm('이전 작성 중이던 신규 주문 임시 저장 데이터가 있습니다. 불러올까요?')) {
        setForm(restored);
      } else {
        draft.clearDraft();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const handleCancel = React.useCallback(() => {
    draft.clearDraft();
    onCancel?.();
  }, [draft, onCancel]);

  const setGroupField = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const setLineField = (lineIndex, key, value) => {
    setForm((current) => {
      const nextLines = current.lines.slice();
      let nextLine = { ...nextLines[lineIndex], [key]: value };
      if (key === 'size_or_quantity') {
        nextLine = recalculateLine(nextLine, { source: 'quantity' });
      }
      nextLines[lineIndex] = nextLine;
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
      const previousLine = nextLines[lineIndex];
      let nextLine = { ...previousLine, [key]: formattedValue };
      nextLine = applyMoneyTouch(nextLine, key, formattedValue);
      nextLine = recalculateLine(nextLine, { source: key });

      nextLines[lineIndex] = nextLine;
      return { ...current, lines: nextLines };
    });
  };

  const handlePartnerChange = (lineIndex, partnerId) => {
    const partner = (partners.data || []).find((item) => item.id === partnerId);
    setForm((current) => {
      const nextLines = current.lines.slice();
      nextLines[lineIndex] = {
        ...recalculateLine(nextLines[lineIndex], { source: 'partner' }),
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
        base_unit_price: '',
        partner_unit_price: '',
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
      const nextLine = recalculateLine({
        ...currentLine,
        service_item_id: serviceItemId,
        service_name: option?.name || currentLine.service_name,
        base_unit_price: option ? String(option.base_price || 0) : '',
        partner_unit_price: option ? String(option.partner_base_price || 0) : '',
      }, { source: 'service_item' });
      nextLines[lineIndex] = nextLine;
      return { ...current, lines: nextLines };
    });
  };

  const saveForm = async () => {
    setError(null);
    setNotice('');

    if (!form.customer_name.trim() || !form.customer_phone.trim() || !form.customer_address.trim()) {
      setError('고객명, 연락처, 주소는 필수입니다.');
      return null;
    }
    if (form.lines.some((line) => !line.service_name.trim())) {
      setError('모든 라인의 상품명은 필수입니다.');
      return null;
    }

    setIsSaving(true);
    try {
      if (mode === 'edit' && orderId) {
        await updateAdminOrderGroup(form.group_id, toGroupMetadataPayload(form));
        const saved = await updateAdminOrder(orderId, toLinePayload(form.lines[0]));
        draft.clearDraft();
        return saved;
      } else {
        const savedGroup = await createOrderGroup(toGroupCreatePayload(form));
        draft.clearDraft();
        return savedGroup.lines?.[0] || savedGroup;
      }
    } catch (requestError) {
      setError(requestError?.message || '주문을 저장하지 못했습니다.');
      return null;
    } finally {
      setIsSaving(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const saved = await saveForm();
    if (saved) {
      onSaved?.(saved);
    }
  };

  const handleSendAs = async () => {
    if (mode !== 'edit' || !orderId) return;
    if (asRequested) {
      setError('이미 협력사에 전달된 AS 요청입니다.');
      return;
    }
    const memo = asMemo.trim();
    if (!memo) {
      setError('AS 요청 내용을 입력해주세요.');
      return;
    }
    setAsBusy(true);
    setError(null);
    setNotice('');
    try {
      const updated = await sendOrderAsRequest(orderId, memo);
      setAsRequested(Boolean(updated.as_requested));
      setAsMemo(updated.as_memo || memo);
      setNotice('AS 요청을 협력사와 고객에게 전송했습니다. 협력사 링크에도 표시됩니다.');
    } catch (requestError) {
      setError(requestError?.message || 'AS 요청 전송에 실패했습니다.');
    } finally {
      setAsBusy(false);
    }
  };

  const hasPartnerPriceWarning = form.lines.some((line) => {
    // 소비자가 필드는 정가(할인 전)라 도급가와 비교는 할인 적용 후(net)로 한다.
    const net = Math.max((parseMoneyInput(line.total_amount) || 0) - (parseMoneyInput(line.discount_amount) || 0), 0);
    const partnerPrice = parseMoneyInput(line.partner_payment_amount) || 0;
    return net > 0 && partnerPrice > net;
  });

  if (isLoadingOrder) {
    return <FormState text="주문 입력 정보를 불러오는 중입니다." onCancel={handleCancel} />;
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
        <button type="button" className="btn btn--ghost btn--sm" onClick={handleCancel}>
          <Icon name="chevronLeft" size={13}/> 취소
        </button>
        <span style={{ width: 1, height: 16, background: 'var(--border)' }}/>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
          {mode === 'edit' ? '주문 수정' : isDuplicate ? '주문 복제' : '신규 주문 등록'}
        </h2>
        <div style={{ flex: 1 }}/>
        <button type="submit" data-testid="order-save" className="btn btn--primary btn--sm" disabled={isSaving}>
          <Icon name="check" size={13}/> {isSaving ? '저장 중' : '저장'}
        </button>
      </div>

      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        <div className="page-shell" style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {isDuplicate && (
              <div data-testid="order-duplicate-banner" style={{ padding: '10px 12px', background: 'var(--brand-bg)', border: '1px solid var(--brand)', borderRadius: 8, fontSize: 12.5, color: 'var(--text)' }}>
                고객정보만 복사되었습니다. 서비스 / 일정 / 협력사 / 금액을 입력해 새 주문으로 등록하세요.
              </div>
            )}
            <Section title="고객 정보">
              <FieldGrid>
                <TextField testId="order-customer-name" label="고객명" required value={form.customer_name} onChange={(value) => setGroupField('customer_name', value)} />
                <TextField testId="order-customer-phone" label="연락처" required value={form.customer_phone} onChange={(value) => setGroupField('customer_phone', value)} placeholder="010-0000-0000" />
                <Field label="유입 경로">
                  <SourceChannelSelect
                    value={form.source_channel}
                    onChange={(value) => setGroupField('source_channel', value)}
                  />
                </Field>
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
                    brokers={brokers.data || []}
                    onFieldChange={setLineField}
                    onMoneyChange={handleMoneyChange}
                    onPartnerChange={handlePartnerChange}
                    onServiceCategoryChange={handleServiceCategoryChange}
                    onServiceItemChange={handleServiceItemChange}
                    onRemove={removeLine}
                    asEnabled={mode === 'edit'}
                    asOpen={asOpen}
                    asMemo={asMemo}
                    asRequested={asRequested}
                    asBusy={asBusy}
                    onAsToggle={setAsOpen}
                    onAsMemoChange={setAsMemo}
                    onSendAs={handleSendAs}
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
            {notice && (
              <div style={{ padding: 10, borderRadius: 6, background: 'var(--success-bg)', color: 'var(--success-fg)', fontSize: 12 }}>
                {notice}
              </div>
            )}
            {hasPartnerPriceWarning && (
              <div style={{ padding: 10, borderRadius: 6, background: 'var(--warn-bg)', color: 'var(--warn-fg)', fontSize: 12 }}>
                도급가가 소비자가보다 큰 라인이 있습니다. 저장은 가능하지만 정산 금액을 확인해주세요.
              </div>
            )}

            <div className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: 0, marginBottom: 8 }}>저장 시 처리</div>
              <div style={{ fontSize: 12, lineHeight: 1.55, color: 'var(--text-secondary)' }}>
                신규 주문 저장 시 고객 확인 링크가 생성됩니다. 상태와 협력사 변경은 타임라인에 함께 기록됩니다.
                견적 안내는 저장 후 주문 상세의 [견적 안내] 버튼에서 미리보기 후 발송합니다.
                (견적서에는 소비자가와 계약금/잔금만 포함되고 도급가는 포함되지 않습니다.)
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
  brokers,
  onFieldChange,
  onMoneyChange,
  onPartnerChange,
  onServiceCategoryChange,
  onServiceItemChange,
  onRemove,
  asEnabled = false,
  asOpen = false,
  asMemo = '',
  asRequested = false,
  asBusy = false,
  onAsToggle,
  onAsMemoChange,
  onSendAs,
}) {
  const serviceItems = getServiceItems(activeServiceCategories, line.service_category_id);
  // AS 블록은 주문 단위 액션이라 편집 모드의 첫 라인에만 노출한다.
  const showAs = asEnabled && lineIndex === 0;

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
              {ORDER_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
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
                  {item.name} · 소비자가 {formatWon(item.base_price)} · 도급가(VAT 포함) {formatWon(item.partner_base_price)}
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
          <Field label="중개사">
            <select
              className="input"
              data-testid={`order-line-${lineIndex}-broker`}
              value={line.broker_id}
              onChange={(event) => onFieldChange(lineIndex, 'broker_id', event.target.value)}
            >
              <option value="">없음</option>
              {brokers.map((broker) => (
                <option key={broker.id} value={broker.id}>{broker.name}</option>
              ))}
            </select>
          </Field>
          <TextField label="상품 상세" span={2} multiline value={line.service_detail} onChange={(value) => onFieldChange(lineIndex, 'service_detail', value)} />
          <TextField label="요청사항" span={2} multiline value={line.special_request} onChange={(value) => onFieldChange(lineIndex, 'special_request', value)} />
        </FieldGrid>

        {showAs && (
          <div
            data-testid="order-as-section"
            style={{ border: '1px solid var(--divider)', borderRadius: 8, background: 'var(--bg-subtle)', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}
          >
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, fontWeight: 700, color: 'var(--text)' }}>
              <input
                type="checkbox"
                data-testid="order-as-checkbox"
                checked={asOpen}
                onChange={(event) => onAsToggle?.(event.target.checked)}
              />
              AS 요청 (사후관리 · 재작업)
              {asRequested && (
                <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--warn-fg)', background: 'var(--warn-bg)', borderRadius: 999, padding: '2px 8px' }}>
                  요청됨
                </span>
              )}
            </label>
            {asOpen && (
              <>
                <textarea
                  className="input"
                  data-testid="order-as-memo"
                  rows={3}
                  placeholder="재작업이 필요한 위치·증상 등 협력사에 전달할 AS 내용을 입력하세요."
                  value={asMemo}
                  onChange={(event) => onAsMemoChange?.(event.target.value)}
                  style={{ resize: 'vertical', fontSize: 13 }}
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    data-testid="order-as-send"
                    className="btn btn--primary btn--sm"
                    disabled={asBusy || asRequested || !asMemo.trim()}
                    onClick={() => onSendAs?.()}
                  >
                    <Icon name="send" size={12} /> {asBusy ? '전송 중' : (asRequested ? 'AS 전달됨' : 'AS 전송')}
                  </button>
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                    {asRequested
                      ? '이미 협력사 링크에 표시된 AS 요청입니다.'
                      : '배정된 협력사와 고객에게 알림을 보내고, 협력사 링크에도 AS 요청이 표시됩니다.'}
                  </span>
                </div>
              </>
            )}
          </div>
        )}

        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)' }}>결제 / 정산</div>
        <FieldGrid>
          <TextField testId={`order-line-${lineIndex}-total-amount`} label="소비자가 (할인 전 정가)" inputMode="numeric" value={line.total_amount} onChange={(value) => onMoneyChange(lineIndex, 'total_amount', value)} />
          <TextField testId={`order-line-${lineIndex}-discount-amount`} label="할인가" inputMode="numeric" value={line.discount_amount} onChange={(value) => onMoneyChange(lineIndex, 'discount_amount', value)} />
          <TextField testId={`order-line-${lineIndex}-deposit-amount`} label="계약금" inputMode="numeric" value={line.deposit_amount} onChange={(value) => onMoneyChange(lineIndex, 'deposit_amount', value)} />
          <TextField label="잔금" inputMode="numeric" value={line.balance_amount} onChange={(value) => onMoneyChange(lineIndex, 'balance_amount', value)} />
          <TextField testId={`order-line-${lineIndex}-onsite-extra-amount`} label="현장 추가" inputMode="numeric" value={line.onsite_extra_amount} onChange={(value) => onMoneyChange(lineIndex, 'onsite_extra_amount', value)} />
          <Field label="총금액 (VAT 포함)">
            <div
              data-testid={`order-line-${lineIndex}-grand-total`}
              className="input"
              style={{ display: 'flex', alignItems: 'center', fontWeight: 700, background: 'var(--bg-subtle)', color: 'var(--text)' }}
            >
              {formatWon(Math.max((parseMoneyInput(line.total_amount) || 0) - (parseMoneyInput(line.discount_amount) || 0), 0) + (parseMoneyInput(line.onsite_extra_amount) || 0))}
            </div>
          </Field>
          <Field label="결제 상태">
            <select className="input" value={line.payment_status} onChange={(event) => onFieldChange(lineIndex, 'payment_status', event.target.value)}>
              <option value="">미입력</option>
              {PAYMENT_STATUSES.map((status) => (
                <option key={status.value} value={status.value}>{status.label}</option>
              ))}
            </select>
          </Field>
          <Field label="VAT">
            <select className="input" data-testid={`order-line-${lineIndex}-vat-type`} value={line.vat_type} onChange={(event) => onFieldChange(lineIndex, 'vat_type', event.target.value)}>
              <option value="included">포함</option>
              <option value="excluded">별도</option>
            </select>
          </Field>
          <TextField label="결제 메모" span={2} multiline value={line.payment_memo} onChange={(value) => onFieldChange(lineIndex, 'payment_memo', value)} />
          <TextField label="증빙 메모" span={2} multiline value={line.evidence_memo} onChange={(value) => onFieldChange(lineIndex, 'evidence_memo', value)} />
          <TextField testId={`order-line-${lineIndex}-partner-payment-amount`} label="도급가 (VAT 포함)" inputMode="numeric" value={line.partner_payment_amount} onChange={(value) => onMoneyChange(lineIndex, 'partner_payment_amount', value)} />
          <Field label="협력사 정산 상태">
            <select className="input" value={line.partner_payment_status} onChange={(event) => onFieldChange(lineIndex, 'partner_payment_status', event.target.value)}>
              <option value="">미입력</option>
              {PARTNER_PAYMENT_STATUSES.map((status) => (
                <option key={status.value} value={status.value}>{status.label}</option>
              ))}
            </select>
          </Field>
          <TextField testId={`order-line-${lineIndex}-broker-payment-amount`} label="중개 수수료 (VAT 포함)" inputMode="numeric" value={line.broker_payment_amount} onChange={(value) => onMoneyChange(lineIndex, 'broker_payment_amount', value)} />
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
    broker_id: '',
    service_category_id: '',
    service_item_id: '',
    service_name: '',
    size_or_quantity: '',
    service_detail: '',
    special_request: '',
    total_amount: '',
    discount_amount: '',
    deposit_amount: '',
    balance_amount: '',
    onsite_extra_amount: '',
    vat_type: 'included',
    payment_status: '',
    payment_memo: '',
    evidence_memo: '',
    partner_payment_amount: '',
    partner_payment_status: '',
    broker_payment_amount: '',
    partner_settled_at: null,
    base_unit_price: '',
    partner_unit_price: '',
    total_amount_touched: false,
    deposit_amount_touched: false,
    balance_amount_touched: false,
    partner_payment_amount_touched: false,
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

// 복제용: 새 주문이므로 그룹/라인 식별자와 서비스/일정/협력사/금액은 비우고 고객정보만 가져온다.
function toDuplicateForm(order) {
  return {
    ...createEmptyGroupForm(),
    customer_name: order.customer_name || '',
    customer_phone: order.customer_phone || '',
    customer_address: order.customer_address || '',
    customer_address_detail: order.customer_address_detail || '',
    source_channel: order.source_channel || '',
    customer_visible_payment: Boolean(order.customer_visible_payment),
  };
}

function toLineForm(order) {
  return {
    ...createEmptyLineForm(),
    status: orderWorkflowStatusValue(order.status, order.payment_status) || ORDER_STATUSES[0],
    received_date: order.received_date || todayString(),
    scheduled_date: order.scheduled_date || '',
    requested_time: order.requested_time || '',
    partner_id: order.partner_id || '',
    team_name: order.team_name || '',
    broker_id: order.broker_id || '',
    service_category_id: order.service_category_id || '',
    service_item_id: order.service_item_id || '',
    service_name: order.service_name || '',
    size_or_quantity: order.size_or_quantity || '',
    service_detail: order.service_detail || '',
    special_request: order.special_request || '',
    // 저장값 total_amount 는 net(할인 후). 폼 소비자가 필드는 정가(=net+할인)로 복원한다.
    total_amount: order.total_amount == null
      ? toInputNumber(order.total_amount)
      : toInputNumber((Number(order.total_amount) || 0) + (Number(order.discount_amount) || 0)),
    discount_amount: toInputNumber(order.discount_amount),
    deposit_amount: toInputNumber(order.deposit_amount),
    balance_amount: toInputNumber(order.balance_amount),
    onsite_extra_amount: toInputNumber(order.onsite_extra_amount),
    vat_type: order.vat_type || 'included',
    payment_status: order.payment_status || '',
    payment_memo: order.payment_memo || '',
    evidence_memo: order.evidence_memo || '',
    partner_payment_amount: toInputNumber(order.partner_payment_amount),
    partner_payment_status: order.partner_payment_status || '',
    broker_payment_amount: toInputNumber(order.broker_payment_amount),
    partner_settled_at: order.partner_settled_at || null,
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
    broker_id: emptyToNull(line.broker_id),
    service_category_id: emptyToNull(line.service_category_id),
    service_item_id: emptyToNull(line.service_item_id),
    service_name: line.service_name.trim(),
    size_or_quantity: emptyToNull(line.size_or_quantity),
    service_detail: emptyToNull(line.service_detail),
    special_request: emptyToNull(line.special_request),
    // 소비자가 필드는 정가(할인 전). 저장 total_amount 는 할인 적용 후(net)로 보낸다.
    total_amount: netConsumerAmount(line),
    discount_amount: numberOrNull(line.discount_amount) || 0,
    deposit_amount: numberOrNull(line.deposit_amount),
    balance_amount: numberOrNull(line.balance_amount),
    onsite_extra_amount: numberOrNull(line.onsite_extra_amount),
    vat_type: emptyToNull(line.vat_type),
    payment_status: emptyToNull(line.payment_status),
    payment_memo: emptyToNull(line.payment_memo),
    evidence_memo: emptyToNull(line.evidence_memo),
    partner_payment_amount: numberOrNull(line.partner_payment_amount),
    partner_payment_status: emptyToNull(line.partner_payment_status),
    broker_payment_amount: numberOrNull(line.broker_payment_amount),
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

// 폼의 소비자가 필드는 정가(할인 전)다. 저장할 total_amount 는 할인 적용 후(net).
function netConsumerAmount(line) {
  const gross = parseMoneyInput(line.total_amount);
  if (gross === null) {
    return null;
  }
  const discount = parseMoneyInput(line.discount_amount) || 0;
  return Math.max(gross - discount, 0);
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

function applyMoneyTouch(line, key, formattedValue) {
  const touchMap = {
    total_amount: 'total_amount_touched',
    deposit_amount: 'deposit_amount_touched',
    balance_amount: 'balance_amount_touched',
    partner_payment_amount: 'partner_payment_amount_touched',
  };
  const touchKey = touchMap[key];
  if (!touchKey) {
    return line;
  }
  return { ...line, [touchKey]: formattedValue !== '' };
}

function recalculateLine(line, { source }) {
  const quantity = parseQuantity(line.size_or_quantity);
  const baseUnitPrice = Number(line.base_unit_price || 0);
  const partnerUnitPrice = Number(line.partner_unit_price || 0);
  const discount = parseMoneyInput(line.discount_amount) || 0;
  const onsiteExtra = parseMoneyInput(line.onsite_extra_amount) || 0;
  // 소비자가(total_amount 필드)는 할인 전 정가(gross). 총금액(VAT포함)=소비자가-할인+현장추가.
  // 계약금/잔금은 총금액 기준으로 잡고, 저장은 net(=소비자가-할인)으로 한다(buildPayload).
  const calculatedConsumer = Math.max(Math.round(baseUnitPrice * quantity), 0);
  const calculatedPartnerPrice = Math.max(Math.round(partnerUnitPrice * quantity), 0);
  const next = { ...line };

  if (baseUnitPrice > 0 && (!next.total_amount_touched || next.total_amount === '')) {
    next.total_amount = formatMoneyInput(calculatedConsumer);
    next.total_amount_touched = false;
  }

  if (partnerUnitPrice > 0 && (!next.partner_payment_amount_touched || next.partner_payment_amount === '')) {
    next.partner_payment_amount = formatMoneyInput(calculatedPartnerPrice);
    next.partner_payment_amount_touched = false;
  }

  const netConsumer = Math.max((parseMoneyInput(next.total_amount) || 0) - discount, 0);
  const grandTotal = netConsumer + onsiteExtra;

  if (next.total_amount !== '' && (!next.deposit_amount_touched || next.deposit_amount === '')) {
    next.deposit_amount = formatMoneyInput(Math.round(grandTotal * 0.3));
    next.deposit_amount_touched = false;
  }

  if (
    !next.balance_amount_touched
    || next.balance_amount === ''
    || source === 'total_amount'
    || source === 'deposit_amount'
    || source === 'discount_amount'
    || source === 'onsite_extra_amount'
  ) {
    next.balance_amount = calculateBalanceAmount(formatMoneyInput(grandTotal), next.deposit_amount);
    next.balance_amount_touched = false;
  }

  return next;
}

function parseQuantity(value) {
  const match = String(value || '').replace(/,/g, '').match(/\d+(?:\.\d+)?/);
  if (!match) {
    return 1;
  }
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

function formatWon(value) {
  const amount = Number(value || 0);
  return `₩${Math.round(amount).toLocaleString()}`;
}
