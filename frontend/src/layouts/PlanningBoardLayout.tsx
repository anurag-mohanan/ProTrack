import { AppBar, Box, Button, Toolbar, Typography } from '@mui/material';
import { Outlet, useNavigate } from 'react-router-dom';
import { PageErrorBoundary } from '../components/common/PageErrorBoundary';
import { useAuth } from '../context/AuthContext';

/** Minimal chrome for TV / wall monitor sessions. */
export function PlanningBoardLayout() {
  const { displayName, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="sticky" color="transparent" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Toolbar sx={{ gap: 2, minHeight: 56 }}>
          <Typography variant="h6" sx={{ fontWeight: 800, flexGrow: 1 }}>
            Planning Board — Live
          </Typography>
          <Typography variant="body2" color="text.secondary">
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
