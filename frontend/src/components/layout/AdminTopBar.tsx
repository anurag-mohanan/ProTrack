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
import LogoutIcon from '@mui/icons-material/Logout';
import PersonIcon from '@mui/icons-material/Person';
import TuneIcon from '@mui/icons-material/Tune';
import EngineeringIcon from '@mui/icons-material/Engineering';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { AdminSearchBar } from '../admin/AdminSearchBar';
import { LogoHomeLink } from '../branding/LogoHomeLink';
import { NotificationBell } from '../common/NotificationBell';
import { ProsohmButton } from '../ui/ProsohmButton';
import { AdminBreadcrumbs, useAdminBreadcrumbTitle } from './AdminBreadcrumbs';
import { ADMIN_DRAWER_WIDTH } from './AdminSidebar';
import { PRODUCT_TAGLINE } from '../../config/appMeta';
import { formatCellValue } from '../../utils/format';

interface AdminTopBarProps {
  displayName: string;
  roleName: string;
  onLogout: () => void;
}

export function AdminTopBar({ displayName, roleName, onLogout }: AdminTopBarProps) {
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const pageTitle = useAdminBreadcrumbTitle();

  const initials = displayName
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <AppBar
      position="fixed"
      sx={{
        zIndex: (theme) => theme.zIndex.drawer + 1,
        width: { sm: `calc(100% - ${ADMIN_DRAWER_WIDTH}px)` },
        ml: { sm: `${ADMIN_DRAWER_WIDTH}px` },
        bgcolor: '#111827',
        boxShadow: (theme) => theme.palette.prosohm.shadowHeader,
      }}
    >
      <Toolbar sx={{ minHeight: '72px !important', px: { xs: 2, md: 3 }, gap: 2 }}>
        <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 1.5, flexShrink: 0 }}>
          <LogoHomeLink light size="sm" />
        </Box>

        <Box sx={{ flexGrow: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 800,
                fontSize: { xs: '1rem', md: '1.125rem' },
                lineHeight: 1.2,
                color: 'common.white',
              }}
            >
              {pageTitle}
            </Typography>
            <Chip
              label="System Administration"
              size="small"
              sx={{
                height: 22,
                bgcolor: 'rgba(148,163,184,0.16)',
                color: 'grey.200',
                fontWeight: 700,
              }}
            />
          </Box>
          <Typography
            variant="caption"
            sx={{ color: 'grey.400', display: { xs: 'none', lg: 'block' } }}
          >
            {PRODUCT_TAGLINE}
          </Typography>
          <AdminBreadcrumbs />
        </Box>

        <Box sx={{ display: { xs: 'none', lg: 'flex' }, flex: 1, justifyContent: 'center', maxWidth: 560 }}>
          <AdminSearchBar />
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexShrink: 0 }}>
          <ProsohmButton
            buttonVariant="outlined"
            size="small"
            startIcon={<EngineeringIcon />}
            onClick={() => navigate('/dashboard')}
            sx={{
              display: { xs: 'none', md: 'inline-flex' },
              color: 'grey.100',
              borderColor: 'rgba(148,163,184,0.35)',
              '&:hover': { borderColor: 'grey.300', bgcolor: 'rgba(148,163,184,0.08)' },
            }}
          >
            Engineering Operations
          </ProsohmButton>

          <NotificationBell />

          <IconButton onClick={(event) => setAnchorEl(event.currentTarget)} size="small">
            <Avatar
              sx={{
                width: 40,
                height: 40,
                bgcolor: 'secondary.main',
                fontWeight: 700,
                fontSize: '0.875rem',
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
            slotProps={{ paper: { sx: { minWidth: 220, mt: 1, borderRadius: 2 } } }}
          >
            <Box sx={{ px: 2, py: 1.5 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {displayName}
              </Typography>
              <Typography variant="captionLabel" color="text.secondary">
                {formatCellValue(roleName)}
              </Typography>
            </Box>
            <MenuItem component={RouterLink} to="/profile" onClick={() => setAnchorEl(null)}>
              <PersonIcon fontSize="small" sx={{ mr: 1.5 }} />
              Profile
            </MenuItem>
            <MenuItem component={RouterLink} to="/profile?tab=preferences" onClick={() => setAnchorEl(null)}>
              <TuneIcon fontSize="small" sx={{ mr: 1.5 }} />
              Preferences
            </MenuItem>
            <MenuItem
              onClick={() => {
                setAnchorEl(null);
                onLogout();
              }}
            >
              <LogoutIcon fontSize="small" sx={{ mr: 1.5 }} />
              Logout
            </MenuItem>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
}
