import { useEffect, type ReactNode } from 'react';
import {
  Box,
  Drawer,
  IconButton,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import type { SvgIconComponent } from '@mui/icons-material';

export type DrawerWidthPreset = 'detail' | 'form';

function resolveDrawerWidth(
  preset: DrawerWidthPreset,
  customWidth?: number | string,
): string {
  if (customWidth !== undefined) {
    return typeof customWidth === 'number' ? `${customWidth}px` : customWidth;
  }
  if (preset === 'form') {
    return 'min(560px, 100vw)';
  }
  return '38vw';
}

interface RecordDetailDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  icon?: SvgIconComponent;
  status?: ReactNode;
  quickActions?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: number | string;
  widthPreset?: DrawerWidthPreset;
}

export function RecordDetailDrawer({
  open,
  onClose,
  title,
  subtitle,
  icon: Icon,
  status,
  quickActions,
  children,
  footer,
  width,
  widthPreset = 'detail',
}: RecordDetailDrawerProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.between('sm', 'md'));

  const drawerWidth = isMobile
    ? '100%'
    : isTablet
      ? '60%'
      : resolveDrawerWidth(widthPreset, width);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      transitionDuration={{ enter: 225, exit: 200 }}
      slotProps={{
        paper: {
          sx: {
            width: drawerWidth,
            maxWidth: '100vw',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: theme.palette.prosohm.shadowDialog,
            borderLeft: `1px solid ${theme.palette.prosohm.border}`,
          },
        },
        backdrop: {
          sx: { backdropFilter: 'blur(2px)' },
        },
      }}
      ModalProps={{ keepMounted: false }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 2,
          px: 3,
          py: 2.5,
          borderBottom: `1px solid ${theme.palette.prosohm.border}`,
          bgcolor: 'background.paper',
          position: 'sticky',
          top: 0,
          zIndex: 2,
        }}
      >
        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', minWidth: 0, flex: 1 }}>
          {Icon ? (
            <Box
              sx={{
                width: 44,
                height: 44,
                borderRadius: 2.5,
                display: 'grid',
                placeItems: 'center',
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                flexShrink: 0,
              }}
            >
              <Icon fontSize="small" />
            </Box>
          ) : null}
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                {title}
              </Typography>
              {status}
            </Box>
            {subtitle ? (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {subtitle}
              </Typography>
            ) : null}
          </Box>
        </Box>
        <IconButton onClick={onClose} aria-label="Close panel" sx={{ mt: -0.5 }}>
          <CloseIcon />
        </IconButton>
      </Box>

      {quickActions ? (
        <Box
          sx={{
            px: 3,
            py: 1.5,
            borderBottom: `1px solid ${theme.palette.prosohm.border}`,
            bgcolor: 'background.paper',
            display: 'flex',
            gap: 1,
            flexWrap: 'wrap',
          }}
        >
          {quickActions}
        </Box>
      ) : null}

      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          px: 3,
          py: 3,
          bgcolor: 'background.default',
        }}
      >
        {children}
      </Box>

      {footer ? (
        <Box
          sx={{
            px: 3,
            py: 2,
            borderTop: `1px solid ${theme.palette.prosohm.border}`,
            bgcolor: 'background.paper',
            position: 'sticky',
            bottom: 0,
            zIndex: 2,
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 1.5,
            flexWrap: 'wrap',
          }}
        >
          {footer}
        </Box>
      ) : null}
    </Drawer>
  );
}
