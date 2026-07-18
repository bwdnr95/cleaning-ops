import { OrdersPage } from '../orders/OrdersPage';

interface RecurringOrdersListProps {
  readonly onOpenOrder?: (orderId: string) => void;
  readonly onEditOrder?: (orderId: string) => void;
}

export function RecurringOrdersList({ onOpenOrder, onEditOrder }: RecurringOrdersListProps) {
  return (
    <OrdersPage
      initialDatePreset="all"
      onEditOrder={onEditOrder}
      onOpenOrder={onOpenOrder}
      orderScope="recurring"
    />
  );
}
