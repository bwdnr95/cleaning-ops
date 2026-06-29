import React from 'react';
import { Avatar, Icon } from '../../components/common/ui';
import { ApiError } from '../../api/client';
import { formatPhone } from '../../domain/phone';
import { useAuth } from '../../store/authStore';

export function PartnerAccount() {
  const auth = useAuth();
  const [currentPassword, setCurrentPassword] = React.useState('');
  const [newPassword, setNewPassword] = React.useState('');
  const [error, setError] = React.useState(null);
  const [notice, setNotice] = React.useState(null);
  const [isSaving, setIsSaving] = React.useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (isSaving) {
      return;
    }
    const current = currentPassword.trim();
    const next = newPassword.trim();
    if (!current || !next) {
      setError('현재 비밀번호와 새 비밀번호를 모두 입력해주세요.');
      setNotice(null);
      return;
    }

    setError(null);
    setNotice(null);
    setIsSaving(true);
    try {
      await auth.changePassword(current, next);
      setCurrentPassword('');
      setNewPassword('');
      setNotice('비밀번호가 변경되었습니다.');
    } catch (requestError) {
      setError(toChangePasswordMessage(requestError));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div data-testid="partner-account-page" style={{ height: '100%', background: '#f4f6f8', overflow: 'auto', padding: 14 }}>
      <Panel>
        <SectionLabel>협력사 정보</SectionLabel>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Avatar name={auth.user?.name} size={44} tone="brand" />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 700 }}>{auth.user?.name || '협력사'}</div>
            <div className="mono" style={{ fontSize: 12.5, color: 'var(--text-tertiary)', marginTop: 2 }}>
              {formatPhone(auth.user?.phone)}
            </div>
          </div>
        </div>
      </Panel>

      <Panel>
        <SectionLabel>비밀번호 변경</SectionLabel>
        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 10 }}>
          <label style={{ display: 'grid', gap: 5 }}>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>현재 비밀번호</span>
            <input
              className="input"
              data-testid="partner-current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              disabled={isSaving}
              onChange={(event) => setCurrentPassword(event.target.value)}
              style={inputStyle}
            />
          </label>
          <label style={{ display: 'grid', gap: 5 }}>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>새 비밀번호</span>
            <input
              className="input"
              data-testid="partner-new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              disabled={isSaving}
              onChange={(event) => setNewPassword(event.target.value)}
              style={inputStyle}
            />
          </label>

          {error && <div style={{ fontSize: 12, color: 'var(--danger-fg)' }}>{error}</div>}
          {notice && <div style={{ fontSize: 12, color: 'var(--success-fg)', fontWeight: 700 }}>{notice}</div>}

          <button
            type="submit"
            data-testid="partner-change-password"
            disabled={isSaving}
            style={primaryButtonStyle(isSaving)}
          >
            {isSaving ? '변경 중' : '비밀번호 변경'}
          </button>
        </form>
      </Panel>

      <button
        type="button"
        data-testid="partner-logout"
        onClick={() => void auth.logout('partner')}
        style={logoutButtonStyle}
      >
        <Icon name="logOut" size={16} /> 로그아웃
      </button>
    </div>
  );
}

function toChangePasswordMessage(error) {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.detail === 'invalid_current_password') {
      return '현재 비밀번호가 올바르지 않습니다.';
    }
    if (error.detail === 'weak_password') {
      return '새 비밀번호는 10자 이상으로 입력해주세요.';
    }
    if (error.detail === 'password_reuse') {
      return '현재 비밀번호와 다른 새 비밀번호를 입력해주세요.';
    }
    if (error.issues?.[0]?.message) {
      return error.issues[0].message;
    }
    if (error.message) {
      return error.message;
    }
  }
  return '비밀번호를 변경하지 못했습니다.';
}

function Panel({ children }) {
  return <div style={{ background: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, border: '1px solid var(--border)' }}>{children}</div>;
}

function SectionLabel({ children }) {
  return <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 600, letterSpacing: '0.04em', marginBottom: 10 }}>{children}</div>;
}

const inputStyle = { width: '100%', height: 44 };

function primaryButtonStyle(disabled) {
  return {
    width: '100%',
    height: 46,
    marginTop: 2,
    background: 'var(--brand)',
    color: '#fff',
    border: 'none',
    borderRadius: 10,
    fontSize: 14.5,
    fontWeight: 700,
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.7 : 1,
  };
}

const logoutButtonStyle = {
  width: '100%',
  height: 50,
  marginTop: 4,
  background: '#fff',
  color: 'var(--danger-fg)',
  border: '1px solid var(--danger-border)',
  borderRadius: 10,
  fontSize: 14.5,
  fontWeight: 700,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  cursor: 'pointer',
};
