import { useState } from 'react';
import {
  AppBar,
  Avatar,
  Box,
  IconButton,
  Menu,
  MenuItem,
  Toolbar,
  Typography,
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import PersonIcon from '@mui/icons-material/Person';
import TuneIcon from '@mui/icons-material/Tune';
import { Link as RouterLink } from 'react-router-dom';
import { NotificationBell } from '../common/NotificationBell';
import { AppGlobalSearchBar } from './AppGlobalSearchBar';
import { useBreadcrumbTitle } from './AppBreadcrumbs';
import { DRAWER_WIDTH } from './AppSidebar';
import { formatCellValue } from '../../utils/format';

interface AppTopBarProps {
  displayName: string;
  roleName: string;
  onLogout: () => void;
}

export function AppTopBar({ displayName, roleName, onLogout }: AppTopBarProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const pageTitle = useBreadcrumbTitle();

  const initials = displayName
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <AppBar
      position="fixed"
      sx={{
        zIndex: (theme) => theme.zIndex.drawer + 1,
        width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
        ml: { sm: `${DRAWER_WIDTH}px` },
        bgcolor: 'prosohm.header',
        boxShadow: (theme) => theme.palette.prosohm.shadowHeader,
      }}
    >
      <Toolbar sx={{ minHeight: '64px !important', px: { xs: 1.5, md: 2 }, gap: 2 }}>
        <Typography
          variant="h6"
          sx={{
            fontWeight: 800,
            fontSize: { xs: '1rem', md: '1.125rem' },
            lineHeight: 1.2,
            flexShrink: 0,
            minWidth: 0,
          }}
        >
          {pageTitle}
        </Typography>

        <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', minWidth: 0 }}>
          <Box sx={{ display: { xs: 'none', md: 'flex' }, width: '100%', maxWidth: 480 }}>
            <AppGlobalSearchBar />
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
          <NotificationBell />
          <IconButton onClick={(event) => setAnchorEl(event.currentTarget)} size="small">
            <Avatar
              sx={{
                width: 36,
                height: 36,
                bgcolor: 'primary.main',
                fontWeight: 700,
                fontSize: '0.8125rem',
              }}
            >
              {initials || 'PT'}
            </Avatar>
          </IconButton>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            slotProps={{
              paper: {
                sx: { minWidth: 220, mt: 1, borderRadius: 2 },
              },
            }}
          >
            <Box sx={{ px: 2, py: 1.5 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {displayName}
              </Typography>
              <Typography variant="captionLabel" color="text.secondary">
                {formatCellValue(roleName)}
              </Typography>
            </Box>
            <MenuItem component={RouterLink} to="/profile" onClick={() => setAnchorEl(null)}>
              <PersonIcon fontSize="small" sx={{ mr: 1.5 }} />
              Profile
            </MenuItem>
            <MenuItem component={RouterLink} to="/profile?tab=preferences" onClick={() => setAnchorEl(null)}>
              <TuneIcon fontSize="small" sx={{ mr: 1.5 }} />
              Preferences
            </MenuItem>
            <MenuItem
              onClick={() => {
                setAnchorEl(null);
                onLogout();
              }}
            >
              <LogoutIcon fontSize="small" sx={{ mr: 1.5 }} />
              Logout
            </MenuItem>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
}
