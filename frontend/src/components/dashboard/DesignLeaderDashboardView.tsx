import FolderOpenRoundedIcon from '@mui/icons-material/FolderOpenRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import PendingActionsRoundedIcon from '@mui/icons-material/PendingActionsRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import TaskAltRoundedIcon from '@mui/icons-material/TaskAltRounded';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { formatNumber } from '../../utils/format';
import { ExecutiveKpiGrid } from './ExecutiveKpiGrid';

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
      subtitle: 'Assigned to your team',
      icon: FolderOpenRoundedIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Due This Week',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      subtitle: 'Team deadlines',
      icon: ScheduleRoundedIcon,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Overdue Projects',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      subtitle: 'Needs attention',
      icon: WarningAmberRoundedIcon,
      statusColor: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? ('error' as const) : undefined,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Pending Reviews',
      value: unavailable ? '—' : formatNumber(pendingReviews, 0),
      subtitle: 'Milestones awaiting review',
      icon: TaskAltRoundedIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Pending Timesheets',
      value: unavailable ? '—' : formatNumber(pendingTimesheets, 0),
      subtitle: 'Team submissions',
      icon: PendingActionsRoundedIcon,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Team Utilization',
      value: unavailable
        ? '—'
        : teamUtilization
          ? `${formatNumber(teamUtilization.actual_hours, 0)}h`
          : '—',
      subtitle: teamUtilization?.team_name ?? 'Current team capacity',
      icon: GroupsRoundedIcon,
      onClick: () => navigate('/workload'),
    },
  ];

  return <ExecutiveKpiGrid cards={cards} />;
}
