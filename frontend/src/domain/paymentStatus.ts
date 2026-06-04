export const PAYMENT_STATUSES = [
  { value: 'pending', label: '확인 대기' },
  { value: 'deposit_paid', label: '계약금 확인' },
  { value: 'balance_pending', label: '잔금 확인 필요' },
  { value: 'paid', label: '완납' },
  { value: 'unpaid', label: '미수' },
  { value: 'refunded', label: '환불' },
];

export const PARTNER_PAYMENT_STATUSES = [
  { value: 'unpaid', label: '미지급' },
  { value: 'ready', label: '지급 대기' },
  { value: 'paid', label: '지급 완료' },
  { value: 'hold', label: '보류' },
];

export const PAYMENT_CHECK_STATUSES = ['pending', 'balance_pending', 'unpaid'];
export const BALANCE_INCOMPLETE_STATUSES = ['pending', 'deposit_paid', 'balance_pending', 'unpaid'];

export function paymentStatusLabel(status) {
  return PAYMENT_STATUSES.find((item) => item.value === status)?.label || status || '-';
}

export function partnerPaymentStatusLabel(status) {
  return PARTNER_PAYMENT_STATUSES.find((item) => item.value === status)?.label || status || '-';
}

export function isPaymentCheckNeeded(status) {
  return PAYMENT_CHECK_STATUSES.includes(status);
}

export function isBalanceIncomplete(status) {
  return BALANCE_INCOMPLETE_STATUSES.includes(status);
}
