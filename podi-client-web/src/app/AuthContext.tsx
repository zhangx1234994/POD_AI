import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { authApi, type LoginPayload, type TokenResponse } from '../services/authApi';
import { setClientAnalyticsAuthContext } from '../services/clientAnalytics';

const STORAGE_KEY = 'podi-client-auth';

type SessionUser = {
  id: string;
  role: string;
  expiresAt: number;
};

type AuthState = {
  accessToken: string;
  refreshToken?: string | null;
  user: SessionUser;
};

type AuthContextValue = {
  auth: AuthState | null;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const [, payload] = token.split('.');
    if (!payload) return null;
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = window.atob(normalized);
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

function buildAuthState(tokens: TokenResponse): AuthState | null {
  const payload = decodeJwtPayload(tokens.accessToken);
  const sub = typeof payload?.sub === 'string' ? payload.sub : null;
  if (!sub) return null;
  const expSeconds = typeof payload?.exp === 'number' ? payload.exp : Math.floor(Date.now() / 1000 + tokens.expiresIn);
  return {
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken,
    user: {
      id: sub,
      role: tokens.role,
      expiresAt: expSeconds * 1000,
    },
  };
}

function loadStoredAuth(): AuthState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthState;
    if (!parsed?.accessToken || !parsed?.user?.id) return null;
    if (!parsed.user?.expiresAt || parsed.user.expiresAt <= Date.now()) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState | null>(() => loadStoredAuth());

  useEffect(() => {
    if (!auth) {
      localStorage.removeItem(STORAGE_KEY);
      setClientAnalyticsAuthContext(null);
      return;
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
    setClientAnalyticsAuthContext({ id: auth.user.id, role: auth.user.role });
  }, [auth]);

  useEffect(() => {
    if (!auth?.user.expiresAt) return;
    const remaining = auth.user.expiresAt - Date.now();
    if (remaining <= 0) {
      setAuth(null);
      return;
    }
    const timer = window.setTimeout(() => setAuth(null), remaining);
    return () => window.clearTimeout(timer);
  }, [auth?.user.expiresAt]);

  const login = useCallback(async (payload: LoginPayload) => {
    const tokens = await authApi.login(payload);
    const nextAuth = buildAuthState(tokens);
    if (!nextAuth) {
      throw new Error('LOGIN_PAYLOAD_INVALID');
    }
    setAuth(nextAuth);
  }, []);

  const logout = useCallback(() => {
    setAuth(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      auth,
      isAuthenticated: Boolean(auth?.accessToken),
      login,
      logout,
    }),
    [auth, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
