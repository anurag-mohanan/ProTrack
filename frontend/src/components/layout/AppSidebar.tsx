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
import type { CurrentUser } from '../../types';
import { accessContextFromUser, canAccessAdministration, getMainNavItems } from '../../utils/permissions';

export const DRAWER_WIDTH = 272;

function NavButton({
  path,
  label,
  icon: Icon,
  accent = false,
}: {
  path: string;
  label: string;
  icon: React.ComponentType<{ fontSize?: 'small' | 'inherit' | 'large' | 'medium' }>;
  accent?: boolean;
}) {
  return (
    <ListItemButton
      component={NavLink}
      to={path}
      sx={{
        color: accent ? 'secondary.light' : 'prosohm.sidebarTextMuted',
        bgcolor: accent ? 'rgba(148,163,184,0.08)' : undefined,
        border: accent ? '1px solid rgba(148,163,184,0.18)' : undefined,
        borderRadius: accent ? 2 : 0,
        mx: accent ? 1 : 0,
        mb: accent ? 0.5 : 0,
        '&.active': {
          bgcolor: accent ? 'rgba(148,163,184,0.16)' : 'prosohm.sidebarActive',
          color: 'prosohm.sidebarText',
          borderLeft: accent ? undefined : '3px solid',
          borderColor: 'primary.main',
          pl: accent ? 2 : 'calc(16px - 3px)',
          '& .MuiListItemIcon-root': {
            color: accent ? 'secondary.light' : 'primary.main',
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
            fontWeight: accent ? 700 : 600,
            fontSize: '0.875rem',
          },
        }}
      />
    </ListItemButton>
  );
}

interface AppSidebarProps {
  user: CurrentUser | null;
}

export function AppSidebar({ user }: AppSidebarProps) {
  const ctx = accessContextFromUser(user);
  const visibleNavItems = getMainNavItems(ctx);
  const showAdministratorEntry = canAccessAdministration(ctx);

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
          Engineering Operations
        </Typography>
        <List disablePadding>
          {visibleNavItems.map((item) => (
            <NavButton key={item.path} path={item.path} label={item.label} icon={item.icon} />
          ))}
        </List>

        {showAdministratorEntry ? (
          <>
            <Divider sx={{ my: 2, borderColor: 'prosohm.sidebarDivider' }} />
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1 }}>
              <AdminPanelSettingsIcon sx={{ fontSize: 16, color: 'secondary.light' }} />
              <Typography variant="overline" sx={{ color: 'prosohm.sidebarTextMuted' }}>
                System Administration
              </Typography>
            </Box>
            <List disablePadding>
              <NavButton
                path="/admin/dashboard"
                label="System Administration"
                icon={AdminPanelSettingsIcon}
                accent
              />
            </List>
          </>
        ) : null}
      </Box>
    </Drawer>
  );
}
