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
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import { NavLink } from 'react-router-dom';
import { LogoHomeLink } from '../branding/LogoHomeLink';
import { ADMIN_WORKSPACE_NAV } from '../../config/adminNavigation';

export const ADMIN_DRAWER_WIDTH = 272;

function NavButton({
  path,
  label,
  icon: Icon,
  end = false,
}: {
  path: string;
  label: string;
  icon: React.ComponentType<{ fontSize?: 'small' | 'inherit' | 'large' | 'medium' }>;
  end?: boolean;
}) {
  return (
    <ListItemButton
      component={NavLink}
      to={path}
      end={end}
      sx={{
        color: 'prosohm.sidebarTextMuted',
        '&.active': {
          bgcolor: 'prosohm.sidebarActive',
          color: 'prosohm.sidebarText',
          borderLeft: '3px solid',
          borderColor: 'secondary.main',
          pl: 'calc(16px - 3px)',
          '& .MuiListItemIcon-root': {
            color: 'secondary.main',
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

export function AdminSidebar() {
  return (
    <Drawer
      variant="permanent"
      sx={{
        width: ADMIN_DRAWER_WIDTH,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: ADMIN_DRAWER_WIDTH,
          boxSizing: 'border-box',
          bgcolor: '#0B1220',
          color: 'prosohm.sidebarText',
          backgroundImage: 'linear-gradient(180deg, rgba(15,23,42,1) 0%, rgba(2,6,23,1) 100%)',
          borderRight: '1px solid',
          borderColor: 'rgba(148,163,184,0.12)',
        },
      }}
    >
      <Toolbar sx={{ px: 2.5, minHeight: '72px !important' }}>
        <LogoHomeLink light size="md" to="/admin/dashboard" />
      </Toolbar>

      <Box sx={{ px: 1, pb: 2, overflow: 'auto' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1 }}>
          <AdminPanelSettingsIcon sx={{ fontSize: 16, color: 'secondary.main' }} />
          <Typography variant="overline" sx={{ color: 'prosohm.sidebarTextMuted' }}>
            System Administration
          </Typography>
        </Box>

        <List disablePadding>
          {ADMIN_WORKSPACE_NAV.map((item) => (
            <NavButton
              key={item.path}
              path={item.path}
              label={item.label}
              icon={item.icon}
              end={item.path === '/admin/dashboard'}
            />
          ))}
        </List>

        <Divider sx={{ my: 2, borderColor: 'rgba(148,163,184,0.16)' }} />

        <List disablePadding>
          <NavButton path="/dashboard" label="Engineering Operations" icon={ArrowBackIcon} />
        </List>
      </Box>
    </Drawer>
  );
}
