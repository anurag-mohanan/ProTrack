import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { moduleForPath, type ModuleKey } from '../config/accessControl';
import { useAuth } from '../context/AuthContext';
import { accessContextFromUser, userHasModule } from '../utils/permissions';

interface ModuleRouteProps {
  module?: ModuleKey;
  redirectTo?: string;
}

export function ModuleRoute({ module, redirectTo = '/dashboard' }: ModuleRouteProps) {
  const { user } = useAuth();
  const location = useLocation();
  const ctx = accessContextFromUser(user);
  const requiredModule = module ?? moduleForPath(location.pathname);

  if (requiredModule && !userHasModule(ctx, requiredModule)) {
    return <Navigate to={redirectTo} replace />;
  }

  return <Outlet />;
}
