import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { moduleForPath, type ModuleKey } from '../config/accessControl';
import { useAuth } from '../context/AuthContext';
import { accessContextFromUser, getDefaultLandingPath, userHasModule } from '../utils/permissions';

interface ModuleRouteProps {
  module?: ModuleKey;
  redirectTo?: string;
}

export function ModuleRoute({ module, redirectTo }: ModuleRouteProps) {
  const { user } = useAuth();
  const location = useLocation();
  const ctx = accessContextFromUser(user);
  const requiredModule = module ?? moduleForPath(location.pathname);
  const fallback = redirectTo ?? getDefaultLandingPath(user?.role_name);

  if (requiredModule && !userHasModule(ctx, requiredModule)) {
    return <Navigate to={fallback} replace />;
  }

  return <Outlet />;
}
