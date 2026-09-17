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

// 주문 목록 뷰의 스코프. 정기 주문 탭(recurring)은 과거 회차까지 한눈에 보는 게 기본이라
// 방문일 프리셋 기본값만 '전체'로 다르고, 나머지 기본값·해시 파라미터 이름은 주문관리와 같다.
export type OrdersViewScope = 'regular' | 'recurring';

export const DEFAULT_RECURRING_ORDERS_VIEW: OrdersView = {
  ...DEFAULT_ORDERS_VIEW,
  datePreset: 'all',
};

// 정기청소 페이지 상단 탭. 해시에는 `view=` 키로 싣는다(`tab=`은 주문 상태 탭이 이미 쓰는 키).
export type RecurringTab = 'contracts' | 'monthly' | 'orders';
// 주문 상세/폼의 출처 — '목록'으로 돌아갈 곳. 해시에는 `from=` 키로 싣는다(기본 orders는 생략).
export type OrderReturnPage = 'orders' | 'recurring';

export interface AdminOrderFormRoute {
  readonly mode: 'create' | 'edit';
  readonly orderId: string | null;
  readonly duplicateFromOrderId?: string | null;
}

export interface AdminRoute {
  readonly page: string;
  readonly detailOrderId: string | null;
  readonly orderForm: AdminOrderFormRoute | null;
  readonly ordersView: OrdersView;
  readonly recurringTab: RecurringTab;
  readonly returnPage: OrderReturnPage;
}

// normalizeAdminRoute 입력 — 부분/느슨한 객체를 받아 AdminRoute로 정규화한다.
interface AdminRouteInput {
  readonly page?: string | null;
  readonly detailOrderId?: string | null;
  readonly orderForm?: AdminOrderFormRoute | null;
  readonly ordersView?: Partial<OrdersView> | null;
  readonly recurringTab?: string | null;
  readonly returnPage?: string | null;
}

const ADMIN_PAGE_KEYS = Object.keys(ADMIN_PAGE_META);
const RECURRING_TABS: readonly string[] = ['contracts', 'monthly', 'orders'];
const DEFAULT_RECURRING_TAB: RecurringTab = 'contracts';
const DEFAULT_ORDER_RETURN_PAGE: OrderReturnPage = 'orders';

export const DEFAULT_ADMIN_ROUTE: AdminRoute = {
  page: 'dashboard',
  detailOrderId: null,
  orderForm: null,
  ordersView: DEFAULT_ORDERS_VIEW,
  recurringTab: DEFAULT_RECURRING_TAB,
  returnPage: DEFAULT_ORDER_RETURN_PAGE,
};

export function getDefaultOrdersView(scope: OrdersViewScope = 'regular'): OrdersView {
  return scope === 'recurring' ? DEFAULT_RECURRING_ORDERS_VIEW : DEFAULT_ORDERS_VIEW;
}

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

