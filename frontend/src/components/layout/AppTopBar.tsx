import { useState } from 'react';
import {
  AppBar,
  Avatar,
  Box,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  Toolbar,
  Typography,
} from '@mui/material';
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded';
import PersonRoundedIcon from '@mui/icons-material/PersonRounded';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';
import HelpOutlineRoundedIcon from '@mui/icons-material/HelpOutlineRounded';
import { Link as RouterLink } from 'react-router-dom';
import { NotificationBell } from '../common/NotificationBell';
import { AppGlobalSearchBar } from './AppGlobalSearchBar';
import { useBreadcrumbTitle } from './AppBreadcrumbs';
import { DRAWER_WIDTH } from './AppSidebar';
import { designTokens } from '../../theme/designTokens';
import { formatCellValue } from '../../utils/format';

interface AppTopBarProps {
  displayName: string;
  roleName: string;
  onLogout: () => void;
}

export function AppTopBar({ displayName, roleName, onLogout }: AppTopBarProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const pageTitle = useBreadcrumbTitle();

  const initials = displayName
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <AppBar
      position="fixed"
      elevation={0}
      sx={{
        zIndex: (theme) => theme.zIndex.drawer + 1,
        width: { sm: `calc(100% - ${DRAWER_WIDTH}px)` },
        ml: { sm: `${DRAWER_WIDTH}px` },
        bgcolor: designTokens.semantic.card,
        color: 'text.primary',
        borderBottom: '1px solid',
        borderColor: 'divider',
        boxShadow: designTokens.elevation.header,
      }}
    >
      <Toolbar sx={{ minHeight: '64px !important', px: { xs: 1.5, md: 2.5 }, gap: 2 }}>
        <Box sx={{ minWidth: 0, flexShrink: 0 }}>
          <Typography
            variant="h6"
            sx={{
              fontWeight: 700,
              fontSize: { xs: '1rem', md: '1.05rem' },
              lineHeight: 1.2,
              letterSpacing: '-0.02em',
              maxWidth: { xs: 180, sm: 280, md: 420 },
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={pageTitle}
          >
            {pageTitle}
          </Typography>
          <Chip
            label={formatCellValue(roleName)}
            size="small"
            sx={{
              mt: 0.5,
              height: 22,
              fontSize: '0.6875rem',
              fontWeight: 600,
              bgcolor: designTokens.semantic.primarySoft,
              color: designTokens.semantic.primary,
            }}
          />
        </Box>

        <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', minWidth: 0 }}>
          <Box sx={{ display: { xs: 'none', md: 'flex' }, width: '100%', maxWidth: 520 }}>
            <AppGlobalSearchBar />
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
          <NotificationBell />
          <IconButton
            onClick={(event) => setAnchorEl(event.currentTarget)}
            size="small"
            sx={{
              ml: 0.5,
              transition: `transform ${designTokens.motion.fast}`,
              '&:hover': { transform: 'scale(1.04)' },
            }}
          >
            <Avatar
              sx={{
                width: 38,
                height: 38,
                bgcolor: designTokens.semantic.primary,
                fontWeight: 700,
                fontSize: '0.8125rem',
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
                sx: { minWidth: 240, mt: 1, borderRadius: `${designTokens.radius.md}px` },
              },
            }}
          >
            <Box sx={{ px: 2, py: 1.5 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {displayName}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {formatCellValue(roleName)}
              </Typography>
            </Box>
            <MenuItem component={RouterLink} to="/profile" onClick={() => setAnchorEl(null)}>
              <PersonRoundedIcon fontSize="small" sx={{ mr: 1.5 }} />
              Profile
            </MenuItem>
            <MenuItem component={RouterLink} to="/profile?tab=preferences" onClick={() => setAnchorEl(null)}>
              <TuneRoundedIcon fontSize="small" sx={{ mr: 1.5 }} />
              Preferences
            </MenuItem>
            <MenuItem component={RouterLink} to="/help" onClick={() => setAnchorEl(null)}>
              <HelpOutlineRoundedIcon fontSize="small" sx={{ mr: 1.5 }} />
              Help Center
            </MenuItem>
            <MenuItem
              onClick={() => {
                setAnchorEl(null);
                onLogout();
              }}
            >
              <LogoutRoundedIcon fontSize="small" sx={{ mr: 1.5 }} />
              Logout
            </MenuItem>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
}
