import React from 'react';

import { AdminShell, Topbar } from '../components/layout/AdminShell';
import { getDashboardSummary } from '../api/admin';
import { useApiResource } from '../api/useApiResource';
import { AdminLoginPage, PartnerLoginPage } from '../features/auth/LoginPages';
import { CalendarPage } from '../features/admin/calendar/CalendarPage';
import { Dashboard } from '../features/admin/dashboard/Dashboard';
import { MessagesPage } from '../features/admin/messages/MessagesPage';
import { OrderDetailPage } from '../features/admin/orders/OrderDetailPage';
import { OrderFormPage } from '../features/admin/orders/OrderFormPage';
import { OrdersPage } from '../features/admin/orders/OrdersPage';
import { PartnersPage } from '../features/admin/partners/PartnersPage';
import { PhotoReviewPage } from '../features/admin/photo-review/PhotoReviewPage';
import { ProductsPage } from '../features/admin/products/ProductsPage';
import { RecurringContractsPage } from '../features/admin/recurring/RecurringContractsPage';
import { ReportsPage } from '../features/admin/reports/ReportsPage';
import { CustomerReservation } from '../features/customer/CustomerReservation';
import { PartnerApp } from '../features/partner/PartnerApp';
import { useAuth } from '../store/authStore';

const ADMIN_PAGE_META = {
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
    subtitle: '사진검수 / 고객 전달 대기',
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
};

const DEFAULT_ORDERS_VIEW = { tab: 'all', datePreset: 'upcoming' };
const ADMIN_PAGE_KEYS = Object.keys(ADMIN_PAGE_META);
const DEFAULT_ADMIN_ROUTE = {
  page: 'dashboard',
  detailOrderId: null,
  orderForm: null,
  ordersView: DEFAULT_ORDERS_VIEW,
};

