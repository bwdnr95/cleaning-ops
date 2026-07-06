import { OrderWorkflowGuide } from './OrderWorkflowGuide';
import { CustomerDeliveryPanel, MessageActionsPanel, RelatedPagesPanel } from './OrderDetailMessagePanels';
import type {
  AdminOrderDetail,
  AdminPartnerOption,
  MessageActionDraft,
  OrderDetailSiblingLine,
  OrderDetailTimelineEvent,
} from './OrderDetailModel';
import { PaymentPanel } from './OrderDetailPaymentPanel';
import { PartnerAssignPanel, SchedulePanel, StatusChangePanel } from './OrderDetailStatusPanels';
import { SiblingLinesPanel, TimelinePanel } from './OrderDetailTimelinePanels';

interface OrderDetailSidebarProps {
  readonly order: AdminOrderDetail;
  readonly displayStatus: string;
  readonly partners: readonly AdminPartnerOption[];
  readonly selectedStatus: string;
  readonly selectedPartnerId: string;
  readonly selectedScheduledDate: string;
  readonly selectedRequestedTime: string;
  readonly selectedPaymentStatus: string;
  readonly selectedPartnerPaymentStatus: string;
  readonly selectedReceiptType: string;
  readonly selectedReceiptStatus: string;
  readonly selectedOnsiteExtra: string;
  readonly grandTotalWithOnsite: number;
  readonly recomputedBalance: number;
  readonly timeline: readonly OrderDetailTimelineEvent[];
  readonly siblings: readonly OrderDetailSiblingLine[];
  readonly notice: string | null;
  readonly error: string | null;
  readonly isSticky?: boolean;
  readonly isSaving: boolean;
  readonly isPreviewLoading: boolean;
  readonly hasUnsavedChanges: boolean;
  readonly hasScheduleChanges: boolean;
  readonly isStatusDirty: boolean;
  readonly isPartnerDirty: boolean;
  readonly isPaymentDirty: boolean;
  readonly hasCustomerVisiblePhotos: boolean;
  readonly hasSavedBalanceDue: boolean;
  readonly canSendBalanceDue: boolean;
  readonly balanceDueBlockedText: string;
  readonly canOpenAsRequest: boolean;
  readonly asRequestBlockedText?: string;
  readonly onSelectedStatusChange: (value: string) => void;
  readonly onSelectedPartnerIdChange: (value: string) => void;
  readonly onSelectedScheduledDateChange: (value: string) => void;
  readonly onSelectedRequestedTimeChange: (value: string) => void;
  readonly onSelectedPaymentStatusChange: (value: string) => void;
  readonly onSelectedPartnerPaymentStatusChange: (value: string) => void;
  readonly onSelectedReceiptTypeChange: (value: string) => void;
  readonly onSelectedReceiptStatusChange: (value: string) => void;
  readonly onSelectedOnsiteExtraChange: (value: string) => void;
  readonly onStatusSave: () => void;
  readonly onPartnerSave: () => void;
  readonly onScheduleSave: () => void;
  readonly onPaymentSave: () => void;
  readonly onMessagePreview: (draft: MessageActionDraft) => void;
  readonly onAsRequestOpen: () => void;
  readonly onNavigate: (page: string) => void;
  readonly onOpenOrder?: (orderId: string) => void;
  readonly messageActions: {
    readonly customerScheduleConfirmed: MessageActionDraft;
    readonly customerDayBefore: MessageActionDraft;
    readonly partnerAssignment: MessageActionDraft;
    readonly customerBalanceDue: MessageActionDraft;
    readonly customerQuote: MessageActionDraft;
    readonly customerPhotoReady: MessageActionDraft;
  };
}

