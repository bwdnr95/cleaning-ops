import type { AdminOrder } from '../../../api/admin';
import { formatQuantity } from '../../../domain/format';
import { formatAppDateTime } from '../../../domain/time';
import type { OrderDetailMessageLog } from './OrderDetailModel';

export function formatService(order: Pick<AdminOrder, 'service_name' | 'size_or_quantity'>): string {
  const quantity = formatQuantity(order.size_or_quantity);
  return quantity ? `${order.service_name} ${quantity}` : order.service_name;
}

export function formatWon(value: number | string | null | undefined): string {
  const amount = Number(value || 0);
  return amount ? `₩${amount.toLocaleString()}` : '-';
}

export function formatDateTime(value: string | null | undefined): string {
  return formatAppDateTime(value);
}

export function photoTypeLabel(type: string): string {
  if (type === 'before') return '비포';
  if (type === 'after') return '애프터';
  return '기타';
}

export function messageTypeLabel(type: string | null | undefined): string {
  if (type === 'customer_schedule_confirmed') return '일정확정';
  if (type === 'customer_day_before') return '전날안내';
  if (type === 'partner_assignment') return '협력사배정';
  if (type === 'customer_photo_ready') return '사진전달';
  if (type === 'customer_balance_due') return '잔금안내';
  if (type === 'customer_quote') return '견적서';
  if (type === 'partner_customer_info') return '협력사 고객정보';
  if (type === 'partner_as_request') return '협력사 AS';
  if (type === 'customer_as_notice') return '고객 AS';
  return type || '-';
}

export function messageStatusLabel(status: string | null | undefined): string {
  if (status === 'sent') return '요청성공';
  if (status === 'failed') return '요청실패';
  if (status === 'delivered') return '배송완료';
  if (status === 'delivery_failed') return '배송실패';
  return status || '-';
}

export function isMessageFailure(status: string | null | undefined): boolean {
  return status === 'failed' || status === 'delivery_failed';
}

export function isMessagePending(status: string | null | undefined): boolean {
  return status === 'pending';
}

export function messageStatusTone(status: string | null | undefined): string {
  if (status === 'delivered') return 'success';
  if (status === 'sent') return 'info';
  if (isMessagePending(status)) return 'warn';
  if (isMessageFailure(status)) return 'danger';
  return 'neutral';
}

export function messageProviderLabel(log: OrderDetailMessageLog): string {
  if (log.provider === 'mock') return 'Mock';
  if (log.provider === 'solapi') {
    return log.provider_group_id || log.provider_message_id
      ? `SOL API ${log.provider_group_id || log.provider_message_id}`
      : 'SOL API';
  }
  if (log.provider === 'configuration_error') return 'Config';
  return log.provider || 'Provider 미기록';
}

export function messageProviderErrorText(log: OrderDetailMessageLog): string {
  const map: Record<string, string> = {
    missing_recipient: '수신번호 없음',
    solapi_missing_credentials: 'SOL API 인증 설정 누락',
    solapi_missing_sender_number: 'SOL API 발신번호 누락',
    solapi_missing_kakao_channel_id: 'SOL API 카카오 발신프로필 ID 누락',
    solapi_missing_kakao_pf_id: 'SOL API 카카오 발신프로필 ID 누락',
    solapi_missing_kakao_template_id: '알림톡 승인 템플릿 ID 누락',
    solapi_http_error: 'SOL API HTTP 오류',
    solapi_request_failed: 'SOL API 요청 실패',
    solapi_invalid_response: 'SOL API 응답 오류',
    solapi_provider_failed: 'SOL API 발송 실패',
    unsupported_message_provider: 'Provider 설정 오류',
  };
  return (
    map[log.provider_error_code || '']
    || log.provider_status_message
    || log.error_message
    || '실패 사유 미상'
  );
}

export function messageChannelLabel(channel: string | null | undefined): string {
  if (channel === 'sms') return 'SMS';
  if (channel === 'lms') return 'LMS';
  if (channel === 'alimtalk') return '알림톡';
  return channel || '-';
}

export function messagePreviewWarningLabel(warning: string): string {
  const map: Record<string, string> = {
    solapi_missing_kakao_channel_id: 'SOL API 카카오 발신프로필 ID가 아직 설정되지 않았습니다.',
    solapi_missing_kakao_pf_id: 'SOL API 카카오 발신프로필 ID가 아직 설정되지 않았습니다.',
    solapi_missing_kakao_template_id: '이 메시지 타입의 승인 템플릿 ID가 아직 설정되지 않았습니다.',
    alimtalk_fallback_sms_enabled: '알림톡 설정이 준비되지 않으면 같은 문구를 SMS로 fallback 발송합니다.',
  };
  return map[warning] || warning;
}

export function normalizeHttpUrl(value: string | null | undefined): string {
  const input = String(value || '').trim();
  if (!input) {
    return '';
  }
  try {
    const url = new URL(input);
    return ['http:', 'https:'].includes(url.protocol) ? url.toString() : '';
  } catch {
    return '';
  }
}

export function timelineEventLabel(type: string): string {
  const labels: Record<string, string> = {
    created: '주문 생성',
    status_changed: '상태 변경',
    partner_assigned: '협력사 배정',
    message_sent: '안내 발송',
    photo_uploaded: '사진 업로드',
    photo_approved: '사진 공개',
    photo_revoked: '사진 비공개 처리',
    customer_link_sent: '고객 링크 발송',
    memo_added: '메모 추가',
    payment_updated: '결제/정산 변경',
    as_requested: 'AS 요청',
  };
  return labels[type] || type;
}

export function toActionErrorMessage(error: { readonly message?: string } | null | undefined): string {
  if (error?.message === 'partner_not_assigned') {
    return '협력사 배정 후 안내를 발송할 수 있습니다.';
  }
  if (error?.message === 'no_customer_visible_photos') {
    return '고객에게 공개된 사진이 있어야 사진 링크를 발송할 수 있습니다.';
  }
  if (error?.message === 'customer_balance_not_due') {
    return '미수금이 있는 주문에만 잔금 안내를 발송할 수 있습니다.';
  }
  if (error?.message === 'as_request_required') {
    return 'AS 요청 처리 후에만 AS 안내를 다시 발송할 수 있습니다.';
  }
  if (error?.message === 'invalid_as_request_status') {
    return 'AS 요청은 작업완료 이후 또는 고객확인필요 상태에서 보낼 수 있습니다.';
  }
  if (error?.message === 'recurring_customer_payment_not_per_visit') {
    return '월 청구 정기계약 주문이라 주문별 금액을 입력할 수 없습니다. 금액은 정기청소 > 계약에서 수정하세요.';
  }
  if (error?.message === 'recurring_partner_payment_not_per_visit') {
    return '월 정산 정기계약 주문이라 주문별 도급가·정산상태를 바꿀 수 없습니다. 정산은 정기청소 > 월 트래커에서 처리하세요.';
  }
  return '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.';
}
