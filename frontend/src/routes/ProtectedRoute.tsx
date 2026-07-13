import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { LoadingState } from '../components/common/LoadingState';
import { requiresForcedPasswordChange } from '../config/env';
import { useAuth } from '../context/AuthContext';
import { getDefaultLandingPath } from '../utils/permissions';

function requiresPasswordChange(mustChangePassword: boolean | undefined): boolean {
  return requiresForcedPasswordChange(mustChangePassword);
}

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingState message="Checking session…" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

export function RequirePasswordChangedRoute() {
  const { user } = useAuth();
  const location = useLocation();

  if (requiresPasswordChange(user?.must_change_password) && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />;
  }

  return <Outlet />;
}

export function ChangePasswordGate() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingState message="Checking session…" />;
  }

  if (!requiresPasswordChange(user?.must_change_password)) {
    return <Navigate to={getDefaultLandingPath(user?.role_name)} replace />;
  }

  return <Outlet />;
}

export function PublicRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <LoadingState message="Checking session…" />;
  }

  if (isAuthenticated) {
    if (requiresPasswordChange(user?.must_change_password)) {
      return <Navigate to="/change-password" replace />;
    }
    return <Navigate to={getDefaultLandingPath(user?.role_name)} replace />;
  }

  return <Outlet />;
}
