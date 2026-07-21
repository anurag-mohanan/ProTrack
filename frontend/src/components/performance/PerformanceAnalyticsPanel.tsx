import { Box, Grid, Stack, Typography } from '@mui/material';
import AssessmentOutlinedIcon from '@mui/icons-material/AssessmentOutlined';
import HourglassEmptyOutlinedIcon from '@mui/icons-material/HourglassEmptyOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';

type ReviewRow = {
  id: string;
  status: string;
  stage?: string;
  overall_score?: number | string | null;
  due_date?: string | null;
  cycle_kind?: string | null;
  employee_name: string;
};

export function PerformanceAnalyticsPanel() {
  const myQuery = useQuery({
    queryKey: ['performance-reviews', 'me'],
    queryFn: async () => (await apiClient.get<ReviewRow[]>('/hr/reviews/me')).data,
  });
  const teamQuery = useQuery({
    queryKey: ['performance-reviews', 'team', 'analytics'],
    queryFn: async () => (await apiClient.get<ReviewRow[]>('/hr/reviews/team')).data,
  });

  const rows = useMemo(() => {
    const team = teamQuery.data ?? [];
    if (team.length) return team;
    return myQuery.data ?? [];
  }, [myQuery.data, teamQuery.data]);

  const stats = useMemo(() => {
    const open = rows.filter((r) => r.stage !== 'acknowledged' && r.status !== 'acknowledged');
    const done = rows.filter((r) => r.stage === 'acknowledged' || r.status === 'acknowledged');
    const overdue = open.filter((r) => r.due_date && r.due_date < new Date().toISOString().slice(0, 10));
    const rated = rows.filter((r) => r.overall_score != null && r.overall_score !== '');
    const buckets = { low: 0, mid: 0, high: 0 };
    for (const row of rated) {
      const score = Number(row.overall_score);
      if (Number.isNaN(score)) continue;
      if (score < 3) buckets.low += 1;
      else if (score < 4) buckets.mid += 1;
      else buckets.high += 1;
    }
    const quarterly = rows.filter((r) => r.cycle_kind === 'quarterly').length;
    const annual = rows.filter((r) => (r.cycle_kind || 'annual') === 'annual').length;
    return {
      open: open.length,
      done: done.length,
      overdue: overdue.length,
      buckets,
      quarterly,
      annual,
      calibration: open.filter((r) => r.stage === 'calibration').length,
    };
  }, [rows]);

  if (myQuery.isLoading || teamQuery.isLoading) {
    return <LoadingState message="Loading analytics…" />;
  }

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Snapshot of review progress and rating distribution for your scope (team reviews when available).
      </Typography>
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 6, md: 3 }}>
          <KpiMetricCard
            title="Open"
            value={String(stats.open)}
            subtitle={`${stats.overdue} overdue`}
            icon={HourglassEmptyOutlinedIcon}
            compact
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <KpiMetricCard title="Acknowledged" value={String(stats.done)} icon={TaskAltOutlinedIcon} compact />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <KpiMetricCard
            title="In calibration"
            value={String(stats.calibration)}
            icon={TuneOutlinedIcon}
            compact
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <KpiMetricCard
            title="Annual reviews"
            value={String(stats.annual)}
            subtitle="In current scope"
            icon={AssessmentOutlinedIcon}
            compact
          />
        </Grid>
      </Grid>
      <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: 2, border: 1, borderColor: 'divider' }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
          Rating distribution
        </Typography>
        <Typography variant="body2">Below 3.0: {stats.buckets.low}</Typography>
        <Typography variant="body2">3.0 – 3.9: {stats.buckets.mid}</Typography>
        <Typography variant="body2">4.0+: {stats.buckets.high}</Typography>
      </Box>
    </Stack>
  );
}
