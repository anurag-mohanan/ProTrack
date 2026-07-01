import type { ReactNode } from 'react';
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

interface ModernDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  icon?: SvgIconComponent;
  children: ReactNode;
  footer?: ReactNode;
  width?: number | string;
}

export function ModernDrawer({
  open,
  onClose,
  title,
  subtitle,
  icon: Icon,
  children,
  footer,
  width = 560,
}: ModernDrawerProps) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        paper: {
          sx: {
            width: fullScreen ? '100%' : width,
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
        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', minWidth: 0 }}>
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
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
              {title}
            </Typography>
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
