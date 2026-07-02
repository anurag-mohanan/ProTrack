import {
  Box,
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
import ArchiveIcon from '@mui/icons-material/Archive';
import ScheduleIcon from '@mui/icons-material/Schedule';
import GroupsIcon from '@mui/icons-material/Groups';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import { NavLink } from 'react-router-dom';
import { LogoHomeLink } from '../branding/LogoHomeLink';
import { AdminNavigation } from './AdminNavigation';
import { getAdminNavSections } from '../../config/adminNavigation';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import {
  canAccessAdministration,
  canViewReports,
  canViewResourcePlanning,
  canViewWorkload,
} from '../../utils/permissions';

export const DRAWER_WIDTH = 272;

const navItems = [
  { label: 'Dashboard', path: '/dashboard', icon: DashboardIcon },
  { label: 'Projects', path: '/projects', icon: FolderIcon },
  { label: 'Archived Projects', path: '/projects/archived', icon: ArchiveIcon },
  { label: 'Timesheets', path: '/timesheets', icon: ScheduleIcon },
  { label: 'Workload', path: '/workload', icon: GroupsIcon },
  { label: 'Resource Planning', path: '/resource-planning', icon: CalendarMonthIcon },
  { label: 'Reports', path: '/reports', icon: AssessmentIcon },
];

interface AppSidebarProps {
  roleName: string;
}

function NavButton({
  path,
  label,
  icon: Icon,
}: {
  path: string;
  label: string;
  icon: typeof DashboardIcon;
}) {
  return (
    <ListItemButton
      component={NavLink}
      to={path}
      sx={{
        color: 'prosohm.sidebarTextMuted',
        '&.active': {
          bgcolor: 'prosohm.sidebarActive',
          color: 'prosohm.sidebarText',
          borderLeft: '3px solid',
          borderColor: 'primary.main',
          pl: 'calc(16px - 3px)',
          '& .MuiListItemIcon-root': {
            color: 'primary.main',
          },
        },
      }}
    >
      <ListItemIcon sx={{ minWidth: 40, color: 'inherit' }}>
        <Icon fontSize="small" />
      </ListItemIcon>
      <ListItemText
        primary={label}
        sx={{
          '& .MuiListItemText-primary': {
            fontWeight: 600,
            fontSize: '0.875rem',
          },
        }}
      />
    </ListItemButton>
  );
}

export function AppSidebar({ roleName }: AppSidebarProps) {
  const visibleNavItems = navItems.filter((item) => {
    if (item.path === '/reports') return canViewReports(roleName);
    if (item.path === '/workload') return canViewWorkload(roleName);
    if (item.path === '/resource-planning') return canViewResourcePlanning(roleName);
    return true;
  });

  const adminSections = getAdminNavSections(roleName);

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: DRAWER_WIDTH,
          boxSizing: 'border-box',
          bgcolor: 'prosohm.sidebar',
          color: 'prosohm.sidebarText',
          backgroundImage: (theme) => theme.palette.prosohm.gradientSidebar,
        },
      }}
    >
      <Toolbar sx={{ px: 2.5, minHeight: '72px !important' }}>
        <LogoHomeLink light size="md" />
      </Toolbar>

      <Box sx={{ px: 1, pb: 2, overflow: 'auto' }}>
        <Typography
          variant="overline"
          sx={{ px: 2, py: 1, display: 'block', color: 'prosohm.sidebarTextMuted' }}
        >
          Main
        </Typography>
        <List disablePadding>
          {visibleNavItems.map((item) => (
            <NavButton key={item.path} {...item} />
          ))}
        </List>

        {canAccessAdministration(roleName) ? (
          <>
            <Divider sx={{ my: 2, borderColor: 'prosohm.sidebarDivider' }} />
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1 }}>
              <AdminPanelSettingsIcon sx={{ fontSize: 16, color: 'primary.main' }} />
              <Typography variant="overline" sx={{ color: 'prosohm.sidebarTextMuted' }}>
                Administration
              </Typography>
            </Box>
            <AdminNavigation sections={adminSections} />
          </>
        ) : null}
      </Box>
    </Drawer>
  );
}