export function App() {
  const auth = useAuth();
  const isStandaloneCustomerLink = isCustomerLinkRoute();
  const isStandalonePartnerLink = isPartnerLinkRoute();
  const mode = isStandalonePartnerLink ? 'partner' : 'admin';
  const [adminRoute, setAdminRoute] = React.useState(() => readAdminRouteFromLocation());
  // 주문 상세의 '정기' 배지에서 계약으로 역링크할 때 전달할 계약 id(데모 affordance: 해시 라우트와 별개).
  const [openRecurringContractId, setOpenRecurringContractId] = React.useState<string | null>(null);
  const consumeOpenRecurringContract = React.useCallback(() => setOpenRecurringContractId(null), []);
  const adminSession = auth.getSession('admin');
  const partnerSession = auth.getSession('partner');
  const adminSummaryLoader = React.useCallback(() => {
    if (mode !== 'admin' || adminSession.user?.role !== 'admin') {
      return Promise.resolve(null);
    }
    return getDashboardSummary();
  }, [adminSession.user?.role, mode]);
  const adminSummary = useApiResource(adminSummaryLoader, `${mode}:${adminSession.accessToken || 'guest'}`);
  const navBadges = toAdminNavBadges(adminSummary.data);
  const isSwitchingRole = auth.activeRole !== mode;

  React.useEffect(() => {
    if (auth.activeRole !== mode) {
      auth.setActiveRole(mode);
    }
  }, [auth, mode]);

  React.useEffect(() => {
    if (mode !== 'admin' || isStandaloneCustomerLink) {
      return undefined;
    }

    if (!window.location.hash) {
      replaceAdminHistory(adminRoute);
    }

    const syncRouteFromHistory = () => {
      setAdminRoute(readAdminRouteFromLocation());
    };
    window.addEventListener('popstate', syncRouteFromHistory);
    window.addEventListener('hashchange', syncRouteFromHistory);
    return () => {
      window.removeEventListener('popstate', syncRouteFromHistory);
      window.removeEventListener('hashchange', syncRouteFromHistory);
    };
  }, [adminRoute, isStandaloneCustomerLink, mode]);

  const navigateAdmin = React.useCallback((nextRoute, options = {}) => {
    const route = normalizeAdminRoute(nextRoute);
    setAdminRoute(route);
    writeAdminHistory(route, options);
  }, []);

  const detailOrderId = adminRoute.detailOrderId;
  const orderForm = adminRoute.orderForm;
  const ordersView = adminRoute.ordersView;

  if (isStandaloneCustomerLink) {
    return (
      <main style={{ minHeight: '100vh', height: '100vh', width: '100vw', background: '#f7f6f3' }}>
        <CustomerReservation />
      </main>
    );
  }

  return (
    <main style={{ height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg)' }}>
        {mode === 'admin' && (
          <>
            {isSwitchingRole ? (
              <RouteState text="화면을 전환하는 중입니다." />
            ) : adminSession.user?.role === 'admin' ? (
              <AdminShell
                page={adminRoute.page}
                onPageChange={(nextPage) => navigateAdmin(toPageRoute(nextPage))}
                onCreateOrder={() => navigateAdmin(toOrderCreateRoute(adminRoute.page))}
                navBadges={navBadges}
                user={adminSession.user}
                onLogout={() => void auth.logout('admin')}
              >
                {({ page, setPage }) => {
                  if (orderForm) {
                    return (
                      <>
                        <Topbar
                          title={orderForm.duplicateFromOrderId ? '주문 복제' : orderForm.mode === 'edit' ? '주문 수정' : '신규 주문 등록'}
                          breadcrumb={['운영', '주문관리', orderForm.duplicateFromOrderId ? '복제' : orderForm.mode === 'edit' ? '수정' : '신규']}
                        />
                        <OrderFormPage
                          mode={orderForm.mode}
                          orderId={orderForm.orderId}
                          duplicateFromOrderId={orderForm.duplicateFromOrderId || null}
                          onCancel={() => {
                            if (orderForm.mode === 'edit' && orderForm.orderId) {
                              navigateAdmin(toOrderDetailRoute(orderForm.orderId, ordersView));
                              return;
                            }
                            navigateAdmin(toPageRoute(page, ordersView));
                          }}
                          onSaved={(order) => {
                            navigateAdmin(toOrderDetailRoute(order.id, ordersView));
                          }}
                        />
                      </>
                    );
                  }

                  if (detailOrderId) {
                    return (
                      <>
                        <Topbar
                          title="주문 상세"
                          breadcrumb={['운영', '주문관리', '상세']}
                        />
                        <OrderDetailPage
                          orderId={detailOrderId}
                          onBack={() => navigateAdmin(toPageRoute('orders', ordersView))}
                          onEdit={() => navigateAdmin(toOrderEditRoute(detailOrderId, ordersView))}
                          onDuplicate={() => navigateAdmin(toOrderDuplicateRoute(detailOrderId, ordersView))}
                          onOpenOrder={(nextOrderId) => navigateAdmin(toOrderDetailRoute(nextOrderId, ordersView))}
                          onOpenRecurringContract={(contractId) => {
                            setOpenRecurringContractId(contractId);
                            setPage('recurring');
                          }}
                          onNav={(nextPage) => {
                            setPage(nextPage);
                          }}
                        />
                      </>
                    );
                  }

                  const meta = ADMIN_PAGE_META[page] ?? ADMIN_PAGE_META.dashboard;
                  return (
                    <>
                      <Topbar {...meta} />
                      {page === 'dashboard' && (
                        <Dashboard
                          userName={adminSession.user?.name}
                          onCreateOrder={() => navigateAdmin(toOrderCreateRoute('dashboard'))}
                          onNav={(nextPage, options = {}) => {
                            let nextOrdersView = DEFAULT_ORDERS_VIEW;
                            if (nextPage === 'orders') {
                              nextOrdersView = toOrdersView(options);
                            }
                            navigateAdmin(toPageRoute(nextPage, nextOrdersView));
                          }}
                          onOpenOrder={(orderId) => navigateAdmin(toOrderDetailRoute(orderId, ordersView))}
                        />
                      )}
                      {page === 'orders' && (
                        <OrdersPage
                          initialTab={ordersView.tab}
                          initialDatePreset={ordersView.datePreset}
                          onOpenOrder={(orderId) => navigateAdmin(toOrderDetailRoute(orderId, ordersView))}
                          onEditOrder={(orderId) => navigateAdmin(toOrderEditRoute(orderId, ordersView))}
                          onCreateOrder={() => navigateAdmin(toOrderCreateRoute('orders', ordersView))}
                        />
                      )}
                      {page === 'calendar' && (
                        <CalendarPage
                          onOpenOrder={(orderId) => navigateAdmin(toOrderDetailRoute(orderId, ordersView))}
                          onCreateOrder={() => navigateAdmin(toOrderCreateRoute('calendar'))}
                        />
                      )}
                      {page === 'photos' && (
                        <PhotoReviewPage
                          onOpenOrder={(orderId) => navigateAdmin(toOrderDetailRoute(orderId, ordersView))}
                          onNav={(nextPage) => {
                            setPage(nextPage);
                          }}
                        />
                      )}
                      {page === 'products' && <ProductsPage />}
                      {page === 'partners' && <PartnersPage />}
                      {page === 'recurring' && (
                        <RecurringContractsPage
                          initialContractId={openRecurringContractId}
                          onInitialContractConsumed={consumeOpenRecurringContract}
                        />
                      )}
                      {page === 'reports' && <ReportsPage />}
                      {page === 'sends' && (
                        <MessagesPage
                          onOpenOrder={(orderId) => navigateAdmin(toOrderDetailRoute(orderId, ordersView))}
                        />
                      )}
                      {!['dashboard', 'orders', 'calendar', 'photos', 'products', 'partners', 'recurring', 'reports', 'sends'].includes(page) && (
                        <ComingSoon page={page} />
                      )}
                    </>
                  );
                }}
              </AdminShell>
            ) : (
              <AdminLoginPage />
            )}
          </>
        )}

        {mode === 'partner' && (
          <>{isSwitchingRole ? <RouteState text="화면을 전환하는 중입니다." /> : partnerSession.user?.role === 'partner' ? <PartnerApp /> : <PartnerLoginPage />}</>
        )}
    </main>
  );
}

function RouteState({ text }) {
  return (
    <div style={{ minHeight: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
      {text}
    </div>
  );
}

function ComingSoon({ page }) {
  return (
    <div className="coming-soon">
      <div className="card">
        <div className="app-eyebrow">준비 중</div>
        <h2>{page}</h2>
        <p>운영 흐름에 맞춰 이어서 연결할 영역입니다.</p>
      </div>
    </div>
  );
}

function toOrdersView(options) {
  const tab = typeof options.ordersTab === 'string' ? options.ordersTab : DEFAULT_ORDERS_VIEW.tab;
  const datePreset = typeof options.datePreset === 'string'
    ? options.datePreset
    : getDefaultOrdersDatePreset(tab);

  return { tab, datePreset };
}

function toPageRoute(page, ordersView = DEFAULT_ORDERS_VIEW) {
  return {
    page,
    detailOrderId: null,
    orderForm: null,
    ordersView,
  };
}

function toOrderCreateRoute(_returnPage = 'orders', ordersView = DEFAULT_ORDERS_VIEW) {
  return {
    page: 'orders',
    detailOrderId: null,
    orderForm: { mode: 'create', orderId: null },
    ordersView,
  };
}

function toOrderDetailRoute(orderId, ordersView = DEFAULT_ORDERS_VIEW) {
  return {
    page: 'orders',
    detailOrderId: orderId,
    orderForm: null,
    ordersView,
  };
}

function toOrderEditRoute(orderId, ordersView = DEFAULT_ORDERS_VIEW) {
  return {
    page: 'orders',
    detailOrderId: orderId,
    orderForm: { mode: 'edit', orderId },
    ordersView,
  };
}

function toOrderDuplicateRoute(orderId, ordersView = DEFAULT_ORDERS_VIEW) {
  // 복제는 create 저장 경로를 쓰되 원본 주문의 고객정보만 복사한다.
  return {
    page: 'orders',
    detailOrderId: null,
    orderForm: { mode: 'create', orderId: null, duplicateFromOrderId: orderId },
    ordersView,
  };
}

function readAdminRouteFromLocation() {
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

function normalizeAdminRoute(route) {
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

function replaceAdminHistory(route) {
  writeAdminHistory(route, { replace: true });
}

function writeAdminHistory(route, { replace = false } = {}) {
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

function getDefaultOrdersDatePreset(tab) {
  if (tab === 'today') {
    return 'today';
  }
  if (tab === 'tomorrow_notice') {
    return 'tomorrow';
  }
  if (['payment_check', 'photo_review', 'deliver', 'partner_pending', 'monthly_done', 'monthly_revenue'].includes(tab)) {
    return tab.startsWith('monthly_') ? 'month' : 'all';
  }
  return DEFAULT_ORDERS_VIEW.datePreset;
}

function toAdminNavBadges(summary) {
  if (!summary) {
    return {};
  }

  const orderQueueCount = Number(summary.partner_pending || 0)
    + Number(summary.today_jobs || 0)
    + Number(summary.tomorrow_notice_targets || 0)
    + Number(summary.customer_delivery_needed || 0)
    + Number(summary.payment_check_needed || 0);
  const photoQueueCount = Number(summary.photo_review_pending || 0)
    + Number(summary.customer_delivery_needed || 0);

  return {
    orders: orderQueueCount > 0 ? String(orderQueueCount) : null,
    photos: photoQueueCount > 0 ? String(photoQueueCount) : null,
  };
}

function isCustomerLinkRoute() {
  return /^\/(?:c|customer)(?:\/|$)/.test(window.location.pathname);
}

function isPartnerLinkRoute() {
  return /^\/partner(?:\/|$)/.test(window.location.pathname);
}
