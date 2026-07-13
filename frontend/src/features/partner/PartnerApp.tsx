import React from 'react';
import { BrandLogo } from '../../components/common/BrandLogo';
import { Icon } from '../../components/common/ui';
import { useAuth } from '../../store/authStore';
import { PartnerJobDetail } from './PartnerJobDetail';
import { PartnerAccount } from './PartnerAccount';

export function PartnerApp() {
  const auth = useAuth();
  const [tab, setTab] = React.useState('jobs');
  const [detailOpen, setDetailOpen] = React.useState(false);

  // 작업 상세는 자체 헤더/하단 CTA를 가진 전체 화면이라 앱바·네비를 숨긴다.
  // 내 정보 탭에서는 detailOpen이 의미 없으므로 항상 셸(앱바+네비)을 보여준다.
  const showShell = tab !== 'jobs' || !detailOpen;
  const company = (auth.user?.partner_name || '').trim();
  const manager = (auth.user?.name || '협력사').trim();
  // 앱바엔 회사명(있으면)을 우선 노출, 없으면 담당자명으로 폴백.
  const title = company || manager;

  return (
    <main style={{ height: '100%', width: '100%', maxWidth: 768, margin: '0 auto', display: 'flex', flexDirection: 'column', background: 'var(--bg-subtle)', overflow: 'hidden' }}>
      {showShell && (
        <PartnerTopBar
          title={title}
          subtitle={tab === 'account' ? '내 정보' : '오늘의 현장'}
          onLogout={() => void auth.logout('partner')}
        />
      )}

      <div style={{ flex: 1, minHeight: 0 }}>
        {tab === 'jobs' ? (
          <PartnerJobDetail onDetailOpenChange={setDetailOpen} />
        ) : (
          <PartnerAccount />
        )}
      </div>

      {showShell && (
        <nav aria-label="협력사 메뉴" style={navBarStyle}>
          <NavButton
            testId="partner-nav-jobs"
            icon="truck"
            label="내 작업"
            active={tab === 'jobs'}
            onClick={() => setTab('jobs')}
          />
          <NavButton
            testId="partner-nav-account"
            icon="user"
            label="내 정보"
            active={tab === 'account'}
            onClick={() => setTab('account')}
          />
        </nav>
      )}
    </main>
  );
}

function PartnerTopBar({ title, subtitle, onLogout }) {
  return (
    <header
      data-testid="partner-topbar"
      style={{
        flexShrink: 0,
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        padding: '11px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 11,
      }}
    >
      <BrandLogo size="sm" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--brand)' }}>클린잡 · 협력사 작업센터</div>
        <div title={`${title} · ${subtitle}`} style={{ fontSize: 15.5, fontWeight: 800, color: 'var(--text)', letterSpacing: '-0.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {title} <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-secondary)' }}>· {subtitle}</span>
        </div>
      </div>
      <button
        type="button"
        data-testid="partner-topbar-logout"
        aria-label="로그아웃"
        onClick={onLogout}
        style={{
          height: 34,
          padding: '0 9px',
          border: '1px solid var(--danger-border)',
          borderRadius: 9,
          background: 'var(--surface)',
          color: 'var(--danger-fg)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 11.5,
          fontWeight: 800,
          flexShrink: 0,
          cursor: 'pointer',
        }}
      >
        <Icon name="logOut" size={13} />
        로그아웃
      </button>
    </header>
  );
}

function NavButton({ testId, icon, label, active, onClick }) {
  const color = active ? 'var(--brand)' : 'var(--text-tertiary)';
  return (
    <button
      type="button"
      data-testid={testId}
      aria-current={active ? 'page' : undefined}
      onClick={onClick}
      style={{
        flex: 1,
        height: '100%',
        minHeight: 44,
        border: 'none',
        background: 'transparent',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 3,
        color,
        cursor: 'pointer',
      }}
    >
      <Icon name={icon} size={22} color={color} />
      <span style={{ fontSize: 11.5, fontWeight: active ? 700 : 500 }}>{label}</span>
    </button>
  );
}

const navBarStyle = {
  flexShrink: 0,
  height: 62,
  // 3-4: 일반 모바일 브라우저(사파리/크롬)에서 하단 네비가 잘리지 않도록,
  // 컨테이너는 100dvh(App.tsx)를 쓰고 여기선 iOS 홈 인디케이터 영역을 추가로 확보한다.
  boxSizing: 'content-box' as const,
  paddingBottom: 'env(safe-area-inset-bottom)',
  display: 'flex',
  alignItems: 'stretch',
  background: 'var(--surface)',
  borderTop: '1px solid var(--border)',
};
