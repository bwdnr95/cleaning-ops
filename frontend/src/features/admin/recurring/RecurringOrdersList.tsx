import type React from 'react';

import { OrdersPage } from '../orders/OrdersPage';

type OrdersPageProps = React.ComponentProps<typeof OrdersPage>;

// 주문관리와 동일한 목록 뷰(initial* + onViewChange) 통과 인터페이스.
// App이 라우트 해시(#recurring?view=orders&…)에서 복원한 값을 그대로 넘기고, 변경은 onViewChange로 되돌려 받는다.
export type RecurringOrdersViewProps = Pick<
  OrdersPageProps,
  | 'initialTab'
  | 'initialDatePreset'
  | 'initialQuery'
  | 'initialPartnerId'
  | 'initialBrokerId'
  | 'initialPage'
  | 'initialVisitFrom'
  | 'initialVisitTo'
  | 'initialReceivedDatePreset'
  | 'initialReceivedFrom'
  | 'initialReceivedTo'
  | 'initialSortBy'
  | 'initialPageSize'
  | 'onViewChange'
>;

interface RecurringOrdersListProps extends RecurringOrdersViewProps {
  readonly onOpenOrder?: (orderId: string) => void;
  readonly onEditOrder?: (orderId: string) => void;
}

export function RecurringOrdersList({
  onOpenOrder,
  onEditOrder,
  // 정기 회차는 과거까지 한눈에 보는 게 기본 — 라우트 기본값(DEFAULT_RECURRING_ORDERS_VIEW)과 동일.
  initialDatePreset = 'all',
  ...viewProps
}: RecurringOrdersListProps) {
  return (
    <OrdersPage
      {...viewProps}
      initialDatePreset={initialDatePreset}
      onEditOrder={onEditOrder}
      onOpenOrder={onOpenOrder}
      orderScope="recurring"
    />
  );
}
