export const LEGACY_ORDER_STATUSES = [
  '신규접수',
  '상담중',
  '협력사확인중',
  '일정확정',
  '전날안내필요',
  '전날안내완료',
  '작업예정',
  '작업진행',
  '사진검수대기',
  '고객전달필요',
  '고객전달완료',
  '서비스완료',
  '취소',
];

export const ORDER_STATUS_OPTIONS = [
  { value: '상담중', label: '상담중/미배정' },
  { value: '협력사확인중', label: '일정 및 협력사 확인중' },
  { value: '작업예정', label: '일정 및 작업 확정' },
  { value: '고객전달필요', label: '작업완료' },
  { value: '서비스완료', label: '최종결제완료' },
  { value: '취소', label: '취소' },
];

export const ORDER_STATUSES = ORDER_STATUS_OPTIONS.map((option) => option.value);

const ORDER_STATUS_LABELS: Record<string, string> = {
  신규접수: '상담중/미배정',
  상담중: '상담중/미배정',
  협력사확인중: '일정 및 협력사 확인중',
  일정확정: '일정 및 작업 확정',
  전날안내필요: '일정 및 작업 확정',
  전날안내완료: '일정 및 작업 확정',
  작업예정: '일정 및 작업 확정',
  작업진행: '일정 및 작업 확정',
  사진검수대기: '작업완료',
  고객전달필요: '작업완료',
  고객전달완료: '작업완료',
  서비스완료: '최종결제완료',
  취소: '취소',
};

const ORDER_STATUS_TONES: Record<string, string> = {
  신규접수: 'neutral',
  상담중: 'purple',
  협력사확인중: 'warn',
  일정확정: 'info',
  전날안내필요: 'info',
  전날안내완료: 'info',
  작업예정: 'info',
  작업진행: 'info',
  사진검수대기: 'warn',
  고객전달필요: 'warn',
  고객전달완료: 'warn',
  서비스완료: 'success',
  취소: 'danger',
};

const SIMPLIFIED_ORDER_STATUS_VALUES: Record<string, string> = {
  신규접수: '상담중',
  상담중: '상담중',
  협력사확인중: '협력사확인중',
  일정확정: '작업예정',
  전날안내필요: '작업예정',
  전날안내완료: '작업예정',
  작업예정: '작업예정',
  작업진행: '작업예정',
  사진검수대기: '고객전달필요',
  고객전달필요: '고객전달필요',
  고객전달완료: '고객전달필요',
  서비스완료: '서비스완료',
  취소: '취소',
};

export function orderStatusLabel(status: string | null | undefined): string {
  if (!status) return '';
  return ORDER_STATUS_LABELS[status] || status;
}

export function orderStatusTone(status: string | null | undefined): string {
  if (!status) return 'neutral';
  return ORDER_STATUS_TONES[status] || 'neutral';
}

export function simplifiedOrderStatusValue(status: string | null | undefined): string {
  if (!status) return '';
  return SIMPLIFIED_ORDER_STATUS_VALUES[status] || status;
}

export function orderWorkflowStatusValue(
  status: string | null | undefined,
  paymentStatus: string | null | undefined,
): string {
  const simplifiedStatus = simplifiedOrderStatusValue(status);
  if (simplifiedStatus === '서비스완료' && !isFinalPaymentComplete(paymentStatus)) {
    return '고객전달필요';
  }
  return simplifiedStatus;
}

export function isFinalPaymentComplete(paymentStatus: string | null | undefined): boolean {
  return ['paid', 'complete', 'completed'].includes(paymentStatus || '');
}

export const PHOTO_TYPES = ['before', 'after', 'etc'];

export const MESSAGE_TYPES = [
  'customer_schedule_confirmed',
  'customer_day_before',
  'partner_assignment',
  'customer_photo_ready',
  'customer_balance_due',
];
