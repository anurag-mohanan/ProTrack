import { Box, Grid } from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import ScheduleIcon from '@mui/icons-material/Schedule';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import PendingActionsIcon from '@mui/icons-material/PendingActions';
import GroupsIcon from '@mui/icons-material/Groups';
import MonetizationOnIcon from '@mui/icons-material/MonetizationOn';
import DoNotDisturbIcon from '@mui/icons-material/DoNotDisturb';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  dashboardQueryKeys,
  fetchAttentionProjects,
  fetchDashboardKpis,
  fetchDashboardMyTasks,
  fetchDashboardRecentActivity,
} from '../api/dashboard';
import { ActionKpiCard, DashboardSection } from '../components/dashboard/DashboardCards';
import { DashboardFutureStrip } from '../components/dashboard/DashboardFutureStrip';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { MyTasksWidget } from '../components/dashboard/MyTasksWidget';
import { ProjectsAttentionTable } from '../components/dashboard/ProjectsAttentionTable';
import { RecentActivityWidget } from '../components/dashboard/RecentActivityWidget';
import { WidgetErrorBoundary } from '../components/dashboard/WidgetErrorBoundary';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { formatNumber } from '../utils/format';

export function DashboardPage() {
  const navigate = useNavigate();

  const kpisQuery = useQuery({
    queryKey: dashboardQueryKeys.kpis,
    queryFn: fetchDashboardKpis,
  });
  const attentionQuery = useQuery({
    queryKey: dashboardQueryKeys.attentionProjects,
    queryFn: fetchAttentionProjects,
  });
  const tasksQuery = useQuery({
    queryKey: dashboardQueryKeys.myTasks,
    queryFn: fetchDashboardMyTasks,
  });
  const activityQuery = useQuery({
    queryKey: dashboardQueryKeys.recentActivity,
    queryFn: fetchDashboardRecentActivity,
  });

  const initialLoading =
    kpisQuery.isLoading &&
    attentionQuery.isLoading &&
    tasksQuery.isLoading &&
    activityQuery.isLoading;

  if (initialLoading) return <LoadingState message="Loading your dashboard…" />;

  const kpis = kpisQuery.data ?? {
    active_projects: 0,
    projects_due_this_week: 0,
    overdue_projects: 0,
    pending_timesheets: 0,
    designer_utilization_percent: 0,
    billable_hours_this_month: 0,
    np_hours_this_month: 0,
  };

  const kpiCards = [
    {
      title: 'Active Projects',
      value: formatNumber(kpis.active_projects, 0),
      subtitle: 'In progress or on hold',
      icon: FolderOpenIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Projects Due This Week',
      value: formatNumber(kpis.projects_due_this_week, 0),
      subtitle: 'Due in the next 7 days',
      icon: ScheduleIcon,
      statusColor: kpis.projects_due_this_week > 0 ? ('warning' as const) : undefined,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Overdue Projects',
      value: formatNumber(kpis.overdue_projects, 0),
      subtitle: 'Past due date',
      icon: WarningAmberIcon,
      statusColor: kpis.overdue_projects > 0 ? ('error' as const) : undefined,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Pending Timesheets',
      value: formatNumber(kpis.pending_timesheets, 0),
      subtitle: 'Awaiting your approval',
      icon: PendingActionsIcon,
      statusColor: kpis.pending_timesheets > 0 ? ('warning' as const) : undefined,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Designer Utilization',
      value: `${formatNumber(kpis.designer_utilization_percent)}%`,
      subtitle: 'Team hours this week',
      icon: GroupsIcon,
      onClick: () => navigate('/workload'),
    },
    {
      title: 'Billable Hours This Month',
      value: formatNumber(kpis.billable_hours_this_month),
      subtitle: 'Approved productive hours',
      icon: MonetizationOnIcon,
      onClick: () => navigate('/reports'),
    },
    {
      title: 'Non-Productive Hours',
      value: formatNumber(kpis.np_hours_this_month),
      subtitle: 'Approved NP hours this month',
      icon: DoNotDisturbIcon,
      onClick: () => navigate('/reports?tab=np-hours'),
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

      {kpisQuery.error ? (
        <Box sx={{ mb: 2 }}>
          <ErrorState error={kpisQuery.error} title="Some KPIs could not be loaded" />
        </Box>
      ) : null}

      <WidgetErrorBoundary title="KPI cards">
        <Grid container spacing={2} sx={{ mb: 3.5 }}>
          {kpiCards.map((card) => (
            <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={card.title}>
              <ActionKpiCard {...card} />
            </Grid>
          ))}
        </Grid>
      </WidgetErrorBoundary>

      <WidgetErrorBoundary title="projects requiring attention">
        <DashboardSection
          title="Projects Requiring Attention"
          subtitle="Overdue, due soon, blocked, or on hold"
        >
          {attentionQuery.isLoading ? (
            <LoadingState message="Loading attention projects…" />
          ) : (
            <ProjectsAttentionTable rows={attentionQuery.data ?? []} />
          )}
        </DashboardSection>
      </WidgetErrorBoundary>

      <WidgetErrorBoundary title="my tasks">
        <DashboardSection title="My Tasks" subtitle="Assignments, approvals, and upcoming milestones">
          {tasksQuery.isLoading ? (
            <LoadingState message="Loading tasks…" />
          ) : (
            <MyTasksWidget tasks={tasksQuery.data ?? { assigned_projects: [], pending_approvals: [], upcoming_milestones: [] }} />
          )}
        </DashboardSection>
      </WidgetErrorBoundary>

      <WidgetErrorBoundary title="recent activity">
        <DashboardSection title="Recent Activity" subtitle="Latest updates across ProTrack">
          {activityQuery.isLoading ? (
            <LoadingState message="Loading activity…" />
          ) : (
            <RecentActivityWidget activities={activityQuery.data ?? []} />
          )}
        </DashboardSection>
      </WidgetErrorBoundary>

      <DashboardFutureStrip
        placeholders={{
          notifications_enabled: false,
          ai_recommendations_enabled: false,
          todays_priorities_enabled: false,
        }}
      />
    </Box>
  );
}
