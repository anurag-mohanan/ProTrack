import { useState } from 'react';
import { Link as RouterLink, Outlet, useLocation } from 'react-router-dom';
import {
  AppBar,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import DashboardIcon from '@mui/icons-material/Dashboard';
import FolderIcon from '@mui/icons-material/Folder';
import FlagIcon from '@mui/icons-material/Flag';
import ScheduleIcon from '@mui/icons-material/Schedule';
import GroupsIcon from '@mui/icons-material/Groups';
import BusinessIcon from '@mui/icons-material/Business';
import PeopleIcon from '@mui/icons-material/People';
import CategoryIcon from '@mui/icons-material/Category';
import AssessmentIcon from '@mui/icons-material/Assessment';

const drawerWidth = 260;

const navSections = [
  {
    title: 'Overview',
    items: [
      { label: 'Dashboard', path: '/', icon: <DashboardIcon /> },
      { label: 'Reports', path: '/reports', icon: <AssessmentIcon /> },
    ],
  },
  {
    title: 'Delivery',
    items: [
      { label: 'Projects', path: '/projects', icon: <FolderIcon /> },
      { label: 'Milestones', path: '/milestones', icon: <FlagIcon /> },
      { label: 'Timesheets', path: '/timesheets', icon: <ScheduleIcon /> },
      { label: 'Resource Planning', path: '/resource-planning', icon: <GroupsIcon /> },
    ],
  },
  {
    title: 'Master Data',
    items: [
      { label: 'Customers', path: '/customers', icon: <BusinessIcon /> },
      { label: 'Streams & Tasks', path: '/streams', icon: <CategoryIcon /> },
      { label: 'Users & Roles', path: '/users', icon: <PeopleIcon /> },
    ],
  },
];

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Toolbar>
        <Typography variant="h6" color="primary" sx={{ fontWeight: 800 }}>
          ProTrack
        </Typography>
      </Toolbar>
      <Divider />
      <Box sx={{ flex: 1, overflowY: 'auto', py: 1 }}>
        {navSections.map((section) => (
          <Box key={section.title} sx={{ mb: 1 }}>
            <Typography
              variant="overline"
              sx={{ px: 2, color: 'text.secondary', fontWeight: 700 }}
            >
              {section.title}
            </Typography>
            <List dense disablePadding>
              {section.items.map((item) => (
                <ListItemButton
                  key={item.path}
                  component={RouterLink}
                  to={item.path}
                  selected={location.pathname === item.path}
                  onClick={() => setMobileOpen(false)}
                  sx={{ mx: 1, borderRadius: 2 }}
                >
                  <ListItemIcon sx={{ minWidth: 40 }}>{item.icon}</ListItemIcon>
                  <ListItemText primary={item.label} />
                </ListItemButton>
              ))}
            </List>
          </Box>
        ))}
      </Box>
      <Divider />
      <Typography variant="caption" sx={{ p: 2, color: 'text.secondary' }}>
        Prosohm · Project Tracking
      </Typography>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          width: { md: `calc(100% - ${drawerWidth}px)` },
          ml: { md: `${drawerWidth}px` },
          bgcolor: 'background.paper',
          color: 'text.primary',
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Toolbar>
          <IconButton
            edge="start"
            onClick={() => setMobileOpen(!mobileOpen)}
            sx={{ mr: 2, display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap>
            {navSections.flatMap((s) => s.items).find((i) => i.path === location.pathname)?.label ?? 'ProTrack'}
          </Typography>
        </Toolbar>
      </AppBar>

      <Box component="nav" sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': { width: drawerWidth, boxSizing: 'border-box' },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': { width: drawerWidth, boxSizing: 'border-box' },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: { xs: 2, md: 3 },
          width: { md: `calc(100% - ${drawerWidth}px)` },
          mt: 8,
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}
