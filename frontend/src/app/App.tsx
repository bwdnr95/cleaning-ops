import React from 'react';

import { AdminShell, Topbar } from '../components/layout/AdminShell';
import { getDashboardSummary } from '../api/admin';
import { useApiResource } from '../api/useApiResource';
import { AdminLoginPage, PartnerLoginPage } from '../features/auth/LoginPages';
import { useAuth } from '../store/authStore';
import {
  ADMIN_PAGE_META,
  DEFAULT_ORDERS_VIEW,
  type OrdersView,
  normalizeAdminRoute,
  readAdminRouteFromLocation,
  replaceAdminHistory,
  toAdminNavBadges,
  toOrderCreateRoute,
  toOrderDetailRoute,
  toOrderDuplicateRoute,
  toOrderEditRoute,
  toOrdersView,
  toPageRoute,
  writeAdminHistory,
} from './adminRouteState';
import { ComingSoon, isCustomerLinkRoute, isPartnerLinkRoute, RouteState } from './AppRoutePrimitives';
import {
  BrokersPage,
  CalendarPage,
  CustomerReservation,
  Dashboard,
  MessagesPage,
  OrderDetailPage,
  OrderFormPage,
  OrdersPage,
  PartnerApp,
  PartnersPage,
  PhotoReviewPage,
  ProductsPage,
  RecurringContractsPage,
  ReportsPage,
} from './lazyPages';

