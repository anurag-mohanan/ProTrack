import { AppBar, Box, Button, Toolbar, Typography } from '@mui/material';
import HomeRoundedIcon from '@mui/icons-material/HomeRounded';
import { Outlet, useNavigate } from 'react-router-dom';
import { PageErrorBoundary } from '../components/common/PageErrorBoundary';
import { LogoHomeLink } from '../components/branding/LogoHomeLink';
import { useAuth } from '../context/AuthContext';
import { getDefaultLandingPath } from '../utils/permissions';

/** Minimal chrome for TV / wall monitor sessions — logo, home, live title. */
export function PlanningBoardLayout() {
  const { displayName, logout, user } = useAuth();
  const navigate = useNavigate();
  const homePath = getDefaultLandingPath(user?.role_name);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="sticky" color="transparent" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Toolbar sx={{ gap: 1.5, minHeight: 64, py: 0.5 }}>
          <LogoHomeLink to={homePath} size="sm" />
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1.2 }}>
              Planning Board — Live
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Program manager operations monitor
            </Typography>
          </Box>
          <Button
            size="small"
            variant="outlined"
            startIcon={<HomeRoundedIcon />}
            onClick={() => navigate(homePath)}
            sx={{ display: { xs: 'none', sm: 'inline-flex' } }}
          >
            Home
          </Button>
          <Button
            size="small"
            variant="outlined"
            aria-label="Go to home"
            onClick={() => navigate(homePath)}
            sx={{ display: { xs: 'inline-flex', sm: 'none' }, minWidth: 40, px: 1 }}
          >
            <HomeRoundedIcon fontSize="small" />
          </Button>
          <Typography variant="body2" color="text.secondary" sx={{ display: { xs: 'none', md: 'block' } }}>
            {displayName}
          </Typography>
          <Button size="small" onClick={() => void handleLogout()}>
            Sign out
          </Button>
        </Toolbar>
      </AppBar>
      <Box sx={{ flexGrow: 1, p: { xs: 1.5, md: 2 } }}>
        <PageErrorBoundary title="Planning board could not be loaded.">
          <Outlet />
        </PageErrorBoundary>
      </Box>
    </Box>
  );
}