export function toOrdersView(options: OrdersViewOptions = {}, scope: OrdersViewScope = 'regular'): OrdersView {
  const tab = typeof options.ordersTab === 'string' ? options.ordersTab : DEFAULT_ORDERS_VIEW.tab;
  const datePreset = typeof options.datePreset === 'string'
    ? options.datePreset
    : getDefaultOrdersDatePreset(tab, scope);

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

interface OrderSubRouteOptions {
  readonly returnPage?: OrderReturnPage;
}

export function toPageRoute(page: string, ordersView = DEFAULT_ORDERS_VIEW): AdminRoute {
  return {
    page,
    detailOrderId: null,
    orderForm: null,
    ordersView,
    recurringTab: DEFAULT_RECURRING_TAB,
    returnPage: DEFAULT_ORDER_RETURN_PAGE,
  };
}

// 정기청소 페이지 라우트. ordersView는 '정기 주문' 탭의 목록 뷰(기본값은 정기 스코프 기본값).
export function toRecurringRoute(
  recurringTab: RecurringTab = DEFAULT_RECURRING_TAB,
  ordersView = DEFAULT_RECURRING_ORDERS_VIEW,
): AdminRoute {
  return {
    ...toPageRoute('recurring', ordersView),
    recurringTab,
  };
}

// 주문 상세/폼의 '목록' 복귀 라우트 — 출처가 정기청소면 정기 주문 탭으로, 아니면 주문관리로.
export function toOrderReturnRoute(returnPage: OrderReturnPage, ordersView: OrdersView): AdminRoute {
  if (returnPage === 'recurring') {
    return toRecurringRoute('orders', ordersView);
  }
  return toPageRoute('orders', ordersView);
}

export function toOrderCreateRoute(_returnPage = 'orders', ordersView = DEFAULT_ORDERS_VIEW): AdminRoute {
  return {
    page: 'orders',
    detailOrderId: null,
    orderForm: { mode: 'create', orderId: null },
    ordersView,
    recurringTab: DEFAULT_RECURRING_TAB,
    returnPage: DEFAULT_ORDER_RETURN_PAGE,
  };
}

export function toOrderDetailRoute(
  orderId: string,
  ordersView = DEFAULT_ORDERS_VIEW,
  { returnPage = DEFAULT_ORDER_RETURN_PAGE }: OrderSubRouteOptions = {},
): AdminRoute {
  return {
    page: 'orders',
    detailOrderId: orderId,
    orderForm: null,
    ordersView,
    recurringTab: DEFAULT_RECURRING_TAB,
    returnPage,
  };
}

export function toOrderEditRoute(
  orderId: string,
  ordersView = DEFAULT_ORDERS_VIEW,
  { returnPage = DEFAULT_ORDER_RETURN_PAGE }: OrderSubRouteOptions = {},
): AdminRoute {
  return {
    page: 'orders',
    detailOrderId: orderId,
    orderForm: { mode: 'edit', orderId },
    ordersView,
    recurringTab: DEFAULT_RECURRING_TAB,
    returnPage,
  };
}

export function toOrderDuplicateRoute(
  orderId: string,
  ordersView = DEFAULT_ORDERS_VIEW,
  { returnPage = DEFAULT_ORDER_RETURN_PAGE }: OrderSubRouteOptions = {},
): AdminRoute {
  return {
    page: 'orders',
    detailOrderId: null,
    orderForm: { mode: 'create', orderId: null, duplicateFromOrderId: orderId },
    ordersView,
    recurringTab: DEFAULT_RECURRING_TAB,
    returnPage,
  };
}

export function readAdminRouteFromLocation(): AdminRoute {
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
  // 출처(from=)는 주문 상세/폼 하위 라우트에서만 읽는다 — 목록 해시에 수제로 붙은 from은 뷰 기본값 해석에 끼어들면 안 된다.
  const isOrderSubRoute = page === 'orders' && Boolean(segments[1]);
  const returnPage = isOrderSubRoute
    ? normalizeOrderReturnPage(params.get('from'))
    : DEFAULT_ORDER_RETURN_PAGE;
  const recurringTab = normalizeRecurringTab(params.get('view'));
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
  }, getOrdersViewScope(page, returnPage));

  if (page === 'orders' && segments[1] === 'new') {
    return normalizeAdminRoute(toOrderCreateRoute('orders', ordersView));
  }
  if (page === 'orders' && segments[1]) {
    const orderId = segments[1];
    if (segments[2] === 'edit') {
      return normalizeAdminRoute(toOrderEditRoute(orderId, ordersView, { returnPage }));
    }
    if (segments[2] === 'duplicate') {
      return normalizeAdminRoute(toOrderDuplicateRoute(orderId, ordersView, { returnPage }));
    }
    return normalizeAdminRoute(toOrderDetailRoute(orderId, ordersView, { returnPage }));
  }
  if (page === 'recurring') {
    // 정기 주문 탭일 때만 목록 뷰를 해시에서 복원한다(계약/월 트래커 탭은 목록 파라미터가 없다).
    return normalizeAdminRoute(toRecurringRoute(
      recurringTab,
      recurringTab === 'orders' ? ordersView : DEFAULT_RECURRING_ORDERS_VIEW,
    ));
  }

  return normalizeAdminRoute(toPageRoute(page, page === 'orders' ? ordersView : DEFAULT_ORDERS_VIEW));
}

