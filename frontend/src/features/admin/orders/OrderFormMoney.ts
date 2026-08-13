import { getAppTodayValue } from '../../../domain/time';
import type {
  OrderLineForm,
  OrderMoneyField,
  OrderRecalculationSource,
} from './OrderFormTypes';

export function todayString() {
  return getAppTodayValue();
}

export function emptyToNull(value: string) {
  return value === '' ? null : value;
}

export function numberOrNull(value: string) {
  return parseMoneyInput(value);
}

export function netConsumerAmount(line: OrderLineForm) {
  const gross = parseMoneyInput(line.total_amount);
  if (gross === null) return null;
  const discount = parseMoneyInput(line.discount_amount) || 0;
  return Math.max(gross - discount, 0);
}

export function toInputNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined) return '';
  return formatMoneyInput(Math.round(Number(value)));
}

export function formatMoneyInput(value: string | number | null | undefined) {
  const digits = String(value ?? '').replace(/[^\d]/g, '');
  if (digits === '') return '';
  return Number(digits).toLocaleString();
}

export function parseMoneyInput(value: string | number | null | undefined) {
  const digits = String(value ?? '').replace(/[^\d]/g, '');
  if (digits === '') return null;
  return Number(digits);
}

function calculateBalanceAmount(totalAmount: string, depositAmount: string) {
  const total = parseMoneyInput(totalAmount);
  const deposit = parseMoneyInput(depositAmount);
  if (total === null || deposit === null) return '';
  return formatMoneyInput(Math.max(total - deposit, 0));
}

export function applyMoneyTouch(
  line: OrderLineForm,
  key: OrderMoneyField,
  formattedValue: string,
): OrderLineForm {
  const isTouched = formattedValue !== '';
  switch (key) {
    case 'total_amount':
      return { ...line, total_amount_touched: isTouched };
    case 'deposit_amount':
      return { ...line, deposit_amount_touched: isTouched };
    case 'balance_amount':
      return { ...line, balance_amount_touched: isTouched };
    case 'partner_payment_amount':
      return { ...line, partner_payment_amount_touched: isTouched };
    default:
      return line;
  }
}

export function recalculateLine(
  line: OrderLineForm,
  { source }: { readonly source: OrderRecalculationSource },
): OrderLineForm {
  const quantity = parseQuantity(line.size_or_quantity);
  const baseUnitPrice = Number(line.base_unit_price || 0);
  const partnerUnitPrice = Number(line.partner_unit_price || 0);
  const discount = parseMoneyInput(line.discount_amount) || 0;
  const onsiteExtra = parseMoneyInput(line.onsite_extra_amount) || 0;
  let next = { ...line };

  if (baseUnitPrice > 0 && (!next.total_amount_touched || next.total_amount === '')) {
    next = { ...next, total_amount: formatMoneyInput(Math.max(Math.round(baseUnitPrice * quantity), 0)), total_amount_touched: false };
  }
  if (partnerUnitPrice > 0 && (!next.partner_payment_amount_touched || next.partner_payment_amount === '')) {
    next = { ...next, partner_payment_amount: formatMoneyInput(Math.max(Math.round(partnerUnitPrice * quantity), 0)), partner_payment_amount_touched: false };
  }

  const netConsumer = Math.max((parseMoneyInput(next.total_amount) || 0) - discount, 0);
  const grandTotal = netConsumer + onsiteExtra;
  if (next.total_amount !== '' && (!next.deposit_amount_touched || next.deposit_amount === '')) {
    next = { ...next, deposit_amount: formatMoneyInput(Math.round(grandTotal * 0.3)), deposit_amount_touched: false };
  }
  if (
    !next.balance_amount_touched
    || next.balance_amount === ''
    || source === 'total_amount'
    || source === 'deposit_amount'
    || source === 'discount_amount'
    || source === 'onsite_extra_amount'
  ) {
    next = {
      ...next,
      balance_amount: calculateBalanceAmount(formatMoneyInput(grandTotal), next.deposit_amount),
      balance_amount_touched: false,
    };
  }
  return next;
}

function parseQuantity(value: string) {
  const match = String(value || '').replace(/,/g, '').match(/\d+(?:\.\d+)?/);
  if (!match) return 1;
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

export function formatWon(value: string | number | null | undefined) {
  const amount = Number(value || 0);
  return `₩${Math.round(amount).toLocaleString()}`;
}
