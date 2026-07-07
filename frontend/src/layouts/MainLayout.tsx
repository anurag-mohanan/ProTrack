import { useEffect } from 'react';
import { Box, Toolbar } from '@mui/material';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { AppSidebar, DRAWER_WIDTH } from '../components/layout/AppSidebar';
import { AppFooter } from '../components/layout/AppFooter';
import { AppTopBar } from '../components/layout/AppTopBar';
import { ImpersonationBanner } from '../components/layout/ImpersonationBanner';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export function MainLayout() {
  const { user, displayName, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { showInfo } = useToast();
  const roleName = user?.role_name ?? '';

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
        const searchInput = document.getElementById('global-search-input') as HTMLInputElement | null;
        searchInput?.focus();
        searchInput?.select();
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
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minWidth: 0 }}>
        <ImpersonationBanner />
        <AppTopBar
          displayName={displayName}
          roleName={roleName}
          onLogout={() => void handleLogout()}
        />
        <Box sx={{ display: 'flex', flexGrow: 1, minWidth: 0 }}>
          <AppSidebar user={user} />
          <Box
            component="main"
            sx={{
              flexGrow: 1,
              width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
              display: 'flex',
              flexDirection: 'column',
              minWidth: 0,
            }}
          >
            <Toolbar sx={{ minHeight: '64px !important' }} />
            <Box sx={{ flexGrow: 1, p: { xs: 2, md: 3 }, minWidth: 0 }}>
              <Outlet />
            </Box>
            <AppFooter />
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
