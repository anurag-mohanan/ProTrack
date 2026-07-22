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
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import AdminPanelSettingsRoundedIcon from '@mui/icons-material/AdminPanelSettingsRounded';
import { NavLink } from 'react-router-dom';
import { LogoHomeLink } from '../branding/LogoHomeLink';
import { getAdminWorkspaceNav } from '../../config/adminNavigation';
import { useAuth } from '../../context/AuthContext';
import { accessContextFromUser } from '../../utils/permissions';
import { navItemNeedsExactMatch } from '../../utils/navActive';

export const ADMIN_DRAWER_WIDTH = 272;

import { designTokens } from '../../theme/designTokens';

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
        mx: 1,
        mb: 0.25,
        borderRadius: `${designTokens.radius.md}px`,
        color: 'rgba(255,255,255,0.68)',
        transition: `all ${designTokens.motion.fast}`,
        '&:hover': {
          bgcolor: designTokens.semantic.sidebarHover,
          color: '#fff',
        },
        '&.active': {
          bgcolor: designTokens.semantic.sidebarActive,
          color: '#fff',
          boxShadow: 'inset 3px 0 0 #60a5fa',
          pl: 'calc(16px - 3px)',
          '& .MuiListItemIcon-root': {
            color: '#93c5fd',
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
  const { user } = useAuth();
  const workspaceNav = getAdminWorkspaceNav(accessContextFromUser(user));
  const workspacePaths = workspaceNav.map((item) => item.path);

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
          <AdminPanelSettingsRoundedIcon sx={{ fontSize: 16, color: '#93c5fd' }} />
          <Typography variant="overline" sx={{ color: 'prosohm.sidebarTextMuted' }}>
            System Administration
          </Typography>
        </Box>

        <List disablePadding>
          {workspaceNav.map((item) => (
            <NavButton
              key={item.path}
              path={item.path}
              label={item.label}
              icon={item.icon}
              end={navItemNeedsExactMatch(item.path, workspacePaths)}
            />
          ))}
        </List>

        <Divider sx={{ my: 2, borderColor: 'rgba(148,163,184,0.16)' }} />

        <List disablePadding>
          <NavButton path="/dashboard" label="Engineering Operations" icon={ArrowBackRoundedIcon} end />
        </List>
      </Box>
    </Drawer>
  );
}
