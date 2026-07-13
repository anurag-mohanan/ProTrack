import { Box, Grid, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { aiQueryKeys, fetchExecutiveWall } from '../api/ai';
import { dashboardQueryKeys, fetchAttentionProjects } from '../api/dashboard';
import { fetchResourcePlanningGrid, resourcePlanningQueryKeys } from '../api/resourcePlanning';
import { DeliveryPlanningPanel } from '../components/analytics/DeliveryPlanningPanel';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { designTokens } from '../theme/designTokens';
import { formatNumber } from '../utils/format';

export default function PlanningBoardPage() {
  const wallQuery = useQuery({
    queryKey: aiQueryKeys.executiveWall,
    queryFn: fetchExecutiveWall,
    refetchInterval: 60_000,
  });

  const attentionQuery = useQuery({
    queryKey: dashboardQueryKeys.attentionProjects,
    queryFn: fetchAttentionProjects,
    refetchInterval: 60_000,
  });

  const gridQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.grid({ granularity: 'week' }),
    queryFn: () => fetchResourcePlanningGrid({ granularity: 'week' }),
    refetchInterval: 60_000,
  });

  if (wallQuery.isLoading) return <LoadingState message="Loading planning board…" />;
  if (wallQuery.error) {
    return <ErrorState error={wallQuery.error} title="Unable to load planning board" />;
  }

  const data = wallQuery.data!;
  const attention = attentionQuery.data ?? [];
  const upcoming = attention.filter((row) => row.attention_reason === 'due_soon');
  const delayed = attention.filter((row) => row.attention_reason === 'overdue');
  const designers = gridQuery.data?.designers ?? [];
  const overloaded = designers.filter(
    (row) => Number(row.capacity_hours || 0) > 0 && Number(row.allocated_hours || 0) >= Number(row.capacity_hours),
  ).length;

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Read-only operations monitor · refreshes every 60 seconds · no edit controls
      </Typography>

      <Grid container spacing={2}>
        {[
          { label: 'Active Projects', value: data.active_projects },
          { label: 'Utilization', value: `${data.utilization_percent}%` },
          { label: 'Late Milestones', value: data.late_milestones, warn: data.late_milestones > 0 },
          { label: 'Hours This Month', value: formatNumber(data.hours_logged_month, 0) },
          { label: 'Team Capacity', value: formatNumber(data.capacity_hours, 0) },
          {
            label: 'Health (G/Y/R)',
            value: `${data.health_summary.green ?? 0}/${data.health_summary.yellow ?? 0}/${data.health_summary.red ?? 0}`,
          },
        ].map((stat) => (
          <Grid key={stat.label} size={{ xs: 6, md: 4, lg: 2 }}>
            <Box
              sx={{
                p: 2,
                borderRadius: 2,
                border: 1,
                borderColor: 'divider',
                bgcolor: 'background.paper',
              }}
            >
              <Typography
                variant="h4"
                sx={{
                  fontWeight: 800,
                  color: stat.warn ? designTokens.semantic.warning : 'text.primary',
                }}
              >
                {stat.value}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {stat.label}
              </Typography>
            </Box>
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 7 }}>
          <DeliveryPlanningPanel
            upcoming={upcoming}
            delayed={delayed}
            loading={attentionQuery.isLoading}
            hideResourcePlanningLink
          />
        </Grid>
        <Grid size={{ xs: 12, lg: 5 }}>
          <Stack spacing={2}>
            <Box sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
                Current Deliveries
              </Typography>
              <Stack spacing={0.75}>
                {data.current_deliveries.length ? (
                  data.current_deliveries.map((row, index) => (
                    <Typography key={index} variant="body2">
                      {String(row.tool_number)} — {String(row.customer_name ?? '')} (
                      {String(row.due_date ?? 'TBD')})
                    </Typography>
                  ))
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No urgent deliveries
                  </Typography>
                )}
              </Stack>
            </Box>

            <Box sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
                Capacity snapshot
              </Typography>
              {gridQuery.isLoading ? (
                <Typography variant="body2" color="text.secondary">
                  Loading capacity…
                </Typography>
              ) : gridQuery.error ? (
                <Typography variant="body2" color="text.secondary">
                  Capacity grid unavailable
                </Typography>
              ) : (
                <Stack spacing={0.75}>
                  <Typography variant="body2">
                    Designers on board: <strong>{designers.length}</strong>
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ color: overloaded > 0 ? designTokens.semantic.warning : 'text.primary' }}
                  >
                    At or over capacity: <strong>{overloaded}</strong>
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Assignments cannot be changed from this monitor account.
                  </Typography>
                </Stack>
              )}
            </Box>
          </Stack>
        </Grid>
      </Grid>
    </Stack>
  );
}
