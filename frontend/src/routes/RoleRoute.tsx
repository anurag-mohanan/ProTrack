import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface RoleRouteProps {
  allowed: (roleName: string) => boolean;
  redirectTo?: string;
}

export function RoleRoute({ allowed, redirectTo = '/dashboard' }: RoleRouteProps) {
  const { user } = useAuth();
  if (!allowed(user?.role_name ?? '')) {
    return <Navigate to={redirectTo} replace />;
  }
  return <Outlet />;
}
