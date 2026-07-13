import { Icon } from '../../../components/common/ui';
import { isRelativeAppDateValue } from '../../../domain/time';
import type { AdminOrderDetail, MessageActionDraft } from './OrderDetailModel';
import { isDayBeforeNoticeAllowedStatus } from './OrderDetailRules';
import { CopyLinkButton, PanelTitle } from './OrderDetailPrimitives';

export function MessageActionsPanel({
  order,
  isSaving,
  isPreviewLoading,
  canSendBalanceDue,
  balanceDueBlockedText,
  canOpenAsRequest,
  asRequestBlockedText,
  messageActions,
  onMessagePreview,
  onAsRequestOpen,
}: {
  readonly order: AdminOrderDetail;
  readonly isSaving: boolean;
  readonly isPreviewLoading: boolean;
  readonly canSendBalanceDue: boolean;
  readonly balanceDueBlockedText: string;
  readonly canOpenAsRequest: boolean;
  readonly asRequestBlockedText?: string;
  readonly messageActions: {
    readonly customerScheduleConfirmed: MessageActionDraft;
    readonly customerDayBefore: MessageActionDraft;
    readonly partnerAssignment: MessageActionDraft;
    readonly customerBalanceDue: MessageActionDraft;
    readonly customerQuote: MessageActionDraft;
    readonly customerAccessLink: MessageActionDraft;
  };
  readonly onMessagePreview: (draft: MessageActionDraft) => void;
  readonly onAsRequestOpen: () => void;
}) {
  const hasDayBeforeStatus = isDayBeforeNoticeAllowedStatus(order.status);
  const isTomorrowVisit = isRelativeAppDateValue(order.scheduled_date, 1);
  const canSendDayBefore = hasDayBeforeStatus && isTomorrowVisit;
  const dayBeforeBlockedText = !order.scheduled_date || !hasDayBeforeStatus
    ? '방문일과 협력사 작업확인이 확정된 주문에서만 발송할 수 있습니다.'
    : !isTomorrowVisit
      ? '방문 하루 전인 주문에서만 전날 안내를 발송할 수 있습니다.'
      : undefined;
  return (
    <div className="card" style={{ padding: 14 }}>
      <PanelTitle>안내 발송</PanelTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button data-testid="send-customer-access-link" className="btn btn--secondary btn--block" disabled={isSaving || isPreviewLoading} onClick={() => onMessagePreview(messageActions.customerAccessLink)}>
          <Icon name="send" size={13}/> 고객 접속 링크 LMS
        </button>
        <button data-testid="send-customer-schedule-confirmed" className="btn btn--secondary btn--block" disabled={isSaving || isPreviewLoading} onClick={() => onMessagePreview(messageActions.customerScheduleConfirmed)}>
          <Icon name="send" size={13}/> 일정확정 안내
        </button>
        <button
          data-testid="send-customer-day-before"
          className="btn btn--secondary btn--block"
          disabled={isSaving || isPreviewLoading || !canSendDayBefore}
          title={dayBeforeBlockedText}
          onClick={() => onMessagePreview(messageActions.customerDayBefore)}
        >
          <Icon name="send" size={13}/> 전날 안내
        </button>
        <button data-testid="send-partner-assignment" className="btn btn--secondary btn--block" disabled={isSaving || isPreviewLoading || !order.partner_id} onClick={() => onMessagePreview(messageActions.partnerAssignment)}>
          <Icon name="truck" size={13}/> 협력사 배정 안내
        </button>
        <button
          data-testid="send-customer-balance-due"
          className="btn btn--secondary btn--block"
          disabled={isSaving || isPreviewLoading || !canSendBalanceDue}
          title={canSendBalanceDue ? undefined : balanceDueBlockedText}
          onClick={() => onMessagePreview(messageActions.customerBalanceDue)}
        >
          <Icon name="creditCard" size={13}/> 잔금 안내
        </button>
        {!canSendBalanceDue && (
          <span style={{ color: 'var(--text-tertiary)', fontSize: 11.5, lineHeight: 1.45 }}>
            {balanceDueBlockedText}
          </span>
        )}
        <button data-testid="send-customer-quote" className="btn btn--secondary btn--block" disabled={isSaving || isPreviewLoading} onClick={() => onMessagePreview(messageActions.customerQuote)}>
          <Icon name="send" size={13}/> 견적 안내
        </button>
        <button
          data-testid="send-order-as-request"
          className="btn btn--secondary btn--block"
          disabled={isSaving || isPreviewLoading || !canOpenAsRequest}
          title={asRequestBlockedText}
          onClick={onAsRequestOpen}
        >
          <Icon name="send" size={13}/> AS 요청 처리
        </button>
        {asRequestBlockedText && (
          <span style={{ color: 'var(--text-tertiary)', fontSize: 11.5, lineHeight: 1.45 }}>
            {asRequestBlockedText}
          </span>
        )}
      </div>
    </div>
  );
}

