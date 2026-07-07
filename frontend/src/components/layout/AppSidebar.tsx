import { useState } from 'react';
import {
  Box,
  Collapse,
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
import AdminPanelSettingsRoundedIcon from '@mui/icons-material/AdminPanelSettingsRounded';
import ExpandLessRoundedIcon from '@mui/icons-material/ExpandLessRounded';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { NavLink } from 'react-router-dom';
import { LogoHomeLink } from '../branding/LogoHomeLink';
import type { CurrentUser } from '../../types';
import { designTokens } from '../../theme/designTokens';
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
        mx: 1,
        mb: 0.25,
        borderRadius: `${designTokens.radius.md}px`,
        color: accent ? 'rgba(255,255,255,0.92)' : 'rgba(255,255,255,0.68)',
        transition: `all ${designTokens.motion.fast}`,
        '&:hover': {
          bgcolor: designTokens.semantic.sidebarHover,
          color: '#fff',
        },
        '&.active': {
          bgcolor: designTokens.semantic.sidebarActive,
          color: '#fff',
          boxShadow: 'inset 3px 0 0 #60a5fa',
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
        slotProps={{
          primary: { sx: { fontWeight: 600, fontSize: '0.875rem' } },
        }}
      />
    </ListItemButton>
  );
}

interface AppSidebarProps {
  user: CurrentUser | null;
}

export function AppSidebar({ user }: AppSidebarProps) {
  const [adminOpen, setAdminOpen] = useState(true);
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
          bgcolor: designTokens.semantic.sidebar,
          color: '#fff',
          borderRight: 'none',
          boxShadow: designTokens.elevation.nav,
        },
      }}
    >
      <Toolbar sx={{ px: 2.5, minHeight: '72px !important' }}>
        <LogoHomeLink light size="md" />
      </Toolbar>

      <Box sx={{ px: 0.5, pb: 2, overflow: 'auto' }}>
        <Typography
          variant="overline"
          sx={{ px: 2.5, py: 1, display: 'block', color: 'rgba(255,255,255,0.45)', letterSpacing: '0.08em' }}
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
            <Divider sx={{ my: 2, mx: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                px: 2,
                py: 0.5,
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <AdminPanelSettingsRoundedIcon sx={{ fontSize: 16, color: '#93c5fd' }} />
                <Typography variant="overline" sx={{ color: 'rgba(255,255,255,0.45)' }}>
                  Administration
                </Typography>
              </Box>
              <IconButton
                size="small"
                onClick={() => setAdminOpen((open) => !open)}
                sx={{ color: 'rgba(255,255,255,0.6)' }}
              >
                {adminOpen ? <ExpandLessRoundedIcon fontSize="small" /> : <ExpandMoreRoundedIcon fontSize="small" />}
              </IconButton>
            </Box>
            <Collapse in={adminOpen}>
              <List disablePadding>
                <NavButton
                  path="/admin/dashboard"
                  label="System Administration"
                  icon={AdminPanelSettingsRoundedIcon}
                  accent
                />
              </List>
            </Collapse>
          </>
        ) : null}
      </Box>
    </Drawer>
  );
}
