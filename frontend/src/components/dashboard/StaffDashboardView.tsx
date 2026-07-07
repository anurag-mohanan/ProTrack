import FolderOpenRoundedIcon from '@mui/icons-material/FolderOpenRounded';
import BuildRoundedIcon from '@mui/icons-material/BuildRounded';
import TaskAltRoundedIcon from '@mui/icons-material/TaskAltRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import TimerRoundedIcon from '@mui/icons-material/TimerRounded';
import PendingActionsRoundedIcon from '@mui/icons-material/PendingActionsRounded';
import EventRoundedIcon from '@mui/icons-material/EventRounded';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { formatCellValue, formatNumber } from '../../utils/format';
import { ExecutiveKpiGrid } from './ExecutiveKpiGrid';

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
      icon: FolderOpenRoundedIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'My Current Project',
      value: unavailable ? '—' : currentProjectLabel,
      subtitle: formatCellValue(metrics?.current_part_description) || 'No active assignment',
      icon: BuildRoundedIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: metrics?.task_label ?? 'Assigned Milestones',
      value: unavailable ? '—' : formatNumber(metrics?.assigned_milestones ?? 0, 0),
      subtitle: 'Open milestones',
      icon: TaskAltRoundedIcon,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Upcoming Due Dates',
      value: unavailable ? '—' : formatNumber(metrics?.upcoming_due_dates ?? 0, 0),
      subtitle: 'Due within 7 days',
      icon: EventRoundedIcon,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Hours Logged This Week',
      value: unavailable ? '—' : formatNumber(metrics?.hours_logged_this_week ?? 0, 1),
      subtitle: 'Approved and draft entries',
      icon: TimerRoundedIcon,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Pending Timesheet Submission',
      value: unavailable ? '—' : formatNumber(metrics?.pending_timesheet_submissions ?? 0, 0),
      subtitle: 'Draft timesheets',
      icon: PendingActionsRoundedIcon,
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
      icon: ScheduleRoundedIcon,
      onClick: () => navigate('/timesheets'),
    },
  ];

  return <ExecutiveKpiGrid cards={cards} />;
}
