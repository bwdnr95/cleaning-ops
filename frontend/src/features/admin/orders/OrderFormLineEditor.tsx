import { DatePicker } from '../../../components/common/DatePicker';
import { Icon } from '../../../components/common/ui';
import { ORDER_STATUS_OPTIONS } from '../../../domain/orderStatus';
import { OrderFormAsFields } from './OrderFormAsFields';
import { getServiceItems } from './OrderFormModel';
import { formatWon } from './OrderFormMoney';
import { OrderFormPaymentFields } from './OrderFormPaymentFields';
import { Field, FieldGrid, TextField } from './OrderFormPrimitives';
import type {
  OrderFormBroker,
  OrderFormPartner,
  OrderFormServiceCategory,
  OrderLineField,
  OrderLineForm,
  OrderMoneyField,
} from './OrderFormTypes';

interface OrderFormLineEditorProps {
  readonly line: OrderLineForm;
  readonly lineIndex: number;
  readonly canRemove: boolean;
  readonly activeServiceCategories: readonly OrderFormServiceCategory[];
  readonly partners: readonly OrderFormPartner[];
  readonly brokers: readonly OrderFormBroker[];
  readonly onFieldChange: (lineIndex: number, key: OrderLineField, value: string) => void;
  readonly onMoneyChange: (lineIndex: number, key: OrderMoneyField, value: string) => void;
  readonly onPartnerChange: (lineIndex: number, partnerId: string) => void;
  readonly onServiceCategoryChange: (lineIndex: number, categoryId: string) => void;
  readonly onServiceItemChange: (lineIndex: number, serviceItemId: string) => void;
  readonly onReceiptTypeChange: (lineIndex: number, value: string) => void;
  readonly onRemove: (lineIndex: number) => void;
  readonly asEnabled?: boolean;
  readonly asOpen?: boolean;
  readonly asMemo?: string;
  readonly asRequested?: boolean;
  readonly asBusy?: boolean;
  readonly onAsToggle: (isOpen: boolean) => void;
  readonly onAsMemoChange: (memo: string) => void;
  readonly onSendAs: () => void;
}

export function OrderFormLineEditor({
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
  onReceiptTypeChange,
  onRemove,
  asEnabled = false,
  asOpen = false,
  asMemo = '',
  asRequested = false,
  asBusy = false,
  onAsToggle,
  onAsMemoChange,
  onSendAs,
}: OrderFormLineEditorProps) {
  const serviceItems = getServiceItems(activeServiceCategories, line.service_category_id);
  const hasArchivedPartner = Boolean(
    line.partner_id && !partners.some((partner) => partner.id === line.partner_id),
  );
  const showAs = asEnabled && lineIndex === 0;

  return (
    <div style={{ border: '1px solid var(--divider)', borderRadius: 8, background: 'var(--surface-subtle)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 12px', borderBottom: '1px solid var(--divider)' }}>
        <div style={{ fontSize: 12, fontWeight: 700 }}>라인 {lineIndex + 1}</div>
        <div style={{ flex: 1 }}/>
        {canRemove && (
          <button type="button" data-testid={`order-remove-line-${lineIndex}`} className="btn btn--ghost btn--sm" onClick={() => onRemove(lineIndex)}>
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
              {hasArchivedPartner && (
                <option value={line.partner_id} disabled>{line.team_name || '기존 협력사'} (보관됨 · 이력 전용)</option>
              )}
              {partners.map((partner) => <option key={partner.id} value={partner.id}>{partner.name}</option>)}
            </select>
          </Field>
          <Field label="카테고리">
            <select className="input" data-testid={`order-line-${lineIndex}-service-category`} value={line.service_category_id} onChange={(event) => onServiceCategoryChange(lineIndex, event.target.value)}>
              <option value="">직접 입력</option>
              {activeServiceCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select>
          </Field>
          <Field label="상세상품">
            <select className="input" data-testid={`order-line-${lineIndex}-service-item`} value={line.service_item_id} onChange={(event) => onServiceItemChange(lineIndex, event.target.value)} disabled={!line.service_category_id}>
              <option value="">직접 입력</option>
              {serviceItems.map((item) => (
                <option key={item.id} value={item.id}>{item.name} · 소비자가 {formatWon(item.base_price)} · 도급가(VAT 포함) {formatWon(item.partner_base_price)}</option>
              ))}
            </select>
          </Field>
          <TextField testId={`order-line-${lineIndex}-service-name`} label="상품명" required value={line.service_name} onChange={(value) => onFieldChange(lineIndex, 'service_name', value)} />
          <TextField label="수량/규격" value={line.size_or_quantity} onChange={(value) => onFieldChange(lineIndex, 'size_or_quantity', value)} />
          <Field label="접수일"><DatePicker testId={`order-line-${lineIndex}-received-date`} value={line.received_date} onChange={(value) => onFieldChange(lineIndex, 'received_date', value)} /></Field>
          <Field label="방문 예정일"><DatePicker testId={`order-line-${lineIndex}-scheduled-date`} value={line.scheduled_date} onChange={(value) => onFieldChange(lineIndex, 'scheduled_date', value)} placeholder="방문일 선택" /></Field>
          <TextField testId={`order-line-${lineIndex}-requested-time`} label="요청 시간" value={line.requested_time} onChange={(value) => onFieldChange(lineIndex, 'requested_time', value)} placeholder="14:00 또는 오후 2-5시" />
          <Field label="중개사">
            <select className="input" data-testid={`order-line-${lineIndex}-broker`} value={line.broker_id} onChange={(event) => onFieldChange(lineIndex, 'broker_id', event.target.value)}>
              <option value="">없음</option>
              {brokers.map((broker) => <option key={broker.id} value={broker.id}>{broker.name}</option>)}
            </select>
          </Field>
          <TextField label="상품 상세" span={2} multiline value={line.service_detail} onChange={(value) => onFieldChange(lineIndex, 'service_detail', value)} />
          <TextField label="요청사항" span={2} multiline value={line.special_request} onChange={(value) => onFieldChange(lineIndex, 'special_request', value)} />
        </FieldGrid>

        {showAs && (
          <OrderFormAsFields isOpen={asOpen} memo={asMemo} isRequested={asRequested} isBusy={asBusy} onToggle={onAsToggle} onMemoChange={onAsMemoChange} onSend={onSendAs} />
        )}
        <OrderFormPaymentFields line={line} lineIndex={lineIndex} onFieldChange={onFieldChange} onMoneyChange={onMoneyChange} onReceiptTypeChange={onReceiptTypeChange} />
      </div>
    </div>
  );
}
