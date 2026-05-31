import React from 'react';
import { Avatar, Icon } from '../common/ui';

// Admin app shell — sidebar + topbar + page router

export const NAV = [
  { key: 'dashboard',  label: '대시보드',     icon: 'home' },
  { key: 'orders',     label: '주문관리',     icon: 'inbox' },
  { key: 'calendar',   label: '일정 캘린더',  icon: 'calendar' },
  { key: 'photos',     label: '사진검수',     icon: 'image' },
  { key: 'products',   label: '상품관리',     icon: 'package',  badge: null },
  { key: 'partners',   label: '협력사관리',   icon: 'truck',    badge: null },
  { key: 'reports',    label: '보고서',       icon: 'trending', badge: null },
  { key: 'sends',      label: '발송이력',     icon: 'send',     badge: null },
];

export function AdminShell({ initialPage = 'dashboard', children, onNav = undefined, onCreateOrder = undefined, navBadges = {} }) {
  const [page, setPage] = React.useState(initialPage);

  const handleNav = (k) => {
    setPage(k);
    if (onNav) onNav(k);
  };

  return (
    <div data-testid="admin-shell" style={{ display: 'flex', height: '100%', background: 'var(--bg)' }}>
      {/* Sidebar */}
      <aside style={{
        width: 220, flexShrink: 0,
        borderRight: '1px solid var(--border)',
        background: 'var(--surface)',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ height: 52, padding: '0 14px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid var(--border)' }}>
          <img
            src="/cleanjob-logo.png"
            alt="클린잡"
            style={{ height: 30, width: 'auto', display: 'block' }}
          />
          <div style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 700, letterSpacing: '0.04em' }}>
            운영 시스템
          </div>
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
          <Avatar name="전" size={26} tone="brand"/>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600 }}>전소영</div>
            <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}>운영팀 · 매니저</div>
          </div>
          <button className="btn btn--ghost btn--sm" style={{ padding: '0 6px' }}>
            <Icon name="settings" size={13}/>
          </button>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {children({ page, setPage })}
      </main>
      <button
        type="button"
        data-testid="admin-mobile-create-order"
        className="btn btn--primary admin-create-fab"
        onClick={() => onCreateOrder?.()}
      >
        <Icon name="plus" size={16}/>
      </button>
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

      {actions}
    </header>
  );
}
