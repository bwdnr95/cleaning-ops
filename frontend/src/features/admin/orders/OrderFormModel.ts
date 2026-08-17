import type {
  AdminOrder,
  AdminOrderLineInput,
  OrderGroupCreateInput,
  OrderGroupUpdateInput,
} from '../../../api/admin';
import { ORDER_STATUSES, orderWorkflowStatusValue } from '../../../domain/orderStatus';
import { receiptStatusForPayload } from '../../../domain/receiptType';
import {
  emptyToNull,
  netConsumerAmount,
  numberOrNull,
  todayString,
  toInputNumber,
} from './OrderFormMoney';
import type {
  OrderFormServiceCategory,
  OrderFormServiceItem,
  OrderGroupForm,
  OrderLineForm,
} from './OrderFormTypes';

type OrderFormSource = AdminOrder & {
  readonly group_notes?: string | null;
  readonly notes?: string | null;
  readonly source_channel?: string | null;
  readonly customer_visible_payment?: boolean;
};

export function createEmptyGroupForm(): OrderGroupForm {
  return {
    group_id: '', customer_name: '', customer_phone: '', customer_address: '',
    customer_address_detail: '', source_channel: '', customer_visible_payment: false,
    notes: '', lines: [createEmptyLineForm()],
  };
}

export function createEmptyLineForm(): OrderLineForm {
  return {
    local_id: crypto.randomUUID(), status: ORDER_STATUSES[0], received_date: todayString(),
    scheduled_date: '', visit_dates: [], requested_time: '', partner_id: '', team_name: '', broker_id: '',
    service_category_id: '', service_item_id: '', service_name: '', size_or_quantity: '',
    service_detail: '', special_request: '', total_amount: '', discount_amount: '',
    deposit_amount: '', balance_amount: '', onsite_extra_amount: '', vat_type: 'included',
    payment_status: '', payment_memo: '', evidence_memo: '', receipt_type: '',
    receipt_status: '', partner_payment_amount: '', partner_payment_status: '',
    broker_payment_amount: '', partner_settled_at: null, base_unit_price: '',
    partner_unit_price: '', total_amount_touched: false, deposit_amount_touched: false,
    balance_amount_touched: false, partner_payment_amount_touched: false,
  };
}

export function toForm(order: OrderFormSource): OrderGroupForm {
  return {
    group_id: order.group_id || '', customer_name: order.customer_name || '',
    customer_phone: order.customer_phone || '', customer_address: order.customer_address || '',
    customer_address_detail: order.customer_address_detail || '',
    source_channel: order.source_channel || '',
    customer_visible_payment: Boolean(order.customer_visible_payment),
    notes: order.group_notes ?? order.notes ?? '', lines: [toLineForm(order)],
  };
}

export function toDuplicateForm(order: OrderFormSource): OrderGroupForm {
  return {
    ...createEmptyGroupForm(), customer_name: order.customer_name || '',
    customer_phone: order.customer_phone || '', customer_address: order.customer_address || '',
    customer_address_detail: order.customer_address_detail || '',
    source_channel: order.source_channel || '',
    customer_visible_payment: Boolean(order.customer_visible_payment),
  };
}

function toLineForm(order: OrderFormSource): OrderLineForm {
  return {
    ...createEmptyLineForm(),
    status: orderWorkflowStatusValue(order.status, order.payment_status) || ORDER_STATUSES[0],
    received_date: order.received_date || todayString(), scheduled_date: order.scheduled_date || '',
    visit_dates: order.visit_dates || (order.scheduled_date ? [order.scheduled_date] : []),
    requested_time: order.requested_time || '', partner_id: order.partner_id || '',
    team_name: order.team_name || '', broker_id: order.broker_id || '',
    service_category_id: order.service_category_id || '', service_item_id: order.service_item_id || '',
    service_name: order.service_name || '', size_or_quantity: order.size_or_quantity || '',
    service_detail: order.service_detail || '', special_request: order.special_request || '',
    total_amount: order.total_amount == null
      ? toInputNumber(order.total_amount)
      : toInputNumber((Number(order.total_amount) || 0) + (Number(order.discount_amount) || 0)),
    discount_amount: toInputNumber(order.discount_amount), deposit_amount: toInputNumber(order.deposit_amount),
    balance_amount: toInputNumber(order.balance_amount), onsite_extra_amount: toInputNumber(order.onsite_extra_amount),
    vat_type: order.vat_type || 'included', payment_status: order.payment_status || '',
    payment_memo: order.payment_memo || '', evidence_memo: order.evidence_memo || '',
    receipt_type: order.receipt_type || '', receipt_status: order.receipt_status || '',
    partner_payment_amount: toInputNumber(order.partner_payment_amount),
    partner_payment_status: order.partner_payment_status || '',
    broker_payment_amount: toInputNumber(order.broker_payment_amount),
    partner_settled_at: order.partner_settled_at || null,
  };
}

