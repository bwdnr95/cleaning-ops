import React from 'react';

import { orderWorkflowStatusValue } from '../../../domain/orderStatus';
import { isBalanceIncomplete } from '../../../domain/paymentStatus';
import { receiptStatusAfterTypeChange } from '../../../domain/receiptType';
import type { AdminOrderDetail } from './OrderDetailModel';
import { isAsRequestAllowedStatus, isBalanceNoticeAllowedStatus } from './OrderDetailRules';

export function useOrderDetailFormState(order: AdminOrderDetail | null) {
  const [selectedStatus, setSelectedStatus] = React.useState('');
  const [selectedPartnerId, setSelectedPartnerId] = React.useState('');
  const [selectedVisitDates, setSelectedVisitDates] = React.useState<readonly string[]>([]);
  const [selectedRequestedTime, setSelectedRequestedTime] = React.useState('');
  const [selectedPaymentStatus, setSelectedPaymentStatus] = React.useState('');
  const [selectedPartnerPaymentStatus, setSelectedPartnerPaymentStatus] = React.useState('');
  const [selectedReceiptType, setSelectedReceiptType] = React.useState('');
  const [selectedReceiptStatus, setSelectedReceiptStatus] = React.useState('');
  const [selectedOnsiteExtra, setSelectedOnsiteExtra] = React.useState('');

  React.useEffect(() => {
    if (!order) {
      return;
    }
    setSelectedStatus(orderWorkflowStatusValue(order.status, order.payment_status));
    setSelectedPartnerId(order.partner_id || '');
    setSelectedVisitDates(order.visit_dates || (order.scheduled_date ? [order.scheduled_date] : []));
    setSelectedRequestedTime(order.requested_time || '');
    setSelectedPaymentStatus(order.payment_status || '');
    setSelectedPartnerPaymentStatus(order.partner_payment_status || '');
    setSelectedReceiptType(order.receipt_type || '');
    setSelectedReceiptStatus(order.receipt_status || '');
    setSelectedOnsiteExtra(order.onsite_extra_amount != null ? String(order.onsite_extra_amount) : '');
  }, [order]);

  const displayStatus = order ? orderWorkflowStatusValue(order.status, order.payment_status) : '';
  const savedVisitDates = order?.visit_dates || (order?.scheduled_date ? [order.scheduled_date] : []);
  const hasVisitDateChanges = !sameStringList(selectedVisitDates, savedVisitDates);
  const hasUnsavedChanges = Boolean(order) && (
    selectedStatus !== displayStatus
    || selectedPartnerId !== (order?.partner_id || '')
    || hasVisitDateChanges
    || selectedRequestedTime !== (order?.requested_time || '')
    || selectedPaymentStatus !== (order?.payment_status || '')
    || selectedPartnerPaymentStatus !== (order?.partner_payment_status || '')
    || selectedReceiptType !== (order?.receipt_type || '')
    || selectedReceiptStatus !== (order?.receipt_status || '')
    || Number(selectedOnsiteExtra || 0) !== Number(order?.onsite_extra_amount || 0)
  );
  const hasScheduleChanges = Boolean(order) && (
    hasVisitDateChanges
    || selectedRequestedTime !== (order?.requested_time || '')
  );
  const isStatusDirty = Boolean(order) && selectedStatus !== displayStatus;
  const isPartnerDirty = Boolean(order) && selectedPartnerId !== (order?.partner_id || '');
  const isPaymentDirty = Boolean(order) && (
    selectedPaymentStatus !== (order?.payment_status || '')
    || selectedPartnerPaymentStatus !== (order?.partner_payment_status || '')
    || selectedReceiptType !== (order?.receipt_type || '')
    || selectedReceiptStatus !== (order?.receipt_status || '')
    || Number(selectedOnsiteExtra || 0) !== Number(order?.onsite_extra_amount || 0)
  );
  const onsiteExtraNumber = Number(selectedOnsiteExtra || 0);
  const grandTotalWithOnsite = Number(order?.total_amount || 0) + onsiteExtraNumber;
  const recomputedBalance = Math.max(grandTotalWithOnsite - Number(order?.deposit_amount || 0), 0);
  const visiblePhotos = order?.photos || [];
  const hasCustomerVisiblePhotos = visiblePhotos.some((photo) => photo.is_customer_visible);
  const paymentStatusForBalance = order?.payment_status || 'pending';
  const hasSavedBalanceDue = Boolean(order)
    && isBalanceIncomplete(paymentStatusForBalance)
    && Number(order?.balance_amount ?? recomputedBalance) > 0;
  const isBalanceNoticeWorkflowReady = isBalanceNoticeAllowedStatus(order?.status);
  const canSendBalanceDue = hasSavedBalanceDue && isBalanceNoticeWorkflowReady && !isPaymentDirty;
  const canSendBalanceDueAfterStatusChange = hasSavedBalanceDue
    && isBalanceNoticeAllowedStatus(selectedStatus)
    && !isPaymentDirty;
  const balanceDueBlockedText = isPaymentDirty
    ? '결제/정산 변경을 먼저 저장하세요.'
    : !isBalanceNoticeWorkflowReady
      ? '작업완료 이후 상태에서만 잔금 안내를 보낼 수 있습니다.'
      : '미수 잔금이 있는 주문에서만 발송합니다.';
  const isAsRequestWorkflowReady = isAsRequestAllowedStatus(order?.status);
  const hasAcceptedAsRequest = Boolean(order?.as_requested);
  const canOpenAsRequest = Boolean(order?.partner_id)
    && !hasAcceptedAsRequest
    && !hasUnsavedChanges
    && isAsRequestWorkflowReady;
  const asRequestBlockedText = !order?.partner_id
    ? '협력사 배정 후 AS 요청을 보낼 수 있습니다.'
    : hasAcceptedAsRequest
      ? '이미 협력사에 전달된 AS 요청입니다.'
      : hasUnsavedChanges
        ? '저장하지 않은 변경사항을 먼저 저장하세요.'
        : !isAsRequestWorkflowReady
          ? '작업완료 이후 또는 고객확인필요 상태에서 AS 요청을 보낼 수 있습니다.'
          : undefined;

  const setReceiptType = (next: string) => {
    setSelectedReceiptType(next);
    setSelectedReceiptStatus(receiptStatusAfterTypeChange(next, selectedReceiptStatus));
  };

  return {
    selectedStatus,
    selectedPartnerId,
    selectedVisitDates,
    selectedRequestedTime,
    selectedPaymentStatus,
    selectedPartnerPaymentStatus,
    selectedReceiptType,
    selectedReceiptStatus,
    selectedOnsiteExtra,
    setSelectedStatus,
    setSelectedPartnerId,
    setSelectedVisitDates,
    setSelectedRequestedTime,
    setSelectedPaymentStatus,
    setSelectedPartnerPaymentStatus,
    setSelectedReceiptType: setReceiptType,
    setSelectedReceiptStatus,
    setSelectedOnsiteExtra,
    displayStatus,
    hasUnsavedChanges,
    hasScheduleChanges,
    isStatusDirty,
    isPartnerDirty,
    isPaymentDirty,
    grandTotalWithOnsite,
    recomputedBalance,
    hasCustomerVisiblePhotos,
    hasSavedBalanceDue,
    canSendBalanceDue,
    canSendBalanceDueAfterStatusChange,
    balanceDueBlockedText,
    canOpenAsRequest,
    asRequestBlockedText,
    visiblePhotos,
    messageLogs: order?.message_logs || [],
    timeline: order?.timeline || [],
  };
}

function sameStringList(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}
