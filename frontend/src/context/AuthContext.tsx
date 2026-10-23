import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
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
import { queryClient, resetQueryCache } from '../lib/queryClient';
import { userDisplayName } from '../utils/format';

const PERMISSION_SYNC_INTERVAL_MS = 60_000;

function accessSignature(user: CurrentUser): string {
  return JSON.stringify([
    user.role_id,
    user.role_name,
    user.is_active,
    user.must_change_password,
    [...(user.resolved_modules ?? [])].sort(),
    [...(user.resolved_special_permissions ?? [])].sort(),
    [...(user.team_ids ?? [])].sort(),
    user.module_actions ?? null,
    user.data_scope ?? null,
    user.requires_timesheet ?? null,
    user.can_enter_own_timesheet ?? null,
  ]);
}

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

  // Pick up role, module, permission and team changes made by an admin without a re-login.
  const userRef = useRef(user);
  useEffect(() => {
    userRef.current = user;
  }, [user]);
  const userId = user?.id ?? null;
  useEffect(() => {
    if (!userId) return undefined;
    let cancelled = false;
    const sync = async () => {
      if (!getAccessToken() || document.visibilityState !== 'visible') return;
      let latest: CurrentUser;
      try {
        latest = await fetchCurrentUser();
      } catch (error) {
        const status = (error as { status?: number; response?: { status?: number } })?.status
          ?? (error as { response?: { status?: number } })?.response?.status;
        if (!cancelled && status === 401) {
          clearAccessToken();
          clearAdminToken();
          resetQueryCache();
          setUser(null);
        }
        // Any other failure (e.g. offline) keeps the last known permissions until the next sync.
        return;
      }
      if (cancelled) return;
      const current = userRef.current;
      if (current && accessSignature(current) === accessSignature(latest)) return;
      setUser(latest);
      void queryClient.invalidateQueries();
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible') void sync();
    };
    window.addEventListener('focus', onVisible);
    document.addEventListener('visibilitychange', onVisible);
    const timer = window.setInterval(() => void sync(), PERMISSION_SYNC_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.removeEventListener('focus', onVisible);
      document.removeEventListener('visibilitychange', onVisible);
      window.clearInterval(timer);
    };
  }, [userId]);

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
