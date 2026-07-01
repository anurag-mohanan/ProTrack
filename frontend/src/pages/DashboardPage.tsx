import { Box, Grid, Typography } from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import ScheduleIcon from '@mui/icons-material/Schedule';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import Inventory2OutlinedIcon from '@mui/icons-material/Inventory2Outlined';
import MonetizationOnIcon from '@mui/icons-material/MonetizationOn';
import TimelapseIcon from '@mui/icons-material/Timelapse';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { dashboardQueryKeys, fetchDashboardSummary } from '../api/dashboard';
import { ActionKpiCard, DashboardSection } from '../components/dashboard/DashboardCards';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { MyTasksWidget } from '../components/dashboard/MyTasksWidget';
import { ProjectsAttentionTable } from '../components/dashboard/ProjectsAttentionTable';
import { RecentActivityWidget } from '../components/dashboard/RecentActivityWidget';
import { WidgetErrorBoundary } from '../components/dashboard/WidgetErrorBoundary';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { formatNumber } from '../utils/format';

export function DashboardPage() {
  const navigate = useNavigate();

  const dashboardQuery = useQuery({
    queryKey: dashboardQueryKeys.summary,
    queryFn: fetchDashboardSummary,
    retry: 1,
  });

  if (dashboardQuery.isLoading) {
    return <LoadingState message="Loading your dashboard…" />;
  }

  const summary = dashboardQuery.data;
  const unavailable = dashboardQuery.isError || !summary;

  const completedThisMonth = summary?.completed_this_month ?? 0;
  const dueThisWeek = summary?.projects_due_this_week ?? 0;
  const overdueProjects = summary?.overdue_projects ?? 0;
  const quotedHoursActive = summary?.total_quoted_hours_active ?? summary?.total_quoted_hours ?? 0;
  const actualHoursProductive =
    summary?.total_actual_hours_productive ?? summary?.billable_hours ?? 0;
  const attentionProjects = summary?.attention_projects ?? [];
  const myTasks = summary?.my_tasks ?? { pending_approvals: [], upcoming_milestones: [] };
  const recentActivity = summary?.recent_activity ?? [];

  const kpiCards = [
    {
      title: 'Active Projects',
      value: unavailable ? '—' : formatNumber(summary.in_progress_projects, 0),
      subtitle: unavailable ? 'No data available' : 'Status: In Progress',
      icon: FolderOpenIcon,
      statusColor: summary && summary.in_progress_projects > 0 ? ('primary' as const) : undefined,
      onClick: () => navigate('/projects?status=in_progress'),
    },
    {
      title: 'Projects On Hold',
      value: unavailable ? '—' : formatNumber(summary.on_hold_projects, 0),
      subtitle: unavailable ? 'No data available' : 'Waiting for customer',
      icon: PauseCircleIcon,
      onClick: () => navigate('/projects?status=waiting_for_customer'),
    },
    {
      title: 'Completed Projects',
      value: unavailable ? '—' : formatNumber(completedThisMonth, 0),
      subtitle: unavailable ? 'No data available' : 'Completed this month',
      icon: TaskAltIcon,
      statusColor: !unavailable && completedThisMonth > 0 ? ('success' as const) : undefined,
      onClick: () => navigate('/projects?lifecycle=completed&completed=month'),
    },
    {
      title: 'Projects Due This Week',
      value: unavailable ? '—' : formatNumber(dueThisWeek, 0),
      subtitle: unavailable ? 'No data available' : 'Due Mon–Sun this week',
      icon: ScheduleIcon,
      statusColor: !unavailable && dueThisWeek > 0 ? ('warning' as const) : undefined,
      onClick: () => navigate('/projects?due=week'),
    },
    {
      title: 'Overdue Projects',
      value: unavailable ? '—' : formatNumber(overdueProjects, 0),
      subtitle: unavailable ? 'No data available' : 'Past due date',
      icon: WarningAmberIcon,
      statusColor: !unavailable && overdueProjects > 0 ? ('error' as const) : undefined,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Archived Projects',
      value: unavailable ? '—' : formatNumber(summary.archived_projects, 0),
      subtitle: unavailable ? 'No data available' : 'Archived portfolio',
      icon: Inventory2OutlinedIcon,
      onClick: () => navigate('/projects?lifecycle=archived'),
    },
    {
      title: 'Total Quoted Hours',
      value: unavailable ? '—' : formatNumber(quotedHoursActive),
      subtitle: unavailable ? 'No data available' : 'Active projects',
      icon: MonetizationOnIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Total Actual Hours',
      value: unavailable ? '—' : formatNumber(actualHoursProductive),
      subtitle: unavailable ? 'No data available' : 'Approved productive hours',
      icon: TimelapseIcon,
      onClick: () => navigate('/reports?tab=productive-hours'),
    },
  ];

  return (
    <Box sx={{ maxWidth: 1280, mx: 'auto' }}>
      <PageHeader title="Dashboard" subtitle="Engineering overview" />

      <DashboardHeader
        onNewProject={() => navigate('/projects')}
        onTimesheet={() => navigate('/timesheets')}
        onCustomer={() => navigate('/admin/customers')}
        onUser={() => navigate('/admin/users')}
      />

      <WidgetErrorBoundary title="KPI cards">
        <Grid container spacing={2} sx={{ mb: 3.5 }}>
          {kpiCards.map((card) => (
            <Grid size={{ xs: 12, sm: 6, lg: 3 }} key={card.title}>
              <ActionKpiCard {...card} />
            </Grid>
          ))}
        </Grid>
      </WidgetErrorBoundary>

      <WidgetErrorBoundary title="projects requiring attention">
        <DashboardSection
          title="Projects Requiring Attention"
          subtitle="Overdue, due within 5 days, on hold, or blocked"
        >
          {unavailable || !attentionProjects.length ? (
            <Typography variant="body2" color="text.secondary">
              No data available
            </Typography>
          ) : (
            <ProjectsAttentionTable rows={attentionProjects} />
          )}
        </DashboardSection>
      </WidgetErrorBoundary>

      <WidgetErrorBoundary title="my tasks">
        <DashboardSection title="My Tasks" subtitle="Your upcoming milestones and pending approvals">
          {unavailable ? (
            <Typography variant="body2" color="text.secondary">
              No data available
            </Typography>
          ) : (
            <MyTasksWidget tasks={myTasks} />
          )}
        </DashboardSection>
      </WidgetErrorBoundary>

      <WidgetErrorBoundary title="recent activity">
        <DashboardSection title="Recent Activity" subtitle="Latest engineering updates">
          {unavailable || !recentActivity.length ? (
            <Typography variant="body2" color="text.secondary">
              No data available
            </Typography>
          ) : (
            <RecentActivityWidget activities={recentActivity} />
          )}
        </DashboardSection>
      </WidgetErrorBoundary>
    </Box>
  );
}
