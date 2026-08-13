import { PARTNER_PAYMENT_STATUSES, PAYMENT_STATUSES } from '../../../domain/paymentStatus';
import { RECEIPT_STATUSES, RECEIPT_TYPES } from '../../../domain/receiptType';
import { formatWon, parseMoneyInput } from './OrderFormMoney';
import { Field, FieldGrid, TextField } from './OrderFormPrimitives';
import type { OrderLineField, OrderLineForm, OrderMoneyField } from './OrderFormTypes';

interface OrderFormPaymentFieldsProps {
  readonly line: OrderLineForm;
  readonly lineIndex: number;
  readonly onFieldChange: (lineIndex: number, key: OrderLineField, value: string) => void;
  readonly onMoneyChange: (lineIndex: number, key: OrderMoneyField, value: string) => void;
  readonly onReceiptTypeChange: (lineIndex: number, value: string) => void;
}

export function OrderFormPaymentFields({
  line,
  lineIndex,
  onFieldChange,
  onMoneyChange,
  onReceiptTypeChange,
}: OrderFormPaymentFieldsProps) {
  const isReceiptStatusDisabled = !line.receipt_type || line.receipt_type === 'none';
  const grandTotal = Math.max(
    (parseMoneyInput(line.total_amount) || 0) - (parseMoneyInput(line.discount_amount) || 0),
    0,
  ) + (parseMoneyInput(line.onsite_extra_amount) || 0);

  return (
    <>
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
            {formatWon(grandTotal)}
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
        <Field label="증빙 자료">
          <select
            className="input"
            data-testid={`order-line-${lineIndex}-receipt-type`}
            value={line.receipt_type}
            onChange={(event) => onReceiptTypeChange(lineIndex, event.target.value)}
          >
            <option value="">미선택</option>
            {RECEIPT_TYPES.map((type) => (
              <option key={type.value} value={type.value}>{type.label}</option>
            ))}
          </select>
        </Field>
        <Field label="발급 상태">
          <select
            className="input"
            data-testid={`order-line-${lineIndex}-receipt-status`}
            value={line.receipt_status}
            disabled={isReceiptStatusDisabled}
            onChange={(event) => onFieldChange(lineIndex, 'receipt_status', event.target.value)}
          >
            <option value="">미선택</option>
            {RECEIPT_STATUSES.map((status) => (
              <option key={status.value} value={status.value}>{status.label}</option>
            ))}
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
    </>
  );
}
