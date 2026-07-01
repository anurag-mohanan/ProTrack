import { Box, FormControl, Grid, InputLabel, MenuItem, Select, Typography } from '@mui/material';
import CancelIcon from '@mui/icons-material/Cancel';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import ScheduleIcon from '@mui/icons-material/Schedule';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import Inventory2OutlinedIcon from '@mui/icons-material/Inventory2Outlined';
import MonetizationOnIcon from '@mui/icons-material/MonetizationOn';
import TimelapseIcon from '@mui/icons-material/Timelapse';
import DoNotDisturbIcon from '@mui/icons-material/DoNotDisturb';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { dashboardQueryKeys, fetchDashboardSummary } from '../api/dashboard';
import { ContentCard } from '../components/ui/cards';
import type { ProjectStage } from '../types';
import { PROJECT_STAGE_LABELS } from '../types/common';
import { ActionKpiCard, DashboardSection } from '../components/dashboard/DashboardCards';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { MyTasksWidget } from '../components/dashboard/MyTasksWidget';
import { NpHoursPanel } from '../components/dashboard/NpHoursPanel';
import { ProjectsAttentionTable } from '../components/dashboard/ProjectsAttentionTable';
import { RecentActivityWidget } from '../components/dashboard/RecentActivityWidget';
import { WidgetErrorBoundary } from '../components/dashboard/WidgetErrorBoundary';
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
  const [projectStageFilter, setProjectStageFilter] = useState<ProjectStage | 'all'>(
    'all',
  );

  const stageParam = projectStageFilter === 'all' ? undefined : projectStageFilter;

  const dashboardQuery = useQuery({
    queryKey: dashboardQueryKeys.summary(stageParam),
    queryFn: () => fetchDashboardSummary(stageParam),
    staleTime: QUERY_STALE_TIMES.dashboard,
    retry: 1,
  });

  if (dashboardQuery.isLoading) {
    return <LoadingState message="Loading your dashboard…" />;
  }

  const summary = dashboardQuery.data;
  const unavailable = dashboardQuery.isError || !summary;

  const dueNext7Days = summary?.projects_due_this_week ?? 0;
  const overdueProjects = summary?.overdue_projects ?? 0;
  const completedThisMonth = summary?.completed_this_month ?? 0;
  const quotedHoursActive = summary?.total_quoted_hours_active ?? summary?.total_quoted_hours ?? 0;
  const actualHoursProductive =
    summary?.total_actual_hours_productive ?? summary?.billable_hours ?? 0;
  const npHoursThisMonth = summary?.np_hours_this_month ?? summary?.np_hours ?? 0;

  const beingWorkedOn =
    summary?.being_worked_on_projects ?? summary?.in_progress_projects ?? 0;
  const cancelledProjects = summary?.cancelled_projects ?? 0;

  const rowOneCards = [
    {
      title: 'Projects Being Worked On',
      value: unavailable ? '—' : formatNumber(beingWorkedOn, 0),
      subtitle: unavailable ? 'No data available' : 'Active engineering work',
      icon: FolderOpenIcon,
      statusColor: !unavailable && beingWorkedOn > 0 ? ('primary' as const) : undefined,
      onClick: () =>
        navigate('/projects?execution_status=currently_being_worked_on'),
    },
    {
      title: 'Projects On Hold',
      value: unavailable ? '—' : formatNumber(summary!.on_hold_projects, 0),
      subtitle: unavailable ? 'No data available' : 'Work paused',
      icon: PauseCircleIcon,
      onClick: () => navigate('/projects?execution_status=on_hold'),
    },
    {
      title: 'Cancelled Projects',
      value: unavailable ? '—' : formatNumber(cancelledProjects, 0),
      subtitle: unavailable ? 'No data available' : 'Cancelled portfolio',
      icon: CancelIcon,
      onClick: () => navigate('/projects?lifecycle=cancelled'),
    },
    {
      title: 'Projects Due Next 7 Days',
      value: unavailable ? '—' : formatNumber(dueNext7Days, 0),
      subtitle: unavailable ? 'No data available' : 'Due within 7 days',
      icon: ScheduleIcon,
      statusColor: !unavailable && dueNext7Days > 0 ? ('warning' as const) : undefined,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Overdue Projects',
      value: unavailable ? '—' : formatNumber(overdueProjects, 0),
      subtitle: unavailable ? 'No data available' : 'Past due date',
      icon: WarningAmberIcon,
      statusColor: !unavailable && overdueProjects > 0 ? ('error' as const) : undefined,
      onClick: () => navigate('/projects?due=overdue'),
    },
  ];

  const rowTwoCards = [
    {
      title: 'Completed Projects',
      value: unavailable ? '—' : formatNumber(completedThisMonth, 0),
      subtitle: unavailable ? 'No data available' : 'Completed this month',
      icon: TaskAltIcon,
      statusColor: !unavailable && completedThisMonth > 0 ? ('success' as const) : undefined,
      onClick: () =>
        navigate('/projects?execution_status=completed&lifecycle=completed&completed=month'),
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
      subtitle: unavailable ? 'No data available' : 'Approved productive',
      icon: TimelapseIcon,
      onClick: () => navigate('/reports?tab=productive-hours'),
    },
    {
      title: 'Archived Projects',
      value: unavailable ? '—' : formatNumber(summary?.archived_projects ?? 0, 0),
      subtitle: unavailable ? 'No data available' : 'Archived portfolio',
      icon: Inventory2OutlinedIcon,
      onClick: () => navigate('/projects?lifecycle=archived'),
    },
    {
      title: 'Non-Productive Hours',
      value: unavailable ? '—' : formatNumber(npHoursThisMonth),
      subtitle: unavailable ? 'No data available' : 'Approved NP this month',
      icon: DoNotDisturbIcon,
      onClick: () => navigate('/reports?tab=np-hours'),
    },
  ];

  return (
    <Box sx={{ maxWidth: 1440, mx: 'auto', px: { xs: 0, sm: 0.5 } }}>
      <DashboardHeader
        onNewProject={() => navigate('/projects')}
        onTimesheet={() => navigate('/timesheets')}
        onCustomer={() => navigate('/admin/customers')}
        onUser={() => navigate('/admin/users')}
      />

      <Box sx={{ mb: 2.5 }}>
        <ContentCard>
          <FormControl sx={{ minWidth: 220 }}>
            <InputLabel>Project Stage</InputLabel>
            <Select
              label="Project Stage"
              value={projectStageFilter}
              onChange={(event) =>
                setProjectStageFilter(event.target.value as ProjectStage | 'all')
              }
            >
              <MenuItem value="all">All Stages</MenuItem>
              {(
                Object.entries(PROJECT_STAGE_LABELS) as Array<[ProjectStage, string]>
              ).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </ContentCard>
      </Box>

      <WidgetErrorBoundary title="KPI cards">
        <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
          {rowOneCards.map((card) => (
            <Grid size={{ xs: 12, sm: 6, lg: 3 }} key={card.title}>
              <ActionKpiCard {...card} />
            </Grid>
          ))}
        </Grid>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              sm: 'repeat(2, 1fr)',
              md: 'repeat(3, 1fr)',
              lg: 'repeat(5, 1fr)',
            },
            gap: 2.5,
            mb: 4,
          }}
        >
          {rowTwoCards.map((card) => (
            <ActionKpiCard key={card.title} {...card} />
          ))}
        </Box>
      </WidgetErrorBoundary>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, xl: 8 }}>
          <WidgetErrorBoundary title="projects requiring attention">
            <DashboardSection
              title="Projects Requiring Attention"
              subtitle="Overdue, due within 7 days, on hold, or blocked"
            >
              {unavailable || !summary?.attention_projects?.length ? (
                <Typography variant="body2" color="text.secondary">
                  No data available
                </Typography>
              ) : (
                <ProjectsAttentionTable rows={summary.attention_projects} />
              )}
            </DashboardSection>
          </WidgetErrorBoundary>
        </Grid>
        <Grid size={{ xs: 12, xl: 4 }}>
          <WidgetErrorBoundary title="non-productive hours">
            <NpHoursPanel panel={summary?.np_hours_panel} />
          </WidgetErrorBoundary>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, lg: 6 }}>
          <WidgetErrorBoundary title="my tasks">
            <DashboardSection
              title="My Tasks"
              subtitle="Milestones, reviews, and approvals assigned to you"
            >
              {unavailable ? (
                <Typography variant="body2" color="text.secondary">
                  No data available
                </Typography>
              ) : (
                <MyTasksWidget tasks={summary.my_tasks ?? EMPTY_TASKS} />
              )}
            </DashboardSection>
          </WidgetErrorBoundary>
        </Grid>
        <Grid size={{ xs: 12, lg: 6 }}>
          <WidgetErrorBoundary title="recent activity">
            <DashboardSection title="Recent Activity" subtitle="Latest engineering updates">
              {unavailable || !summary?.recent_activity?.length ? (
                <Typography variant="body2" color="text.secondary">
                  No data available
                </Typography>
              ) : (
                <RecentActivityWidget activities={summary.recent_activity} />
              )}
            </DashboardSection>
          </WidgetErrorBoundary>
        </Grid>
      </Grid>
    </Box>
  );
}
