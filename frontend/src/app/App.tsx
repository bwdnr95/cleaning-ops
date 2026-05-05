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
    breadcrumb: ['Workspace', '대시보드'],
  },
  orders: {
    title: '주문관리',
    subtitle: '158건',
    breadcrumb: ['Workspace', '주문관리'],
  },
  calendar: {
    title: '일정 캘린더',
    subtitle: '2026년 5월 · 56건',
    breadcrumb: ['Workspace', '일정 캘린더'],
  },
  photos: {
    title: '사진검수',
    subtitle: '6건 대기',
    breadcrumb: ['Workspace', '사진검수'],
  },
  products: {
    title: '상품관리',
    subtitle: '서비스 기준가',
    breadcrumb: ['Workspace', '상품관리'],
  },
  sends: {
    title: '발송이력',
    subtitle: '고객/협력사 안내',
    breadcrumb: ['Workspace', '발송이력'],
  },
  partners: {
    title: '협력사관리',
    subtitle: '계정 / 배정 현황',
    breadcrumb: ['Workspace', '협력사관리'],
  },
};

export function App() {
  const auth = useAuth();
  const isStandaloneCustomerLink = isCustomerLinkRoute();
  const [mode, setMode] = React.useState('admin');
  const [theme, setTheme] = React.useState('light');
  const [detailOrderId, setDetailOrderId] = React.useState(null);
  const [orderForm, setOrderForm] = React.useState(null);
  const [ordersTab, setOrdersTab] = React.useState('all');
  const adminSummaryLoader = React.useCallback(() => {
    if (auth.user?.role !== 'admin') {
      return Promise.resolve(null);
    }
    return getDashboardSummary();
  }, [auth.user?.role]);
  const adminSummary = useApiResource(adminSummaryLoader, auth.user?.role || 'guest');
  const navBadges = toAdminNavBadges(adminSummary.data);

  React.useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

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
          <div className="app-eyebrow">Cleaning Ops Control Center</div>
          <h1>운영관리 앱 미리보기</h1>
        </div>
        <div className="app-toolbar-actions">
          {auth.isAuthenticated && (
            <div className="app-session">
              <span>{auth.user?.name}</span>
              <button className="app-tab" onClick={() => void auth.logout()}>
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
              onClick={() => setMode(key)}
            >
              {label}
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
            {auth.user?.role === 'admin' ? (
              <AdminShell
                initialPage="dashboard"
                onNav={() => {
                  setDetailOrderId(null);
                  setOrderForm(null);
                  setOrdersTab('all');
                }}
                navBadges={navBadges}
              >
                {({ page, setPage }) => {
                  if (orderForm) {
                    return (
                      <>
                        <Topbar
                          title={orderForm.mode === 'edit' ? '주문 수정' : '신규 주문 등록'}
                          breadcrumb={['Workspace', '주문관리', orderForm.mode === 'edit' ? orderForm.orderId : 'new']}
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
                          breadcrumb={['Workspace', '주문관리', detailOrderId]}
                        />
                        <OrderDetailPage
                          orderId={detailOrderId}
                          onBack={() => setDetailOrderId(null)}
                          onEdit={() => setOrderForm({ mode: 'edit', orderId: detailOrderId })}
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
                            const nextOrdersTab = 'ordersTab' in options ? options.ordersTab : null;
                            setDetailOrderId(null);
                            setOrderForm(null);
                            if (typeof nextOrdersTab === 'string') {
                              setOrdersTab(nextOrdersTab);
                            }
                            setPage(nextPage);
                          }}
                          onOpenOrder={(orderId) => setDetailOrderId(orderId)}
                        />
                      )}
                      {page === 'orders' && (
                        <OrdersPage
                          initialTab={ordersTab}
                          onOpenOrder={(orderId) => setDetailOrderId(orderId)}
                          onCreateOrder={() => setOrderForm({ mode: 'create', orderId: null })}
                        />
                      )}
                      {page === 'calendar' && (
                        <CalendarPage
                          onOpenOrder={(orderId) => setDetailOrderId(orderId)}
                          onCreateOrder={() => setOrderForm({ mode: 'create', orderId: null })}
                        />
                      )}
                      {page === 'photos' && <PhotoReviewPage />}
                      {page === 'products' && <ProductsPage />}
                      {page === 'partners' && <PartnersPage />}
                      {page === 'sends' && <MessagesPage />}
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
            {auth.user?.role === 'partner' ? <PartnerJobDetail /> : <PartnerLoginPage />}
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
        <div className="app-eyebrow">Next module</div>
        <h2>{page}</h2>
        <p>기획서 기준에 맞춰 같은 레이어 규칙으로 이어서 구현할 영역입니다.</p>
      </div>
    </div>
  );
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