export function toGroupCreatePayload(form: OrderGroupForm): OrderGroupCreateInput {
  return { ...toGroupMetadataPayload(form), lines: form.lines.map(toLinePayload) };
}

export function toGroupMetadataPayload(form: OrderGroupForm): OrderGroupUpdateInput & {
  readonly customer_name: string;
  readonly customer_phone: string;
  readonly customer_address: string;
} {
  return {
    customer_name: form.customer_name.trim(), customer_phone: form.customer_phone.trim(),
    customer_address: form.customer_address.trim(),
    customer_address_detail: emptyToNull(form.customer_address_detail.trim()),
    source_channel: emptyToNull(form.source_channel),
    customer_visible_payment: form.customer_visible_payment, notes: emptyToNull(form.notes),
  };
}

export function toLinePayload(line: OrderLineForm): AdminOrderLineInput {
  return {
    status: line.status, received_date: line.received_date,
    scheduled_date: emptyToNull(line.visit_dates[0] || line.scheduled_date),
    visit_dates: line.visit_dates,
    requested_time: emptyToNull(line.requested_time),
    partner_id: emptyToNull(line.partner_id), team_name: emptyToNull(line.team_name),
    broker_id: emptyToNull(line.broker_id), service_category_id: emptyToNull(line.service_category_id),
    service_item_id: emptyToNull(line.service_item_id), service_name: line.service_name.trim(),
    size_or_quantity: emptyToNull(line.size_or_quantity), service_detail: emptyToNull(line.service_detail),
    special_request: emptyToNull(line.special_request), total_amount: netConsumerAmount(line),
    discount_amount: numberOrNull(line.discount_amount) || 0, deposit_amount: numberOrNull(line.deposit_amount),
    balance_amount: numberOrNull(line.balance_amount), onsite_extra_amount: numberOrNull(line.onsite_extra_amount),
    vat_type: emptyToNull(line.vat_type), payment_status: emptyToNull(line.payment_status),
    payment_memo: emptyToNull(line.payment_memo), evidence_memo: emptyToNull(line.evidence_memo),
    receipt_type: emptyToNull(line.receipt_type),
    receipt_status: receiptStatusForPayload(line.receipt_type, line.receipt_status),
    partner_payment_amount: numberOrNull(line.partner_payment_amount),
    partner_payment_status: emptyToNull(line.partner_payment_status),
    broker_payment_amount: numberOrNull(line.broker_payment_amount),
  };
}

export function changedPayload<T extends object>(nextPayload: T, previousPayload: Partial<T>): Partial<T> {
  const result: Partial<T> = {};
  for (const key in nextPayload) {
    const nextValue = nextPayload[key];
    const previousValue = previousPayload[key];
    const isEqual = Array.isArray(nextValue) && Array.isArray(previousValue)
      ? nextValue.length === previousValue.length
        && nextValue.every((value, index) => value === previousValue[index])
      : nextValue === previousValue;
    if (!isEqual) {
      result[key] = nextPayload[key];
    }
  }
  return result;
}

export function getServiceItems(
  categories: readonly OrderFormServiceCategory[],
  categoryId: string,
): readonly OrderFormServiceItem[] {
  return categories
    .filter((category) => category.id === categoryId)
    .flatMap((category) => (category.items || []).filter((item) => item.is_active));
}
