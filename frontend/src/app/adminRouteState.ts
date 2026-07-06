import type { DashboardSummary } from '../api/admin';

export const ADMIN_PAGE_META = {
  dashboard: {
    title: '대시보드',
    subtitle: '운영 현황',
    breadcrumb: ['운영', '대시보드'],
  },
  orders: {
    title: '주문관리',
    subtitle: '전체 운영 주문',
    breadcrumb: ['운영', '주문관리'],
  },
  calendar: {
    title: '일정 캘린더',
    subtitle: '방문 일정',
    breadcrumb: ['운영', '일정 캘린더'],
  },
  photos: {
    title: '사진/고객전달',
    subtitle: '사진 공개 상태 / 고객 전달 대기',
    breadcrumb: ['운영', '사진/고객전달'],
  },
  products: {
    title: '상품관리',
    subtitle: '서비스 기준가',
    breadcrumb: ['운영', '상품관리'],
  },
  sends: {
    title: '발송이력',
    subtitle: '고객/협력사 안내',
    breadcrumb: ['운영', '발송이력'],
  },
  brokers: {
    title: '중개사관리',
    subtitle: '중개사별 건수 / 매출',
    breadcrumb: ['운영', '중개사관리'],
  },
  partners: {
    title: '협력사관리',
    subtitle: '계정 / 배정 현황',
    breadcrumb: ['운영', '협력사관리'],
  },
  recurring: {
    title: '정기청소',
    subtitle: '정기계약 / 월 트래커',
    breadcrumb: ['운영', '정기청소'],
  },
  reports: {
    title: '보고서',
    subtitle: '매출 / 협력사 / 서비스 / 정산',
    breadcrumb: ['운영', '보고서'],
  },
} as const;

export interface OrdersView {
  readonly tab: string;
  readonly datePreset: string;
}

export const DEFAULT_ORDERS_VIEW: OrdersView = { tab: 'all', datePreset: 'upcoming' };

const ADMIN_PAGE_KEYS = Object.keys(ADMIN_PAGE_META);

export const DEFAULT_ADMIN_ROUTE = {
  page: 'dashboard',
  detailOrderId: null,
  orderForm: null,
  ordersView: DEFAULT_ORDERS_VIEW,
};

interface OrdersViewOptions {
  readonly ordersTab?: string | null;
  readonly datePreset?: string | null;
}

export function toOrdersView(options: OrdersViewOptions = {}) {
  const tab = typeof options.ordersTab === 'string' ? options.ordersTab : DEFAULT_ORDERS_VIEW.tab;
  const datePreset = typeof options.datePreset === 'string'
    ? options.datePreset
    : getDefaultOrdersDatePreset(tab);

  return { tab, datePreset };
}

export function toPageRoute(page: string, ordersView = DEFAULT_ORDERS_VIEW) {
  return {
    page,
    detailOrderId: null,
    orderForm: null,
    ordersView,
  };
}

export function toOrderCreateRoute(_returnPage = 'orders', ordersView = DEFAULT_ORDERS_VIEW) {
  return {
    page: 'orders',
    detailOrderId: null,
    orderForm: { mode: 'create', orderId: null },
    ordersView,
  };
}

export function toOrderDetailRoute(orderId: string, ordersView = DEFAULT_ORDERS_VIEW) {
  return {
    page: 'orders',
    detailOrderId: orderId,
    orderForm: null,
    ordersView,
  };
}

export function toOrderEditRoute(orderId: string, ordersView = DEFAULT_ORDERS_VIEW) {
  return {
    page: 'orders',
    detailOrderId: orderId,
    orderForm: { mode: 'edit', orderId },
    ordersView,
  };
}

export function toOrderDuplicateRoute(orderId: string, ordersView = DEFAULT_ORDERS_VIEW) {
  return {
    page: 'orders',
    detailOrderId: null,
    orderForm: { mode: 'create', orderId: null, duplicateFromOrderId: orderId },
    ordersView,
  };
}

