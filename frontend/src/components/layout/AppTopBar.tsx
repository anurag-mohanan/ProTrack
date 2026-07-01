import { useMemo, useState } from 'react';
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
import { useLocation } from 'react-router-dom';
import { NotificationBell } from '../common/NotificationBell';
import { ProsohmLogo } from '../branding/ProsohmLogo';
import { ProsohmButton } from '../ui/ProsohmButton';
import { DRAWER_WIDTH } from './AppSidebar';

const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/projects': 'Projects',
  '/projects/archived': 'Archived Projects',
  '/admin/deleted-projects': 'Deleted Projects',
  '/timesheets': 'Timesheets',
  '/workload': 'Workload',
  '/reports': 'Reports',
  '/admin/users': 'Users',
  '/admin/customers': 'Customers',
  '/admin/contacts': 'Contacts',
  '/admin/streams': 'Streams',
  '/admin/task-types': 'Task Types',
  '/admin/project-types': 'Project Types',
  '/admin/project-templates': 'Project Templates',
  '/admin/roles': 'Roles',
  '/admin/settings': 'System Settings',
  '/admin/import-historical-projects': 'Historical Import',
};

function resolvePageTitle(pathname: string): string {
  if (pageTitles[pathname]) return pageTitles[pathname];
  if (pathname.startsWith('/projects/')) return 'Project Details';
  if (pathname.startsWith('/admin/project-templates/')) return 'Template Editor';
  if (pathname.startsWith('/timesheets/')) return 'Timesheet Entry';
  return 'ProTrack';
}

interface AppTopBarProps {
  displayName: string;
  roleName: string;
  onLogout: () => void;
}

export function AppTopBar({ displayName, roleName, onLogout }: AppTopBarProps) {
  const location = useLocation();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const pageTitle = useMemo(
    () => resolvePageTitle(location.pathname),
    [location.pathname],
  );

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
      <Toolbar sx={{ minHeight: '72px !important', px: { xs: 2, md: 3 } }}>
        <Box sx={{ display: { xs: 'flex', sm: 'none' }, mr: 1 }}>
          <ProsohmLogo size="sm" />
        </Box>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography variant="pageTitle" noWrap>
            {pageTitle}
          </Typography>
          <Typography variant="captionLabel" color="text.secondary" noWrap>
            ProTrack · Prosohm Engineering Management
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
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
              {roleName || '—'}
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
            <MenuItem onClick={() => setAnchorEl(null)}>
              <PersonIcon fontSize="small" sx={{ mr: 1.5 }} />
              Profile
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
