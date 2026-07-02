import { Box, FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import ScheduleIcon from '@mui/icons-material/Schedule';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import TimerIcon from '@mui/icons-material/Timer';
import ArchiveIcon from '@mui/icons-material/Archive';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchTeams } from '../api/lookups';
import { useNavigate } from 'react-router-dom';
import { dashboardQueryKeys, fetchDashboardSummary } from '../api/dashboard';
import { ContentCard } from '../components/ui/cards';
import { ActionKpiCard, DashboardSection } from '../components/dashboard/DashboardCards';
import { CustomerWorkloadWidget } from '../components/dashboard/CustomerWorkloadWidget';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import {
  DashboardKpiSkeleton,
  DashboardPanelSkeleton,
} from '../components/dashboard/DashboardSkeletons';
import { DesignerAvailabilityWidget } from '../components/dashboard/DesignerAvailabilityWidget';
import { MyTasksWidget } from '../components/dashboard/MyTasksWidget';
import { ProjectsAttentionTable } from '../components/dashboard/ProjectsAttentionTable';
import { RecentActivityWidget } from '../components/dashboard/RecentActivityWidget';
import { TeamSummaryWidget } from '../components/dashboard/TeamSummaryWidget';
import { WidgetErrorBoundary } from '../components/dashboard/WidgetErrorBoundary';
import { PageContainer } from '../components/common/PageContainer';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { formatNumber } from '../utils/format';

const EMPTY_TASKS = {
  pending_approvals: [],
  upcoming_milestones: [],
  pending_reviews: [],
};

const EMPTY_AVAILABILITY = {
  total_designers: 0,
  allocated: 0,
  available: 0,
  on_leave: 0,
};

