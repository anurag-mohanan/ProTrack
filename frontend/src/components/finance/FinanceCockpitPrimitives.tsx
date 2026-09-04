/**
 * Shared visual primitives for Finance cockpit (Phase B UX).
 * Uses design-system tokens — Abacum/Adaptive/QBO-inspired density without new design language.
 */
import type { ReactNode } from 'react';
import { Box, Chip, LinearProgress, Paper, Stack, Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import { designTokens } from '../../theme/designTokens';
import { chartTheme } from '../../theme/chartTheme';
import { formatIndianNumber, toFiniteNumber } from '../../utils/format';

export function financeMoney(value: unknown, currency = 'INR'): string {
  const n = toFiniteNumber(value);
  return `${formatIndianNumber(n)} ${currency}`;
}

/** Shared list-row chrome for Quotes / Expenses / Commercial panels. */
export const financeListRowSx = {
  p: 1.5,
  borderRadius: `${designTokens.radius.md}px`,
  border: '1px solid',
  borderColor: 'divider',
  bgcolor: 'background.paper',
  display: 'flex',
  justifyContent: 'space-between',
  gap: 2,
  flexWrap: 'wrap' as const,
  alignItems: 'flex-start',
  transition: 'border-color 120ms ease, background-color 120ms ease',
  '&:hover': {
    borderColor: 'primary.light',
    bgcolor: alpha('#0f766e', 0.02),
  },
};

export function FinanceSection({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  const theme = useTheme();
  return (
    <Paper
      elevation={0}
      sx={{
        borderRadius: `${designTokens.radius.lg}px`,
        border: `1px solid ${theme.palette.divider}`,
        boxShadow: designTokens.elevation.card,
        overflow: 'hidden',
        bgcolor: designTokens.semantic.card,
      }}
    >
      <Box
        sx={{
          px: 2.5,
          pt: 2,
          pb: 1.5,
          display: 'flex',
          alignItems: { xs: 'flex-start', sm: 'center' },
          justifyContent: 'space-between',
          gap: 1.5,
          flexWrap: 'wrap',
          borderBottom: `1px solid ${chartTheme.surface.hairline}`,
          background: `linear-gradient(180deg, ${alpha(theme.palette.primary.main, 0.03)} 0%, transparent 100%)`,
        }}
      >
        <Box>
          <Typography sx={{ fontWeight: 700, letterSpacing: '-0.02em', color: chartTheme.ink.primary }}>
            {title}
          </Typography>
          {subtitle ? (
            <Typography variant="body2" sx={{ color: chartTheme.ink.secondary, mt: 0.25 }}>
              {subtitle}
            </Typography>
          ) : null}
        </Box>
        {action}
      </Box>
      <Box sx={{ p: 2.5 }}>{children}</Box>
    </Paper>
  );
}

export function FinanceUtilizationMeter({
  label,
  spent,
  allocated,
  currency = 'INR',
}: {
  label?: string;
  spent: number;
  allocated: number;
  currency?: string;
}) {
  const pct = allocated > 0 ? Math.min(150, (spent / allocated) * 100) : 0;
  const color =
    pct > 100
      ? designTokens.utilization.high
      : pct > 85
        ? designTokens.utilization.medium
        : designTokens.utilization.low;

  return (
    <Box>
      {label ? (
        <Stack direction="row" sx={{ mb: 0.75, justifyContent: 'space-between' }}>
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
          <Typography variant="caption" sx={{ fontWeight: 600 }}>
            {pct.toFixed(0)}%
          </Typography>
        </Stack>
      ) : null}
      <LinearProgress
        variant="determinate"
        value={Math.min(100, pct)}
        sx={{
          height: 8,
          borderRadius: 99,
          bgcolor: chartTheme.surface.track,
          '& .MuiLinearProgress-bar': { bgcolor: color, borderRadius: 99 },
        }}
      />
      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
        {financeMoney(spent, currency)} of {financeMoney(allocated, currency)}
      </Typography>
    </Box>
  );
}

export function FinanceRenewalChip({
  name,
  daysUntil,
  amountLabel,
}: {
  name: string;
  daysUntil: number;
  amountLabel: string;
}) {
  const urgent = daysUntil <= 3;
  return (
    <Chip
      label={`${name} · ${daysUntil}d · ${amountLabel}`}
      size="small"
      sx={{
        height: 'auto',
        py: 0.75,
        px: 0.5,
        borderRadius: `${designTokens.radius.md}px`,
        bgcolor: urgent ? designTokens.health.red.soft : designTokens.semantic.neutralSoft,
        color: urgent ? designTokens.health.red.main : chartTheme.ink.primary,
        fontWeight: 600,
        '& .MuiChip-label': { whiteSpace: 'normal', lineHeight: 1.3 },
      }}
    />
  );
}

export function FinanceHeroBanner({
  title,
  subtitle,
  chips,
}: {
  title: string;
  subtitle: string;
  chips?: ReactNode;
}) {
  const theme = useTheme();
  return (
    <Box
      sx={{
        borderRadius: `${designTokens.radius.lg}px`,
        px: { xs: 2, md: 2.5 },
        py: { xs: 2, md: 2.25 },
        background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.09)} 0%, ${alpha(
          '#0f766e',
          0.08,
        )} 55%, ${chartTheme.surface.muted} 100%)`,
        border: `1px solid ${chartTheme.surface.hairline}`,
      }}
    >
      <Typography
        sx={{
          fontWeight: 800,
          letterSpacing: '-0.03em',
          fontSize: { xs: '1.15rem', md: '1.35rem' },
          color: chartTheme.ink.primary,
        }}
      >
        {title}
      </Typography>
      <Typography variant="body2" sx={{ color: chartTheme.ink.secondary, mt: 0.5, maxWidth: 720 }}>
        {subtitle}
      </Typography>
      {chips ? (
        <Stack direction="row" spacing={1} sx={{ mt: 1.5, flexWrap: 'wrap', gap: 1 }}>
          {chips}
        </Stack>
      ) : null}
    </Box>
  );
}
