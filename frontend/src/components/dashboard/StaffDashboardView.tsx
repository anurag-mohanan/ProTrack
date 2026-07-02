import { Box } from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import BuildIcon from '@mui/icons-material/Build';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import ScheduleIcon from '@mui/icons-material/Schedule';
import TimerIcon from '@mui/icons-material/Timer';
import PendingActionsIcon from '@mui/icons-material/PendingActions';
import EventIcon from '@mui/icons-material/Event';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { formatCellValue, formatNumber } from '../../utils/format';
import { ActionKpiCard } from './DashboardCards';

const kpiGridSx = {
  display: 'grid',
  gridTemplateColumns: {
    xs: '1fr',
    sm: 'repeat(2, 1fr)',
    lg: 'repeat(4, 1fr)',
  },
  gap: 2,
  mb: 3,
};

interface StaffDashboardViewProps {
  summary: DashboardSummary | undefined;
  unavailable: boolean;
  navigate: NavigateFunction;
}

export function StaffDashboardView({ summary, unavailable, navigate }: StaffDashboardViewProps) {
  const metrics = summary?.staff_metrics;
  const currentProjectLabel = metrics?.current_tool_number
    ? formatCellValue(metrics.current_tool_number)
    : '—';

  const cards = [
    {
      title: 'My Projects',
      value: unavailable ? '—' : formatNumber(metrics?.my_projects ?? 0, 0),
      subtitle: 'Assigned to you',
      icon: FolderOpenIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'My Current Project',
      value: unavailable ? '—' : currentProjectLabel,
      subtitle: formatCellValue(metrics?.current_part_description) || 'No active assignment',
      icon: BuildIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: metrics?.task_label ?? 'Assigned Milestones',
      value: unavailable ? '—' : formatNumber(metrics?.assigned_milestones ?? 0, 0),
      subtitle: 'Open milestones',
      icon: TaskAltIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Upcoming Due Dates',
      value: unavailable ? '—' : formatNumber(metrics?.upcoming_due_dates ?? 0, 0),
      subtitle: 'Due within 7 days',
      icon: EventIcon,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Hours Logged This Week',
      value: unavailable ? '—' : formatNumber(metrics?.hours_logged_this_week ?? 0, 1),
      subtitle: 'Approved and draft entries',
      icon: TimerIcon,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Pending Timesheet Submission',
      value: unavailable ? '—' : formatNumber(metrics?.pending_timesheet_submissions ?? 0, 0),
      subtitle: 'Draft timesheets',
      icon: PendingActionsIcon,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'My Tasks Today',
      value: unavailable
        ? '—'
        : formatNumber(
            (summary?.my_tasks.upcoming_milestones.length ?? 0) +
              (summary?.my_tasks.pending_reviews?.length ?? 0),
            0,
          ),
      subtitle: "Today's priorities",
      icon: ScheduleIcon,
      onClick: () => navigate('/timesheets'),
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
