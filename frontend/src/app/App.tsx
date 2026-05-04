import React from 'react';

import { DesktopFrame, PhoneFrame } from '../components/frames/DeviceFrames';
import { AdminShell, Topbar } from '../components/layout/AdminShell';
import { AdminLoginPage, PartnerLoginPage } from '../features/auth/LoginPages';
import { CalendarPage } from '../features/admin/calendar/CalendarPage';
import { Dashboard } from '../features/admin/dashboard/Dashboard';
import { OrderDetailPage } from '../features/admin/orders/OrderDetailPage';
import { OrderFormPage } from '../features/admin/orders/OrderFormPage';
import { OrdersPage } from '../features/admin/orders/OrdersPage';
import { PhotoReviewPage } from '../features/admin/photo-review/PhotoReviewPage';
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
};

export function App() {
  const auth = useAuth();
  const [mode, setMode] = React.useState('admin');
  const [theme, setTheme] = React.useState('light');
  const [detailOrderId, setDetailOrderId] = React.useState(null);
  const [orderForm, setOrderForm] = React.useState(null);

  React.useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

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
              <AdminShell initialPage="dashboard">
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
                          onNav={setPage}
                          onOpenOrder={(orderId) => setDetailOrderId(orderId)}
                        />
                      )}
                      {page === 'orders' && (
                        <OrdersPage
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
                      {!['dashboard', 'orders', 'calendar', 'photos'].includes(page) && (
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
