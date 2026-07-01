import { Box, LinearProgress, Typography } from '@mui/material';
import { Grid } from '@mui/material';
import { StatisticCard } from '../ui/design-system';
import type { ProjectKpis } from '../../types/CommandCenter';
import { formatNumber } from '../../utils/format';

export function KpiPanel({ kpis }: { kpis: ProjectKpis }) {
  const budget = Math.min(Number(kpis.budget_consumption_percent), 100);

  return (
    <Box>
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <StatisticCard title="Completion" value={`${formatNumber(kpis.completion_percent)}%`} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <StatisticCard title="Quoted Hours" value={formatNumber(kpis.quoted_hours)} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <StatisticCard title="Actual Hours" value={formatNumber(kpis.actual_hours)} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <StatisticCard title="Remaining" value={formatNumber(kpis.remaining_hours)} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <StatisticCard
            title="Variance"
            value={formatNumber(kpis.variance)}
            subtitle={`${formatNumber(kpis.variance_percent)}%`}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <StatisticCard title="Days Left" value={String(kpis.days_remaining)} />
        </Grid>
      </Grid>
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Budget consumption
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {formatNumber(kpis.budget_consumption_percent)}%
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={budget}
          sx={{ height: 10, borderRadius: 1 }}
          color={budget > 100 ? 'error' : budget > 85 ? 'warning' : 'primary'}
        />
      </Box>
    </Box>
  );
}
