import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  fetchCurrentUser,
  impersonateUser as impersonateUserApi,
  login as loginApi,
  logoutSession,
  stopImpersonation as stopImpersonationApi,
} from '../api/auth';
import type { CurrentUser, LoginRequest } from '../types';
import {
  clearAccessToken,
  clearAdminToken,
  getAccessToken,
  getAdminToken,
  setAccessToken,
  setAdminToken,
} from '../services/authStorage';
import { resetQueryCache } from '../lib/queryClient';
import { userDisplayName } from '../utils/format';

interface AuthContextValue {
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isImpersonating: boolean;
  login: (credentials: LoginRequest) => Promise<CurrentUser>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<CurrentUser | null>;
  impersonateUser: (userId: string) => Promise<void>;
  stopImpersonation: () => Promise<void>;
  displayName: string;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadUser = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return null;
    }

    try {
      const currentUser = await fetchCurrentUser();
      setUser(currentUser);
      return currentUser;
    } catch {
      clearAccessToken();
      clearAdminToken();
      setUser(null);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  const login = useCallback(async (credentials: LoginRequest) => {
    const tokenResponse = await loginApi(credentials);
    resetQueryCache();
    clearAdminToken();
    setAccessToken(tokenResponse.access_token);
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
    return currentUser;
  }, []);

  const refreshUser = useCallback(async () => {
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
    return currentUser;
  }, []);

  const logout = useCallback(async () => {
    try {
      if (getAccessToken()) {
        await logoutSession();
      }
    } catch {
      // Clear local session even if the server call fails.
    } finally {
      clearAccessToken();
      clearAdminToken();
      resetQueryCache();
      setUser(null);
    }
  }, []);

  const impersonateUser = useCallback(async (userId: string) => {
    const currentToken = getAccessToken();
    if (!currentToken) {
      throw new Error('Not authenticated');
    }
    if (!getAdminToken()) {
      setAdminToken(currentToken);
    }
    const tokenResponse = await impersonateUserApi(userId);
    resetQueryCache();
    setAccessToken(tokenResponse.access_token);
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
  }, []);

  const stopImpersonation = useCallback(async () => {
    const tokenResponse = await stopImpersonationApi();
    resetQueryCache();
    setAccessToken(tokenResponse.access_token);
    clearAdminToken();
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isLoading,
      isImpersonating: Boolean(user?.impersonator_id),
      login,
      logout,
      refreshUser,
      impersonateUser,
      stopImpersonation,
      displayName: user ? userDisplayName(user) : '',
    }),
    [user, isLoading, login, logout, refreshUser, impersonateUser, stopImpersonation],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
