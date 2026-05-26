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
import { ReportsPage } from '../features/admin/reports/ReportsPage';
import { CustomerReservation } from '../features/customer/CustomerReservation';
import { PartnerJobDetail } from '../features/partner/PartnerJobDetail';
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
    title: '사진검수',
    subtitle: '검수 / 고객 전달',
    breadcrumb: ['운영', '사진검수'],
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
  reports: {
    title: '보고서',
    subtitle: '매출 / 협력사 / 서비스 / 정산',
    breadcrumb: ['운영', '보고서'],
  },
};

const DEFAULT_ORDERS_VIEW = { tab: 'all', datePreset: 'all' };

export function App() {
  const auth = useAuth();
  const isStandaloneCustomerLink = isCustomerLinkRoute();
  const isStandalonePartnerLink = isPartnerLinkRoute();
  const mode = isStandalonePartnerLink ? 'partner' : 'admin';
  const [detailOrderId, setDetailOrderId] = React.useState(null);
  const [orderForm, setOrderForm] = React.useState(null);
  const [ordersView, setOrdersView] = React.useState(DEFAULT_ORDERS_VIEW);
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

  React.useEffect(() => {
    if (auth.activeRole !== mode) {
      auth.setActiveRole(mode);
    }
  }, [auth, mode]);

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
            {adminSession.user?.role === 'admin' ? (
              <AdminShell
                initialPage="dashboard"
                onNav={() => {
                  setDetailOrderId(null);
                  setOrderForm(null);
                  setOrdersView(DEFAULT_ORDERS_VIEW);
                }}
                navBadges={navBadges}
              >
                {({ page, setPage }) => {
                  if (orderForm) {
                    return (
                      <>
                        <Topbar
                          title={orderForm.mode === 'edit' ? '주문 수정' : '신규 주문 등록'}
                          breadcrumb={['운영', '주문관리', orderForm.mode === 'edit' ? orderForm.orderId : '신규']}
                        />
                        <OrderFormPage
                          mode={orderForm.mode}
                          orderId={orderForm.orderId}
                          onCancel={() => setOrderForm(null)}
                          onSaved={(order) => {
                            setOrderForm(null);
                            setDetailOrderId(order.id);
                            setPage('orders');
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
                          breadcrumb={['운영', '주문관리', detailOrderId]}
                        />
                        <OrderDetailPage
                          orderId={detailOrderId}
                          onBack={() => setDetailOrderId(null)}
                          onEdit={() => setOrderForm({ mode: 'edit', orderId: detailOrderId })}
                          onOpenOrder={(nextOrderId) => setDetailOrderId(nextOrderId)}
                          onNav={(nextPage) => {
                            setDetailOrderId(null);
                            setOrderForm(null);
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
                          onCreateOrder={() => setOrderForm({ mode: 'create', orderId: null })}
                          onNav={(nextPage, options = {}) => {
                            setDetailOrderId(null);
                            setOrderForm(null);
                            if (nextPage === 'orders') {
                              setOrdersView(toOrdersView(options));
                            }
                            setPage(nextPage);
                          }}
                          onOpenOrder={(orderId) => setDetailOrderId(orderId)}
                        />
                      )}
                      {page === 'orders' && (
                        <OrdersPage
                          initialTab={ordersView.tab}
                          initialDatePreset={ordersView.datePreset}
                          onOpenOrder={(orderId) => setDetailOrderId(orderId)}
                          onEditOrder={(orderId) => setOrderForm({ mode: 'edit', orderId })}
                          onCreateOrder={() => setOrderForm({ mode: 'create', orderId: null })}
                        />
                      )}
                      {page === 'calendar' && (
                        <CalendarPage
                          onOpenOrder={(orderId) => setDetailOrderId(orderId)}
                          onCreateOrder={() => setOrderForm({ mode: 'create', orderId: null })}
                        />
                      )}
                      {page === 'photos' && (
                        <PhotoReviewPage
                          onOpenOrder={(orderId) => setDetailOrderId(orderId)}
                          onNav={(nextPage) => {
                            setDetailOrderId(null);
                            setOrderForm(null);
                            setPage(nextPage);
                          }}
                        />
                      )}
                      {page === 'products' && <ProductsPage />}
                      {page === 'partners' && <PartnersPage />}
                      {page === 'reports' && <ReportsPage />}
                      {page === 'sends' && (
                        <MessagesPage
                          onOpenOrder={(orderId) => setDetailOrderId(orderId)}
                        />
                      )}
                      {!['dashboard', 'orders', 'calendar', 'photos', 'products', 'partners', 'reports', 'sends'].includes(page) && (
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
          <>{partnerSession.user?.role === 'partner' ? <PartnerJobDetail /> : <PartnerLoginPage />}</>
        )}
    </main>
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
