import { deleteAdminOrder, sendOrderAsRequest, updateAdminOrder } from '../../../api/admin';
import { orderStatusLabel } from '../../../domain/orderStatus';
import { receiptStatusForPayload } from '../../../domain/receiptType';
import type { AdminOrderDetail, AdminPartnerOption, MessageActionDraft } from './OrderDetailModel';
import { isAsRequestAllowedStatus, MESSAGE_ACTIONS, WORK_DONE_STATUS } from './OrderDetailRules';

interface UseOrderDetailMutationsInput {
  readonly order: AdminOrderDetail | null;
  readonly partners: readonly AdminPartnerOption[];
  readonly selectedStatus: string;
  readonly selectedPartnerId: string;
  readonly selectedVisitDates: readonly string[];
  readonly selectedRequestedTime: string;
  readonly selectedPaymentStatus: string;
  readonly selectedPartnerPaymentStatus: string;
  readonly selectedReceiptType: string;
  readonly selectedReceiptStatus: string;
  readonly selectedOnsiteExtra: string;
  readonly canSendBalanceDueAfterStatusChange: boolean;
  readonly isPaymentDirty: boolean;
  readonly hasUnsavedChanges: boolean;
  readonly reloadOrder: () => void;
  readonly runAction: (action: () => Promise<void>) => Promise<void>;
  readonly openMessagePreview: (draft: MessageActionDraft) => Promise<boolean>;
  readonly setNotice: (notice: string) => void;
  readonly setError: (error: string) => void;
  readonly setIsDeleting: (isDeleting: boolean) => void;
  readonly setIsAsRequestModalOpen: (isOpen: boolean) => void;
  readonly onBack: () => void;
}

export function useOrderDetailMutations({
  order,
  partners,
  selectedStatus,
  selectedPartnerId,
  selectedVisitDates,
  selectedRequestedTime,
  selectedPaymentStatus,
  selectedPartnerPaymentStatus,
  selectedReceiptType,
  selectedReceiptStatus,
  selectedOnsiteExtra,
  canSendBalanceDueAfterStatusChange,
  isPaymentDirty,
  hasUnsavedChanges,
  reloadOrder,
  runAction,
  openMessagePreview,
  setNotice,
  setError,
  setIsDeleting,
  setIsAsRequestModalOpen,
  onBack,
}: UseOrderDetailMutationsInput) {
  const handleStatusChange = async () => {
    if (!order) return;
    const enteredWorkDone = selectedStatus === WORK_DONE_STATUS && order.status !== WORK_DONE_STATUS;
    await runAction(async () => {
      const selectedStatusLabel = orderStatusLabel(selectedStatus);
      await updateAdminOrder(order.id, { status: selectedStatus });
      reloadOrder();
      if (enteredWorkDone && canSendBalanceDueAfterStatusChange) {
        const previewOpened = await openMessagePreview(MESSAGE_ACTIONS.customerBalanceDue);
        if (!previewOpened) {
          setError(`${selectedStatusLabel} 상태는 저장됐습니다. 잔금 안내 미리보기만 불러오지 못했으니 '잔금 안내' 버튼으로 다시 시도하세요.`);
        }
      } else {
        const balanceNotice = enteredWorkDone
          ? isPaymentDirty
            ? ' 결제/정산 변경이 있어 잔금 안내는 자동으로 열지 않았습니다.'
            : ' 완납 또는 잔금 없음 상태라 잔금 안내는 생략했습니다.'
          : '';
        setNotice(`${selectedStatusLabel} 상태 변경을 타임라인에 기록했습니다.${balanceNotice}`);
      }
    });
  };

  const handlePartnerAssign = async () => {
    if (!order) return;
    const partner = partners.find((item) => item.id === selectedPartnerId);
    await runAction(async () => {
      await updateAdminOrder(order.id, {
        partner_id: selectedPartnerId || null,
        team_name: partner?.name || null,
      });
      setNotice('협력사 배정을 타임라인에 기록했습니다.');
      reloadOrder();
    });
  };

  const handleScheduleUpdate = async () => {
    if (!order) return;
    await runAction(async () => {
      await updateAdminOrder(order.id, {
        visit_dates: selectedVisitDates,
        requested_time: selectedRequestedTime || null,
      });
      setNotice('방문 일정 변경을 타임라인에 기록했습니다.');
      reloadOrder();
    });
  };

  const handlePaymentUpdate = async () => {
    if (!order) return;
    await runAction(async () => {
      const onsite = Number(selectedOnsiteExtra || 0);
      const balance = Math.max(Number(order.total_amount || 0) + onsite - Number(order.deposit_amount || 0), 0);
      await updateAdminOrder(order.id, {
        payment_status: selectedPaymentStatus || null,
        partner_payment_status: selectedPartnerPaymentStatus || null,
        receipt_type: selectedReceiptType || null,
        receipt_status: receiptStatusForPayload(selectedReceiptType, selectedReceiptStatus),
        onsite_extra_amount: onsite,
        balance_amount: balance,
      });
      setNotice('결제/정산 변경을 타임라인에 기록했습니다.');
      reloadOrder();
    });
  };

  const openAsRequestModal = () => {
    if (!order?.partner_id) {
      setError('협력사 배정 후 AS 요청을 보낼 수 있습니다.');
      return;
    }
    if (order.as_requested) {
      setError('이미 협력사에 전달된 AS 요청입니다.');
      return;
    }
    if (hasUnsavedChanges) {
      setError('저장하지 않은 변경사항을 먼저 저장한 뒤 AS 요청을 보내세요.');
      return;
    }
    if (!isAsRequestAllowedStatus(order.status)) {
      setError('AS 요청은 작업완료 이후 또는 고객확인필요 상태에서 보낼 수 있습니다.');
      return;
    }
    setError('');
    setNotice('');
    setIsAsRequestModalOpen(true);
  };

  const handleAsRequestSubmit = async (memo: string) => {
    if (!order) return;
    if (order.as_requested) {
      setError('이미 협력사에 전달된 AS 요청입니다.');
      setIsAsRequestModalOpen(false);
      return;
    }
    await runAction(async () => {
      await sendOrderAsRequest(order.id, memo);
      setIsAsRequestModalOpen(false);
      setNotice('AS 요청 상태로 전환하고 협력사/고객 안내를 발송했습니다.');
      reloadOrder();
    });
  };

  const handleDelete = async () => {
    if (!order) return;
    const ok = window.confirm(
      `이 주문(${order.id})을 삭제하시겠습니까?\n\n`
      + '운영 기록(타임라인, 메시지 로그, 사진)은 보존되지만 목록에서는 사라집니다.',
    );
    if (!ok) return;

    setError('');
    setNotice('');
    setIsDeleting(true);
    try {
      await deleteAdminOrder(order.id);
      onBack();
    } catch (requestError) {
      setError(`삭제 실패: ${requestError instanceof Error ? requestError.message : String(requestError)}`);
    } finally {
      setIsDeleting(false);
    }
  };

  return {
    handleStatusChange,
    handlePartnerAssign,
    handleScheduleUpdate,
    handlePaymentUpdate,
    openAsRequestModal,
    handleAsRequestSubmit,
    handleDelete,
  };
}
