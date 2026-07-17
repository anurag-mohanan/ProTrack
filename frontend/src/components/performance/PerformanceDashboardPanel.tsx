import { Box, Grid, Stack, Typography } from '@mui/material';
import AssessmentOutlinedIcon from '@mui/icons-material/AssessmentOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import StarOutlineOutlinedIcon from '@mui/icons-material/StarOutlineOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { formatScore } from '../performanceReview/performanceReviewConstants';

type DashboardPayload = {
  employee: {
    id: string;
    name: string;
    email: string;
    role?: string | null;
    joining_date?: string | null;
    company_experience?: string | null;
    team_count?: number;
  };
  current_rating?: {
    period_label?: string;
    overall_score?: number | null;
    stage?: string;
    kind?: string;
  } | null;
  prior_rating?: { overall_score?: number | null; period_label?: string } | null;
  open_reviews: Array<{ id: string; period_label?: string; stage?: string; kind?: string; overall_score?: number | null }>;
  completed_reviews: Array<{
    id: string;
    period_label?: string;
    overall_score?: number | null;
    stage?: string;
  }>;
  skills: { rated_count: number; proficient_or_expert: number };
  manager_notes?: string | null;
  utilization?: {
    missing_working_days?: number | null;
    hours_logged_90d?: number | null;
    last_entry_date?: string | null;
  };
};

type Props = {
  onOpenReview?: (reviewId: string) => void;
};

export function PerformanceDashboardPanel({ onOpenReview }: Props) {
  const query = useQuery({
    queryKey: ['performance', 'dashboard'],
    queryFn: async () => (await apiClient.get<DashboardPayload>('/hr/performance/dashboard')).data,
  });

  if (query.isLoading) return <LoadingState message="Loading performance dashboard…" />;
  if (query.isError || !query.data) {
    return (
      <Typography color="error" variant="body2">
        Unable to load performance dashboard.
      </Typography>
    );
  }

  const data = query.data;
  const current = data.current_rating;
  const prior = data.prior_rating;
  const util = data.utilization;

  return (
    <Stack spacing={2.5}>
      <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: 2, border: 1, borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ fontWeight: 800 }}>
          {data.employee.name}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {[data.employee.role, data.employee.company_experience, data.employee.email]
            .filter(Boolean)
            .join(' · ')}
        </Typography>
        {data.employee.joining_date ? (
          <Typography variant="caption" color="text.secondary">
            Joined {data.employee.joining_date}
            {data.employee.team_count ? ` · ${data.employee.team_count} team(s)` : ''}
          </Typography>
        ) : null}
      </Box>

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Current rating"
            value={formatScore(current?.overall_score ?? null) || '—'}
            subtitle={current?.period_label || 'No acknowledged review yet'}
            icon={StarOutlineOutlinedIcon}
            compact
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Prior rating"
            value={formatScore(prior?.overall_score ?? null) || '—'}
            subtitle={prior?.period_label || '—'}
            icon={AssessmentOutlinedIcon}
            compact
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Open reviews"
            value={String(data.open_reviews.length)}
            subtitle={`${data.completed_reviews.length} completed`}
            icon={TaskAltOutlinedIcon}
            compact
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Skills rated"
            value={String(data.skills.rated_count)}
            subtitle={`${data.skills.proficient_or_expert} proficient/expert`}
            icon={GroupsOutlinedIcon}
            compact
          />
        </Grid>
      </Grid>

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: 2, border: 1, borderColor: 'divider', height: '100%' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
              Open & recent reviews
            </Typography>
            {data.open_reviews.length === 0 && data.completed_reviews.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No reviews yet.
              </Typography>
            ) : (
              <Stack spacing={0.75}>
                {[...data.open_reviews, ...data.completed_reviews.slice(0, 4)].map((row) => (
                  <Box
                    key={row.id}
                    onClick={() => onOpenReview?.(row.id)}
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 1,
                      cursor: onOpenReview ? 'pointer' : 'default',
                      '&:hover': onOpenReview ? { bgcolor: 'action.hover' } : undefined,
                      borderRadius: 1,
                      px: 0.5,
                      py: 0.25,
                    }}
                  >
                    <Typography variant="body2">{row.period_label || 'Review'}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.stage ? String(row.stage) : formatScore(row.overall_score ?? null) || '—'}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            )}
          </Box>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Stack spacing={1.5}>
            <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: 2, border: 1, borderColor: 'divider' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                Utilization & compliance
              </Typography>
              <Typography variant="body2">
                Hours (90d): {util?.hours_logged_90d != null ? util.hours_logged_90d.toFixed(1) : '—'}
              </Typography>
              <Typography variant="body2">
                Missing working days: {util?.missing_working_days ?? '—'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Last timesheet entry: {util?.last_entry_date || '—'}
              </Typography>
            </Box>
            <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: 2, border: 1, borderColor: 'divider' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                Manager notes
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                {data.manager_notes || 'No manager summary on the latest acknowledged review.'}
              </Typography>
            </Box>
          </Stack>
        </Grid>
      </Grid>
    </Stack>
  );
}
