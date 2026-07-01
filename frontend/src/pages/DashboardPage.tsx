import { Box, FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import ScheduleIcon from '@mui/icons-material/Schedule';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchTeams } from '../api/lookups';
import { useNavigate } from 'react-router-dom';
import { dashboardQueryKeys, fetchDashboardSummary } from '../api/dashboard';
import { ContentCard } from '../components/ui/cards';
import { ActionKpiCard, DashboardSection } from '../components/dashboard/DashboardCards';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { MyTasksWidget } from '../components/dashboard/MyTasksWidget';
import { ProjectsAttentionTable } from '../components/dashboard/ProjectsAttentionTable';
import { RecentActivityWidget } from '../components/dashboard/RecentActivityWidget';
import { WidgetErrorBoundary } from '../components/dashboard/WidgetErrorBoundary';
import { EmptyState } from '../components/common/EmptyState';
import { LoadingState } from '../components/common/LoadingState';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { formatNumber } from '../utils/format';

const EMPTY_TASKS = {
  pending_approvals: [],
  upcoming_milestones: [],
  pending_reviews: [],
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

  if (dashboardQuery.isLoading) {
    return <LoadingState message="Loading your dashboard…" />;
  }

  const summary = dashboardQuery.data;
  const unavailable = dashboardQuery.isError || !summary;

  const kpiCards = [
    {
      title: 'Active Projects',
      value: unavailable
        ? '—'
        : formatNumber(summary!.being_worked_on_projects ?? summary!.in_progress_projects ?? 0, 0),
      subtitle: unavailable ? 'No data available' : 'Currently being worked on',
      icon: FolderOpenIcon,
      statusColor: !unavailable && (summary!.being_worked_on_projects ?? 0) > 0 ? ('primary' as const) : undefined,
      onClick: () => navigate('/projects?execution_status=currently_being_worked_on'),
    },
    {
      title: 'Projects On Hold',
      value: unavailable ? '—' : formatNumber(summary!.on_hold_projects, 0),
      subtitle: unavailable ? 'No data available' : 'Work paused',
      icon: PauseCircleIcon,
      onClick: () => navigate('/projects?execution_status=on_hold'),
    },
    {
      title: 'Projects Due Next 7 Days',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      subtitle: unavailable ? 'No data available' : 'Due within 7 days',
      icon: ScheduleIcon,
      statusColor: !unavailable && (summary!.projects_due_this_week ?? 0) > 0 ? ('warning' as const) : undefined,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Overdue Projects',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      subtitle: unavailable ? 'No data available' : 'Past due date',
      icon: WarningAmberIcon,
      statusColor: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? ('error' as const) : undefined,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Completed Projects',
      value: unavailable ? '—' : formatNumber(summary!.completed_this_month ?? 0, 0),
      subtitle: unavailable ? 'No data available' : 'Completed this month',
      icon: TaskAltIcon,
      statusColor: !unavailable && (summary!.completed_this_month ?? 0) > 0 ? ('success' as const) : undefined,
      onClick: () =>
        navigate('/projects?execution_status=completed&lifecycle=completed&completed=month'),
    },
  ];

  return (
    <Box sx={{ maxWidth: 1280, mx: 'auto' }}>
      <DashboardHeader
        onNewProject={() => navigate('/projects')}
        onTimesheet={() => navigate('/timesheets')}
        onCustomer={() => navigate('/admin/customers')}
        onUser={() => navigate('/admin/users')}
      />

      {(teamsQuery.data?.length ?? 0) > 0 ? (
        <Box sx={{ mb: 2 }}>
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
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              sm: 'repeat(2, 1fr)',
              lg: 'repeat(5, 1fr)',
            },
            gap: 2,
            mb: 2.5,
          }}
        >
          {kpiCards.map((card) => (
            <ActionKpiCard key={card.title} {...card} />
          ))}
        </Box>
      </WidgetErrorBoundary>

      <Box sx={{ mb: 2.5 }}>
        <WidgetErrorBoundary title="projects requiring attention">
          <DashboardSection
            title="Projects Requiring Attention"
            subtitle="Overdue, due within 7 days, on hold, or blocked"
          >
            {unavailable || !summary?.attention_projects?.length ? (
              <EmptyState title="No projects require attention" description="You're all caught up." />
            ) : (
              <ProjectsAttentionTable rows={summary.attention_projects} />
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
          <DashboardSection title="Recent Activity" subtitle="Latest engineering updates">
            {unavailable || !summary?.recent_activity?.length ? (
              <EmptyState title="No activity yet" description="Updates will appear here." />
            ) : (
              <RecentActivityWidget activities={summary.recent_activity} />
            )}
          </DashboardSection>
        </WidgetErrorBoundary>

        <WidgetErrorBoundary title="my tasks">
          <DashboardSection
            title="My Tasks"
            subtitle="Milestones, reviews, and approvals assigned to you"
          >
            {unavailable ? (
              <EmptyState title="No tasks available" />
            ) : (
              <MyTasksWidget tasks={summary.my_tasks ?? EMPTY_TASKS} />
            )}
          </DashboardSection>
        </WidgetErrorBoundary>
      </Box>
    </Box>
  );
}
