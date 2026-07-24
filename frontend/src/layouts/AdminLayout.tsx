import { Box, Toolbar } from '@mui/material';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { AdminSidebar } from '../components/layout/AdminSidebar';
import { AdminTopBar } from '../components/layout/AdminTopBar';
import { AppFooter } from '../components/layout/AppFooter';
import { ImpersonationBanner } from '../components/layout/ImpersonationBanner';
import { PageErrorBoundary } from '../components/common/PageErrorBoundary';
import { ModuleHomeButton } from '../components/navigation/ModuleHomeButton';
import { useAuth } from '../context/AuthContext';
import { shellMinHeightSx, useResponsiveShell } from '../hooks/useResponsiveShell';
import { resolveModuleHome } from '../navigation/moduleHomes';

export function AdminLayout() {
  const { user, displayName, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const roleName = user?.role_name ?? '';
  const { isCompact, mobileNavOpen, openMobileNav, closeMobileNav } = useResponsiveShell();
  const moduleHome = resolveModuleHome(location.pathname);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <Box sx={{ display: 'flex', ...shellMinHeightSx(), bgcolor: 'background.default' }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minWidth: 0, maxWidth: '100%' }}>
        <ImpersonationBanner />
        <AdminTopBar
          displayName={displayName}
          roleName={roleName}
          onLogout={() => void handleLogout()}
          isCompact={isCompact}
          onOpenNav={openMobileNav}
        />
        <Box sx={{ display: 'flex', flexGrow: 1, minWidth: 0, maxWidth: '100%' }}>
          <AdminSidebar mobileOpen={mobileNavOpen} onMobileClose={closeMobileNav} />
          <Box
            component="main"
            sx={{
              flexGrow: 1,
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              minWidth: 0,
              maxWidth: '100%',
            }}
          >
            <Toolbar sx={{ minHeight: '64px !important' }} />
            <Box
              sx={{
                flexGrow: 1,
                p: { xs: 1.25, sm: 1.5, md: 2 },
                minWidth: 0,
                maxWidth: '100%',
                overflowX: 'clip',
              }}
            >
              {moduleHome ? <ModuleHomeButton home={moduleHome} /> : null}
              <PageErrorBoundary title="This admin section could not be loaded.">
                <Outlet />
              </PageErrorBoundary>
            </Box>
            <AppFooter />
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
