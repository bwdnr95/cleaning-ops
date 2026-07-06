import type { MessageActionDraft } from './OrderDetailModel';

export const MESSAGE_ACTIONS = {
  customerScheduleConfirmed: {
    messageType: 'customer_schedule_confirmed',
    recipientType: 'customer',
    title: '일정확정 안내',
    successText: '고객 일정확정 안내를 발송했습니다.',
  },
  customerDayBefore: {
    messageType: 'customer_day_before',
    recipientType: 'customer',
    title: '전날 안내',
    successText: '고객 전날 안내를 발송했습니다.',
  },
  partnerAssignment: {
    messageType: 'partner_assignment',
    recipientType: 'partner',
    title: '협력사 배정 안내',
    successText: '협력사 배정 안내를 발송했습니다.',
  },
  customerPhotoReady: {
    messageType: 'customer_photo_ready',
    recipientType: 'customer',
    title: '사진 링크 발송',
    successText: '고객 사진 확인 링크를 발송했습니다.',
  },
  customerBalanceDue: {
    messageType: 'customer_balance_due',
    recipientType: 'customer',
    title: '잔금 안내',
    successText: '고객 잔금 안내를 발송했습니다.',
  },
  customerQuote: {
    messageType: 'customer_quote',
    recipientType: 'customer',
    title: '견적 안내',
    successText: '고객 견적 안내를 발송했습니다.',
  },
  partnerAsRequest: {
    messageType: 'partner_as_request',
    recipientType: 'partner',
    title: '협력사 AS 요청',
    successText: '협력사 AS 요청 안내를 발송했습니다.',
  },
  customerAsNotice: {
    messageType: 'customer_as_notice',
    recipientType: 'customer',
    title: '고객 AS 안내',
    successText: '고객 AS 안내를 발송했습니다.',
  },
} satisfies Record<string, MessageActionDraft>;

export const WORK_DONE_STATUS = '고객전달필요';

const BALANCE_NOTICE_ALLOWED_STATUSES = ['고객전달필요', '고객전달완료', '서비스완료'];
const AS_REQUEST_ALLOWED_STATUSES = ['고객전달필요', '고객전달완료', '고객확인필요', '서비스완료'];

export function isBalanceNoticeAllowedStatus(status: string | null | undefined): boolean {
  return BALANCE_NOTICE_ALLOWED_STATUSES.includes(status || '');
}

export function isAsRequestAllowedStatus(status: string | null | undefined): boolean {
  return AS_REQUEST_ALLOWED_STATUSES.includes(status || '');
}
