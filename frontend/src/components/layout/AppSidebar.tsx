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
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import { NavLink } from 'react-router-dom';
import { LogoHomeLink } from '../branding/LogoHomeLink';
import { AdminNavigation } from './AdminNavigation';
import { getAdminNavSections } from '../../config/adminNavigation';
import { canAccessAdministration, getMainNavItems } from '../../utils/permissions';

export const DRAWER_WIDTH = 272;

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
  icon: React.ComponentType<{ fontSize?: 'small' | 'inherit' | 'large' | 'medium' }>;
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
  const visibleNavItems = getMainNavItems(roleName);
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
            <NavButton key={item.path} path={item.path} label={item.label} icon={item.icon} />
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
