import React from 'react';

import {
  adminChangePassword,
  adminLogin,
  logout as requestLogout,
  partnerChangePassword,
  partnerLogin,
} from '../api/auth';
import { setApiAuthHandlers } from '../api/client';

const STORAGE_KEY = 'cleaning_ops_auth_sessions_v2';
const LEGACY_STORAGE_KEY = 'cleaning_ops_auth_session';
const ROLES = ['admin', 'partner'];
const EMPTY_SESSION = { user: null, accessToken: null, refreshToken: null };
const AuthContext = React.createContext(null);

const initialState = readStoredState();

export function AuthProvider({ children }) {
  const [state, setState] = React.useState(initialState);
  const stateRef = React.useRef(state);
  stateRef.current = state;

  const replaceSession = React.useCallback((session) => {
    const role = session?.user?.role;
    if (!ROLES.includes(role)) {
      return;
    }

    setState((current) => {
      const nextState = {
        activeRole: role,
        sessions: {
          ...current.sessions,
          [role]: toSessionState(session),
        },
      };
      writeStoredState(nextState);
      return nextState;
    });
  }, []);

  const clearAuth = React.useCallback((role = undefined) => {
    setState((current) => {
      const targetRole = ROLES.includes(role) ? role : current.activeRole;
      const nextState = {
        ...current,
        sessions: {
          ...current.sessions,
          [targetRole]: EMPTY_SESSION,
        },
      };
      writeStoredState(nextState);
      return nextState;
    });
  }, []);

  const setActiveRole = React.useCallback((role) => {
    if (!ROLES.includes(role)) {
      return;
    }

    setState((current) => {
      if (current.activeRole === role) {
        return current;
      }
      const nextState = { ...current, activeRole: role };
      writeStoredState(nextState);
      return nextState;
    });
  }, []);

  React.useEffect(() => {
    setApiAuthHandlers({
      getAccessToken: () => getActiveSession(stateRef.current).accessToken,
      getRefreshToken: () => getActiveSession(stateRef.current).refreshToken,
      onRefresh: (session) => replaceSession(session),
      onUnauthorized: () => clearAuth(stateRef.current.activeRole),
    });
  }, [clearAuth, replaceSession]);

  const login = React.useCallback(
    async (role, identifier, password) => {
      const request = role === 'admin' ? adminLogin : partnerLogin;
      const session = await request({ identifier, password });
      replaceSession(session);
    },
    [replaceSession],
  );

  const logout = React.useCallback(
    async (role = undefined) => {
      const targetRole = ROLES.includes(role) ? role : state.activeRole;
      const token = getSession(state, targetRole).refreshToken;
      clearAuth(targetRole);

      if (token) {
        try {
          await requestLogout(token);
        } catch {
          // The local session is already cleared; server-side revoke can be retried by logging in again.
        }
      }
    },
    [clearAuth, state],
  );

  const changePassword = React.useCallback(
    async (currentPassword, newPassword) => {
      const activeSession = getActiveSession(state);
      if (!activeSession.user) {
        throw new Error('not_authenticated');
      }

      const request = activeSession.user.role === 'admin' ? adminChangePassword : partnerChangePassword;
      const session = await request({ currentPassword, newPassword });
      replaceSession(session);
    },
    [replaceSession, state],
  );

  const activeSession = getActiveSession(state);

  const value = React.useMemo(
    () => ({
      ...activeSession,
      activeRole: state.activeRole,
      sessions: state.sessions,
      isAuthenticated: Boolean(activeSession.user && activeSession.accessToken && activeSession.refreshToken),
      isRoleAuthenticated: (role) => {
        const session = getSession(state, role);
        return Boolean(session.user && session.accessToken && session.refreshToken);
      },
      getSession: (role) => getSession(state, role),
      login,
      logout,
      changePassword,
      clearAuth,
      replaceSession,
      setActiveRole,
    }),
    [activeSession, changePassword, clearAuth, login, logout, replaceSession, setActiveRole, state],
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

function toSessionState(session) {
  return {
    user: session.user,
    accessToken: session.access_token,
    refreshToken: session.refresh_token,
  };
}

function getActiveSession(state) {
  return getSession(state, state.activeRole);
}

function getSession(state, role) {
  return state.sessions?.[role] || EMPTY_SESSION;
}

function readStoredState() {
  const emptyState = {
    activeRole: 'admin',
    sessions: {
      admin: EMPTY_SESSION,
      partner: EMPTY_SESSION,
    },
  };

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      const activeRole = ROLES.includes(parsed.activeRole) ? parsed.activeRole : 'admin';
      return {
        activeRole,
        sessions: {
          admin: normalizeStoredSession(parsed.sessions?.admin),
          partner: normalizeStoredSession(parsed.sessions?.partner),
        },
      };
    }

    const legacyStored = localStorage.getItem(LEGACY_STORAGE_KEY);
    if (!legacyStored) {
      return emptyState;
    }

    const legacy = normalizeStoredSession(JSON.parse(legacyStored));
    const role = legacy.user?.role;
    if (!ROLES.includes(role)) {
      return emptyState;
    }

    return {
      activeRole: role,
      sessions: {
        ...emptyState.sessions,
        [role]: legacy,
      },
    };
  } catch {
    return emptyState;
  }
}

function normalizeStoredSession(session) {
  if (!session?.user || !session.accessToken || !session.refreshToken) {
    return EMPTY_SESSION;
  }

  return {
    user: session.user,
    accessToken: session.accessToken,
    refreshToken: session.refreshToken,
  };
}

function writeStoredState(state) {
  // R1 keeps tokens in localStorage so refresh survives reloads. Move to httpOnly cookies when the backend supports it.
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}
