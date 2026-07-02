import { Box, Toolbar } from '@mui/material';
import { Outlet, useNavigate } from 'react-router-dom';
import { AppSidebar, DRAWER_WIDTH } from '../components/layout/AppSidebar';
import { AppTopBar } from '../components/layout/AppTopBar';
import { ImpersonationBanner } from '../components/layout/ImpersonationBanner';
import { useAuth } from '../context/AuthContext';

export function MainLayout() {
  const { user, displayName, logout } = useAuth();
  const navigate = useNavigate();
  const roleName = user?.role_name ?? '';

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minWidth: 0 }}>
        <ImpersonationBanner />
        <AppTopBar
          displayName={displayName}
          roleName={roleName}
          onLogout={() => void handleLogout()}
        />
        <Box sx={{ display: 'flex', flexGrow: 1, minWidth: 0 }}>
          <AppSidebar roleName={roleName} />
          <Box
            component="main"
            sx={{
              flexGrow: 1,
              width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
              p: { xs: 2, md: 3 },
            }}
          >
            <Toolbar sx={{ minHeight: '72px !important' }} />
            <Outlet />
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
