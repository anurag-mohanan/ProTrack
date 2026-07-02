import { Box, Typography } from '@mui/material';
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { dashboardQueryKeys, fetchDashboardSummary } from '../api/dashboard';
import { PageContainer } from '../components/common/PageContainer';
import { ErrorState } from '../components/common/ErrorState';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { DashboardSection } from '../components/dashboard/DashboardCards';
import { DashboardKpiSkeleton, DashboardPanelSkeleton } from '../components/dashboard/DashboardSkeletons';
import { DesignLeaderDashboardView } from '../components/dashboard/DesignLeaderDashboardView';
import { MyTasksWidget } from '../components/dashboard/MyTasksWidget';
import { buildOperationalKpis, OperationalKpiGrid } from '../components/dashboard/OperationalKpiGrid';
import { ProjectsAttentionTable } from '../components/dashboard/ProjectsAttentionTable';
import { StaffDashboardView } from '../components/dashboard/StaffDashboardView';
import { SystemNotificationsWidget } from '../components/dashboard/SystemNotificationsWidget';
import { TeamSummaryWidget } from '../components/dashboard/TeamSummaryWidget';
import { WidgetErrorBoundary } from '../components/dashboard/WidgetErrorBoundary';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useAuth } from '../context/AuthContext';
import {
  getDashboardRoleGroup,
  isAdminRole,
  isReadOnlyRole,
} from '../utils/permissions';

const EMPTY_TASKS = {
  pending_approvals: [],
  upcoming_milestones: [],
  pending_reviews: [],
};

export function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const roleName = user?.role_name ?? '';
  const roleGroup = getDashboardRoleGroup(roleName);

  const dashboardQuery = useQuery({
    queryKey: dashboardQueryKeys.summary(undefined, undefined),
    queryFn: () => fetchDashboardSummary(undefined, undefined),
    staleTime: QUERY_STALE_TIMES.dashboard,
    retry: 1,
  });

  const summary = dashboardQuery.data;
  const loading = dashboardQuery.isLoading;
  const unavailable = dashboardQuery.isError || !summary;

  const operationalKpis = useMemo(
    () =>
      buildOperationalKpis({
        summary,
        unavailable,
        navigate,
        includeOperationalRow: roleGroup === 'admin' || roleGroup === 'engineering_manager',
      }),
    [navigate, roleGroup, summary, unavailable],
  );

  if (dashboardQuery.error) {
    return <ErrorState error={dashboardQuery.error} title="Unable to load dashboard" />;
  }

  const showAttention = roleGroup !== 'staff';
  const showTeamSummary = roleGroup === 'admin' || roleGroup === 'engineering_manager';
  const showSystemNotifications = isAdminRole(roleName);
  const showMyTasks = roleGroup !== 'read_only';

  return (
    <PageContainer>
      <DashboardHeader
        onNewProject={() => navigate('/projects?create=1')}
        onTimesheet={() => navigate('/timesheets')}
        onCustomer={() => navigate('/admin/customers?create=1')}
        onUser={() => navigate('/admin/users?create=1')}
        onReports={() => navigate('/reports')}
        onAdministration={() => navigate('/admin/dashboard')}
        onImportTimesheets={() => navigate('/admin/imports/historical-timesheets')}
        onApproveTimesheets={() => navigate('/timesheets')}
        onAssignDesigners={() => navigate('/projects')}
        onOpenCurrentProject={() => navigate('/projects')}
      />

      <WidgetErrorBoundary title="KPI cards">
        {loading ? (
          <DashboardKpiSkeleton count={roleGroup === 'staff' ? 4 : 8} />
        ) : roleGroup === 'staff' ? (
          <StaffDashboardView summary={summary} unavailable={unavailable} navigate={navigate} />
        ) : roleGroup === 'design_leader' ? (
          <DesignLeaderDashboardView summary={summary} unavailable={unavailable} navigate={navigate} />
        ) : roleGroup === 'read_only' ? (
          <OperationalKpiGrid
            rowOne={operationalKpis.rowOne.slice(0, 4)}
            rowTwo={operationalKpis.rowTwo.slice(0, 2)}
            rowThree={[]}
          />
        ) : (
          <OperationalKpiGrid
            rowOne={operationalKpis.rowOne}
            rowTwo={operationalKpis.rowTwo}
            rowThree={operationalKpis.rowThree}
          />
        )}
      </WidgetErrorBoundary>

      {showAttention ? (
        <Box sx={{ mb: 3 }}>
          <WidgetErrorBoundary title="projects requiring attention">
            <DashboardSection
              title="Projects Requiring Attention"
              subtitle={
                isReadOnlyRole(roleName)
                  ? 'Read-only portfolio view'
                  : 'Overdue, due within 7 days, on hold, or blocked'
              }
            >
              {loading ? (
                <DashboardPanelSkeleton height={260} />
              ) : (
                <ProjectsAttentionTable rows={summary?.attention_projects ?? []} />
              )}
            </DashboardSection>
          </WidgetErrorBoundary>
        </Box>
      ) : null}

      {showTeamSummary ? (
        <Box sx={{ mb: 3 }}>
          <WidgetErrorBoundary title="team summary">
            <DashboardSection title="Team Summary" subtitle="Projects, hours, and capacity by team">
              {loading ? (
                <DashboardPanelSkeleton height={220} />
              ) : (
                <TeamSummaryWidget rows={summary?.team_summary ?? []} />
              )}
            </DashboardSection>
          </WidgetErrorBoundary>
        </Box>
      ) : null}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: showSystemNotifications && showMyTasks ? '1fr 1fr' : '1fr' },
          gap: 2.5,
        }}
      >
        {showSystemNotifications ? (
          <WidgetErrorBoundary title="system notifications">
            <DashboardSection title="System Notifications" subtitle="Recent user and import activity">
              {loading ? (
                <DashboardPanelSkeleton height={280} />
              ) : (
                <SystemNotificationsWidget activities={summary?.activity_feed ?? []} />
              )}
            </DashboardSection>
          </WidgetErrorBoundary>
        ) : null}

        {showMyTasks ? (
          <WidgetErrorBoundary title="my tasks">
            <DashboardSection
              title="My Tasks"
              subtitle={
                roleGroup === 'staff'
                  ? 'Your milestones, reviews, and timesheets'
                  : 'Milestones, reviews, and approvals assigned to you'
              }
            >
              {loading ? (
                <DashboardPanelSkeleton height={280} />
              ) : (
                <MyTasksWidget tasks={summary?.my_tasks ?? EMPTY_TASKS} />
              )}
            </DashboardSection>
          </WidgetErrorBoundary>
        ) : null}
      </Box>

      {roleGroup === 'staff' && !loading && summary?.my_tasks ? (
        <Box sx={{ mt: 3 }}>
          <Typography variant="body2" color="text.secondary">
            Use quick actions above to submit timesheets, update milestones, or open your current project.
          </Typography>
        </Box>
      ) : null}
    </PageContainer>
  );
}
