import React from 'react';

import { ApiError } from '../../api/client';
import { Icon } from '../../components/common/ui';
import { useAuth } from '../../store/authStore';

const LOGIN_META = {
  admin: {
    title: '관리자 로그인',
    eyebrow: '운영 관리자',
    description: '주문 접수, 배정, 사진 검수까지 운영 흐름을 관리합니다.',
    identifierLabel: '이메일 또는 전화번호',
    identifierPlaceholder: 'admin@cleanops.kr',
    submitLabel: '관리자 로그인',
  },
  partner: {
    title: '협력사 로그인',
    eyebrow: '협력사 현장',
    description: '배정된 현장 일정과 작업 사진 업로드를 확인합니다.',
    identifierLabel: '전화번호 또는 이메일',
    identifierPlaceholder: '01012345678',
    submitLabel: '협력사 로그인',
  },
};

export function AdminLoginPage() {
  return <LoginPage role="admin" />;
}

export function PartnerLoginPage() {
  return <LoginPage role="partner" />;
}

function LoginPage({ role }) {
  const auth = useAuth();
  const meta = LOGIN_META[role];
  const [identifier, setIdentifier] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [error, setError] = React.useState(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await auth.login(role, identifier.trim(), password);
    } catch (requestError) {
      setError(toLoginMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={`auth-page auth-page--${role}`}>
      <form className="auth-panel" data-testid={`${role}-login-form`} onSubmit={handleSubmit}>
        <div className="auth-mark">
          <Icon name={role === 'admin' ? 'shield' : 'truck'} size={18} />
        </div>
        <div className="app-eyebrow">{meta.eyebrow}</div>
        <h2>{meta.title}</h2>
        <p>{meta.description}</p>

        <label className="auth-field">
          <span>{meta.identifierLabel}</span>
          <input
            className="input"
            data-testid={`${role}-login-identifier`}
            value={identifier}
            placeholder={meta.identifierPlaceholder}
            autoComplete="username"
            onChange={(event) => setIdentifier(event.target.value)}
            required
          />
        </label>

        <label className="auth-field">
          <span>비밀번호</span>
          <input
            className="input"
            data-testid={`${role}-login-password`}
            type="password"
            value={password}
            autoComplete="current-password"
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>

        {error && <div className="auth-error">{error}</div>}

        <button className="btn btn--primary btn--block btn--lg" data-testid={`${role}-login-submit`} type="submit" disabled={isSubmitting}>
          {isSubmitting ? '확인 중' : meta.submitLabel}
        </button>
      </form>
    </div>
  );
}

function toLoginMessage(error) {
  if (error instanceof ApiError) {
    if (error.message === 'login_locked') {
      return '로그인 시도가 잠시 제한되었습니다. 잠시 후 다시 시도해주세요.';
    }
    if (error.status === 401) {
      return '계정 정보가 올바르지 않습니다.';
    }
    return error.message;
  }

  return '로그인 요청을 처리하지 못했습니다.';
}
