import { Box } from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import ScheduleIcon from '@mui/icons-material/Schedule';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import PendingActionsIcon from '@mui/icons-material/PendingActions';
import GroupsIcon from '@mui/icons-material/Groups';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { formatNumber } from '../../utils/format';
import { ActionKpiCard } from './DashboardCards';

const kpiGridSx = {
  display: 'grid',
  gridTemplateColumns: {
    xs: '1fr',
    sm: 'repeat(2, 1fr)',
    lg: 'repeat(3, 1fr)',
  },
  gap: 2,
  mb: 3,
};

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
      icon: FolderOpenIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Due This Week',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      subtitle: 'Team deadlines',
      icon: ScheduleIcon,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Overdue Projects',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      subtitle: 'Needs attention',
      icon: WarningAmberIcon,
      statusColor: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? ('error' as const) : undefined,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Pending Reviews',
      value: unavailable ? '—' : formatNumber(pendingReviews, 0),
      subtitle: 'Milestones awaiting review',
      icon: TaskAltIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Pending Timesheets',
      value: unavailable ? '—' : formatNumber(pendingTimesheets, 0),
      subtitle: 'Team submissions',
      icon: PendingActionsIcon,
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
      icon: GroupsIcon,
      onClick: () => navigate('/workload'),
    },
  ];

  return (
    <Box sx={kpiGridSx}>
      {cards.map((card) => (
        <ActionKpiCard key={card.title} {...card} />
      ))}
    </Box>
  );
}
