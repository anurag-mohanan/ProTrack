import { Box, Typography } from '@mui/material';
import type { ProjectHealth } from '../../../types/common';
import { designTokens } from '../../../theme/designTokens';

const HEALTH_KEYS: Record<ProjectHealth | 'grey', keyof typeof designTokens.health> = {
  green: 'green',
  yellow: 'yellow',
  red: 'red',
  grey: 'grey',
};

interface HealthIndicatorProps {
  health: ProjectHealth | 'grey';
  label?: string;
  size?: 'sm' | 'md';
  showLabel?: boolean;
}

export function HealthIndicator({
  health,
  label,
  size = 'md',
  showLabel = true,
}: HealthIndicatorProps) {
  const token = designTokens.health[HEALTH_KEYS[health]];
  const dotSize = size === 'sm' ? 8 : 10;

  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
      <Box
        sx={{
          width: dotSize,
          height: dotSize,
          borderRadius: '50%',
          bgcolor: token.main,
          boxShadow: `0 0 0 3px ${token.soft}`,
          flexShrink: 0,
        }}
      />
      {showLabel ? (
        <Typography
          variant="caption"
          sx={{ fontWeight: 600, color: token.main, textTransform: 'capitalize' }}
        >
          {label ?? health}
        </Typography>
      ) : null}
    </Box>
  );
}
