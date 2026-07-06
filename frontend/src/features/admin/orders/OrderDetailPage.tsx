import React from 'react';

import { getAdminOrder, listPartners } from '../../../api/admin';
import { getAdminMessageSettings } from '../../../api/messages';
import { useApiResource } from '../../../api/useApiResource';
import { useIsNarrowViewport } from '../../../components/common/useIsNarrowViewport';
import { MessagePreviewModal } from './MessagePreviewModal';
import { OrderAsRequestModal } from './OrderAsRequestModal';
import { OrderDetailHeader } from './OrderDetailHeader';
import { OrderDetailSidebar } from './OrderDetailSidebar';
import { OrderDetailSummarySections } from './OrderDetailSummarySections';
import {
  normalizeHttpUrl,
  toActionErrorMessage,
} from './OrderDetailFormat';
import { DetailState } from './OrderDetailPrimitives';
import { MESSAGE_ACTIONS } from './OrderDetailRules';
import { useOrderDetailFormState } from './useOrderDetailFormState';
import { useOrderDetailMessagePreview } from './useOrderDetailMessagePreview';
import { useOrderDetailMutations } from './useOrderDetailMutations';

export function OrderDetailPage({ orderId, onBack, onEdit, onDuplicate, onNav, onOpenOrder, onOpenRecurringContract }) {
  const loadOrder = React.useCallback(() => getAdminOrder(orderId), [orderId]);
  const orderResource = useApiResource(loadOrder, orderId);
  const partnersResource = useApiResource(listPartners);
  const messageSettingsResource = useApiResource(getAdminMessageSettings);
  const order = orderResource.data;
  const detailForm = useOrderDetailFormState(order);
  const isNarrowViewport = useIsNarrowViewport();
  const [isSaving, setIsSaving] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [notice, setNotice] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [isAsRequestModalOpen, setIsAsRequestModalOpen] = React.useState(false);

  const runAction = React.useCallback(async (action) => {
    setError(null);
    setNotice(null);
    setIsSaving(true);
    try {
      await action();
    } catch (requestError) {
      setError(toActionErrorMessage(requestError));
    } finally {
      setIsSaving(false);
    }
  }, []);

  const messagePreview = useOrderDetailMessagePreview({
    order,
    reloadOrder: orderResource.reload,
    runAction,
    setNotice,
    setError,
  });

  const mutations = useOrderDetailMutations({
    order,
    partners: partnersResource.data || [],
    selectedStatus: detailForm.selectedStatus,
    selectedPartnerId: detailForm.selectedPartnerId,
    selectedScheduledDate: detailForm.selectedScheduledDate,
    selectedRequestedTime: detailForm.selectedRequestedTime,
    selectedPaymentStatus: detailForm.selectedPaymentStatus,
    selectedPartnerPaymentStatus: detailForm.selectedPartnerPaymentStatus,
    selectedReceiptType: detailForm.selectedReceiptType,
    selectedReceiptStatus: detailForm.selectedReceiptStatus,
    selectedOnsiteExtra: detailForm.selectedOnsiteExtra,
    canSendBalanceDueAfterStatusChange: detailForm.canSendBalanceDueAfterStatusChange,
    isPaymentDirty: detailForm.isPaymentDirty,
    hasUnsavedChanges: detailForm.hasUnsavedChanges,
    reloadOrder: orderResource.reload,
    runAction,
    openMessagePreview: messagePreview.openMessagePreview,
    setNotice,
    setError,
    setIsDeleting,
    setIsAsRequestModalOpen,
    onBack,
  });

  React.useEffect(() => {
    if (!detailForm.hasUnsavedChanges) {
      return undefined;
    }
    const handleBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [detailForm.hasUnsavedChanges]);

  const confirmLeaveIfDirty = React.useCallback(
    () => !detailForm.hasUnsavedChanges || window.confirm('저장하지 않은 변경이 있습니다. 저장하지 않고 이동할까요?'),
    [detailForm.hasUnsavedChanges],
  );

  const navigateWithGuard = React.useCallback(
    (page) => { if (confirmLeaveIfDirty()) { onNav?.(page); } },
    [confirmLeaveIfDirty, onNav],
  );

  if (orderResource.isLoading) {
    return <DetailState text="주문 상세를 불러오는 중입니다." onBack={onBack} />;
  }

  if (orderResource.error) {
    return <DetailState text="주문 상세를 불러오지 못했습니다." tone="danger" onBack={onBack} />;
  }

  if (!order) {
    return <DetailState text="주문을 찾을 수 없습니다." onBack={onBack} />;
  }

  const selectedPartner = (partnersResource.data || []).find((partner) => partner.id === order.partner_id);
  const kakaoChannelUrl = normalizeHttpUrl(messageSettingsResource.data?.kakao_channel_url);

  return (
    <div data-testid="admin-order-detail-page" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--bg)' }}>
      <OrderDetailHeader
        order={order}
        displayStatus={detailForm.displayStatus}
        hasUnsavedChanges={detailForm.hasUnsavedChanges}
        isDeleting={isDeleting}
        onBack={() => { if (confirmLeaveIfDirty()) onBack(); }}
        onEdit={() => { if (confirmLeaveIfDirty()) onEdit(); }}
        onDuplicate={onDuplicate ? () => { if (confirmLeaveIfDirty()) onDuplicate(); } : undefined}
        onRefresh={orderResource.reload}
        onDelete={() => void mutations.handleDelete()}
        onOpenCalendar={() => navigateWithGuard('calendar')}
        onOpenRecurringContract={onOpenRecurringContract}
        isCompact={isNarrowViewport}
      />

      <div className="scroll" style={{ flex: 1, overflow: 'auto', padding: isNarrowViewport ? 12 : 20 }}>
        <div className="page-shell" style={{ display: 'grid', gridTemplateColumns: isNarrowViewport ? 'minmax(0, 1fr)' : 'minmax(0, 1fr) 320px', gap: isNarrowViewport ? 12 : 16 }}>
          <OrderDetailSummarySections
            order={order}
            selectedPartner={selectedPartner}
            visiblePhotos={detailForm.visiblePhotos}
            messageLogs={detailForm.messageLogs}
            kakaoChannelUrl={kakaoChannelUrl}
          />

          <OrderDetailSidebar
            order={order}
            displayStatus={detailForm.displayStatus}
            partners={partnersResource.data || []}
            selectedStatus={detailForm.selectedStatus}
            selectedPartnerId={detailForm.selectedPartnerId}
            selectedScheduledDate={detailForm.selectedScheduledDate}
            selectedRequestedTime={detailForm.selectedRequestedTime}
            selectedPaymentStatus={detailForm.selectedPaymentStatus}
            selectedPartnerPaymentStatus={detailForm.selectedPartnerPaymentStatus}
            selectedReceiptType={detailForm.selectedReceiptType}
            selectedReceiptStatus={detailForm.selectedReceiptStatus}
            selectedOnsiteExtra={detailForm.selectedOnsiteExtra}
            grandTotalWithOnsite={detailForm.grandTotalWithOnsite}
            recomputedBalance={detailForm.recomputedBalance}
            timeline={detailForm.timeline}
            siblings={order.sibling_lines || []}
            notice={notice}
            error={error}
            isSticky={!isNarrowViewport}
            isSaving={isSaving}
            isPreviewLoading={messagePreview.isPreviewLoading}
            hasUnsavedChanges={detailForm.hasUnsavedChanges}
            hasScheduleChanges={detailForm.hasScheduleChanges}
            isStatusDirty={detailForm.isStatusDirty}
            isPartnerDirty={detailForm.isPartnerDirty}
            isPaymentDirty={detailForm.isPaymentDirty}
            hasCustomerVisiblePhotos={detailForm.hasCustomerVisiblePhotos}
            hasSavedBalanceDue={detailForm.hasSavedBalanceDue}
            canSendBalanceDue={detailForm.canSendBalanceDue}
            balanceDueBlockedText={detailForm.balanceDueBlockedText}
            canOpenAsRequest={detailForm.canOpenAsRequest}
            asRequestBlockedText={detailForm.asRequestBlockedText}
            onSelectedStatusChange={detailForm.setSelectedStatus}
            onSelectedPartnerIdChange={detailForm.setSelectedPartnerId}
            onSelectedScheduledDateChange={detailForm.setSelectedScheduledDate}
            onSelectedRequestedTimeChange={detailForm.setSelectedRequestedTime}
            onSelectedPaymentStatusChange={detailForm.setSelectedPaymentStatus}
            onSelectedPartnerPaymentStatusChange={detailForm.setSelectedPartnerPaymentStatus}
            onSelectedReceiptTypeChange={detailForm.setSelectedReceiptType}
            onSelectedReceiptStatusChange={detailForm.setSelectedReceiptStatus}
            onSelectedOnsiteExtraChange={detailForm.setSelectedOnsiteExtra}
            onStatusSave={() => void mutations.handleStatusChange()}
            onPartnerSave={() => void mutations.handlePartnerAssign()}
            onScheduleSave={() => void mutations.handleScheduleUpdate()}
            onPaymentSave={() => void mutations.handlePaymentUpdate()}
            onMessagePreview={(draft) => void messagePreview.openMessagePreview(draft)}
            onAsRequestOpen={mutations.openAsRequestModal}
            onNavigate={navigateWithGuard}
            onOpenOrder={onOpenOrder}
            messageActions={MESSAGE_ACTIONS}
          />
        </div>
      </div>
      <MessagePreviewModal
        draft={messagePreview.messageDraft}
        channel={messagePreview.messagePreviewChannel}
        preview={messagePreview.messagePreviewData}
        previewError={messagePreview.messagePreviewError}
        isLoading={messagePreview.isPreviewLoading}
        isSaving={isSaving}
        onChannelChange={messagePreview.handlePreviewChannelChange}
        onClose={messagePreview.closeMessagePreview}
        onConfirm={messagePreview.handleConfirmMessageSend}
      />
      <OrderAsRequestModal
        open={isAsRequestModalOpen}
        defaultMemo={order.as_memo || ''}
        customerName={order.customer_name}
        serviceName={order.service_name}
        partnerName={order.team_name || selectedPartner?.name || '배정 협력사'}
        isSaving={isSaving}
        onClose={() => setIsAsRequestModalOpen(false)}
        onSubmit={mutations.handleAsRequestSubmit}
      />
    </div>
  );
}
