import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchDashboardSummary } from '../api/dashboard';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { formatNumber } from '../utils/format';

interface StatCardProps {
  title: string;
  value: string;
  subtitle?: string;
}

function StatCard({ title, value, subtitle }: StatCardProps) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {title}
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          {value}
        </Typography>
        {subtitle ? (
          <Typography variant="caption" color="text.secondary">
            {subtitle}
          </Typography>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: fetchDashboardSummary,
  });

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;
  if (!data) return <EmptyState title="No dashboard data available" />;

  const cards = [
    { title: 'Total Projects', value: formatNumber(data.total_projects, 0) },
    { title: 'Active Projects', value: formatNumber(data.in_progress_projects, 0) },
    { title: 'Completed Projects', value: formatNumber(data.completed_projects, 0) },
    { title: 'Total Quoted Hours', value: formatNumber(data.total_quoted_hours) },
    { title: 'Total Actual Hours', value: formatNumber(data.total_actual_hours) },
    {
      title: 'Hours Variance',
      value: formatNumber(data.hours_variance),
      subtitle: data.hours_variance > 0 ? 'Over quoted' : data.hours_variance < 0 ? 'Under quoted' : 'On target',
    },
  ];

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }} gutterBottom>
        Dashboard
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Portfolio overview and hour utilization
      </Typography>

      <Grid container spacing={2}>
        {cards.map((card) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={card.title}>
            <StatCard {...card} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
