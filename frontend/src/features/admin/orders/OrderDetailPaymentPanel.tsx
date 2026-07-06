import { Icon } from '../../../components/common/ui';
import { PARTNER_PAYMENT_STATUSES, PAYMENT_STATUSES } from '../../../domain/paymentStatus';
import { RECEIPT_STATUSES, RECEIPT_TYPES } from '../../../domain/receiptType';
import { formatWon } from './OrderDetailFormat';
import type { AdminOrderDetail } from './OrderDetailModel';
import { PanelTitle } from './OrderDetailPrimitives';

export function PaymentPanel({
  order,
  selectedPaymentStatus,
  selectedPartnerPaymentStatus,
  selectedReceiptType,
  selectedReceiptStatus,
  selectedOnsiteExtra,
  grandTotalWithOnsite,
  recomputedBalance,
  isSaving,
  isPaymentDirty,
  onSelectedPaymentStatusChange,
  onSelectedPartnerPaymentStatusChange,
  onSelectedReceiptTypeChange,
  onSelectedReceiptStatusChange,
  onSelectedOnsiteExtraChange,
  onPaymentSave,
}: {
  readonly order: AdminOrderDetail;
  readonly selectedPaymentStatus: string;
  readonly selectedPartnerPaymentStatus: string;
  readonly selectedReceiptType: string;
  readonly selectedReceiptStatus: string;
  readonly selectedOnsiteExtra: string;
  readonly grandTotalWithOnsite: number;
  readonly recomputedBalance: number;
  readonly isSaving: boolean;
  readonly isPaymentDirty: boolean;
  readonly onSelectedPaymentStatusChange: (value: string) => void;
  readonly onSelectedPartnerPaymentStatusChange: (value: string) => void;
  readonly onSelectedReceiptTypeChange: (value: string) => void;
  readonly onSelectedReceiptStatusChange: (value: string) => void;
  readonly onSelectedOnsiteExtraChange: (value: string) => void;
  readonly onPaymentSave: () => void;
}) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <PanelTitle dirty={isPaymentDirty}>결제 / 정산</PanelTitle>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
        <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>고객 결제 상태</span>
        <select className="input" value={selectedPaymentStatus} onChange={(event) => onSelectedPaymentStatusChange(event.target.value)} style={{ width: '100%', height: 34 }}>
          <option value="">미입력</option>
          {PAYMENT_STATUSES.map((status) => (
            <option key={status.value} value={status.value}>{status.label}</option>
          ))}
        </select>
      </label>
      <ReceiptControls
        selectedReceiptType={selectedReceiptType}
        selectedReceiptStatus={selectedReceiptStatus}
        onSelectedReceiptTypeChange={onSelectedReceiptTypeChange}
        onSelectedReceiptStatusChange={onSelectedReceiptStatusChange}
      />
      <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
        <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>협력사 정산 상태</span>
        <select className="input" value={selectedPartnerPaymentStatus} onChange={(event) => onSelectedPartnerPaymentStatusChange(event.target.value)} style={{ width: '100%', height: 34 }}>
          <option value="">미입력</option>
          {PARTNER_PAYMENT_STATUSES.map((status) => (
            <option key={status.value} value={status.value}>{status.label}</option>
          ))}
        </select>
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
        <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>현장 추가금</span>
        <input
          data-testid="detail-onsite-extra"
          className="input"
          inputMode="numeric"
          value={selectedOnsiteExtra}
          onChange={(event) => onSelectedOnsiteExtraChange(event.target.value.replace(/[^\d]/g, ''))}
          placeholder="0"
          style={{ width: '100%', height: 34 }}
        />
        <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>
          총금액 {formatWon(grandTotalWithOnsite)} · 잔금 {formatWon(recomputedBalance)} · 계약금 {formatWon(order.deposit_amount)} 유지
        </span>
      </label>
      <button
        className={`btn btn--block ${isPaymentDirty ? 'btn--primary' : 'btn--secondary'}`}
        disabled={isSaving || !isPaymentDirty}
        onClick={onPaymentSave}
      >
        <Icon name="creditCard" size={13}/> 결제/정산 저장
      </button>
    </div>
  );
}

function ReceiptControls({
  selectedReceiptType,
  selectedReceiptStatus,
  onSelectedReceiptTypeChange,
  onSelectedReceiptStatusChange,
}: {
  readonly selectedReceiptType: string;
  readonly selectedReceiptStatus: string;
  readonly onSelectedReceiptTypeChange: (value: string) => void;
  readonly onSelectedReceiptStatusChange: (value: string) => void;
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
      <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>증빙 자료</span>
      <select
        data-testid="detail-receipt-type"
        className="input"
        value={selectedReceiptType}
        onChange={(event) => onSelectedReceiptTypeChange(event.target.value)}
        style={{ width: '100%', height: 34 }}
      >
        <option value="">미입력</option>
        {RECEIPT_TYPES.map((item) => (
          <option key={item.value} value={item.value}>{item.label}</option>
        ))}
      </select>
      <select
        data-testid="detail-receipt-status"
        className="input"
        value={selectedReceiptStatus}
        disabled={selectedReceiptType === 'none' || selectedReceiptType === ''}
        onChange={(event) => onSelectedReceiptStatusChange(event.target.value)}
        style={{ width: '100%', height: 34 }}
      >
        <option value="">발급 상태 선택</option>
        {RECEIPT_STATUSES.map((item) => (
          <option key={item.value} value={item.value}>{item.label}</option>
        ))}
      </select>
    </label>
  );
}
