import type React from 'react';

import { AddressInput } from '../../../components/AddressInput';
import { Icon } from '../../../components/common/ui';
import { OrderFormLineEditor } from './OrderFormLineEditor';
import { Field, FieldGrid, Section, TextField } from './OrderFormPrimitives';
import { SourceChannelSelect } from './SourceChannelSelect';
import type {
  OrderFormAmountLock,
  OrderFormBroker,
  OrderFormGroupFieldChange,
  OrderFormLineFieldChange,
  OrderFormVisitDatesChange,
  OrderFormPartner,
  OrderFormServiceCategory,
  OrderGroupForm,
  OrderMoneyField,
} from './OrderFormTypes';

export type OrderFormMode = 'create' | 'edit';

interface OrderFormFeedback {
  readonly error: string | null;
  readonly notice: string;
  readonly hasPartnerPriceWarning: boolean;
}

interface OrderFormAsState {
  readonly isOpen: boolean;
  readonly memo: string;
  readonly isRequested: boolean;
  readonly isBusy: boolean;
}

interface OrderFormResources {
  readonly serviceCategories: readonly OrderFormServiceCategory[];
  readonly partners: readonly OrderFormPartner[];
  readonly brokers: readonly OrderFormBroker[];
}

export interface OrderFormViewActions {
  readonly onCancel: () => void;
  readonly onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  readonly onGroupFieldChange: OrderFormGroupFieldChange;
  readonly onLineFieldChange: OrderFormLineFieldChange;
  readonly onVisitDatesChange: OrderFormVisitDatesChange;
  readonly onMoneyChange: (lineIndex: number, key: OrderMoneyField, value: string) => void;
  readonly onPartnerChange: (lineIndex: number, partnerId: string) => void;
  readonly onServiceCategoryChange: (lineIndex: number, categoryId: string) => void;
  readonly onServiceItemChange: (lineIndex: number, serviceItemId: string) => void;
  readonly onReceiptTypeChange: (lineIndex: number, receiptType: string) => void;
  readonly onAddLine: () => void;
  readonly onRemoveLine: (lineIndex: number) => void;
  readonly onAsToggle: (isOpen: boolean) => void;
  readonly onAsMemoChange: (memo: string) => void;
  readonly onSendAs: () => void;
}

interface OrderFormViewProps {
  readonly mode: OrderFormMode;
  readonly isDuplicate: boolean;
  readonly isSaving: boolean;
  readonly form: OrderGroupForm;
  readonly feedback: OrderFormFeedback;
  readonly asState: OrderFormAsState;
  readonly resources: OrderFormResources;
  readonly actions: OrderFormViewActions;
  readonly amountLock: OrderFormAmountLock;
}

