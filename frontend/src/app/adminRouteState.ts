import type { AdminOrderSort, DashboardSummary } from '../api/admin';

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
  readonly query: string;
  readonly partnerId: string;
  readonly brokerId: string;
  readonly page: number;
  readonly visitFrom: string;
  readonly visitTo: string;
  readonly receivedDatePreset: string;
  readonly receivedFrom: string;
  readonly receivedTo: string;
  readonly sortBy: AdminOrderSort;
  readonly pageSize: number;
}

export const DEFAULT_ORDERS_VIEW: OrdersView = {
  tab: 'all',
  datePreset: 'upcoming',
  query: '',
  partnerId: 'all',
  brokerId: 'all',
  page: 1,
  visitFrom: '',
  visitTo: '',
  receivedDatePreset: 'all',
  receivedFrom: '',
  receivedTo: '',
  sortBy: 'visit_asc',
  pageSize: 50,
};

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
  readonly query?: string | null;
  readonly partnerId?: string | null;
  readonly brokerId?: string | null;
  readonly page?: number | string | null;
  readonly visitFrom?: string | null;
  readonly visitTo?: string | null;
  readonly receivedDatePreset?: string | null;
  readonly receivedFrom?: string | null;
  readonly receivedTo?: string | null;
  readonly sortBy?: string | null;
  readonly pageSize?: number | string | null;
}

export function toOrdersView(options: OrdersViewOptions = {}) {
  const tab = typeof options.ordersTab === 'string' ? options.ordersTab : DEFAULT_ORDERS_VIEW.tab;
  const datePreset = typeof options.datePreset === 'string'
    ? options.datePreset
    : getDefaultOrdersDatePreset(tab);

  return {
    tab,
    datePreset,
    query: typeof options.query === 'string' ? options.query : DEFAULT_ORDERS_VIEW.query,
    partnerId: options.partnerId || DEFAULT_ORDERS_VIEW.partnerId,
    brokerId: options.brokerId || DEFAULT_ORDERS_VIEW.brokerId,
    page: normalizeOrdersPage(options.page),
    visitFrom: options.visitFrom || DEFAULT_ORDERS_VIEW.visitFrom,
    visitTo: options.visitTo || DEFAULT_ORDERS_VIEW.visitTo,
    receivedDatePreset: options.receivedDatePreset || DEFAULT_ORDERS_VIEW.receivedDatePreset,
    receivedFrom: options.receivedFrom || DEFAULT_ORDERS_VIEW.receivedFrom,
    receivedTo: options.receivedTo || DEFAULT_ORDERS_VIEW.receivedTo,
    sortBy: normalizeOrdersSort(options.sortBy),
    pageSize: normalizeOrdersPageSize(options.pageSize),
  };
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
    query: params.get('q'),
    partnerId: params.get('partner_id'),
    brokerId: params.get('broker_id'),
    page: params.get('page'),
    visitFrom: params.get('visit_from'),
    visitTo: params.get('visit_to'),
    receivedDatePreset: params.get('received'),
    receivedFrom: params.get('received_from'),
    receivedTo: params.get('received_to'),
    sortBy: params.get('sort'),
    pageSize: params.get('page_size'),
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
    query: route?.ordersView?.query,
    partnerId: route?.ordersView?.partnerId,
    brokerId: route?.ordersView?.brokerId,
    page: route?.ordersView?.page,
    visitFrom: route?.ordersView?.visitFrom,
    visitTo: route?.ordersView?.visitTo,
    receivedDatePreset: route?.ordersView?.receivedDatePreset,
    receivedFrom: route?.ordersView?.receivedFrom,
    receivedTo: route?.ordersView?.receivedTo,
    sortBy: route?.ordersView?.sortBy,
    pageSize: route?.ordersView?.pageSize,
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

function normalizeOrdersPage(value: number | string | null | undefined): number {
  const page = Number(value);
  return Number.isInteger(page) && page > 0 ? page : DEFAULT_ORDERS_VIEW.page;
}

function normalizeOrdersSort(value: string | null | undefined): AdminOrderSort {
  if (['visit_asc', 'visit_desc', 'received_asc', 'received_desc'].includes(value || '')) {
    return value as AdminOrderSort;
  }
  return DEFAULT_ORDERS_VIEW.sortBy;
}

function normalizeOrdersPageSize(value: number | string | null | undefined): number {
  const pageSize = Number(value);
  return [10, 20, 50, 100].includes(pageSize) ? pageSize : DEFAULT_ORDERS_VIEW.pageSize;
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
    if (normalized.ordersView.query !== DEFAULT_ORDERS_VIEW.query) {
      params.set('q', normalized.ordersView.query);
    }
    if (normalized.ordersView.partnerId !== DEFAULT_ORDERS_VIEW.partnerId) {
      params.set('partner_id', normalized.ordersView.partnerId);
    }
    if (normalized.ordersView.brokerId !== DEFAULT_ORDERS_VIEW.brokerId) {
      params.set('broker_id', normalized.ordersView.brokerId);
    }
    if (normalized.ordersView.page !== DEFAULT_ORDERS_VIEW.page) {
      params.set('page', String(normalized.ordersView.page));
    }
    if (normalized.ordersView.visitFrom !== DEFAULT_ORDERS_VIEW.visitFrom) {
      params.set('visit_from', normalized.ordersView.visitFrom);
    }
    if (normalized.ordersView.visitTo !== DEFAULT_ORDERS_VIEW.visitTo) {
      params.set('visit_to', normalized.ordersView.visitTo);
    }
    if (normalized.ordersView.receivedDatePreset !== DEFAULT_ORDERS_VIEW.receivedDatePreset) {
      params.set('received', normalized.ordersView.receivedDatePreset);
    }
    if (normalized.ordersView.receivedFrom !== DEFAULT_ORDERS_VIEW.receivedFrom) {
      params.set('received_from', normalized.ordersView.receivedFrom);
    }
    if (normalized.ordersView.receivedTo !== DEFAULT_ORDERS_VIEW.receivedTo) {
      params.set('received_to', normalized.ordersView.receivedTo);
    }
    if (normalized.ordersView.sortBy !== DEFAULT_ORDERS_VIEW.sortBy) {
      params.set('sort', normalized.ordersView.sortBy);
    }
    if (normalized.ordersView.pageSize !== DEFAULT_ORDERS_VIEW.pageSize) {
      params.set('page_size', String(normalized.ordersView.pageSize));
    }
  }

  const query = params.toString();
  return `#${path}${query ? `?${query}` : ''}`;
}
