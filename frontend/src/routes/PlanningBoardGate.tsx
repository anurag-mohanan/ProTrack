import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getDefaultLandingPath, isPlanningBoardRole } from '../utils/permissions';

/** Keep Planning Board sessions on the monitor surface. */
export function PlanningBoardGate() {
  const { user } = useAuth();
  const location = useLocation();
  const roleName = user?.role_name ?? '';

  if (
    isPlanningBoardRole(roleName) &&
    location.pathname !== '/planning-board' &&
    location.pathname !== '/change-password' &&
    location.pathname !== '/login'
  ) {
    return <Navigate to="/planning-board" replace />;
  }

  return <Outlet />;
}

export function DefaultHomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={getDefaultLandingPath(user?.role_name)} replace />;
}
