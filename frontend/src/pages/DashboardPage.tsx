import { Box } from '@mui/material';
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
import { ResourcePlanningSummary } from '../components/dashboard/ResourcePlanningSummary';
import { StaffDashboardView } from '../components/dashboard/StaffDashboardView';
import { WidgetErrorBoundary } from '../components/dashboard/WidgetErrorBoundary';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useAuth } from '../context/AuthContext';
import {
  getDashboardRoleGroup,
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
    () => buildOperationalKpis({ summary, unavailable, navigate }),
    [navigate, summary, unavailable],
  );

  if (dashboardQuery.error) {
    return <ErrorState error={dashboardQuery.error} title="Unable to load dashboard" />;
  }

  const showOperationalLayout = roleGroup === 'admin' || roleGroup === 'engineering_manager' || roleGroup === 'read_only';
  const showAttention = roleGroup !== 'staff';
  const showResourcePlanning = roleGroup === 'admin' || roleGroup === 'engineering_manager';
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
          <DashboardKpiSkeleton count={7} />
        ) : roleGroup === 'staff' ? (
          <StaffDashboardView summary={summary} unavailable={unavailable} navigate={navigate} />
        ) : roleGroup === 'design_leader' ? (
          <DesignLeaderDashboardView summary={summary} unavailable={unavailable} navigate={navigate} />
        ) : showOperationalLayout ? (
          <OperationalKpiGrid cards={operationalKpis} />
        ) : null}
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
                <DashboardPanelSkeleton height={220} />
              ) : (
                <ProjectsAttentionTable rows={summary?.attention_projects ?? []} />
              )}
            </DashboardSection>
          </WidgetErrorBoundary>
        </Box>
      ) : null}

      {showResourcePlanning ? (
        <Box sx={{ mb: 3 }}>
          <WidgetErrorBoundary title="resource planning summary">
            <DashboardSection
              title="Resource Planning Summary"
              subtitle="Team capacity and utilization at a glance"
            >
              {loading ? (
                <DashboardPanelSkeleton height={200} />
              ) : (
                <ResourcePlanningSummary rows={summary?.team_summary ?? []} />
              )}
            </DashboardSection>
          </WidgetErrorBoundary>
        </Box>
      ) : null}

      {showMyTasks ? (
        <Box sx={{ mb: 3 }}>
          <WidgetErrorBoundary title="my tasks">
            <DashboardSection
              title="My Tasks"
              subtitle={
                roleGroup === 'staff'
                  ? 'Your milestones, reviews, and timesheets'
                  : 'Approvals, reviews, and milestones assigned to you'
              }
            >
              {loading ? (
                <DashboardPanelSkeleton height={220} />
              ) : (
                <MyTasksWidget tasks={summary?.my_tasks ?? EMPTY_TASKS} />
              )}
            </DashboardSection>
          </WidgetErrorBoundary>
        </Box>
      ) : null}
    </PageContainer>
  );
}
