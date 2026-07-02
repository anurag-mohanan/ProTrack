import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { accessContextFromUser, type AccessContext } from '../utils/permissions';

interface RoleRouteProps {
  allowed: (ctx: AccessContext) => boolean;
  redirectTo?: string;
}

export function RoleRoute({ allowed, redirectTo = '/dashboard' }: RoleRouteProps) {
  const { user } = useAuth();
  if (!allowed(accessContextFromUser(user))) {
    return <Navigate to={redirectTo} replace />;
  }
  return <Outlet />;
}
