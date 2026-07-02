import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { accessContextFromUser, canAccessAdministration } from '../utils/permissions';

export function AdminRoute() {
  const { user } = useAuth();
  if (!canAccessAdministration(accessContextFromUser(user))) {
    return <Navigate to="/dashboard" replace />;
  }
  return <Outlet />;
}
