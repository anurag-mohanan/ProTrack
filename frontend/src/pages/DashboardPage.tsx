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
import type { WorkflowDashboard } from '../types';
import { getWorkflowDashboard } from '../services/notificationService';
import { formatDate, formatNumber } from '../utils/format';

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

  const workflowQuery = useQuery<WorkflowDashboard>({
    queryKey: ['dashboard', 'workflow'],
    queryFn: getWorkflowDashboard,
  });

  if (isLoading || workflowQuery.isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;
  if (workflowQuery.error) return <ErrorState error={workflowQuery.error} />;
  if (!data || !workflowQuery.data) return <EmptyState title="No dashboard data available" />;

  const workflow = workflowQuery.data;

  const cards = [
    { title: 'Total Projects', value: formatNumber(data.total_projects, 0) },
    { title: 'Not Started', value: formatNumber(data.not_started_projects, 0) },
    { title: 'In Progress', value: formatNumber(data.in_progress_projects, 0) },
    { title: 'Completed', value: formatNumber(data.completed_projects, 0) },
    { title: 'Green Projects', value: formatNumber(data.green_projects, 0) },
    { title: 'Yellow Projects', value: formatNumber(data.yellow_projects, 0) },
    { title: 'Red Projects', value: formatNumber(data.red_projects, 0) },
    { title: 'Quoted Hours', value: formatNumber(data.total_quoted_hours) },
    { title: 'Actual Hours', value: formatNumber(data.total_actual_hours) },
    { title: 'Remaining Hours', value: formatNumber(data.total_remaining_hours) },
    {
      title: 'Pending Approvals',
      value: formatNumber(workflow.pending_timesheet_approvals, 0),
    },
    {
      title: 'Unread Notifications',
      value: formatNumber(workflow.unread_notifications, 0),
    },
    {
      title: 'Projects Due This Week',
      value: formatNumber(workflow.projects_due_this_week, 0),
    },
    {
      title: 'Overdue Milestones',
      value: formatNumber(workflow.overdue_milestones, 0),
    },
    {
      title: 'Variance',
      value: formatNumber(data.hours_variance),
      subtitle:
        data.hours_variance > 0
          ? 'Over quoted'
          : data.hours_variance < 0
            ? 'Under quoted'
            : 'On target',
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

      <Typography variant="h6" sx={{ mt: 4, mb: 2, fontWeight: 700 }}>
        My Tasks
      </Typography>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        {workflow.my_tasks.length === 0 ? (
          <Grid size={{ xs: 12 }}>
            <EmptyState title="No open tasks" />
          </Grid>
        ) : (
          workflow.my_tasks.map((task) => (
            <Grid size={{ xs: 12, md: 6 }} key={task.id}>
              <StatCard
                title={task.title}
                value={task.project_code ?? '—'}
                subtitle={
                  task.due_date ? `Due ${formatDate(task.due_date)}` : 'No due date'
                }
              />
            </Grid>
          ))
        )}
      </Grid>

      <Typography variant="h6" sx={{ mb: 2, fontWeight: 700 }}>
        Recent Activity
      </Typography>
      <Grid container spacing={2}>
        {workflow.recent_activity.length === 0 ? (
          <Grid size={{ xs: 12 }}>
            <EmptyState title="No recent activity" />
          </Grid>
        ) : (
          workflow.recent_activity.map((activity) => (
            <Grid size={{ xs: 12, md: 6 }} key={activity.id}>
              <StatCard
                title={activity.action.replaceAll('_', ' ')}
                value={activity.user_name ?? 'System'}
                subtitle={activity.new_value ?? activity.old_value ?? '—'}
              />
            </Grid>
          ))
        )}
      </Grid>
    </Box>
  );
}
