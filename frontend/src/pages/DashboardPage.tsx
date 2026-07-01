import {
  Box,
  Grid,
  Typography,
} from '@mui/material';
import AssignmentIcon from '@mui/icons-material/Assignment';
import ArchiveIcon from '@mui/icons-material/Archive';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import PendingActionsIcon from '@mui/icons-material/PendingActions';
import ScheduleIcon from '@mui/icons-material/Schedule';
import SpeedIcon from '@mui/icons-material/Speed';
import MonetizationOnIcon from '@mui/icons-material/MonetizationOn';
import MoneyOffIcon from '@mui/icons-material/MoneyOff';
import DoNotDisturbIcon from '@mui/icons-material/DoNotDisturb';
import PercentIcon from '@mui/icons-material/Percent';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { fetchDashboardSummary } from '../api/dashboard';
import { PageHeader } from '../components/common/PageHeader';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { DashboardCard } from '../components/ui/cards';
import type { WorkflowDashboard } from '../types';
import { getWorkflowDashboard } from '../services/notificationService';
import { formatDate, formatNumber } from '../utils/format';

type Accent = 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info' | 'accent';

interface DashboardMetric {
  title: string;
  value: string;
  subtitle?: string;
  accent: Accent;
  icon: typeof FolderOpenIcon;
  onClick?: () => void;
}

export function DashboardPage() {
  const navigate = useNavigate();
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

  const cards: DashboardMetric[] = [
    {
      title: 'Active Projects',
      value: formatNumber(data.active_projects, 0),
      accent: 'primary',
      icon: FolderOpenIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Completed Projects',
      value: formatNumber(data.completed_projects, 0),
      accent: 'success',
      icon: CheckCircleIcon,
      onClick: () => navigate('/projects?lifecycle=completed'),
    },
    {
      title: 'Archived Projects',
      value: formatNumber(data.archived_projects, 0),
      accent: 'secondary',
      icon: ArchiveIcon,
      onClick: () => navigate('/projects/archived'),
    },
    { title: 'Total Projects', value: formatNumber(data.total_projects, 0), accent: 'primary', icon: FolderOpenIcon },
    { title: 'Not Started', value: formatNumber(data.not_started_projects, 0), accent: 'secondary', icon: HourglassEmptyIcon },
    { title: 'In Progress', value: formatNumber(data.in_progress_projects, 0), accent: 'info', icon: SpeedIcon },
    { title: 'Green Projects', value: formatNumber(data.green_projects, 0), accent: 'success', icon: CheckCircleIcon },
    { title: 'Yellow Projects', value: formatNumber(data.yellow_projects, 0), accent: 'warning', icon: WarningAmberIcon },
    { title: 'Red Projects', value: formatNumber(data.red_projects, 0), accent: 'error', icon: WarningAmberIcon },
    { title: 'Quoted Hours', value: formatNumber(data.total_quoted_hours), accent: 'primary', icon: ScheduleIcon },
    { title: 'Actual Hours', value: formatNumber(data.total_actual_hours), accent: 'info', icon: AssignmentIcon },
    {
      title: 'Billable Hours',
      value: formatNumber(data.billable_hours),
      accent: 'success',
      icon: MonetizationOnIcon,
    },
    {
      title: 'Non-Billable Hours',
      value: formatNumber(data.non_billable_hours),
      accent: 'warning',
      icon: MoneyOffIcon,
    },
    {
      title: 'NP Hours',
      value: formatNumber(data.np_hours),
      accent: 'secondary',
      icon: DoNotDisturbIcon,
    },
    {
      title: 'Productive %',
      value: `${formatNumber(data.productive_percent)}%`,
      accent: 'info',
      icon: PercentIcon,
    },
    { title: 'Remaining Hours', value: formatNumber(data.total_remaining_hours), accent: 'secondary', icon: PendingActionsIcon },
    {
      title: 'Pending Approvals',
      value: formatNumber(workflow.pending_timesheet_approvals, 0),
      accent: 'warning',
      icon: PendingActionsIcon,
    },
    {
      title: 'Unread Notifications',
      value: formatNumber(workflow.unread_notifications, 0),
      accent: 'accent',
      icon: NotificationsActiveIcon,
    },
    {
      title: 'Projects Due This Week',
      value: formatNumber(workflow.projects_due_this_week, 0),
      accent: 'info',
      icon: ScheduleIcon,
    },
    {
      title: 'Overdue Milestones',
      value: formatNumber(workflow.overdue_milestones, 0),
      accent: 'error',
      icon: WarningAmberIcon,
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
      accent: data.hours_variance > 0 ? 'warning' : data.hours_variance < 0 ? 'success' : 'primary',
      icon: data.hours_variance > 0 ? TrendingUpIcon : TrendingDownIcon,
    },
  ];

  return (
    <Box>
      <PageHeader
        title="Dashboard"
        subtitle="Portfolio overview, delivery health, and hour utilization"
      />

      <Grid container spacing={2.5}>
        {cards.map((card) => (
          <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={card.title}>
            <DashboardCard
              title={card.title}
              value={card.value}
              subtitle={card.subtitle}
              accent={card.accent}
              icon={card.icon}
              onClick={card.onClick}
            />
          </Grid>
        ))}
      </Grid>

      <Typography variant="sectionTitle" sx={{ mt: 5, mb: 2 }}>
        My Tasks
      </Typography>
      <Grid container spacing={2.5} sx={{ mb: 4 }}>
        {workflow.my_tasks.length === 0 ? (
          <Grid size={{ xs: 12 }}>
            <EmptyState title="No open tasks" />
          </Grid>
        ) : (
          workflow.my_tasks.map((task) => (
            <Grid size={{ xs: 12, md: 6 }} key={task.id}>
              <DashboardCard
                title={task.title}
                value={task.project_code ?? '—'}
                subtitle={task.due_date ? `Due ${formatDate(task.due_date)}` : 'No due date'}
                accent="primary"
                icon={AssignmentIcon}
              />
            </Grid>
          ))
        )}
      </Grid>

      <Typography variant="sectionTitle" sx={{ mb: 2 }}>
        Recent Activity
      </Typography>
      <Grid container spacing={2.5}>
        {workflow.recent_activity.length === 0 ? (
          <Grid size={{ xs: 12 }}>
            <EmptyState title="No recent activity" />
          </Grid>
        ) : (
          workflow.recent_activity.map((activity) => (
            <Grid size={{ xs: 12, md: 6 }} key={activity.id}>
              <DashboardCard
                title={activity.action.replaceAll('_', ' ')}
                value={activity.user_name ?? 'System'}
                subtitle={activity.new_value ?? activity.old_value ?? '—'}
                accent="secondary"
                icon={SpeedIcon}
              />
            </Grid>
          ))
        )}
      </Grid>
    </Box>
  );
}
