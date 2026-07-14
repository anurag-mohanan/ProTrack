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

/** Fixed office TV chrome — locked viewport, no page scroll. */
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
        height: '100dvh',
        maxHeight: '100dvh',
        overflow: 'hidden',
        bgcolor: designTokens.semantic.sidebar,
        color: '#f8fafc',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <AppBar
        position="static"
        elevation={0}
        sx={{
          flexShrink: 0,
          bgcolor: 'rgba(15, 23, 42, 0.98)',
          borderBottom: '1px solid rgba(148, 163, 184, 0.22)',
        }}
      >
        <Toolbar
          sx={{
            gap: 1.5,
            minHeight: { xs: 52, md: 56 },
            height: { xs: 52, md: 56 },
            px: { xs: 1.5, md: 2 },
          }}
        >
          <Box
            sx={{
              bgcolor: '#fff',
              borderRadius: 1.5,
              px: 1,
              py: 0.4,
              display: 'inline-flex',
              alignItems: 'center',
            }}
          >
            <LogoHomeLink to={homePath} size="sm" />
          </Box>

          <Typography
            sx={{
              flexGrow: 1,
              minWidth: 0,
              fontWeight: 800,
              fontSize: { xs: '1.05rem', md: '1.25rem' },
              letterSpacing: '-0.02em',
              color: '#f8fafc',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            Planning Board — Live
          </Typography>

          <Chip
            icon={
              <Box
                sx={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  bgcolor: designTokens.semantic.success,
                  animation: `${livePulse} 1.6s ease-in-out infinite`,
                  ml: '8px !important',
                }}
              />
            }
            label="LIVE"
            size="small"
            sx={{
              height: 28,
              fontWeight: 800,
              fontSize: '0.75rem',
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
              fontSize: '0.9rem',
              whiteSpace: 'nowrap',
            }}
          >
            {now}
          </Typography>

          <Button
            variant="outlined"
            size="small"
            startIcon={<HomeRoundedIcon />}
            onClick={() => navigate(homePath)}
            sx={{
              display: { xs: 'none', sm: 'inline-flex' },
              color: '#e2e8f0',
              borderColor: 'rgba(148, 163, 184, 0.45)',
              fontWeight: 700,
              py: 0.25,
              '&:hover': {
                borderColor: '#93c5fd',
                bgcolor: 'rgba(37, 99, 235, 0.15)',
              },
            }}
          >
            Home
          </Button>

          <Typography
            sx={{
              display: { xs: 'none', md: 'block' },
              color: 'rgba(226, 232, 240, 0.75)',
              fontWeight: 600,
              fontSize: '0.85rem',
              maxWidth: 140,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {displayName}
          </Typography>
          <Button
            size="small"
            onClick={() => void handleLogout()}
            sx={{ color: 'rgba(226, 232, 240, 0.9)', fontWeight: 600, minWidth: 0 }}
          >
            Sign out
          </Button>
        </Toolbar>
      </AppBar>

      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          overflow: 'hidden',
          p: { xs: 1, md: 1.25 },
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <PageErrorBoundary title="Planning board could not be loaded.">
          <Outlet />
        </PageErrorBoundary>
      </Box>
    </Box>
  );
}
