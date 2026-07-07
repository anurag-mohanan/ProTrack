import type { ReactNode } from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { designTokens } from '../../../theme/designTokens';

interface DashboardPanelProps {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  noPadding?: boolean;
  height?: number | string;
}

export function DashboardPanel({
  title,
  subtitle,
  action,
  children,
  noPadding = false,
  height,
}: DashboardPanelProps) {
  return (
    <Paper
      elevation={0}
      sx={{
        borderRadius: `${designTokens.radius.lg}px`,
        border: '1px solid',
        borderColor: 'divider',
        boxShadow: designTokens.elevation.card,
        bgcolor: designTokens.semantic.card,
        height,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transition: `box-shadow ${designTokens.motion.normal}`,
        '&:hover': {
          boxShadow: designTokens.elevation.cardHover,
        },
      }}
    >
      {title ? (
        <Box
          sx={{
            px: 2.5,
            py: 2,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 2,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, letterSpacing: '-0.01em' }}>
              {title}
            </Typography>
            {subtitle ? (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                {subtitle}
              </Typography>
            ) : null}
          </Box>
          {action}
        </Box>
      ) : null}
      <Box sx={{ p: noPadding ? 0 : 2.5, flex: 1, minHeight: 0 }}>{children}</Box>
    </Paper>
  );
}
