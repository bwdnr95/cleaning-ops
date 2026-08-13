import React from 'react';
import { Avatar, Icon } from '../common/ui';
import { BrandLogo } from '../common/BrandLogo';
import { useIsNarrowViewport } from '../common/useIsNarrowViewport';
import { AdminNotificationsBell } from '../../features/admin/notifications/AdminNotificationsBell';

// Admin app shell — sidebar + topbar + page router

export const NAV = [
  { key: 'dashboard',  label: '대시보드',     icon: 'home' },
  { key: 'orders',     label: '주문관리',     icon: 'inbox' },
  { key: 'calendar',   label: '일정 캘린더',  icon: 'calendar' },
  { key: 'photos',     label: '사진/고객전달', icon: 'image' },
  { key: 'products',   label: '상품관리',     icon: 'package',  badge: null },
  { key: 'brokers',    label: '중개사관리',   icon: 'star',     badge: null },
  { key: 'partners',   label: '협력사관리',   icon: 'truck',    badge: null },
  { key: 'recurring',  label: '정기청소',     icon: 'refresh',  badge: null },
  { key: 'reports',    label: '보고서',       icon: 'trending', badge: null },
  { key: 'sends',      label: '발송이력',     icon: 'send',     badge: null },
];

export function AdminShell({
  initialPage = 'dashboard',
  page: controlledPage = undefined,
  onPageChange = undefined,
  children,
  onCreateOrder = undefined,
  showCreateOrderFab = true,
  navBadges = {},
  user = undefined,
  onLogout = undefined,
}) {
  const [uncontrolledPage, setUncontrolledPage] = React.useState(initialPage);
  const page = controlledPage ?? uncontrolledPage;
  const isNarrowViewport = useIsNarrowViewport();

  const setPage = React.useCallback((nextPage) => {
    if (onPageChange) {
      onPageChange(nextPage);
      return;
    }
    setUncontrolledPage(nextPage);
  }, [onPageChange]);

  const handleNav = (k) => {
    setPage(k);
  };

  return (
    <div data-testid="admin-shell" style={{ display: 'flex', height: '100%', background: 'var(--bg)', overflowX: isNarrowViewport ? 'hidden' : 'auto' }}>
      {/* Sidebar */}
      <aside style={{
        width: 220, flexShrink: 0,
        borderRight: '1px solid var(--border)',
        background: 'var(--surface)',
        display: isNarrowViewport ? 'none' : 'flex', flexDirection: 'column',
      }}>
        <div style={{ height: 52, padding: '0 14px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid var(--border)' }}>
          <BrandLogo size="sm" caption="운영 시스템" />
        </div>

        <nav style={{ padding: 8, flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-quaternary)', padding: '10px 8px 4px', letterSpacing: '0.06em', fontWeight: 600 }}>운영 메뉴</div>
          {NAV.map((n) => {
            const active = page === n.key;
            const badge = navBadges[n.key] ?? n.badge;
            return (
              <button key={n.key} data-testid={`admin-nav-${n.key}`} onClick={() => handleNav(n.key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 9,
                  height: 30, padding: '0 8px',
                  border: 'none', borderRadius: 5,
                  background: active ? 'var(--brand-bg)' : 'transparent',
                  color: active ? 'var(--brand)' : 'var(--text-secondary)',
                  fontSize: 12.5, fontWeight: active ? 600 : 500,
                  cursor: 'pointer', textAlign: 'left',
                  letterSpacing: '-0.01em',
                }}
                onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = 'var(--bg-muted)'; }}
                onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent'; }}>
                <Icon name={n.icon} size={14}/>
                <span style={{ flex: 1 }}>{n.label}</span>
                {badge ? (
                  <span style={{
                    fontSize: 10.5, fontWeight: 600,
                    padding: '1px 6px', borderRadius: 10,
                    background: active ? 'var(--brand)' : 'var(--neutral-bg)',
                    color: active ? '#fff' : 'var(--neutral-fg)',
                  }} data-testid={`admin-nav-badge-${n.key}`}>{badge}</span>
                ) : null}
              </button>
            );
          })}
          <button
            type="button"
            data-testid="admin-nav-create-order"
            className="btn btn--primary btn--sm"
            onClick={() => onCreateOrder?.()}
            style={{ margin: '10px 6px 0', justifyContent: 'flex-start' }}
          >
            <Icon name="plus" size={13}/> 신규 주문 등록
          </button>
        </nav>

        <div style={{ padding: 10, borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Avatar name={(user?.name || '관')[0]} size={26} tone="brand"/>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.name || '관리자'}</div>
            <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.email || '운영 관리자'}</div>
          </div>
          <button
            type="button"
            data-testid="admin-logout"
            className="btn btn--ghost btn--sm"
            aria-label="로그아웃"
            title="로그아웃"
            onClick={() => onLogout?.()}
            style={{ height: 30, padding: '0 8px', gap: 4, color: 'var(--danger-fg)', flexShrink: 0 }}
          >
            <Icon name="logOut" size={14}/>
            <span style={{ fontSize: 11.5, fontWeight: 700 }}>로그아웃</span>
          </button>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: isNarrowViewport ? 0 : 760, paddingBottom: isNarrowViewport ? 88 : 0 }}>
        {children({ page, setPage })}
      </main>
      {isNarrowViewport && (
        <nav
          data-testid="admin-mobile-nav"
          className="admin-mobile-nav"
          style={{
            position: 'fixed',
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 45,
            height: 82,
            padding: '8px 10px 10px',
            display: 'flex',
            gap: 6,
            overflowX: 'auto',
            background: 'var(--surface)',
            borderTop: '1px solid var(--border)',
            boxShadow: '0 -8px 24px rgba(15, 23, 42, 0.08)',
          }}
        >
          {NAV.map((item) => {
            const active = page === item.key;
            const badge = navBadges[item.key] ?? item.badge;
            return (
              <button
                key={item.key}
                type="button"
                data-testid={`admin-mobile-nav-${item.key}`}
                onClick={() => handleNav(item.key)}
                style={{
                  position: 'relative',
                  flex: '0 0 68px',
                  border: 'none',
                  borderRadius: 7,
                  background: active ? 'var(--brand-bg)' : 'transparent',
                  color: active ? 'var(--brand)' : 'var(--text-secondary)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                  fontSize: 10.5,
                  fontWeight: active ? 700 : 600,
                  cursor: 'pointer',
                }}
              >
                <Icon name={item.icon} size={15}/>
                <span style={{ whiteSpace: 'nowrap' }}>{item.label}</span>
                {badge ? (
                  <span style={{
                    position: 'absolute',
                    top: 5,
                    right: 7,
                    minWidth: 16,
                    height: 16,
                    padding: '0 4px',
                    borderRadius: 999,
                    background: active ? 'var(--brand)' : 'var(--neutral-bg)',
                    color: active ? '#fff' : 'var(--neutral-fg)',
                    fontSize: 10,
                    fontWeight: 700,
                    lineHeight: '16px',
                  }}>{badge}</span>
                ) : null}
              </button>
            );
          })}
        </nav>
      )}
      {showCreateOrderFab && (
        <button
          type="button"
          data-testid="admin-mobile-create-order"
          aria-label="신규 주문 등록"
          className="btn btn--primary admin-create-fab"
          onClick={() => onCreateOrder?.()}
        >
          <Icon name="plus" size={16}/>
        </button>
      )}
    </div>
  );
}

export function Topbar({ title, subtitle = undefined, breadcrumb = undefined, actions = null }) {
  return (
    <header style={{
      height: 52, padding: '0 12px',
      display: 'flex', alignItems: 'center', gap: 12,
      borderBottom: '1px solid var(--border)',
      background: 'var(--surface)',
      flexShrink: 0,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        {breadcrumb && (
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 1, display: 'flex', alignItems: 'center', gap: 4 }}>
            {breadcrumb.map((b, i) => (
              <React.Fragment key={i}>
                {i > 0 && <Icon name="chevronRight" size={11}/>}
                <span style={i === breadcrumb.length - 1 ? { color: 'var(--text-secondary)' } : {}}>{b}</span>
              </React.Fragment>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <h1 data-testid="admin-topbar-title" style={{ margin: 0, fontSize: 15, fontWeight: 600, letterSpacing: '-0.015em' }}>{title}</h1>
          {subtitle && <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{subtitle}</span>}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {actions}
        <AdminNotificationsBell />
      </div>
    </header>
  );
}
