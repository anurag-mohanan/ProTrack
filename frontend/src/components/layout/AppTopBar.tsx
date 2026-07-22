import { useEffect, useState } from 'react';
import {
  AppBar,
  Avatar,
  Box,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Menu,
  MenuItem,
  Toolbar,
  Typography,
} from '@mui/material';
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded';
import MenuRoundedIcon from '@mui/icons-material/MenuRounded';
import PersonRoundedIcon from '@mui/icons-material/PersonRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';
import HelpOutlineRoundedIcon from '@mui/icons-material/HelpOutlineRounded';
import { Link as RouterLink } from 'react-router-dom';
import { NotificationBell } from '../common/NotificationBell';
import { AppGlobalSearchBar } from './AppGlobalSearchBar';
import { useBreadcrumbTitle } from './AppBreadcrumbs';
import { DRAWER_WIDTH } from './AppSidebar';
import { designTokens } from '../../theme/designTokens';
import { formatCellValue } from '../../utils/format';
import {
  NAV_COMPACT_BREAKPOINT,
  PROTRACK_OPEN_SEARCH_EVENT,
} from '../../hooks/useResponsiveShell';

interface AppTopBarProps {
  displayName: string;
  roleName: string;
  onLogout: () => void;
  onOpenNav?: () => void;
  isCompact?: boolean;
}

export function AppTopBar({
  displayName,
  roleName,
  onLogout,
  onOpenNav,
  isCompact = false,
}: AppTopBarProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const pageTitle = useBreadcrumbTitle();

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
      const searchInput = document.getElementById('global-search-input') as HTMLInputElement | null;
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
        elevation={0}
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
          width: {
            xs: '100%',
            [NAV_COMPACT_BREAKPOINT]: `calc(100% - ${DRAWER_WIDTH}px)`,
          },
          ml: {
            xs: 0,
            [NAV_COMPACT_BREAKPOINT]: `${DRAWER_WIDTH}px`,
          },
          bgcolor: designTokens.semantic.card,
          color: 'text.primary',
          borderBottom: '1px solid',
          borderColor: 'divider',
          boxShadow: designTokens.elevation.header,
        }}
      >
        <Toolbar sx={{ minHeight: '64px !important', px: { xs: 1, sm: 1.5, md: 2.5 }, gap: { xs: 0.75, md: 2 } }}>
          {isCompact ? (
            <IconButton
              edge="start"
              aria-label="Open navigation"
              onClick={onOpenNav}
              size="small"
              sx={{ flexShrink: 0 }}
            >
              <MenuRoundedIcon />
            </IconButton>
          ) : null}

          <Box sx={{ minWidth: 0, flexShrink: 1 }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 700,
                fontSize: { xs: '0.95rem', md: '1.05rem' },
                lineHeight: 1.2,
                letterSpacing: '-0.02em',
                maxWidth: { xs: 140, sm: 220, md: 420 },
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
                display: { xs: 'none', sm: 'inline-flex' },
              }}
            />
          </Box>

          <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', minWidth: 0 }}>
            <Box
              sx={{
                display: { xs: 'none', [NAV_COMPACT_BREAKPOINT]: 'flex' },
                width: '100%',
                maxWidth: 520,
              }}
            >
              <AppGlobalSearchBar />
            </Box>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25, flexShrink: 0 }}>
            <IconButton
              aria-label="Search"
              size="small"
              onClick={() => setSearchOpen(true)}
              sx={{ display: { xs: 'inline-flex', [NAV_COMPACT_BREAKPOINT]: 'none' } }}
            >
              <SearchRoundedIcon />
            </IconButton>
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
                  width: { xs: 34, md: 38 },
                  height: { xs: 34, md: 38 },
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
              <MenuItem
                component={RouterLink}
                to="/profile?tab=preferences"
                onClick={() => setAnchorEl(null)}
              >
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

      <Dialog
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        fullWidth
        maxWidth="sm"
        fullScreen={isCompact}
      >
        <DialogTitle sx={{ pb: 1 }}>Search</DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          <AppGlobalSearchBar autoFocus onSubmitted={() => setSearchOpen(false)} />
        </DialogContent>
      </Dialog>
    </>
  );
}