export function OrderDetailSidebar({
  order,
  displayStatus,
  partners,
  selectedStatus,
  selectedPartnerId,
  selectedScheduledDate,
  selectedRequestedTime,
  selectedPaymentStatus,
  selectedPartnerPaymentStatus,
  selectedReceiptType,
  selectedReceiptStatus,
  selectedOnsiteExtra,
  grandTotalWithOnsite,
  recomputedBalance,
  timeline,
  siblings,
  notice,
  error,
  isSticky = true,
  isSaving,
  isPreviewLoading,
  hasUnsavedChanges,
  hasScheduleChanges,
  isStatusDirty,
  isPartnerDirty,
  isPaymentDirty,
  hasCustomerVisiblePhotos,
  hasSavedBalanceDue,
  canSendBalanceDue,
  balanceDueBlockedText,
  canOpenAsRequest,
  asRequestBlockedText,
  onSelectedStatusChange,
  onSelectedPartnerIdChange,
  onSelectedScheduledDateChange,
  onSelectedRequestedTimeChange,
  onSelectedPaymentStatusChange,
  onSelectedPartnerPaymentStatusChange,
  onSelectedReceiptTypeChange,
  onSelectedReceiptStatusChange,
  onSelectedOnsiteExtraChange,
  onStatusSave,
  onPartnerSave,
  onScheduleSave,
  onPaymentSave,
  onMessagePreview,
  onAsRequestOpen,
  onNavigate,
  onOpenOrder,
  messageActions,
}: OrderDetailSidebarProps) {
  return (
    <aside style={{ display: 'flex', flexDirection: 'column', gap: 12, position: isSticky ? 'sticky' : 'static', top: isSticky ? 0 : undefined, alignSelf: isSticky ? 'flex-start' : 'stretch' }}>
      <OrderWorkflowGuide
        workflowStatus={order.status || ''}
        displayStatus={displayStatus}
        hasPartner={Boolean(order.partner_id)}
        hasSchedule={Boolean(order.scheduled_date)}
        hasUnsavedChanges={hasUnsavedChanges}
        isStatusDirty={isStatusDirty}
        isPartnerDirty={isPartnerDirty}
        hasScheduleChanges={hasScheduleChanges}
        isPaymentDirty={isPaymentDirty}
        hasCustomerVisiblePhotos={hasCustomerVisiblePhotos}
        hasSavedBalanceDue={hasSavedBalanceDue}
        canSendBalanceDue={canSendBalanceDue}
        isAsRequested={Boolean(order.as_requested)}
      />

      {siblings.length > 0 && (
        <SiblingLinesPanel siblings={siblings} onOpenOrder={onOpenOrder} />
      )}

      <StatusChangePanel
        selectedStatus={selectedStatus}
        isSaving={isSaving}
        isStatusDirty={isStatusDirty}
        onSelectedStatusChange={onSelectedStatusChange}
        onStatusSave={onStatusSave}
      />

      <PartnerAssignPanel
        partners={partners}
        selectedPartnerId={selectedPartnerId}
        isSaving={isSaving}
        isPartnerDirty={isPartnerDirty}
        onSelectedPartnerIdChange={onSelectedPartnerIdChange}
        onPartnerSave={onPartnerSave}
      />

      <SchedulePanel
        selectedScheduledDate={selectedScheduledDate}
        selectedRequestedTime={selectedRequestedTime}
        isSaving={isSaving}
        hasScheduleChanges={hasScheduleChanges}
        onSelectedScheduledDateChange={onSelectedScheduledDateChange}
        onSelectedRequestedTimeChange={onSelectedRequestedTimeChange}
        onScheduleSave={onScheduleSave}
      />

      <PaymentPanel
        order={order}
        selectedPaymentStatus={selectedPaymentStatus}
        selectedPartnerPaymentStatus={selectedPartnerPaymentStatus}
        selectedReceiptType={selectedReceiptType}
        selectedReceiptStatus={selectedReceiptStatus}
        selectedOnsiteExtra={selectedOnsiteExtra}
        grandTotalWithOnsite={grandTotalWithOnsite}
        recomputedBalance={recomputedBalance}
        isSaving={isSaving}
        isPaymentDirty={isPaymentDirty}
        onSelectedPaymentStatusChange={onSelectedPaymentStatusChange}
        onSelectedPartnerPaymentStatusChange={onSelectedPartnerPaymentStatusChange}
        onSelectedReceiptTypeChange={onSelectedReceiptTypeChange}
        onSelectedReceiptStatusChange={onSelectedReceiptStatusChange}
        onSelectedOnsiteExtraChange={onSelectedOnsiteExtraChange}
        onPaymentSave={onPaymentSave}
      />

      <MessageActionsPanel
        order={order}
        isSaving={isSaving}
        isPreviewLoading={isPreviewLoading}
        canSendBalanceDue={canSendBalanceDue}
        balanceDueBlockedText={balanceDueBlockedText}
        canOpenAsRequest={canOpenAsRequest}
        asRequestBlockedText={asRequestBlockedText}
        messageActions={messageActions}
        onMessagePreview={onMessagePreview}
        onAsRequestOpen={onAsRequestOpen}
      />

      <RelatedPagesPanel onNavigate={onNavigate} />

      <CustomerDeliveryPanel
        order={order}
        isSaving={isSaving}
        isPreviewLoading={isPreviewLoading}
        hasCustomerVisiblePhotos={hasCustomerVisiblePhotos}
        customerPhotoReadyDraft={messageActions.customerPhotoReady}
        onMessagePreview={onMessagePreview}
      />

      {(notice || error) && (
        <div data-testid={error ? 'admin-action-error' : 'admin-action-notice'} style={{
          padding: 10,
          borderRadius: 6,
          background: error ? 'var(--danger-bg)' : 'var(--success-bg)',
          color: error ? 'var(--danger-fg)' : 'var(--success-fg)',
          fontSize: 12,
        }}>
          {error || notice}
        </div>
      )}

      <TimelinePanel timeline={timeline} />
    </aside>
  );
}
