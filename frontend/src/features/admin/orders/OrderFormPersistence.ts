import type { AdminOrder, UpdateOrderInput } from '../../../api/admin';
import { createOrderGroup, updateAdminOrderEdit } from '../../../api/admin';
import {
  changedPayload,
  toGroupCreatePayload,
  toGroupMetadataPayload,
  toLinePayload,
} from './OrderFormModel';
import { NO_AMOUNT_LOCK, type OrderFormAmountLock, type OrderGroupForm } from './OrderFormTypes';
import type { OrderFormMode } from './OrderFormView';

interface PersistOrderFormInput {
  readonly mode: OrderFormMode;
  readonly orderId: string | null;
  readonly form: OrderGroupForm;
  readonly initialForm: OrderGroupForm | null;
  readonly amountLock?: OrderFormAmountLock;
}

// 서버 오류코드를 운영자 문장으로 바꾼다. 매핑이 없으면 원문을 그대로 보여준다.
const SAVE_ERROR_MESSAGES: Record<string, string> = {
  recurring_customer_payment_not_per_visit:
    '월 청구 정기계약 주문이라 주문별 소비자가를 입력할 수 없습니다. 금액은 정기청소 > 계약에서 수정하세요.',
  recurring_partner_payment_not_per_visit:
    '월 청구(월 정산) 정기계약 주문이라 주문별 도급가·정산상태를 입력할 수 없습니다. 도급가는 정기청소 > 계약, 정산은 월 트래커에서 처리하세요.',
  recurring_partner_payment_date_required:
    '방문 예정일이 있어야 협력사 도급가를 정할 수 있습니다. 방문일을 먼저 지정해주세요.',
  order_partner_history_locked:
    '작업 이력(사진·정산·완료)이 남은 주문이라 협력사를 바꿀 수 없습니다.',
  partner_not_found: '선택한 협력사를 찾을 수 없습니다. 협력사 목록을 새로고침해주세요.',
  partner_inactive: '비활성화된 협력사입니다. 먼저 활성화하거나 다른 협력사를 선택해주세요.',
};

export function orderSaveErrorMessage(error: unknown): string {
  const raw = error instanceof Error && error.message ? error.message : '';
  return SAVE_ERROR_MESSAGES[raw] || raw || '주문을 저장하지 못했습니다.';
}

// 잠긴 금액 필드는 아예 보내지 않는다(서버가 값이 실린 요청을 400 으로 거부한다).
function stripLockedAmounts(
  payload: Partial<UpdateOrderInput>,
  lock: OrderFormAmountLock,
): Partial<UpdateOrderInput> {
  const next = { ...payload };
  if (lock.customerAmount) {
    delete next.total_amount;
    delete next.discount_amount;
    delete next.deposit_amount;
    delete next.balance_amount;
  }
  if (lock.partnerAmount) {
    delete next.partner_payment_amount;
    delete next.partner_payment_status;
  }
  return next;
}

export function validateOrderForm(form: OrderGroupForm): string | null {
  if (!form.customer_name.trim() || !form.customer_phone.trim() || !form.customer_address.trim()) {
    return '고객명, 연락처, 주소는 필수입니다.';
  }
  if (form.lines.some((line) => !line.service_name.trim())) {
    return '모든 라인의 상품명은 필수입니다.';
  }
  return null;
}

export async function persistOrderForm({
  mode,
  orderId,
  form,
  initialForm,
  amountLock = NO_AMOUNT_LOCK,
}: PersistOrderFormInput): Promise<AdminOrder> {
  if (mode === 'edit') {
    if (!orderId) throw new Error('수정할 주문 ID가 없습니다.');
    return updateAdminOrderEdit(orderId, {
      line: stripLockedAmounts(
        changedPayload(
          toLinePayload(form.lines[0]),
          initialForm ? toLinePayload(initialForm.lines[0]) : {},
        ),
        amountLock,
      ),
      group: changedPayload(
        toGroupMetadataPayload(form),
        initialForm ? toGroupMetadataPayload(initialForm) : {},
      ),
    });
  }

  const savedGroup = await createOrderGroup(toGroupCreatePayload(form));
  const savedOrder = savedGroup.lines[0];
  if (!savedOrder) throw new Error('저장된 주문 정보를 확인하지 못했습니다.');
  return savedOrder;
}
