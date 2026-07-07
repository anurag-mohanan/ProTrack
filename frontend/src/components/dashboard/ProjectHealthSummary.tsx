import { Box, Grid, Typography } from '@mui/material';
import type { DashboardSummary } from '../../types';
import { designTokens } from '../../theme/designTokens';
import { formatNumber } from '../../utils/format';
import { HealthIndicator } from '../ui/design-system/HealthIndicator';

interface ProjectHealthSummaryProps {
  summary: DashboardSummary;
}

const HEALTH_ITEMS = [
  { key: 'green' as const, label: 'On Track' },
  { key: 'yellow' as const, label: 'At Risk' },
  { key: 'red' as const, label: 'Critical' },
  { key: 'grey' as const, label: 'Unrated' },
];

export function ProjectHealthSummary({ summary }: ProjectHealthSummaryProps) {
  const counts = {
    green: summary.green_projects ?? 0,
    yellow: summary.yellow_projects ?? 0,
    red: summary.red_projects ?? 0,
    grey: Math.max(
      0,
      (summary.active_projects ?? 0) -
        (summary.green_projects ?? 0) -
        (summary.yellow_projects ?? 0) -
        (summary.red_projects ?? 0),
    ),
  };

  return (
    <Grid container spacing={2}>
      {HEALTH_ITEMS.map((item) => {
        const token = designTokens.health[item.key];
        return (
          <Grid key={item.key} size={{ xs: 6, sm: 3 }}>
            <Box
              sx={{
                p: 2,
                borderRadius: `${designTokens.radius.lg}px`,
                bgcolor: token.soft,
                border: '1px solid',
                borderColor: 'divider',
                transition: `transform ${designTokens.motion.fast}`,
                '&:hover': { transform: 'translateY(-2px)' },
              }}
            >
              <HealthIndicator health={item.key === 'grey' ? 'grey' : item.key} label={item.label} />
              <Typography sx={{ fontSize: 28, fontWeight: 800, mt: 1, letterSpacing: '-0.02em' }}>
                {formatNumber(counts[item.key], 0)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                projects
              </Typography>
            </Box>
          </Grid>
        );
      })}
    </Grid>
  );
}
