import { receiptStatusAfterTypeChange } from '../../../domain/receiptType';
import { createEmptyLineForm, getServiceItems } from './OrderFormModel';
import { applyMoneyTouch, formatMoneyInput, parseMoneyInput, recalculateLine } from './OrderFormMoney';
import type {
  OrderFormGroupField,
  OrderFormPartner,
  OrderFormServiceCategory,
  OrderGroupForm,
  OrderLineField,
  OrderLineForm,
  OrderMoneyField,
} from './OrderFormTypes';

function replaceLine(form: OrderGroupForm, lineIndex: number, line: OrderLineForm): OrderGroupForm {
  return {
    ...form,
    lines: form.lines.map((currentLine, index) => (index === lineIndex ? line : currentLine)),
  };
}

export function updateGroupField<K extends OrderFormGroupField>(
  form: OrderGroupForm,
  key: K,
  value: OrderGroupForm[K],
): OrderGroupForm {
  return { ...form, [key]: value };
}

export function updateLineField<K extends OrderLineField>(
  form: OrderGroupForm,
  lineIndex: number,
  key: K,
  value: OrderLineForm[K],
): OrderGroupForm {
  let nextLine: OrderLineForm = { ...form.lines[lineIndex], [key]: value };
  if (key === 'size_or_quantity') {
    nextLine = recalculateLine(nextLine, { source: 'quantity' });
  }
  return replaceLine(form, lineIndex, nextLine);
}

export function updateVisitDates(
  form: OrderGroupForm,
  lineIndex: number,
  visitDates: readonly string[],
): OrderGroupForm {
  const normalized = [...new Set(visitDates)].sort();
  return replaceLine(form, lineIndex, {
    ...form.lines[lineIndex],
    scheduled_date: normalized[0] || '',
    visit_dates: normalized,
  });
}

export function addOrderLine(form: OrderGroupForm): OrderGroupForm {
  return { ...form, lines: [...form.lines, createEmptyLineForm()] };
}

export function removeOrderLine(form: OrderGroupForm, lineIndex: number): OrderGroupForm {
  if (form.lines.length <= 1) return form;
  return { ...form, lines: form.lines.filter((_, index) => index !== lineIndex) };
}

export function updateMoneyField(
  form: OrderGroupForm,
  lineIndex: number,
  key: OrderMoneyField,
  value: string,
): OrderGroupForm {
  const formattedValue = formatMoneyInput(value);
  let nextLine: OrderLineForm = { ...form.lines[lineIndex], [key]: formattedValue };
  nextLine = applyMoneyTouch(nextLine, key, formattedValue);
  nextLine = recalculateLine(nextLine, { source: key });
  return replaceLine(form, lineIndex, nextLine);
}

export function updatePartner(
  form: OrderGroupForm,
  lineIndex: number,
  partnerId: string,
  partners: readonly OrderFormPartner[],
): OrderGroupForm {
  const partner = partners.find((item) => item.id === partnerId);
  const nextLine = {
    ...recalculateLine(form.lines[lineIndex], { source: 'partner' }),
    partner_id: partnerId,
    team_name: partner?.name || '',
  };
  return replaceLine(form, lineIndex, nextLine);
}

export function updateServiceCategory(
  form: OrderGroupForm,
  lineIndex: number,
  categoryId: string,
): OrderGroupForm {
  return replaceLine(form, lineIndex, {
    ...form.lines[lineIndex],
    service_category_id: categoryId,
    service_item_id: '',
    base_unit_price: '',
    partner_unit_price: '',
  });
}

export function updateServiceItem(
  form: OrderGroupForm,
  lineIndex: number,
  serviceItemId: string,
  categories: readonly OrderFormServiceCategory[],
): OrderGroupForm {
  const currentLine = form.lines[lineIndex];
  const option = getServiceItems(categories, currentLine.service_category_id)
    .find((item) => item.id === serviceItemId);
  const nextLine = recalculateLine({
    ...currentLine,
    service_item_id: serviceItemId,
    service_name: option?.name || currentLine.service_name,
    base_unit_price: option ? String(option.base_price || 0) : '',
    partner_unit_price: option ? String(option.partner_base_price || 0) : '',
  }, { source: 'service_item' });
  return replaceLine(form, lineIndex, nextLine);
}

export function updateReceiptType(
  form: OrderGroupForm,
  lineIndex: number,
  receiptType: string,
): OrderGroupForm {
  const currentLine = form.lines[lineIndex];
  return replaceLine(form, lineIndex, {
    ...currentLine,
    receipt_type: receiptType,
    receipt_status: receiptStatusAfterTypeChange(receiptType, currentLine.receipt_status),
  });
}

export function hasPartnerPriceWarning(form: OrderGroupForm): boolean {
  return form.lines.some((line) => {
    const net = Math.max(
      (parseMoneyInput(line.total_amount) || 0) - (parseMoneyInput(line.discount_amount) || 0),
      0,
    );
    return net > 0 && (parseMoneyInput(line.partner_payment_amount) || 0) > net;
  });
}
