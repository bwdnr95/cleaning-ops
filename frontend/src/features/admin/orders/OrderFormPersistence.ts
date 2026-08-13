import type { AdminOrder } from '../../../api/admin';
import { createOrderGroup, updateAdminOrderEdit } from '../../../api/admin';
import {
  changedPayload,
  toGroupCreatePayload,
  toGroupMetadataPayload,
  toLinePayload,
} from './OrderFormModel';
import type { OrderGroupForm } from './OrderFormTypes';
import type { OrderFormMode } from './OrderFormView';

interface PersistOrderFormInput {
  readonly mode: OrderFormMode;
  readonly orderId: string | null;
  readonly form: OrderGroupForm;
  readonly initialForm: OrderGroupForm | null;
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
}: PersistOrderFormInput): Promise<AdminOrder> {
  if (mode === 'edit') {
    if (!orderId) throw new Error('수정할 주문 ID가 없습니다.');
    return updateAdminOrderEdit(orderId, {
      line: changedPayload(
        toLinePayload(form.lines[0]),
        initialForm ? toLinePayload(initialForm.lines[0]) : {},
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
