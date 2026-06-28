import React from 'react';
import { Icon } from '../../components/common/ui';
import { PartnerJobDetail } from './PartnerJobDetail';
import { PartnerAccount } from './PartnerAccount';

export function PartnerApp() {
  const [tab, setTab] = React.useState('jobs');
  const [detailOpen, setDetailOpen] = React.useState(false);

  // 작업 상세는 자체 뒤로가기/하단 CTA를 가진 전체 화면이라 네비를 숨긴다.
  // 내 정보 탭에서는 detailOpen이 의미 없으므로 항상 네비를 보여준다.
  const showNav = tab !== 'jobs' || !detailOpen;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#f4f6f8', overflow: 'hidden' }}>
      <div style={{ flex: 1, minHeight: 0 }}>
        {tab === 'jobs' ? (
          <PartnerJobDetail onDetailOpenChange={setDetailOpen} />
        ) : (
          <PartnerAccount />
        )}
      </div>

      {showNav && (
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
