import { Box } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { dashboardQueryKeys, fetchDashboardSummary } from '../api/dashboard';
import { PageContainer } from '../components/common/PageContainer';
import { ErrorState } from '../components/common/ErrorState';
import { CustomerWorkloadWidget } from '../components/dashboard/CustomerWorkloadWidget';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { DashboardSection } from '../components/dashboard/DashboardCards';
import { DashboardKpiSkeleton, DashboardPanelSkeleton } from '../components/dashboard/DashboardSkeletons';
import { DesignLeaderDashboardView } from '../components/dashboard/DesignLeaderDashboardView';
import { ExecutiveDashboardView } from '../components/dashboard/ExecutiveDashboardView';
import { MyTasksWidget } from '../components/dashboard/MyTasksWidget';
import { ProjectsAttentionTable } from '../components/dashboard/ProjectsAttentionTable';
import { StaffDashboardView } from '../components/dashboard/StaffDashboardView';
import { WidgetErrorBoundary } from '../components/dashboard/WidgetErrorBoundary';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useAuth } from '../context/AuthContext';
import { getDashboardRoleGroup } from '../utils/permissions';

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

  if (dashboardQuery.error) {
    return <ErrorState error={dashboardQuery.error} title="Unable to load dashboard" />;
  }

  const showExecutiveLayout =
    roleGroup === 'admin' || roleGroup === 'engineering_manager' || roleGroup === 'read_only';
  const isAdminDashboard = roleGroup === 'admin';
  const showDesignLeaderExtras = roleGroup === 'design_leader';
  const showMyTasks = roleGroup === 'staff';

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

      {showExecutiveLayout ? (
        <WidgetErrorBoundary title="executive dashboard">
          <ExecutiveDashboardView
            summary={summary}
            unavailable={unavailable}
            loading={loading}
            navigate={navigate}
            isAdmin={isAdminDashboard}
          />
        </WidgetErrorBoundary>
      ) : (
        <>
          <WidgetErrorBoundary title="KPI cards">
            {loading ? (
              <DashboardKpiSkeleton rows={2} />
            ) : roleGroup === 'staff' ? (
              <StaffDashboardView summary={summary} unavailable={unavailable} navigate={navigate} />
            ) : showDesignLeaderExtras ? (
              <DesignLeaderDashboardView summary={summary} unavailable={unavailable} navigate={navigate} />
            ) : null}
          </WidgetErrorBoundary>

          {showDesignLeaderExtras ? (
            <>
              <Box sx={{ mb: 3 }}>
                <WidgetErrorBoundary title="projects requiring attention">
                  <DashboardSection
                    title="Projects Requiring Attention"
                    subtitle="Overdue, due within 7 days, on hold, or blocked"
                  >
                    {loading ? (
                      <DashboardPanelSkeleton height={220} />
                    ) : (
                      <ProjectsAttentionTable rows={summary?.attention_projects ?? []} />
                    )}
                  </DashboardSection>
                </WidgetErrorBoundary>
              </Box>

              <Box sx={{ mb: 3 }}>
                <WidgetErrorBoundary title="customer workload">
                  <DashboardSection
                    title="Current Customer Workload"
                    subtitle="Active tools in progress and assigned designers per customer"
                  >
                    {loading ? (
                      <DashboardPanelSkeleton height={220} />
                    ) : (
                      <CustomerWorkloadWidget rows={summary?.customer_workload ?? []} compact />
                    )}
                  </DashboardSection>
                </WidgetErrorBoundary>
              </Box>
            </>
          ) : null}

          {showMyTasks ? (
            <Box sx={{ mb: 3 }}>
              <WidgetErrorBoundary title="my tasks">
                <DashboardSection
                  title="My Tasks"
                  subtitle="Your milestones, reviews, and timesheets"
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
        </>
      )}
    </PageContainer>
  );
}
