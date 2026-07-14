import type { ReactNode } from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { designTokens } from '../../../theme/designTokens';
import { chartTheme } from '../../../theme/chartTheme';

interface DashboardPanelProps {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  noPadding?: boolean;
  height?: number | string;
  /** Soft, borderless surface for modern chart cards. */
  variant?: 'default' | 'minimal';
}

export function DashboardPanel({
  title,
  subtitle,
  action,
  children,
  noPadding = false,
  height,
  variant = 'default',
}: DashboardPanelProps) {
  const minimal = variant === 'minimal';

  return (
    <Paper
      elevation={0}
      sx={{
        borderRadius: minimal ? 3 : `${designTokens.radius.lg}px`,
        border: '1px solid',
        borderColor: minimal ? chartTheme.surface.hairline : 'divider',
        boxShadow: minimal ? 'none' : designTokens.elevation.card,
        bgcolor: minimal ? chartTheme.surface.card : designTokens.semantic.card,
        height,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transition: `border-color ${designTokens.motion.normal}, box-shadow ${designTokens.motion.normal}`,
        '&:hover': minimal
          ? { borderColor: 'rgba(15, 23, 42, 0.12)' }
          : { boxShadow: designTokens.elevation.cardHover },
      }}
    >
      {title ? (
        <Box
          sx={{
            px: minimal ? 2.25 : 2.5,
            pt: minimal ? 2 : 2,
            pb: minimal ? 1 : 2,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 2,
            borderBottom: minimal ? 'none' : '1px solid',
            borderColor: 'divider',
          }}
        >
          <Box>
            <Typography
              variant="subtitle1"
              sx={{
                fontWeight: minimal ? 600 : 700,
                letterSpacing: '-0.02em',
                fontSize: minimal ? '0.9375rem' : undefined,
                color: chartTheme.ink.primary,
              }}
            >
              {title}
            </Typography>
            {subtitle ? (
              <Typography
                variant="body2"
                sx={{
                  mt: 0.25,
                  fontSize: minimal ? '0.75rem' : undefined,
                  color: chartTheme.ink.tertiary,
                  fontWeight: 500,
                }}
              >
                {subtitle}
              </Typography>
            ) : null}
          </Box>
          {action}
        </Box>
      ) : null}
      <Box
        sx={{
          p: noPadding ? 0 : minimal ? 2.25 : 2.5,
          pt: minimal && title ? 1 : undefined,
          pb: noPadding ? 0 : minimal ? 2.25 : 2.5,
          flex: 1,
          minHeight: 0,
          // Fixed-height panels must scroll inside the body — never clip mid-row.
          overflowY: height != null ? 'auto' : 'visible',
          overflowX: 'hidden',
        }}
      >
        {children}
      </Box>
    </Paper>
  );
}