export function RelatedPagesPanel({ onNavigate }: { readonly onNavigate: (page: string) => void }) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <PanelTitle>관련 화면</PanelTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button data-testid="detail-nav-calendar" className="btn btn--secondary btn--block" onClick={() => onNavigate('calendar')}>
          <Icon name="calendar" size={13}/> 일정 캘린더
        </button>
        <button data-testid="detail-nav-photos" className="btn btn--secondary btn--block" onClick={() => onNavigate('photos')}>
          <Icon name="image" size={13}/> 사진/고객전달
        </button>
        <button data-testid="detail-nav-messages" className="btn btn--secondary btn--block" onClick={() => onNavigate('sends')}>
          <Icon name="send" size={13}/> 발송이력
        </button>
      </div>
    </div>
  );
}

export function CustomerDeliveryPanel({
  order,
  isSaving,
  isPreviewLoading,
  hasCustomerVisiblePhotos,
  customerPhotoReadyDraft,
  onMessagePreview,
}: {
  readonly order: AdminOrderDetail;
  readonly isSaving: boolean;
  readonly isPreviewLoading: boolean;
  readonly hasCustomerVisiblePhotos: boolean;
  readonly customerPhotoReadyDraft: MessageActionDraft;
  readonly onMessagePreview: (draft: MessageActionDraft) => void;
}) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <PanelTitle>고객 전달</PanelTitle>
      <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginBottom: 8, lineHeight: 1.45 }}>
        고객이 예약 정보와 공개 사진을 확인하는 링크입니다. 복사해서 고객에게 바로 보내세요.
      </div>
      {order.customer_token ? (
        <div style={{ marginBottom: 8 }}>
          <CopyLinkButton
            testId="copy-customer-link"
            label="고객 링크 복사"
            link={`${window.location.origin}/c#token=${encodeURIComponent(order.customer_token)}`}
          />
        </div>
      ) : (
        <div style={{ fontSize: 11.5, color: 'var(--warn-fg)', marginBottom: 8 }}>
          아직 고객 링크가 생성되지 않았습니다.
        </div>
      )}
      {!hasCustomerVisiblePhotos && (
        <div style={{ fontSize: 11.5, color: 'var(--warn-fg)', marginBottom: 8 }}>
          공개 사진이 1장 이상 있어야 사진 링크를 발송할 수 있습니다.
        </div>
      )}
      <button
        data-testid="send-customer-photo-ready"
        className="btn btn--secondary btn--block"
        disabled={isSaving || isPreviewLoading || !hasCustomerVisiblePhotos}
        title={hasCustomerVisiblePhotos ? undefined : '공개 사진이 1장 이상 필요합니다.'}
        onClick={() => onMessagePreview(customerPhotoReadyDraft)}
      >
        <Icon name="send" size={13}/> 사진 링크 발송
      </button>
    </div>
  );
}
