import { Box } from '@mui/material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { aiQueryKeys, fetchAiInsights } from '../api/ai';
import { dashboardQueryKeys, fetchDashboardSummary, fetchRoleKpis } from '../api/dashboard';
import { fetchSystemHealth } from '../api/system';
import { PageContainer } from '../components/common/PageContainer';
import { ErrorState } from '../components/common/ErrorState';
import { AiOperationsPanel } from '../components/ai/AiOperationsPanel';
import { ActivityTimeline } from '../components/dashboard/ActivityTimeline';
import { buildRoleKpiCards } from '../components/dashboard/buildRoleKpiCards';
import { CollaborationActivityWidget } from '../components/dashboard/CollaborationActivityWidget';
import { CustomerWorkloadWidget } from '../components/dashboard/CustomerWorkloadWidget';
import { DashboardChartsSection } from '../components/dashboard/DashboardChartsSection';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { DashboardLayout } from '../components/dashboard/DashboardLayout';
import { DashboardSection } from '../components/dashboard/DashboardCards';
import { DashboardKpiSkeleton, DashboardPanelSkeleton } from '../components/dashboard/DashboardSkeletons';
import { ExecutiveKpiGrid } from '../components/dashboard/ExecutiveKpiGrid';
import { MissingTimesheetsWidget } from '../components/dashboard/MissingTimesheetsWidget';
import { MyProjectsWidget } from '../components/dashboard/MyProjectsWidget';
import { MyTasksWidget } from '../components/dashboard/MyTasksWidget';
import { ProjectsAttentionTable } from '../components/dashboard/ProjectsAttentionTable';
import { WidgetErrorBoundary } from '../components/dashboard/WidgetErrorBoundary';
import { DashboardPanel } from '../components/ui/design-system/DashboardPanel';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useAuth } from '../context/AuthContext';
import { accessContextFromUser, getDashboardRoleGroup } from '../utils/permissions';
import {
  canViewDashboardAiPanel,
  canViewDashboardCollaboration,
  canViewDashboardCustomerWorkload,
  canViewDashboardEngineeringCharts,
  canViewDashboardMissingTimesheets,
  canViewDashboardMyProjects,
  canViewDashboardMyTasks,
  canViewDashboardProjectsAttention,
  canViewDashboardSystemActivity,
} from '../utils/portalAccess';
import { getLeaderTeamScopeIds, shouldScopeProjectsByLeaderTeams } from '../utils/projectTeamScope';

const EMPTY_TASKS = {
  pending_approvals: [],
  upcoming_milestones: [],
  pending_reviews: [],
};

