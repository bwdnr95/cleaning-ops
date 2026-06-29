import React from 'react';
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
  const name = (auth.user?.name || '협력사').trim();

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#f4f6f8', overflow: 'hidden' }}>
      {showShell && <PartnerTopBar name={name} subtitle={tab === 'account' ? '내 정보' : '오늘의 현장'} />}

      <div style={{ flex: 1, minHeight: 0 }}>
        {tab === 'jobs' ? (
          <PartnerJobDetail onDetailOpenChange={setDetailOpen} />
        ) : (
          <PartnerAccount />
        )}
      </div>

      {showShell && (
        <nav style={navBarStyle}>
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
    </div>
  );
}

function PartnerTopBar({ name, subtitle }) {
  const initial = (name || '협').charAt(0) || '협';
  return (
    <header
      data-testid="partner-topbar"
      style={{
        flexShrink: 0,
        background: '#fff',
        borderBottom: '1px solid var(--border)',
        padding: '11px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 11,
      }}
    >
      <span style={{ width: 36, height: 36, borderRadius: 11, background: 'var(--brand)', color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <Icon name="truck" size={19} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.1em', color: 'var(--brand)' }}>CLEAN OPS · 협력사</div>
        <div style={{ fontSize: 15.5, fontWeight: 800, color: 'var(--text)', letterSpacing: '-0.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {name}님 <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-tertiary)' }}>· {subtitle}</span>
        </div>
      </div>
      <span style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--brand-bg)', color: 'var(--brand)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, fontWeight: 800, flexShrink: 0 }}>
        {initial}
      </span>
    </header>
  );
}

function NavButton({ testId, icon, label, active, onClick }) {
  const color = active ? 'var(--brand)' : 'var(--text-tertiary)';
  return (
    <button
      type="button"
      data-testid={testId}
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
  display: 'flex',
  alignItems: 'stretch',
  background: '#fff',
  borderTop: '1px solid var(--border)',
};
