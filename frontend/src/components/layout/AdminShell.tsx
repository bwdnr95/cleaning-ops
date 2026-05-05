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
  { key: 'sends',      label: '발송이력',     icon: 'send',     badge: null },
];

export function AdminShell({ initialPage = 'dashboard', children, onNav = undefined, navBadges = {} }) {
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
        <div style={{ height: 52, padding: '0 16px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--border)' }}>
          <div style={{
            width: 26, height: 26, borderRadius: 6,
            background: 'linear-gradient(135deg, var(--brand) 0%, #818cf8 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontWeight: 700, fontSize: 13, letterSpacing: '-0.04em',
          }}>C</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: '-0.01em' }}>Cleaning Ops</div>
            <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', marginTop: -2 }}>Control Center</div>
          </div>
        </div>

        <nav style={{ padding: 8, flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
          <div style={{ fontSize: 10.5, color: 'var(--text-quaternary)', padding: '10px 8px 4px', letterSpacing: '0.06em', fontWeight: 600 }}>WORKSPACE</div>
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

          <div style={{ fontSize: 10.5, color: 'var(--text-quaternary)', padding: '16px 8px 4px', letterSpacing: '0.06em', fontWeight: 600 }}>QUICK FILTERS</div>
          {[
            { label: '오늘 작업', count: 5 },
            { label: '내 담당', count: 8 },
            { label: '잔금 미확인', count: 2 },
          ].map((f) => (
            <button key={f.label} style={{
              display: 'flex', alignItems: 'center', gap: 9,
              height: 28, padding: '0 8px',
              border: 'none', borderRadius: 5, background: 'transparent',
              color: 'var(--text-tertiary)', fontSize: 12, cursor: 'pointer', textAlign: 'left',
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-quaternary)' }}/>
              <span style={{ flex: 1 }}>{f.label}</span>
              <span style={{ fontSize: 11, color: 'var(--text-quaternary)' }}>{f.count}</span>
            </button>
          ))}
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
    </div>
  );
}

export function Topbar({ title, subtitle = undefined, breadcrumb = undefined, actions = null }) {
  return (
    <header style={{
      height: 52, padding: '0 20px',
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

      <div style={{
        display: 'flex', alignItems: 'center',
        height: 30, width: 240, padding: '0 10px',
        background: 'var(--bg-subtle)',
        border: '1px solid var(--border)',
        borderRadius: 6, gap: 6,
        color: 'var(--text-tertiary)', fontSize: 12,
      }}>
        <Icon name="search" size={13}/>
        <span style={{ flex: 1 }}>주문번호, 고객, 주소 검색</span>
        <span className="kbd">⌘K</span>
      </div>

      {actions}

      <button className="btn btn--ghost btn--sm" style={{ padding: '0 6px', position: 'relative' }}>
        <Icon name="bell" size={14}/>
        <span style={{
          position: 'absolute', top: 2, right: 2,
          width: 6, height: 6, borderRadius: '50%', background: 'var(--danger)',
        }}/>
      </button>
    </header>
  );
}
