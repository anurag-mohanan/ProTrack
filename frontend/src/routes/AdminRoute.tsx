import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { canAccessAdministration } from '../utils/permissions';

export function AdminRoute() {
  const { user } = useAuth();
  if (!canAccessAdministration(user?.role_name ?? '')) {
    return <Navigate to="/dashboard" replace />;
  }
  return <Outlet />;
}