export function readAdminRouteFromLocation() {
  if (typeof window === 'undefined') {
    return DEFAULT_ADMIN_ROUTE;
  }

  const hash = window.location.hash.replace(/^#\/?/, '');
  if (!hash) {
    return DEFAULT_ADMIN_ROUTE;
  }

  const [pathPart, queryString = ''] = hash.split('?');
  const segments = pathPart.split('/').filter(Boolean).map((segment) => decodeURIComponent(segment));
  const params = new URLSearchParams(queryString);
  const page = ADMIN_PAGE_KEYS.includes(segments[0]) ? segments[0] : DEFAULT_ADMIN_ROUTE.page;
  const ordersView = toOrdersView({
    ordersTab: params.get('tab') || undefined,
    datePreset: params.get('date') || undefined,
  });

  if (page === 'orders' && segments[1] === 'new') {
    return normalizeAdminRoute(toOrderCreateRoute('orders', ordersView));
  }
  if (page === 'orders' && segments[1]) {
    const orderId = segments[1];
    if (segments[2] === 'edit') {
      return normalizeAdminRoute(toOrderEditRoute(orderId, ordersView));
    }
    if (segments[2] === 'duplicate') {
      return normalizeAdminRoute(toOrderDuplicateRoute(orderId, ordersView));
    }
    return normalizeAdminRoute(toOrderDetailRoute(orderId, ordersView));
  }

  return normalizeAdminRoute(toPageRoute(page, page === 'orders' ? ordersView : DEFAULT_ORDERS_VIEW));
}

export function normalizeAdminRoute(route) {
  const page = ADMIN_PAGE_KEYS.includes(route?.page) ? route.page : DEFAULT_ADMIN_ROUTE.page;
  const ordersView = toOrdersView({
    ordersTab: route?.ordersView?.tab,
    datePreset: route?.ordersView?.datePreset,
  });
  return {
    page,
    detailOrderId: route?.detailOrderId || null,
    orderForm: route?.orderForm || null,
    ordersView,
  };
}

export function replaceAdminHistory(route) {
  writeAdminHistory(route, { replace: true });
}

export function writeAdminHistory(route, { replace = false } = {}) {
  if (typeof window === 'undefined') {
    return;
  }

  const hash = adminRouteToHash(route);
  if (window.location.hash === hash) {
    return;
  }

  const url = `${window.location.pathname}${window.location.search}${hash}`;
  const method = replace ? 'replaceState' : 'pushState';
  window.history[method]({ cleanOpsAdminRoute: true }, '', url);
}

export function getDefaultOrdersDatePreset(tab: string): string {
  if (tab === 'today') {
    return 'today';
  }
  if (tab === 'tomorrow_notice') {
    return 'tomorrow';
  }
  if (['payment_check', 'photo_review', 'deliver', 'partner_pending', 'monthly_done', 'monthly_revenue', 'unpaid_check', 'customer_check', 'receivable'].includes(tab)) {
    return tab.startsWith('monthly_') ? 'month' : 'all';
  }
  return DEFAULT_ORDERS_VIEW.datePreset;
}

export function toAdminNavBadges(summary: DashboardSummary | null) {
  if (!summary) {
    return {};
  }

  const orderQueueCount = Number(summary.partner_pending || 0)
    + Number(summary.unpaid_check_needed || 0)
    + Number(summary.customer_check_needed || 0)
    + Number(summary.today_jobs || 0)
    + Number(summary.tomorrow_notice_targets || 0);

  return {
    orders: orderQueueCount > 0 ? String(orderQueueCount) : null,
  };
}

function adminRouteToHash(route) {
  const normalized = normalizeAdminRoute(route);
  let path = normalized.page;
  if (normalized.orderForm?.mode === 'create' && normalized.orderForm.duplicateFromOrderId) {
    path = `orders/${encodeURIComponent(normalized.orderForm.duplicateFromOrderId)}/duplicate`;
  } else if (normalized.orderForm?.mode === 'create') {
    path = 'orders/new';
  } else if (normalized.orderForm?.mode === 'edit' && normalized.orderForm.orderId) {
    path = `orders/${encodeURIComponent(normalized.orderForm.orderId)}/edit`;
  } else if (normalized.detailOrderId) {
    path = `orders/${encodeURIComponent(normalized.detailOrderId)}`;
  }

  const params = new URLSearchParams();
  if (path.startsWith('orders')) {
    if (normalized.ordersView.tab !== DEFAULT_ORDERS_VIEW.tab) {
      params.set('tab', normalized.ordersView.tab);
    }
    if (normalized.ordersView.datePreset !== getDefaultOrdersDatePreset(normalized.ordersView.tab)) {
      params.set('date', normalized.ordersView.datePreset);
    }
  }

  const query = params.toString();
  return `#${path}${query ? `?${query}` : ''}`;
}