export function DashboardPage() {
  const navigate = useNavigate();
  const [teamFilter, setTeamFilter] = useState<string>('all');
  const teamParam = teamFilter === 'all' ? undefined : teamFilter;

  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams'],
    queryFn: fetchTeams,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const dashboardQuery = useQuery({
    queryKey: dashboardQueryKeys.summary(undefined, teamParam),
    queryFn: () => fetchDashboardSummary(undefined, teamParam),
    staleTime: QUERY_STALE_TIMES.dashboard,
    retry: 1,
  });

  const summary = dashboardQuery.data;
  const loading = dashboardQuery.isLoading;
  const unavailable = dashboardQuery.isError || !summary;

  const rowOneKpis = [
    {
      title: 'Active Projects',
      value: unavailable
        ? '—'
        : formatNumber(summary!.being_worked_on_projects ?? summary!.in_progress_projects ?? 0, 0),
      subtitle: unavailable ? 'No data available.' : 'Currently being worked on',
      icon: FolderOpenIcon,
      statusColor: !unavailable && (summary!.being_worked_on_projects ?? 0) > 0 ? ('primary' as const) : undefined,
      onClick: () => navigate('/projects?execution_status=currently_being_worked_on'),
    },
    {
      title: 'Projects On Hold',
      value: unavailable ? '—' : formatNumber(summary!.on_hold_projects, 0),
      subtitle: unavailable ? 'No data available.' : 'Work paused',
      icon: PauseCircleIcon,
      onClick: () => navigate('/projects?execution_status=on_hold'),
    },
    {
      title: 'Projects Due Next 7 Days',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      subtitle: unavailable ? 'No data available.' : 'Due within 7 days',
      icon: ScheduleIcon,
      statusColor: !unavailable && (summary!.projects_due_this_week ?? 0) > 0 ? ('warning' as const) : undefined,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Overdue Projects',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      subtitle: unavailable ? 'No data available.' : 'Past due date',
      icon: WarningAmberIcon,
      statusColor: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? ('error' as const) : undefined,
      onClick: () => navigate('/projects?due=overdue'),
    },
  ];

  const rowTwoKpis = [
    {
      title: 'Completed Projects',
      value: unavailable ? '—' : formatNumber(summary!.completed_this_month ?? 0, 0),
      subtitle: unavailable ? 'No data available.' : 'Completed this month',
      icon: TaskAltIcon,
      statusColor: !unavailable && (summary!.completed_this_month ?? 0) > 0 ? ('success' as const) : undefined,
      onClick: () =>
        navigate('/projects?execution_status=completed&lifecycle=completed&completed=month'),
    },
    {
      title: 'Total Quoted Hours',
      value: unavailable ? '—' : formatNumber(summary!.total_quoted_hours_active ?? 0, 1),
      subtitle: unavailable ? 'No data available.' : 'Active projects',
      icon: ScheduleIcon,
      onClick: () => navigate('/projects?lifecycle=active'),
    },
    {
      title: 'Total Actual Hours',
      value: unavailable
        ? '—'
        : formatNumber(summary!.total_actual_hours_productive ?? 0, 1),
      subtitle: unavailable ? 'No data available.' : 'Approved productive hours',
      icon: TimerIcon,
      onClick: () => navigate('/reports'),
    },
    {
      title: 'Archived Projects',
      value: unavailable ? '—' : formatNumber(summary!.archived_projects ?? 0, 0),
      subtitle: unavailable ? 'No data available.' : 'Archived portfolio',
      icon: ArchiveIcon,
      onClick: () => navigate('/projects?lifecycle=archived'),
    },
  ];

  const kpiGridSx = {
    display: 'grid',
    gridTemplateColumns: {
      xs: '1fr',
      sm: 'repeat(2, 1fr)',
      lg: 'repeat(4, 1fr)',
    },
    gap: 2,
  };

  return (
    <PageContainer>
      <DashboardHeader
        onNewProject={() => navigate('/projects')}
        onTimesheet={() => navigate('/timesheets')}
        onCustomer={() => navigate('/admin/customers?create=1')}
        onUser={() => navigate('/admin/users?create=1')}
      />

      {(teamsQuery.data?.length ?? 0) > 0 ? (
        <Box sx={{ mb: 3 }}>
          <ContentCard>
            <FormControl sx={{ minWidth: 220 }} size="small">
              <InputLabel>Team</InputLabel>
              <Select
                label="Team"
                value={teamFilter}
                onChange={(event) => setTeamFilter(String(event.target.value))}
              >
                <MenuItem value="all">All Teams</MenuItem>
                {(teamsQuery.data ?? []).map((team) => (
                  <MenuItem key={team.id} value={team.id}>
                    {team.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </ContentCard>
        </Box>
      ) : null}

      <WidgetErrorBoundary title="KPI cards">
        {loading ? (
          <>
            <DashboardKpiSkeleton count={4} />
            <Box sx={{ mt: 2 }}>
              <DashboardKpiSkeleton count={4} />
            </Box>
          </>
        ) : (
          <>
            <Box sx={{ ...kpiGridSx, mb: 2 }}>
              {rowOneKpis.map((card) => (
                <ActionKpiCard key={card.title} {...card} />
              ))}
            </Box>
            <Box sx={{ ...kpiGridSx, mb: 3 }}>
              {rowTwoKpis.map((card) => (
                <ActionKpiCard key={card.title} {...card} />
              ))}
            </Box>
          </>
        )}
      </WidgetErrorBoundary>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', xl: '1.1fr 0.9fr' },
          gap: 2.5,
          mb: 3,
        }}
      >
        <WidgetErrorBoundary title="customer workload">
          <DashboardSection
            title="Customer Workload"
            subtitle="Active tools by customer, sorted by volume"
          >
            {loading ? (
              <DashboardPanelSkeleton height={280} />
            ) : (
              <CustomerWorkloadWidget rows={summary?.customer_workload ?? []} />
            )}
          </DashboardSection>
        </WidgetErrorBoundary>

        <WidgetErrorBoundary title="designer availability">
          <DashboardSection
            title="Designer Availability"
            subtitle="Current allocation and status across the design team"
          >
            {loading ? (
              <DashboardPanelSkeleton height={360} />
            ) : (
              <DesignerAvailabilityWidget
                summary={summary?.designer_availability_summary ?? EMPTY_AVAILABILITY}
                designers={summary?.designer_availability ?? []}
              />
            )}
          </DashboardSection>
        </WidgetErrorBoundary>
      </Box>

      <Box sx={{ mb: 3 }}>
        <WidgetErrorBoundary title="team summary">
          <DashboardSection
            title="Team Summary"
            subtitle="Projects, hours, and remaining capacity by team"
          >
            {loading ? (
              <DashboardPanelSkeleton height={220} />
            ) : (
              <TeamSummaryWidget rows={summary?.team_summary ?? []} />
            )}
          </DashboardSection>
        </WidgetErrorBoundary>
      </Box>

      <Box sx={{ mb: 3 }}>
        <WidgetErrorBoundary title="projects requiring attention">
          <DashboardSection
            title="Projects Requiring Attention"
            subtitle="Overdue, due within 7 days, on hold, or blocked"
          >
            {loading ? (
              <DashboardPanelSkeleton height={260} />
            ) : (
              <ProjectsAttentionTable rows={summary?.attention_projects ?? []} />
            )}
          </DashboardSection>
        </WidgetErrorBoundary>
      </Box>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' },
          gap: 2.5,
        }}
      >
        <WidgetErrorBoundary title="recent activity">
          <DashboardSection title="Recent Activity" subtitle="Projects, milestones, timesheets, users, imports">
            {loading ? (
              <DashboardPanelSkeleton height={280} />
            ) : (
              <RecentActivityWidget activities={summary?.activity_feed ?? []} />
            )}
          </DashboardSection>
        </WidgetErrorBoundary>

        <WidgetErrorBoundary title="my tasks">
          <DashboardSection
            title="My Tasks"
            subtitle="Milestones, reviews, and approvals assigned to you"
          >
            {loading ? (
              <DashboardPanelSkeleton height={280} />
            ) : (
              <MyTasksWidget tasks={summary?.my_tasks ?? EMPTY_TASKS} />
            )}
          </DashboardSection>
        </WidgetErrorBoundary>
      </Box>
    </PageContainer>
  );
}
