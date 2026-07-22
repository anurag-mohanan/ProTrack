import { useEffect, useState } from 'react';
import {
  AppBar,
  Avatar,
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Menu,
  MenuItem,
  Toolbar,
  Typography,
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import MenuRoundedIcon from '@mui/icons-material/MenuRounded';
import PersonIcon from '@mui/icons-material/Person';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import TuneIcon from '@mui/icons-material/Tune';
import { Link as RouterLink } from 'react-router-dom';
import { AdminSearchBar } from '../admin/AdminSearchBar';
import { NotificationBell } from '../common/NotificationBell';
import { useAdminBreadcrumbTitle } from './AdminBreadcrumbs';
import { ADMIN_DRAWER_WIDTH } from './AdminSidebar';
import { formatCellValue } from '../../utils/format';
import {
  NAV_COMPACT_BREAKPOINT,
  PROTRACK_OPEN_SEARCH_EVENT,
} from '../../hooks/useResponsiveShell';

interface AdminTopBarProps {
  displayName: string;
  roleName: string;
  onLogout: () => void;
  onOpenNav?: () => void;
  isCompact?: boolean;
}

export function AdminTopBar({
  displayName,
  roleName,
  onLogout,
  onOpenNav,
  isCompact = false,
}: AdminTopBarProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const pageTitle = useAdminBreadcrumbTitle();

  const initials = displayName
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  useEffect(() => {
    const onOpenSearch = () => {
      if (isCompact) {
        setSearchOpen(true);
        return;
      }
      const searchInput = document.querySelector(
        'input[aria-label="Admin search"], #admin-search-input',
      ) as HTMLInputElement | null;
      searchInput?.focus();
      searchInput?.select();
    };
    window.addEventListener(PROTRACK_OPEN_SEARCH_EVENT, onOpenSearch);
    return () => window.removeEventListener(PROTRACK_OPEN_SEARCH_EVENT, onOpenSearch);
  }, [isCompact]);

  return (
    <>
      <AppBar
        position="fixed"
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
          width: {
            xs: '100%',
            [NAV_COMPACT_BREAKPOINT]: `calc(100% - ${ADMIN_DRAWER_WIDTH}px)`,
          },
          ml: {
            xs: 0,
            [NAV_COMPACT_BREAKPOINT]: `${ADMIN_DRAWER_WIDTH}px`,
          },
          bgcolor: '#111827',
          boxShadow: (theme) => theme.palette.prosohm.shadowHeader,
        }}
      >
        <Toolbar sx={{ minHeight: '64px !important', px: { xs: 1, sm: 1.5, md: 2 }, gap: { xs: 0.75, md: 2 } }}>
          {isCompact ? (
            <IconButton
              edge="start"
              aria-label="Open navigation"
              onClick={onOpenNav}
              size="small"
              sx={{ color: 'common.white', flexShrink: 0 }}
            >
              <MenuRoundedIcon />
            </IconButton>
          ) : null}

          <Typography
            variant="h6"
            sx={{
              fontWeight: 800,
              fontSize: { xs: '0.95rem', md: '1.125rem' },
              lineHeight: 1.2,
              color: 'common.white',
              flexShrink: 1,
              minWidth: 0,
              maxWidth: { xs: 140, sm: 240, md: 'none' },
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={pageTitle}
          >
            {pageTitle}
          </Typography>

          <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', minWidth: 0 }}>
            <Box
              sx={{
                display: { xs: 'none', [NAV_COMPACT_BREAKPOINT]: 'flex' },
                width: '100%',
                maxWidth: 520,
              }}
            >
              <AdminSearchBar />
            </Box>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
            <IconButton
              aria-label="Search"
              size="small"
              onClick={() => setSearchOpen(true)}
              sx={{
                color: 'common.white',
                display: { xs: 'inline-flex', [NAV_COMPACT_BREAKPOINT]: 'none' },
              }}
            >
              <SearchRoundedIcon />
            </IconButton>
            <NotificationBell />
            <IconButton onClick={(event) => setAnchorEl(event.currentTarget)} size="small">
              <Avatar
                sx={{
                  width: { xs: 34, md: 36 },
                  height: { xs: 34, md: 36 },
                  bgcolor: 'secondary.main',
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
              <MenuItem
                component={RouterLink}
                to="/profile?tab=preferences"
                onClick={() => setAnchorEl(null)}
              >
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

      <Dialog
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        fullWidth
        maxWidth="sm"
        fullScreen={isCompact}
      >
        <DialogTitle sx={{ pb: 1 }}>Search</DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          <AdminSearchBar />
        </DialogContent>
      </Dialog>
    </>
  );
}
