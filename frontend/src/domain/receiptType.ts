// 증빙자료(현금영수증/세금계산서) 1차 유형 + 2차 발급 상태.
// 백엔드 app/domain/constants.py 의 ReceiptType / ReceiptStatus 와 값이 일치해야 한다.

export const RECEIPT_TYPES = [
  { value: 'cash_receipt', label: '현금영수증' },
  { value: 'tax_invoice', label: '세금계산서' },
  { value: 'card_payment', label: '카드결제' },
  { value: 'none', label: '발급X' },
];

export const RECEIPT_STATUSES = [
  { value: 'issued', label: '발급완료' },
  { value: 'pending', label: '미발급' },
  { value: 'not_applicable', label: '해당없음' },
];

export function receiptTypeLabel(value) {
  return RECEIPT_TYPES.find((item) => item.value === value)?.label || '';
}

export function receiptStatusLabel(value) {
  return RECEIPT_STATUSES.find((item) => item.value === value)?.label || '';
}

// 리스트 배지용. tone: 'ok'(발급완료) | 'warn'(미발급) | 'muted'(발급X/미설정)
export function receiptBadge(type, status) {
  if (!type) return { text: '-', tone: 'muted' };
  if (type === 'none') return { text: '발급X', tone: 'muted' };
  const typeText = receiptTypeLabel(type);
  const statusText = receiptStatusLabel(status);
  const tone = status === 'issued' ? 'ok' : status === 'pending' ? 'warn' : 'muted';
  return { text: statusText ? `${typeText}·${statusText}` : typeText, tone };
}