export function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const roleName = user?.role_name ?? '';
  const roleGroup = getDashboardRoleGroup(roleName);
  const leaderTeamIds = getLeaderTeamScopeIds(user);
  const scopeDashboardByTeams = shouldScopeProjectsByLeaderTeams(roleName, user);

  const dashboardQuery = useQuery({
    queryKey: dashboardQueryKeys.summary(
      undefined,
      scopeDashboardByTeams && leaderTeamIds.length === 1 ? leaderTeamIds[0] : undefined,
      scopeDashboardByTeams && leaderTeamIds.length > 1 ? leaderTeamIds : undefined,
    ),
    queryFn: () =>
      fetchDashboardSummary(
        undefined,
        scopeDashboardByTeams && leaderTeamIds.length === 1 ? leaderTeamIds[0] : undefined,
        scopeDashboardByTeams && leaderTeamIds.length > 1 ? leaderTeamIds : undefined,
      ),
    staleTime: QUERY_STALE_TIMES.dashboard,
    retry: 1,
  });

  const systemHealthQuery = useQuery({
    queryKey: ['system-health'],
    queryFn: fetchSystemHealth,
    enabled: roleGroup === 'admin',
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const aiInsightsQuery = useQuery({
    queryKey: aiQueryKeys.insights(10),
    queryFn: () => fetchAiInsights(10),
    enabled: canViewDashboardAiPanel(access),
    staleTime: 5 * 60 * 1000,
  });

  const roleKpisQuery = useQuery({
    queryKey: dashboardQueryKeys.roleKpis,
    queryFn: fetchRoleKpis,
    staleTime: QUERY_STALE_TIMES.dashboard,
    retry: 1,
  });

  const summary = dashboardQuery.data;
  const loading = dashboardQuery.isLoading;
  const unavailable = dashboardQuery.isError || !summary;

  const aiInsights = useMemo(
    () =>
      aiInsightsQuery.data ??
      (summary?.engineering_insights ?? []).map((insight, index) => ({
        id: `legacy-${index}`,
        module: 'dashboard_insights',
        category: insight.category,
        severity: insight.severity as 'info' | 'warning' | 'error',
        title: insight.title,
        detail: insight.detail,
        href: insight.href,
        confidence: 80,
      })),
    [aiInsightsQuery.data, summary?.engineering_insights],
  );

  const kpiCards = useMemo(
    () =>
      buildRoleKpiCards({
        roleGroup,
        summary,
        systemHealth: systemHealthQuery.data,
        roleKpis: roleKpisQuery.data,
        unavailable,
        navigate,
        access,
      }),
    [roleGroup, summary, systemHealthQuery.data, roleKpisQuery.data, unavailable, navigate, access],
  );

  if (dashboardQuery.error) {
    return <ErrorState error={dashboardQuery.error} title="Unable to load dashboard" />;
  }

  const showAiSidebar = canViewDashboardAiPanel(access);
  const showEngineeringCharts = canViewDashboardEngineeringCharts(access);
  const showMyProjects = canViewDashboardMyProjects(access);
  const myProjectRows =
    summary?.my_project_rows?.length
      ? summary.my_project_rows
      : summary?.staff_metrics?.my_project_rows ?? [];

  const headerProps = {
    onNewProject: () => navigate('/projects?create=1'),
    onTimesheet: () => navigate('/timesheets'),
    onCustomer: () => navigate('/admin/customers?create=1'),
    onUser: () => navigate('/admin/users?create=1'),
    onReports: () => navigate('/reports'),
    onAdministration: () => navigate('/admin/dashboard'),
    onImportTimesheets: () => navigate('/admin/imports/historical-timesheets'),
    onApproveTimesheets: () => navigate('/timesheets'),
    onAssignDesigners: () => navigate('/projects'),
    onOpenCurrentProject: () => navigate('/projects'),
  };

  return (
    <PageContainer>
      <DashboardHeader summary={summary} {...headerProps} />

      <DashboardLayout
        sidebar={
          showAiSidebar ? (
            <AiOperationsPanel
              insights={aiInsights}
              navigate={navigate}
              loading={aiInsightsQuery.isLoading}
              onRefresh={() => {
                void queryClient.invalidateQueries({ queryKey: aiQueryKeys.insights(10) });
              }}
            />
          ) : undefined
        }
      >
        <WidgetErrorBoundary title="KPI cards">
          {loading ? <DashboardKpiSkeleton rows={3} /> : <ExecutiveKpiGrid cards={kpiCards} />}
        </WidgetErrorBoundary>

        {showMyProjects ? (
          <Box sx={{ mt: 1.5 }}>
            <WidgetErrorBoundary title="my projects">
              {loading ? (
                <DashboardPanelSkeleton height={200} />
              ) : (
                <MyProjectsWidget rows={myProjectRows} navigate={navigate} />
              )}
            </WidgetErrorBoundary>
          </Box>
        ) : null}

        {canViewDashboardCollaboration(access) ? (
          <Box sx={{ mt: 1.5 }}>
            <WidgetErrorBoundary title="collaboration activity">
              {loading ? (
                <DashboardPanelSkeleton height={180} />
              ) : (
                <CollaborationActivityWidget data={summary?.collaboration_activity} />
              )}
            </WidgetErrorBoundary>
          </Box>
        ) : null}

        {showEngineeringCharts ? (
          <WidgetErrorBoundary title="dashboard charts">
            <DashboardChartsSection summary={summary} loading={loading} navigate={navigate} />
          </WidgetErrorBoundary>
        ) : null}

        {roleGroup === 'design_leader' && canViewDashboardProjectsAttention(access) ? (
          <Box sx={{ mt: 1.5 }}>
            <WidgetErrorBoundary title="projects requiring attention">
              <DashboardSection title="Projects Requiring Attention" subtitle="Overdue, due soon, or blocked">
                {loading ? (
                  <DashboardPanelSkeleton height={200} />
                ) : (
                  <ProjectsAttentionTable rows={summary?.attention_projects ?? []} />
                )}
              </DashboardSection>
            </WidgetErrorBoundary>
          </Box>
        ) : null}

        {canViewDashboardMissingTimesheets(access) &&
        !loading &&
        (summary?.missing_timesheets?.length ?? 0) > 0 ? (
          <Box sx={{ mt: 1.5 }}>
            <MissingTimesheetsWidget rows={summary?.missing_timesheets ?? []} />
          </Box>
        ) : null}

        {canViewDashboardMyTasks(access) ? (
          <Box sx={{ mt: 1.5 }}>
            <WidgetErrorBoundary title="my tasks">
              <DashboardSection title="My Tasks" subtitle="Milestones, reviews, and timesheets">
                {loading ? (
                  <DashboardPanelSkeleton height={200} />
                ) : (
                  <MyTasksWidget tasks={summary?.my_tasks ?? EMPTY_TASKS} />
                )}
              </DashboardSection>
            </WidgetErrorBoundary>
          </Box>
        ) : null}

        {canViewDashboardSystemActivity(access) ? (
          <Box sx={{ mt: 1.5 }}>
            <DashboardPanel title="System Activity" subtitle="Recent administration events">
              {loading ? (
                <DashboardPanelSkeleton height={180} />
              ) : (
                <ActivityTimeline
                  activities={(summary?.activity_feed ?? []).filter(
                    (item) => item.category === 'import' || item.category === 'user',
                  )}
                />
              )}
            </DashboardPanel>
          </Box>
        ) : null}

        {roleGroup === 'design_leader' && canViewDashboardCustomerWorkload(access) ? (
          <Box sx={{ mt: 1.5 }}>
            <DashboardSection title="Customer Workload" subtitle="Active tools by customer">
              {loading ? (
                <DashboardPanelSkeleton height={200} />
              ) : (
                <CustomerWorkloadWidget rows={summary?.customer_workload ?? []} compact />
              )}
            </DashboardSection>
          </Box>
        ) : null}
      </DashboardLayout>
    </PageContainer>
  );
}