export function OrderFormView({
  mode,
  isDuplicate,
  isSaving,
  form,
  feedback,
  asState,
  resources,
  actions,
  amountLock,
}: OrderFormViewProps) {
  return (
    <form className="order-form" data-testid="admin-order-form" onSubmit={actions.onSubmit} style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}>
      <div style={{ padding: '10px 20px', background: 'var(--surface)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <button type="button" className="btn btn--ghost btn--sm" onClick={actions.onCancel}><Icon name="chevronLeft" size={13}/> 취소</button>
        <span style={{ width: 1, height: 16, background: 'var(--border)' }}/>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>{mode === 'edit' ? '주문 수정' : isDuplicate ? '주문 복제' : '신규 주문 등록'}</h2>
        <div style={{ flex: 1 }}/>
        <button type="submit" data-testid="order-save" className="btn btn--primary btn--sm" disabled={isSaving}>
          <Icon name="check" size={13}/> {isSaving ? '저장 중' : '저장'}
        </button>
      </div>

      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: 20 }}>
        <div className="page-shell order-form-layout" style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {isDuplicate && (
              <div data-testid="order-duplicate-banner" style={{ padding: '10px 12px', background: 'var(--brand-bg)', border: '1px solid var(--brand)', borderRadius: 8, fontSize: 12.5, color: 'var(--text)' }}>
                고객정보만 복사되었습니다. 서비스 / 일정 / 협력사 / 금액을 입력해 새 주문으로 등록하세요.
              </div>
            )}
            <Section title="고객 정보">
              <FieldGrid>
                <TextField testId="order-customer-name" label="고객명" required value={form.customer_name} onChange={(value) => actions.onGroupFieldChange('customer_name', value)} />
                <TextField testId="order-customer-phone" label="연락처" required value={form.customer_phone} onChange={(value) => actions.onGroupFieldChange('customer_phone', value)} placeholder="010-0000-0000" />
                <Field label="유입 경로"><SourceChannelSelect value={form.source_channel} onChange={(value) => actions.onGroupFieldChange('source_channel', value)} /></Field>
                <div className="order-form-field--span-2">
                  <AddressInput
                    baseAddress={form.customer_address}
                    detailAddress={form.customer_address_detail}
                    required
                    onChange={({ baseAddress, detailAddress }) => {
                      actions.onGroupFieldChange('customer_address', baseAddress);
                      actions.onGroupFieldChange('customer_address_detail', detailAddress);
                    }}
                  />
                </div>
              </FieldGrid>
            </Section>

            <Section
              title="상품 / 일정"
              action={mode === 'create' ? (
                <button type="button" data-testid="order-add-line" className="btn btn--ghost btn--sm" onClick={actions.onAddLine}>
                  <Icon name="plus" size={12}/> 라인 추가
                </button>
              ) : null}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {form.lines.map((line, lineIndex) => (
                  <OrderFormLineEditor
                    key={line.local_id}
                    line={line}
                    lineIndex={lineIndex}
                    canRemove={mode === 'create' && form.lines.length > 1}
                    amountLock={amountLock}
                    activeServiceCategories={resources.serviceCategories}
                    partners={resources.partners}
                    brokers={resources.brokers}
                    onFieldChange={actions.onLineFieldChange}
                    onVisitDatesChange={actions.onVisitDatesChange}
                    onMoneyChange={actions.onMoneyChange}
                    onPartnerChange={actions.onPartnerChange}
                    onServiceCategoryChange={actions.onServiceCategoryChange}
                    onServiceItemChange={actions.onServiceItemChange}
                    onReceiptTypeChange={actions.onReceiptTypeChange}
                    onRemove={actions.onRemoveLine}
                    asEnabled={mode === 'edit'}
                    asOpen={asState.isOpen}
                    asMemo={asState.memo}
                    asRequested={asState.isRequested}
                    asBusy={asState.isBusy}
                    onAsToggle={actions.onAsToggle}
                    onAsMemoChange={actions.onAsMemoChange}
                    onSendAs={actions.onSendAs}
                  />
                ))}
              </div>
            </Section>
          </div>

          <aside style={{ display: 'flex', flexDirection: 'column', gap: 12, position: 'sticky', top: 0, alignSelf: 'flex-start' }}>
            <div className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: 0, marginBottom: 8 }}>그룹 설정</div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                <input type="checkbox" checked={form.customer_visible_payment} onChange={(event) => actions.onGroupFieldChange('customer_visible_payment', event.target.checked)} />
                고객 페이지에 결제 금액 노출
              </label>
              <TextField testId="order-group-notes" label="그룹 메모" span={1} multiline value={form.notes} onChange={(value) => actions.onGroupFieldChange('notes', value)} />
            </div>
            {feedback.error && <div style={{ padding: 10, borderRadius: 6, background: 'var(--danger-bg)', color: 'var(--danger-fg)', fontSize: 12 }}>{feedback.error}</div>}
            {feedback.notice && <div style={{ padding: 10, borderRadius: 6, background: 'var(--success-bg)', color: 'var(--success-fg)', fontSize: 12 }}>{feedback.notice}</div>}
            {feedback.hasPartnerPriceWarning && (
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
