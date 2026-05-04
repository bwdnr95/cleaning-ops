import React from 'react';

import {
  adminChangePassword,
  adminLogin,
  logout as requestLogout,
  partnerChangePassword,
  partnerLogin,
} from '../api/auth';
import { setApiAuthHandlers } from '../api/client';

const STORAGE_KEY = 'cleaning_ops_auth_session';
const AuthContext = React.createContext(null);

const initialState = readStoredState();

export function AuthProvider({ children }) {
  const [state, setState] = React.useState(initialState);

  const replaceSession = React.useCallback((session) => {
    const nextState = toState(session);
    setState(nextState);
    writeStoredState(nextState);
  }, []);

  const clearAuth = React.useCallback(() => {
    setState({ user: null, accessToken: null, refreshToken: null });
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  React.useEffect(() => {
    setApiAuthHandlers({
      getAccessToken: () => state.accessToken,
      getRefreshToken: () => state.refreshToken,
      onRefresh: (session) => replaceSession(session),
      onUnauthorized: clearAuth,
    });
  }, [clearAuth, replaceSession, state.accessToken, state.refreshToken]);

  const login = React.useCallback(
    async (role, identifier, password) => {
      const request = role === 'admin' ? adminLogin : partnerLogin;
      const session = await request({ identifier, password });
      replaceSession(session);
    },
    [replaceSession],
  );

  const logout = React.useCallback(async () => {
    const token = state.refreshToken;
    clearAuth();

    if (token) {
      try {
        await requestLogout(token);
      } catch {
        // The local session is already cleared; server-side revoke can be retried by logging in again.
      }
    }
  }, [clearAuth, state.refreshToken]);

  const changePassword = React.useCallback(
    async (currentPassword, newPassword) => {
      if (!state.user) {
        throw new Error('not_authenticated');
      }

      const request = state.user.role === 'admin' ? adminChangePassword : partnerChangePassword;
      const session = await request({ currentPassword, newPassword });
      replaceSession(session);
    },
    [replaceSession, state.user],
  );

  const value = React.useMemo(
    () => ({
      ...state,
      isAuthenticated: Boolean(state.user && state.accessToken && state.refreshToken),
      login,
      logout,
      changePassword,
      clearAuth,
      replaceSession,
    }),
    [changePassword, clearAuth, login, logout, replaceSession, state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = React.useContext(AuthContext);
  if (!value) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return value;
}

function toState(session) {
  return {
    user: session.user,
    accessToken: session.access_token,
    refreshToken: session.refresh_token,
  };
}

function readStoredState() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return { user: null, accessToken: null, refreshToken: null };
    }

    const parsed = JSON.parse(stored);
    if (!parsed.user || !parsed.accessToken || !parsed.refreshToken) {
      return { user: null, accessToken: null, refreshToken: null };
    }

    return parsed;
  } catch {
    return { user: null, accessToken: null, refreshToken: null };
  }
}

function writeStoredState(state) {
  // R1 keeps tokens in localStorage so refresh survives reloads. Move to httpOnly cookies when the backend supports it.
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}
