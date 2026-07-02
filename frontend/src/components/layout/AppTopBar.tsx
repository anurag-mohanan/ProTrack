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
import { Link as RouterLink } from 'react-router-dom';
import { NotificationBell } from '../common/NotificationBell';
import { LogoHomeLink } from '../branding/LogoHomeLink';
import { AdminSearchBar } from '../admin/AdminSearchBar';
import { ProsohmButton } from '../ui/ProsohmButton';
import { AppBreadcrumbs, useBreadcrumbTitle } from './AppBreadcrumbs';
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
      <Toolbar sx={{ minHeight: '72px !important', px: { xs: 2, md: 3 }, gap: 2 }}>
        <Box sx={{ display: { xs: 'flex', sm: 'none' }, flexShrink: 0 }}>
          <LogoHomeLink size="sm" />
        </Box>

        <Box sx={{ flexGrow: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 0.25 }}>
          <Typography
            variant="h6"
            sx={{
              fontWeight: 800,
              fontSize: { xs: '1rem', md: '1.125rem' },
              lineHeight: 1.2,
              display: { xs: 'none', md: 'block' },
            }}
          >
            {pageTitle}
          </Typography>
          <AppBreadcrumbs />
        </Box>

        <Box sx={{ display: { xs: 'none', lg: 'flex' }, flex: 1, justifyContent: 'center', maxWidth: 560 }}>
          <AdminSearchBar />
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexShrink: 0 }}>
          <NotificationBell />
          <Box
            sx={{
              display: { xs: 'none', md: 'flex' },
              flexDirection: 'column',
              alignItems: 'flex-end',
              mr: 0.5,
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 700 }}>
              {displayName}
            </Typography>
            <Typography variant="captionLabel" color="text.secondary">
              {formatCellValue(roleName)}
            </Typography>
          </Box>
          <IconButton onClick={(event) => setAnchorEl(event.currentTarget)} size="small">
            <Avatar
              sx={{
                width: 40,
                height: 40,
                bgcolor: 'primary.main',
                fontWeight: 700,
                fontSize: '0.875rem',
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
                {roleName}
              </Typography>
            </Box>
            <MenuItem component={RouterLink} to="/profile" onClick={() => setAnchorEl(null)}>
              <PersonIcon fontSize="small" sx={{ mr: 1.5 }} />
              My Profile
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
          <Box sx={{ display: { xs: 'none', lg: 'block' } }}>
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              startIcon={<LogoutIcon />}
              onClick={onLogout}
            >
              Logout
            </ProsohmButton>
          </Box>
        </Box>
      </Toolbar>
    </AppBar>
  );
}
