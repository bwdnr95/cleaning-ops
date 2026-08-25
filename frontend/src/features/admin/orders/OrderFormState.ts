import { receiptStatusAfterTypeChange } from '../../../domain/receiptType';
import { createEmptyLineForm, getServiceItems } from './OrderFormModel';
import { applyMoneyTouch, formatMoneyInput, parseMoneyInput, recalculateLine } from './OrderFormMoney';
import type {
  OrderFormAmountLock,
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

/**
 * 잠긴 금액 필드를 불러온 값(baseline)으로 되돌린다.
 *
 * 상세상품 선택·수량 변경은 단가 기준으로 금액을 자동 계산하는데, 월 청구 정기 주문에서는
 * 그 값이 저장될 수 없다(서버가 거부). 계산 결과를 화면에 보여주고 저장만 막으면 운영자가
 * 저장된 줄 알기 때문에, 자동 계산 자체를 되돌려 화면과 저장 결과를 일치시킨다.
 */
export function enforceAmountLock(
  form: OrderGroupForm,
  lock: OrderFormAmountLock,
  baseline: OrderLineForm | null,
): OrderGroupForm {
  if (!baseline || (!lock.customerAmount && !lock.partnerAmount)) return form;
  return {
    ...form,
    lines: form.lines.map((line) => ({
      ...line,
      // 계약금·잔금은 소비자가에서 파생되므로 함께 되돌린다. 그러지 않으면 상세상품 선택 때
      // 자동 계산된 계약금(소비자가 30%)만 남아 월 청구 주문에 엉뚱한 금액이 저장된다.
      ...(lock.customerAmount ? {
        total_amount: baseline.total_amount,
        discount_amount: baseline.discount_amount,
        deposit_amount: baseline.deposit_amount,
        balance_amount: baseline.balance_amount,
        total_amount_touched: baseline.total_amount_touched,
        deposit_amount_touched: baseline.deposit_amount_touched,
        balance_amount_touched: baseline.balance_amount_touched,
      } : {}),
      ...(lock.partnerAmount ? {
        partner_payment_amount: baseline.partner_payment_amount,
        partner_payment_status: baseline.partner_payment_status,
        partner_payment_amount_touched: baseline.partner_payment_amount_touched,
      } : {}),
    })),
  };
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
