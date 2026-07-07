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
import { STABLE_TREND } from '../../utils/dashboardKpiMetrics';
import { buildFlatKpiSections, ExecutiveKpiGrid } from './ExecutiveKpiGrid';

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
      icon: FolderOpenRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Current Project',
      value: unavailable ? '—' : currentProjectLabel,
      icon: BuildRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects'),
    },
    {
      title: metrics?.task_label ?? 'Milestones',
      value: unavailable ? '—' : formatNumber(metrics?.assigned_milestones ?? 0, 0),
      icon: TaskAltRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Due Soon',
      value: unavailable ? '—' : formatNumber(metrics?.upcoming_due_dates ?? 0, 0),
      icon: EventRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Hours This Week',
      value: unavailable ? '—' : formatNumber(metrics?.hours_logged_this_week ?? 0, 1),
      icon: TimerRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Pending Timesheets',
      value: unavailable ? '—' : formatNumber(metrics?.pending_timesheet_submissions ?? 0, 0),
      icon: PendingActionsRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'My Tasks',
      value: unavailable
        ? '—'
        : formatNumber(
            (summary?.my_tasks.upcoming_milestones.length ?? 0) +
              (summary?.my_tasks.pending_reviews?.length ?? 0),
            0,
          ),
      icon: ScheduleRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/timesheets'),
    },
  ];

  return <ExecutiveKpiGrid sections={buildFlatKpiSections(cards)} />;
}
