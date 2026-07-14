import { AppBar, Box, Button, Chip, Toolbar, Typography } from '@mui/material';
import HomeRoundedIcon from '@mui/icons-material/HomeRounded';
import { keyframes } from '@mui/system';
import { Outlet, useNavigate } from 'react-router-dom';
import { PageErrorBoundary } from '../components/common/PageErrorBoundary';
import { LogoHomeLink } from '../components/branding/LogoHomeLink';
import { useAuth } from '../context/AuthContext';
import { designTokens } from '../theme/designTokens';
import { getDefaultLandingPath } from '../utils/permissions';

const livePulse = keyframes`
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.45; transform: scale(0.85); }
  100% { opacity: 1; transform: scale(1); }
`;

/** Wall / TV chrome — high contrast, brand navy, distance-readable. */
export function PlanningBoardLayout() {
  const { displayName, logout, user } = useAuth();
  const navigate = useNavigate();
  const homePath = getDefaultLandingPath(user?.role_name);
  const now = new Date().toLocaleString([], {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        bgcolor: designTokens.semantic.sidebar,
        color: '#f8fafc',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: 'rgba(15, 23, 42, 0.96)',
          borderBottom: '1px solid rgba(148, 163, 184, 0.22)',
          backdropFilter: 'blur(10px)',
        }}
      >
        <Toolbar
          sx={{
            gap: 2,
            minHeight: { xs: 72, md: 88 },
            px: { xs: 2, md: 3 },
            py: 1,
          }}
        >
          <Box
            sx={{
              bgcolor: '#fff',
              borderRadius: 2,
              px: 1.25,
              py: 0.75,
              display: 'inline-flex',
              alignItems: 'center',
            }}
          >
            <LogoHomeLink to={homePath} size="md" />
          </Box>

          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <StackTitle />
          </Box>

          <Chip
            icon={
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  bgcolor: designTokens.semantic.success,
                  animation: `${livePulse} 1.6s ease-in-out infinite`,
                  ml: '8px !important',
                }}
              />
            }
            label="LIVE"
            sx={{
              height: 36,
              fontWeight: 800,
              fontSize: '0.85rem',
              letterSpacing: 1,
              bgcolor: 'rgba(22, 163, 74, 0.18)',
              color: '#86efac',
              border: '1px solid rgba(134, 239, 172, 0.35)',
              '& .MuiChip-icon': { color: 'inherit' },
            }}
          />

          <Typography
            variant="body2"
            sx={{
              display: { xs: 'none', lg: 'block' },
              color: 'rgba(226, 232, 240, 0.8)',
              fontWeight: 600,
              fontSize: '1rem',
              whiteSpace: 'nowrap',
            }}
          >
            {now}
          </Typography>

          <Button
            variant="outlined"
            startIcon={<HomeRoundedIcon />}
            onClick={() => navigate(homePath)}
            sx={{
              display: { xs: 'none', sm: 'inline-flex' },
              color: '#e2e8f0',
              borderColor: 'rgba(148, 163, 184, 0.45)',
              fontWeight: 700,
              px: 2,
              '&:hover': {
                borderColor: '#93c5fd',
                bgcolor: 'rgba(37, 99, 235, 0.15)',
              },
            }}
          >
            Home
          </Button>
          <Button
            aria-label="Go to home"
            onClick={() => navigate(homePath)}
            sx={{
              display: { xs: 'inline-flex', sm: 'none' },
              minWidth: 44,
              color: '#e2e8f0',
              border: '1px solid rgba(148, 163, 184, 0.45)',
            }}
          >
            <HomeRoundedIcon />
          </Button>

          <Typography
            sx={{
              display: { xs: 'none', md: 'block' },
              color: 'rgba(226, 232, 240, 0.75)',
              fontWeight: 600,
            }}
          >
            {displayName}
          </Typography>
          <Button
            onClick={() => void handleLogout()}
            sx={{ color: 'rgba(226, 232, 240, 0.9)', fontWeight: 600 }}
          >
            Sign out
          </Button>
        </Toolbar>
      </AppBar>

      <Box sx={{ flexGrow: 1, p: { xs: 2, md: 2.5, xl: 3 } }}>
        <PageErrorBoundary title="Planning board could not be loaded.">
          <Outlet />
        </PageErrorBoundary>
      </Box>
    </Box>
  );
}

function StackTitle() {
  return (
    <Box>
      <Typography
        sx={{
          fontWeight: 800,
          fontSize: { xs: '1.35rem', md: '1.75rem' },
          lineHeight: 1.15,
          letterSpacing: '-0.02em',
          color: '#f8fafc',
        }}
      >
        Planning Board — Live
      </Typography>
      <Typography
        sx={{
          color: 'rgba(148, 163, 184, 0.95)',
          fontWeight: 600,
          fontSize: { xs: '0.8rem', md: '0.95rem' },
        }}
      >
        Program · Operations · Engineering · wall monitor
      </Typography>
    </Box>
  );
}
