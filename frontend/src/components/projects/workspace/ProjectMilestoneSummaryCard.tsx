import { Box, Grid } from '@mui/material';
import { KpiMetricCard } from '../../ui/design-system';
import type { ProjectMilestoneSummary } from '../../../types/Milestone';
import { formatNumber } from '../../../utils/format';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import AccessTimeRoundedIcon from '@mui/icons-material/AccessTimeRounded';
import FlagRoundedIcon from '@mui/icons-material/FlagRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';

interface ProjectMilestoneSummaryCardProps {
  summary: ProjectMilestoneSummary;
}

export function ProjectMilestoneSummaryCard({ summary }: ProjectMilestoneSummaryCardProps) {
  const variance = summary.planned_variance_hours;
  const varianceLabel =
    variance === 0 ? 'On quote' : variance > 0 ? `+${formatNumber(variance)} hrs` : `${formatNumber(variance)} hrs`;

  return (
    <Box sx={{ mb: 2 }}>
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <KpiMetricCard
            compact
            title="Total Planned"
            value={`${formatNumber(summary.total_planned_hours)}h`}
            icon={ScheduleRoundedIcon}
            accent="primary"
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <KpiMetricCard
            compact
            title="Total Actual"
            value={`${formatNumber(summary.total_actual_hours)}h`}
            icon={AccessTimeRoundedIcon}
            accent="info"
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <KpiMetricCard
            compact
            title="Milestones"
            value={String(summary.milestone_count)}
            icon={FlagRoundedIcon}
            accent="info"
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <KpiMetricCard
            compact
            title="Completed"
            value={String(summary.completed_count)}
            icon={CheckCircleRoundedIcon}
            accent="success"
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <KpiMetricCard
            compact
            title="Remaining"
            value={`${formatNumber(summary.remaining_hours)}h`}
            icon={AccessTimeRoundedIcon}
            accent="warning"
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <KpiMetricCard
            compact
            title="Quoted / Planned"
            value={`${formatNumber(summary.quoted_hours)} / ${formatNumber(summary.current_planned_hours)}`}
            subtitle={`Variance ${varianceLabel}`}
            icon={TrendingUpRoundedIcon}
            accent={variance > 0 ? 'warning' : 'success'}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
