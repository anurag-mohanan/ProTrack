import { useEffect } from 'react';
import { Box, Toolbar } from '@mui/material';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { AppSidebar } from '../components/layout/AppSidebar';
import { AppFooter } from '../components/layout/AppFooter';
import { AppTopBar } from '../components/layout/AppTopBar';
import { ImpersonationBanner } from '../components/layout/ImpersonationBanner';
import { PageErrorBoundary } from '../components/common/PageErrorBoundary';
import { ModuleHomeButton } from '../components/navigation/ModuleHomeButton';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import {
  requestOpenGlobalSearch,
  shellMinHeightSx,
  useResponsiveShell,
} from '../hooks/useResponsiveShell';
import { resolveModuleHome } from '../navigation/moduleHomes';

export function MainLayout() {
  const { user, displayName, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { showInfo } = useToast();
  const roleName = user?.role_name ?? '';
  const { isCompact, mobileNavOpen, openMobileNav, closeMobileNav } = useResponsiveShell();
  const moduleHome = resolveModuleHome(location.pathname);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();

      if (key === 'f') {
        event.preventDefault();
        requestOpenGlobalSearch();
      }

      if (key === 'n') {
        event.preventDefault();
        navigate('/projects?create=1');
      }

      if (key === 's') {
        event.preventDefault();
        const submitButton = document.querySelector(
          '#project-form button[type="submit"], #task-type-form button[type="submit"]',
        ) as HTMLButtonElement | null;
        if (submitButton) {
          submitButton.click();
          showInfo('Saved using keyboard shortcut');
        }
      }
    };

    const onEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      const closeButton = document.querySelector(
        '[aria-label="Close"], button[aria-label="Close dialog"], .MuiDialog-root button[type="button"]',
      ) as HTMLButtonElement | null;
      closeButton?.click();
    };

    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keydown', onEscape);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keydown', onEscape);
    };
  }, [location.pathname, navigate, showInfo]);

  return (
    <Box sx={{ display: 'flex', ...shellMinHeightSx(), bgcolor: 'background.default' }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minWidth: 0, maxWidth: '100%' }}>
        <ImpersonationBanner />
        <AppTopBar
          displayName={displayName}
          roleName={roleName}
          onLogout={() => void handleLogout()}
          isCompact={isCompact}
          onOpenNav={openMobileNav}
        />
        <Box sx={{ display: 'flex', flexGrow: 1, minWidth: 0, maxWidth: '100%' }}>
          <AppSidebar
            user={user}
            mobileOpen={mobileNavOpen}
            onMobileClose={closeMobileNav}
          />
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
                p: { xs: 1.5, sm: 2, md: 3 },
                minWidth: 0,
                maxWidth: '100%',
                overflowX: 'clip',
              }}
            >
              {moduleHome ? <ModuleHomeButton home={moduleHome} /> : null}
              <PageErrorBoundary title="This section could not be loaded.">
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
