import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { accessContextFromUser } from '../utils/permissions';
import { canAccessAdminPortalPath } from '../utils/portalAccess';

interface AdminPortalRouteProps {
  children: ReactNode;
}

export function AdminPortalRoute({ children }: AdminPortalRouteProps) {
  const { user } = useAuth();
  const location = useLocation();
  const access = accessContextFromUser(user);

  if (!canAccessAdminPortalPath(access, location.pathname)) {
    return <Navigate to="/admin/dashboard" replace />;
  }

  return <>{children}</>;
}