export function normalizeAdminRoute(route: AdminRouteInput | null | undefined): AdminRoute {
  const page = ADMIN_PAGE_KEYS.includes(route?.page) ? route.page : DEFAULT_ADMIN_ROUTE.page;
  const detailOrderId = route?.detailOrderId || null;
  const orderForm = route?.orderForm || null;
  // 출처(returnPage)는 주문 상세/폼 라우트에서만 의미가 있다. 목록·다른 페이지에선 기본값으로 접어
  // 해시에 `from=`이 새지 않게 한다. 정기 탭도 정기청소 페이지 밖에선 기본값으로 접는다.
  const isOrderSubRoute = page === 'orders' && Boolean(detailOrderId || orderForm);
  const returnPage = isOrderSubRoute ? normalizeOrderReturnPage(route?.returnPage) : DEFAULT_ORDER_RETURN_PAGE;
  const recurringTab = page === 'recurring' ? normalizeRecurringTab(route?.recurringTab) : DEFAULT_RECURRING_TAB;
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
  }, getOrdersViewScope(page, returnPage));
  return {
    page,
    detailOrderId,
    orderForm,
    ordersView,
    recurringTab,
    returnPage,
  };
}

export function replaceAdminHistory(route: AdminRouteInput) {
  writeAdminHistory(route, { replace: true });
}

export function writeAdminHistory(route: AdminRouteInput, { replace = false } = {}) {
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

export function getDefaultOrdersDatePreset(tab: string, scope: OrdersViewScope = 'regular'): string {
  if (scope === 'recurring') {
    // 정기 주문 탭은 대시보드 드릴다운 탭이 없으므로 상태 탭과 무관하게 '전체'가 기본.
    return DEFAULT_RECURRING_ORDERS_VIEW.datePreset;
  }
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

// 정기청소 페이지 자체, 또는 정기 주문 탭에서 연 상세/폼(from=recurring)은 정기 스코프의 기본값을 쓴다.
function getOrdersViewScope(page: string, returnPage: OrderReturnPage): OrdersViewScope {
  return page === 'recurring' || returnPage === 'recurring' ? 'recurring' : 'regular';
}

function normalizeRecurringTab(value: string | null | undefined): RecurringTab {
  return RECURRING_TABS.includes(value || '') ? (value as RecurringTab) : DEFAULT_RECURRING_TAB;
}

function normalizeOrderReturnPage(value: string | null | undefined): OrderReturnPage {
  return value === 'recurring' ? 'recurring' : DEFAULT_ORDER_RETURN_PAGE;
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

function adminRouteToHash(route: AdminRouteInput) {
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
  // 정기청소 페이지: 상단 탭은 `view=`(계약 탭은 생략), 목록 파라미터는 정기 주문 탭일 때만 싣는다.
  const isRecurringOrdersTab = normalized.page === 'recurring' && normalized.recurringTab === 'orders';
  if (normalized.page === 'recurring' && normalized.recurringTab !== DEFAULT_RECURRING_TAB) {
    params.set('view', normalized.recurringTab);
  }
  if (path.startsWith('orders') || isRecurringOrdersTab) {
    const scope = getOrdersViewScope(normalized.page, normalized.returnPage);
    if (normalized.ordersView.tab !== DEFAULT_ORDERS_VIEW.tab) {
      params.set('tab', normalized.ordersView.tab);
    }
    if (normalized.ordersView.datePreset !== getDefaultOrdersDatePreset(normalized.ordersView.tab, scope)) {
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
  // 출처는 normalizeAdminRoute가 상세/폼 라우트에서만 남기므로 목록 해시엔 붙지 않는다.
  if (normalized.returnPage !== DEFAULT_ORDER_RETURN_PAGE) {
    params.set('from', normalized.returnPage);
  }

  const query = params.toString();
  return `#${path}${query ? `?${query}` : ''}`;
}
