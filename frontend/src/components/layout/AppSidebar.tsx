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
import DeleteIcon from '@mui/icons-material/Delete';
import ScheduleIcon from '@mui/icons-material/Schedule';
import GroupsIcon from '@mui/icons-material/Groups';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import PeopleIcon from '@mui/icons-material/People';
import BusinessIcon from '@mui/icons-material/Business';
import ContactPhoneIcon from '@mui/icons-material/ContactPhone';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import CategoryIcon from '@mui/icons-material/Category';
import SecurityIcon from '@mui/icons-material/Security';
import SettingsIcon from '@mui/icons-material/Settings';
import ViewTimelineIcon from '@mui/icons-material/ViewTimeline';
import TypeSpecimenIcon from '@mui/icons-material/TypeSpecimen';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import { NavLink } from 'react-router-dom';
import { ProsohmLogo } from '../branding/ProsohmLogo';
import {
  canAccessAdministration,
  canImportHistoricalProjects,
  canViewDeletedProjects,
  canViewReports,
  canViewWorkload,
} from '../../utils/permissions';

export const DRAWER_WIDTH = 272;

const navItems = [
  { label: 'Dashboard', path: '/dashboard', icon: DashboardIcon },
  { label: 'Projects', path: '/projects', icon: FolderIcon },
  { label: 'Archived Projects', path: '/projects/archived', icon: ArchiveIcon },
  { label: 'Timesheets', path: '/timesheets', icon: ScheduleIcon },
  { label: 'Workload', path: '/workload', icon: GroupsIcon },
  { label: 'Reports', path: '/reports', icon: AssessmentIcon },
];

const adminNavItems = [
  { label: 'Users', path: '/admin/users', icon: PeopleIcon },
  { label: 'Customers', path: '/admin/customers', icon: BusinessIcon },
  { label: 'Contacts', path: '/admin/contacts', icon: ContactPhoneIcon },
  { label: 'Streams', path: '/admin/streams', icon: AccountTreeIcon },
  { label: 'Task Types', path: '/admin/task-types', icon: CategoryIcon },
  { label: 'Project Types', path: '/admin/project-types', icon: TypeSpecimenIcon },
  { label: 'Project Templates', path: '/admin/project-templates', icon: ViewTimelineIcon },
  { label: 'Roles', path: '/admin/roles', icon: SecurityIcon },
  { label: 'System Settings', path: '/admin/settings', icon: SettingsIcon },
  {
    label: 'Deleted Projects',
    path: '/admin/deleted-projects',
    icon: DeleteIcon,
    adminOnly: true,
  },
  {
    label: 'Import Historical Projects',
    path: '/admin/import-historical-projects',
    icon: UploadFileIcon,
    adminOnly: true,
  },
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
          bgcolor: 'rgba(26, 188, 156, 0.16)',
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
    return true;
  });

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
          backgroundImage:
            'linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(0,0,0,0.08) 100%)',
        },
      }}
    >
      <Toolbar sx={{ px: 2.5, minHeight: '72px !important' }}>
        <ProsohmLogo light size="md" />
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
            <Divider sx={{ my: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1 }}>
              <AdminPanelSettingsIcon sx={{ fontSize: 16, color: 'primary.main' }} />
              <Typography variant="overline" sx={{ color: 'prosohm.sidebarTextMuted' }}>
                Administration
              </Typography>
            </Box>
            <List disablePadding>
              {adminNavItems
                .filter((item) => {
                  if (item.path === '/admin/deleted-projects') {
                    return canViewDeletedProjects(roleName);
                  }
                  if (item.adminOnly) return canImportHistoricalProjects(roleName);
                  return true;
                })
                .map((item) => (
                  <NavButton key={item.path} {...item} />
                ))}
            </List>
          </>
        ) : null}
      </Box>
    </Drawer>
  );
}
