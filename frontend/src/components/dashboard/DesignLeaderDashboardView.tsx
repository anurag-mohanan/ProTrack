import FolderOpenRoundedIcon from '@mui/icons-material/FolderOpenRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import PendingActionsRoundedIcon from '@mui/icons-material/PendingActionsRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import TaskAltRoundedIcon from '@mui/icons-material/TaskAltRounded';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { formatNumber } from '../../utils/format';
import { STABLE_TREND } from '../../utils/dashboardKpiMetrics';
import { buildFlatKpiSections, ExecutiveKpiGrid } from './ExecutiveKpiGrid';

interface DesignLeaderDashboardViewProps {
  summary: DashboardSummary | undefined;
  unavailable: boolean;
  navigate: NavigateFunction;
}

export function DesignLeaderDashboardView({
  summary,
  unavailable,
  navigate,
}: DesignLeaderDashboardViewProps) {
  const pendingReviews = summary?.my_tasks.pending_reviews?.length ?? 0;
  const pendingTimesheets = summary?.my_tasks.pending_approvals.length ?? 0;
  const teamUtilization = summary?.team_summary?.[0];

  const cards = [
    {
      title: 'Team Projects',
      value: unavailable ? '—' : formatNumber(summary!.active_projects ?? 0, 0),
      icon: FolderOpenRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Due This Week',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      icon: ScheduleRoundedIcon,
      accent: !unavailable && (summary!.projects_due_this_week ?? 0) > 0 ? ('warning' as const) : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=week'),
    },
    {
      title: 'Overdue',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      icon: WarningAmberRoundedIcon,
      accent: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? ('error' as const) : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Pending Reviews',
      value: unavailable ? '—' : formatNumber(pendingReviews, 0),
      icon: TaskAltRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Pending Timesheets',
      value: unavailable ? '—' : formatNumber(pendingTimesheets, 0),
      icon: PendingActionsRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Team Utilization',
      value: unavailable
        ? '—'
        : teamUtilization
          ? `${formatNumber(teamUtilization.actual_hours, 0)}h`
          : '—',
      icon: GroupsRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/workload'),
    },
  ];

  return <ExecutiveKpiGrid sections={buildFlatKpiSections(cards)} />;
}
