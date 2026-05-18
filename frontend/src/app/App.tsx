import React from 'react';

import { DesktopFrame, PhoneFrame } from '../components/frames/DeviceFrames';
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
};

const DEFAULT_ORDERS_VIEW = { tab: 'all', datePreset: 'all' };

export function App() {
  const auth = useAuth();
  const isStandaloneCustomerLink = isCustomerLinkRoute();
  const [mode, setMode] = React.useState(() => auth.activeRole || 'admin');
  const [theme, setTheme] = React.useState('light');
  const [detailOrderId, setDetailOrderId] = React.useState(null);
  const [orderForm, setOrderForm] = React.useState(null);
  const [ordersView, setOrdersView] = React.useState(DEFAULT_ORDERS_VIEW);
  const adminSession = auth.getSession('admin');
  const partnerSession = auth.getSession('partner');
  const activeModeSession = ['admin', 'partner'].includes(mode) ? auth.getSession(mode) : null;
  const adminSummaryLoader = React.useCallback(() => {
    if (mode !== 'admin' || adminSession.user?.role !== 'admin') {
      return Promise.resolve(null);
    }
    return getDashboardSummary();
  }, [adminSession.user?.role, mode]);
  const adminSummary = useApiResource(adminSummaryLoader, `${mode}:${adminSession.accessToken || 'guest'}`);
  const navBadges = toAdminNavBadges(adminSummary.data);

  React.useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const handleModeChange = (nextMode) => {
    setMode(nextMode);
    if (nextMode === 'admin' || nextMode === 'partner') {
      auth.setActiveRole(nextMode);
    }
  };

  if (isStandaloneCustomerLink) {
    return (
      <div style={{ minHeight: '100vh', height: '100vh', background: '#f7f6f3' }}>
        <CustomerReservation />
      </div>
    );
  }

  return (
    <div className="app-root">
      <div className="app-toolbar">
        <div>
          <div className="app-eyebrow">클린잡 · 운영 시스템</div>
          <h1>운영 컨트롤 센터</h1>
        </div>
        <div className="app-toolbar-actions">
          {activeModeSession?.user && (
            <div className="app-session">
              <span>{activeModeSession.user.name}</span>
              <button className="app-tab" onClick={() => void auth.logout(mode)}>
                로그아웃
              </button>
            </div>
          )}
          {[
            ['admin', '관리자'],
            ['partner', '협력사'],
            ['customer', '고객'],
          ].map(([key, label]) => (
            <button
              key={key}
              data-testid={`app-mode-${key}`}
              className={mode === key ? 'app-tab is-active' : 'app-tab'}
              onClick={() => handleModeChange(key)}
            >
              {label}
              {key !== 'customer' && auth.isRoleAuthenticated(key) && (
                <span className="app-tab-status" aria-label={`${label} 로그인됨`} />
              )}
            </button>
          ))}
          <button
            className="app-tab"
            onClick={() => setTheme((current) => (current === 'light' ? 'dark' : 'light'))}
          >
            {theme === 'light' ? '다크' : '라이트'}
          </button>
        </div>
      </div>

      <main className="app-preview">
        {mode === 'admin' && (
          <DesktopFrame>
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
                      {page === 'sends' && (
                        <MessagesPage
                          onOpenOrder={(orderId) => setDetailOrderId(orderId)}
                        />
                      )}
                      {!['dashboard', 'orders', 'calendar', 'photos', 'products', 'partners', 'sends'].includes(page) && (
                        <ComingSoon page={page} />
                      )}
                    </>
                  );
                }}
              </AdminShell>
            ) : (
              <AdminLoginPage />
            )}
          </DesktopFrame>
        )}

        {mode === 'partner' && (
          <PhoneFrame>
            {partnerSession.user?.role === 'partner' ? <PartnerJobDetail /> : <PartnerLoginPage />}
          </PhoneFrame>
        )}

        {mode === 'customer' && (
          <PhoneFrame time="9:14">
            <CustomerReservation />
          </PhoneFrame>
        )}
      </main>
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
