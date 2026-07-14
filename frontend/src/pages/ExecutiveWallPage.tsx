import { Box, Grid, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { aiQueryKeys, fetchExecutiveWall } from '../api/ai';
import { PageContainer } from '../components/common/PageContainer';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { designTokens } from '../theme/designTokens';
import { formatNumber } from '../utils/format';

export function ExecutiveWallPage() {
  const query = useQuery({
    queryKey: aiQueryKeys.executiveWall(),
    queryFn: () => fetchExecutiveWall(),
    refetchInterval: 60_000,
  });

  if (query.isLoading) return <LoadingState message="Loading executive wall..." />;
  if (query.error) return <ErrorState error={query.error} title="Unable to load executive wall" />;

  const data = query.data!;

  return (
    <PageContainer>
      <Box
        sx={{
          minHeight: 'calc(100vh - 120px)',
          bgcolor: 'background.default',
          p: { xs: 2, md: 3 },
        }}
      >
        <Typography variant="h4" sx={{ fontWeight: 800, mb: 3 }}>
          Engineering Operations — Live
        </Typography>

        <Grid container spacing={2} sx={{ mb: 3 }}>
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
          <Grid size={{ xs: 12, md: 6 }}>
            <Box sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider' }}>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
                Current Deliveries
              </Typography>
              <Stack spacing={0.75}>
                {data.current_deliveries.length ? (
                  data.current_deliveries.map((row, i) => (
                    <Typography key={i} variant="body2">
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
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <Box sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider' }}>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
                Customer Distribution
              </Typography>
              <Stack spacing={0.75}>
                {data.customer_distribution.map((row, i) => (
                  <Typography key={i} variant="body2">
                    {String(row.customer_name)} — {String(row.share_percent)}% (
                    {formatNumber(Number(row.hours), 0)}h)
                  </Typography>
                ))}
              </Stack>
            </Box>
          </Grid>
        </Grid>
      </Box>
    </PageContainer>
  );
}