export function App() {
  const auth = useAuth();
  const isStandaloneCustomerLink = isCustomerLinkRoute();
  const isStandalonePartnerLink = isPartnerLinkRoute();
  const mode = isStandalonePartnerLink ? 'partner' : 'admin';
  const [adminRoute, setAdminRoute] = React.useState(() => readAdminRouteFromLocation());
  const adminRouteRef = React.useRef(adminRoute);
  const [adminNavigationRevision, setAdminNavigationRevision] = React.useState(0);
  React.useEffect(() => {
    adminRouteRef.current = adminRoute;
  }, [adminRoute]);
  // 주문 상세의 '정기' 배지에서 계약으로 역링크할 때 전달할 계약 id(데모 affordance: 해시 라우트와 별개).
  const [openRecurringContractId, setOpenRecurringContractId] = React.useState<string | null>(null);
  const [recurringInitialTab, setRecurringInitialTab] = React.useState<'contracts' | 'orders'>('contracts');
  const [orderReturnPage, setOrderReturnPage] = React.useState<'orders' | 'recurring'>('orders');
  const consumeOpenRecurringContract = React.useCallback(() => setOpenRecurringContractId(null), []);
  const adminSession = auth.getSession('admin');
  const partnerSession = auth.getSession('partner');
  const adminSummaryLoader = React.useCallback(() => {
    if (isStandaloneCustomerLink || mode !== 'admin' || adminSession.user?.role !== 'admin') {
      return Promise.resolve(null);
    }
    return getDashboardSummary();
  }, [adminSession.user?.role, isStandaloneCustomerLink, mode]);
  const adminSummary = useApiResource(adminSummaryLoader, `${mode}:${isStandaloneCustomerLink ? 'customer' : adminSession.accessToken || 'guest'}`);
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
      const route = readAdminRouteFromLocation();
      adminRouteRef.current = route;
      setAdminRoute(route);
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
    adminRouteRef.current = route;
    setAdminNavigationRevision((revision) => revision + 1);
    setAdminRoute(route);
    writeAdminHistory(route, options);
  }, []);

  const syncOrdersView = React.useCallback((nextOrdersView: OrdersView) => {
    const route = normalizeAdminRoute({
      ...adminRouteRef.current,
      ordersView: nextOrdersView,
    });
    adminRouteRef.current = route;
    replaceAdminHistory(route);
  }, []);

  const detailOrderId = adminRoute.detailOrderId;
  const orderForm = adminRoute.orderForm;
  const ordersView = adminRoute.ordersView;
  const openOrder = React.useCallback((orderId: string, returnPage: 'orders' | 'recurring' = 'orders') => {
    setOrderReturnPage(returnPage);
    navigateAdmin(toOrderDetailRoute(orderId, adminRouteRef.current.ordersView));
  }, [navigateAdmin]);
  const editOrder = React.useCallback((orderId: string, returnPage: 'orders' | 'recurring' = 'orders') => {
    setOrderReturnPage(returnPage);
    navigateAdmin(toOrderEditRoute(orderId, adminRouteRef.current.ordersView));
  }, [navigateAdmin]);

  if (isStandaloneCustomerLink) {
    return (
      <main style={{ minHeight: '100dvh', height: '100dvh', width: '100vw', background: '#f7f6f3' }}>
        <React.Suspense fallback={<RouteState text="고객 화면을 불러오는 중입니다." />}>
          <CustomerReservation />
        </React.Suspense>
      </main>
    );
  }

  return (
    <main style={{ height: '100dvh', width: '100vw', overflow: 'hidden', background: 'var(--bg)' }}>
      <React.Suspense fallback={<RouteState text="화면을 불러오는 중입니다." />}>
        {mode === 'admin' && (
          <>
            {isSwitchingRole ? (
              <RouteState text="화면을 전환하는 중입니다." />
            ) : adminSession.user?.role === 'admin' ? (
              <AdminShell
                page={adminRoute.page}
                onPageChange={(nextPage) => {
                  if (nextPage === 'recurring') {
                    setRecurringInitialTab('contracts');
                  }
                  navigateAdmin(toPageRoute(nextPage));
                }}
                onCreateOrder={() => navigateAdmin(toOrderCreateRoute(
                  adminRoute.page,
                  adminRoute.page === 'orders' ? adminRouteRef.current.ordersView : DEFAULT_ORDERS_VIEW,
                ))}
                showCreateOrderFab={!orderForm && adminRoute.page !== 'recurring'}
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
                          onBack={() => {
                            if (orderReturnPage === 'recurring') {
                              setRecurringInitialTab('orders');
                              navigateAdmin(toPageRoute('recurring', ordersView));
                              return;
                            }
                            navigateAdmin(toPageRoute('orders', ordersView));
                          }}
                          onEdit={() => navigateAdmin(toOrderEditRoute(detailOrderId, ordersView))}
                          onDuplicate={() => navigateAdmin(toOrderDuplicateRoute(detailOrderId, ordersView))}
                          onOpenOrder={(nextOrderId) => navigateAdmin(toOrderDetailRoute(nextOrderId, ordersView))}
                          onOpenRecurringContract={(contractId) => {
                            setOpenRecurringContractId(contractId);
                            setRecurringInitialTab('contracts');
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
                          onOpenOrder={(orderId) => openOrder(orderId)}
                        />
                      )}
                      {page === 'orders' && (
                        <OrdersPage
                          key={`orders-${adminNavigationRevision}`}
                          initialTab={ordersView.tab}
                          initialDatePreset={ordersView.datePreset}
                          initialQuery={ordersView.query}
                          initialPartnerId={ordersView.partnerId}
                          initialBrokerId={ordersView.brokerId}
                          initialPage={ordersView.page}
                          initialVisitFrom={ordersView.visitFrom}
                          initialVisitTo={ordersView.visitTo}
                          initialReceivedDatePreset={ordersView.receivedDatePreset}
                          initialReceivedFrom={ordersView.receivedFrom}
                          initialReceivedTo={ordersView.receivedTo}
                          initialSortBy={ordersView.sortBy}
                          initialPageSize={ordersView.pageSize}
                          onViewChange={syncOrdersView}
                          onOpenOrder={(orderId) => openOrder(orderId)}
                          onEditOrder={(orderId) => editOrder(orderId)}
                          onCreateOrder={() => navigateAdmin(toOrderCreateRoute('orders', adminRouteRef.current.ordersView))}
                        />
                      )}
                      {page === 'calendar' && (
                        <CalendarPage
                          onOpenOrder={(orderId) => openOrder(orderId)}
                          onCreateOrder={() => navigateAdmin(toOrderCreateRoute('calendar'))}
                        />
                      )}
                      {page === 'photos' && (
                        <PhotoReviewPage
                          onOpenOrder={(orderId) => openOrder(orderId)}
                          onNav={(nextPage) => {
                            setPage(nextPage);
                          }}
                        />
                      )}
                      {page === 'products' && <ProductsPage />}
                      {page === 'brokers' && <BrokersPage />}
                      {page === 'partners' && <PartnersPage />}
                      {page === 'recurring' && (
                        <RecurringContractsPage
                          initialContractId={openRecurringContractId}
                          initialTab={recurringInitialTab}
                          onInitialContractConsumed={consumeOpenRecurringContract}
                          onEditOrder={(orderId) => editOrder(orderId, 'recurring')}
                          onOpenOrder={(orderId) => openOrder(orderId, 'recurring')}
                        />
                      )}
                      {page === 'reports' && <ReportsPage />}
                      {page === 'sends' && (
                        <MessagesPage
                          onOpenOrder={(orderId) => openOrder(orderId)}
                        />
                      )}
                      {!['dashboard', 'orders', 'calendar', 'photos', 'products', 'brokers', 'partners', 'recurring', 'reports', 'sends'].includes(page) && (
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
      </React.Suspense>
    </main>
  );
}
