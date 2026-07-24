import { Box, Grid, LinearProgress, Stack, Typography } from '@mui/material';
import AssessmentOutlinedIcon from '@mui/icons-material/AssessmentOutlined';
import HourglassEmptyOutlinedIcon from '@mui/icons-material/HourglassEmptyOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { designTokens } from '../../theme/designTokens';

type ReviewRow = {
  id: string;
  status: string;
  stage?: string;
  overall_score?: number | string | null;
  due_date?: string | null;
  cycle_kind?: string | null;
  employee_name: string;
};

function isAcknowledged(row: ReviewRow): boolean {
  return row.stage === 'acknowledged' || row.status === 'acknowledged';
}

function RatingBar({ label, count, total }: { label: string; count: number; total: number }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <Box sx={{ mb: 1.25 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="body2">{label}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
          {count} ({pct}%)
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          height: 8,
          borderRadius: 999,
          bgcolor: designTokens.semantic.neutralSoft,
          '& .MuiLinearProgress-bar': { borderRadius: 999 },
        }}
      />
    </Box>
  );
}

export function PerformanceAnalyticsPanel() {
  const myQuery = useQuery({
    queryKey: ['performance-reviews', 'me'],
    queryFn: async () => (await apiClient.get<ReviewRow[]>('/hr/reviews/me')).data,
  });
  const teamQuery = useQuery({
    queryKey: ['performance-reviews', 'team', 'analytics'],
    queryFn: async () => (await apiClient.get<ReviewRow[]>('/hr/reviews/team')).data,
    retry: false,
  });

  const rows = useMemo(() => {
    if (teamQuery.isSuccess && (teamQuery.data?.length ?? 0) > 0) {
      return teamQuery.data ?? [];
    }
    return myQuery.data ?? [];
  }, [myQuery.data, teamQuery.data, teamQuery.isSuccess]);

  const scopeLabel = useMemo(() => {
    if (teamQuery.isSuccess && (teamQuery.data?.length ?? 0) > 0) {
      return 'team reviews in your managed scope';
    }
    return 'your reviews';
  }, [teamQuery.data, teamQuery.isSuccess]);

  const stats = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    const open = rows.filter((r) => !isAcknowledged(r));
    const done = rows.filter((r) => isAcknowledged(r));
    const overdue = open.filter((r) => Boolean(r.due_date && r.due_date < today));
    const rated = rows.filter((r) => r.overall_score != null && r.overall_score !== '');
    const buckets = { low: 0, mid: 0, high: 0 };
    for (const row of rated) {
      const score = Number(row.overall_score);
      if (Number.isNaN(score)) continue;
      if (score < 3) buckets.low += 1;
      else if (score < 4) buckets.mid += 1;
      else buckets.high += 1;
    }
    const annual = rows.filter((r) => (r.cycle_kind || 'annual') === 'annual').length;
    return {
      open: open.length,
      done: done.length,
      overdue: overdue.length,
      buckets,
      ratedCount: rated.length,
      annual,
      calibration: open.filter((r) => r.stage === 'calibration').length,
    };
  }, [rows]);

  if (myQuery.isLoading || teamQuery.isLoading) {
    return <LoadingState message="Loading analytics…" />;
  }

  if (myQuery.isError && teamQuery.isError) {
    return (
      <Typography color="error" variant="body2">
        Unable to load performance analytics.
      </Typography>
    );
  }

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Snapshot of review progress and rating distribution for {scopeLabel}.
      </Typography>
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 6, md: 3 }}>
          <KpiMetricCard
            title="Open"
            value={String(stats.open)}
            subtitle={`${stats.overdue} overdue`}
            icon={HourglassEmptyOutlinedIcon}
            accent={stats.overdue ? 'warning' : undefined}
            compact
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <KpiMetricCard
            title="Acknowledged"
            value={String(stats.done)}
            icon={TaskAltOutlinedIcon}
            accent="success"
            compact
          />
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
      <Box
        sx={{
          bgcolor: designTokens.semantic.card,
          borderRadius: `${designTokens.radius.lg}px`,
          p: 2,
          border: 1,
          borderColor: 'divider',
          boxShadow: designTokens.elevation.card,
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.25 }}>
          Rating distribution
        </Typography>
        {stats.ratedCount === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No scored reviews in this scope yet.
          </Typography>
        ) : (
          <>
            <RatingBar label="Below 3.0" count={stats.buckets.low} total={stats.ratedCount} />
            <RatingBar label="3.0 – 3.9" count={stats.buckets.mid} total={stats.ratedCount} />
            <RatingBar label="4.0+" count={stats.buckets.high} total={stats.ratedCount} />
          </>
        )}
      </Box>
    </Stack>
  );
}
