import {
  AppBar,
  Box,
  Button,
  Divider,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import DashboardIcon from '@mui/icons-material/Dashboard';
import FolderIcon from '@mui/icons-material/Folder';
import ScheduleIcon from '@mui/icons-material/Schedule';
import GroupsIcon from '@mui/icons-material/Groups';
import LogoutIcon from '@mui/icons-material/Logout';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { NotificationBell } from '../components/common/NotificationBell';
import { useAuth } from '../context/AuthContext';
import { canViewReports, canViewWorkload } from '../utils/permissions';

const drawerWidth = 240;

const navItems = [
  { label: 'Dashboard', path: '/dashboard', icon: <DashboardIcon /> },
  { label: 'Projects', path: '/projects', icon: <FolderIcon /> },
  { label: 'Timesheets', path: '/timesheets', icon: <ScheduleIcon /> },
  { label: 'Workload', path: '/workload', icon: <GroupsIcon /> },
  { label: 'Reports', path: '/reports', icon: <AssessmentIcon /> },
];

export function MainLayout() {
  const { user, displayName, logout } = useAuth();
  const navigate = useNavigate();
  const roleName = user?.role_name ?? '';

  const visibleNavItems = navItems.filter((item) => {
    if (item.path === '/reports') return canViewReports(roleName);
    if (item.path === '/workload') return canViewWorkload(roleName);
    return true;
  });

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'grey.50' }}>
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
          bgcolor: 'background.paper',
          color: 'text.primary',
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Toolbar sx={{ justifyContent: 'space-between' }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }} color="primary">
            ProTrack
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <NotificationBell />
            <Box sx={{ textAlign: 'right' }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {displayName}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {user?.role_name ?? '—'}
              </Typography>
            </Box>
            <Button
              variant="outlined"
              size="small"
              startIcon={<LogoutIcon />}
              onClick={handleLogout}
            >
              Logout
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: {
            width: drawerWidth,
            boxSizing: 'border-box',
            borderRight: 1,
            borderColor: 'divider',
            bgcolor: 'background.paper',
          },
        }}
      >
        <Toolbar />
        <Box sx={{ overflow: 'auto', py: 1 }}>
          <List>
            {visibleNavItems.map((item) => (
              <ListItemButton
                key={item.path}
                component={NavLink}
                to={item.path}
                sx={{
                  mx: 1,
                  borderRadius: 1,
                  '&.active': {
                    bgcolor: 'primary.main',
                    color: 'primary.contrastText',
                    '& .MuiListItemIcon-root': { color: 'primary.contrastText' },
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            ))}
          </List>
          <Divider sx={{ my: 1 }} />
        </Box>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${drawerWidth}px)` },
        }}
      >
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  );
}
