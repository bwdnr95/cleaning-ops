export interface OrderFormServiceItem {
  readonly id: string;
  readonly name: string;
  readonly base_price?: number | null;
  readonly partner_base_price?: number | null;
  readonly is_active: boolean;
}

export interface OrderFormServiceCategory {
  readonly id: string;
  readonly name: string;
  readonly is_active: boolean;
  readonly items?: readonly OrderFormServiceItem[];
}

export interface OrderFormPartner {
  readonly id: string;
  readonly name: string;
}

export interface OrderFormBroker {
  readonly id: string;
  readonly name: string;
}

export interface OrderLineForm {
  readonly local_id: string;
  readonly status: string;
  readonly received_date: string;
  readonly scheduled_date: string;
  readonly visit_dates: readonly string[];
  readonly requested_time: string;
  readonly partner_id: string;
  readonly team_name: string;
  readonly broker_id: string;
  readonly service_category_id: string;
  readonly service_item_id: string;
  readonly service_name: string;
  readonly size_or_quantity: string;
  readonly service_detail: string;
  readonly special_request: string;
  readonly total_amount: string;
  readonly discount_amount: string;
  readonly deposit_amount: string;
  readonly balance_amount: string;
  readonly onsite_extra_amount: string;
  readonly vat_type: string;
  readonly payment_status: string;
  readonly payment_memo: string;
  readonly evidence_memo: string;
  readonly receipt_type: string;
  readonly receipt_status: string;
  readonly partner_payment_amount: string;
  readonly partner_payment_status: string;
  readonly broker_payment_amount: string;
  readonly partner_settled_at: string | null;
  readonly base_unit_price: string;
  readonly partner_unit_price: string;
  readonly total_amount_touched: boolean;
  readonly deposit_amount_touched: boolean;
  readonly balance_amount_touched: boolean;
  readonly partner_payment_amount_touched: boolean;
}

export interface OrderGroupForm {
  readonly group_id: string;
  readonly customer_name: string;
  readonly customer_phone: string;
  readonly customer_address: string;
  readonly customer_address_detail: string;
  readonly source_channel: string;
  readonly customer_visible_payment: boolean;
  readonly notes: string;
  readonly lines: readonly OrderLineForm[];
}

export type OrderFormGroupField = Exclude<keyof OrderGroupForm, 'lines'>;

type StringFieldOf<T> = {
  [K in keyof T]: T[K] extends string ? K : never;
}[keyof T];

export type OrderLineField = StringFieldOf<OrderLineForm>;

export type OrderMoneyField =
  | 'total_amount'
  | 'discount_amount'
  | 'deposit_amount'
  | 'balance_amount'
  | 'onsite_extra_amount'
  | 'partner_payment_amount'
  | 'broker_payment_amount';

export type OrderRecalculationSource = OrderMoneyField | 'partner' | 'quantity' | 'service_item';

export type OrderFormGroupFieldChange = <K extends OrderFormGroupField>(
  key: K,
  value: OrderGroupForm[K],
) => void;

export type OrderFormLineFieldChange = <K extends OrderLineField>(
  lineIndex: number,
  key: K,
  value: OrderLineForm[K],
) => void;

export type OrderFormVisitDatesChange = (
  lineIndex: number,
  value: readonly string[],
) => void;
