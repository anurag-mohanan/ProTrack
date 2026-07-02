import { Box } from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import ScheduleIcon from '@mui/icons-material/Schedule';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import TimerIcon from '@mui/icons-material/Timer';
import ArchiveIcon from '@mui/icons-material/Archive';
import PendingActionsIcon from '@mui/icons-material/PendingActions';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { formatNumber } from '../../utils/format';
import { ActionKpiCard } from './DashboardCards';

const kpiGridSx = {
  display: 'grid',
  gridTemplateColumns: {
    xs: '1fr',
    sm: 'repeat(2, 1fr)',
    lg: 'repeat(4, 1fr)',
  },
  gap: 2,
};

interface BuildOperationalKpisOptions {
  summary: DashboardSummary | undefined;
  unavailable: boolean;
  navigate: NavigateFunction;
  includeOperationalRow?: boolean;
}

export function buildOperationalKpis({
  summary,
  unavailable,
  navigate,
  includeOperationalRow = true,
}: BuildOperationalKpisOptions) {
  const rowOne = [
    {
      title: 'Active Projects',
      value: unavailable
        ? '—'
        : formatNumber(summary!.being_worked_on_projects ?? summary!.in_progress_projects ?? 0, 0),
      subtitle: 'Currently being worked on',
      icon: FolderOpenIcon,
      statusColor: !unavailable && (summary!.being_worked_on_projects ?? 0) > 0 ? ('primary' as const) : undefined,
      onClick: () => navigate('/projects?execution_status=currently_being_worked_on'),
    },
    {
      title: 'Projects On Hold',
      value: unavailable ? '—' : formatNumber(summary!.on_hold_projects, 0),
      subtitle: 'Work paused',
      icon: PauseCircleIcon,
      onClick: () => navigate('/projects?execution_status=on_hold'),
    },
    {
      title: 'Due This Week',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      subtitle: 'Due within 7 days',
      icon: ScheduleIcon,
      statusColor: !unavailable && (summary!.projects_due_this_week ?? 0) > 0 ? ('warning' as const) : undefined,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Overdue Projects',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      subtitle: 'Past due date',
      icon: WarningAmberIcon,
      statusColor: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? ('error' as const) : undefined,
      onClick: () => navigate('/projects?due=overdue'),
    },
  ];

  const rowTwo = [
    {
      title: 'Completed This Month',
      value: unavailable ? '—' : formatNumber(summary!.completed_this_month ?? 0, 0),
      subtitle: 'Completed this month',
      icon: TaskAltIcon,
      statusColor: !unavailable && (summary!.completed_this_month ?? 0) > 0 ? ('success' as const) : undefined,
      onClick: () => navigate('/projects?execution_status=completed&lifecycle=completed&completed=month'),
    },
    {
      title: 'Total Quoted Hours',
      value: unavailable ? '—' : formatNumber(summary!.total_quoted_hours_active ?? 0, 1),
      subtitle: 'Active projects',
      icon: ScheduleIcon,
      onClick: () => navigate('/projects?lifecycle=active'),
    },
    {
      title: 'Total Actual Hours',
      value: unavailable ? '—' : formatNumber(summary!.total_actual_hours_productive ?? 0, 1),
      subtitle: 'Approved productive hours',
      icon: TimerIcon,
      onClick: () => navigate('/reports'),
    },
    {
      title: 'Archived Projects',
      value: unavailable ? '—' : formatNumber(summary!.archived_projects ?? 0, 0),
      subtitle: 'Archived portfolio',
      icon: ArchiveIcon,
      onClick: () => navigate('/projects?lifecycle=archived'),
    },
  ];

  const metrics = summary?.operational_metrics;
  const rowThree = includeOperationalRow
    ? [
        {
          title: 'Pending Timesheets',
          value: unavailable ? '—' : formatNumber(metrics?.pending_timesheet_approvals ?? 0, 0),
          subtitle: 'Awaiting approval',
          icon: PendingActionsIcon,
          onClick: () => navigate('/timesheets'),
        },
        {
          title: 'Pending Project Approvals',
          value: unavailable ? '—' : formatNumber(metrics?.pending_project_approvals ?? 0, 0),
          subtitle: 'Projects on hold',
          icon: PauseCircleIcon,
          onClick: () => navigate('/projects?execution_status=on_hold'),
        },
        {
          title: 'Pending Imports',
          value: unavailable ? '—' : formatNumber(metrics?.pending_import_jobs ?? 0, 0),
          subtitle: 'Import jobs in progress',
          icon: UploadFileIcon,
          onClick: () => navigate('/admin/imports/historical-timesheets'),
        },
      ]
    : [];

  return { rowOne, rowTwo, rowThree, kpiGridSx };
}

export function OperationalKpiGrid({
  rowOne,
  rowTwo,
  rowThree,
}: {
  rowOne: Parameters<typeof ActionKpiCard>[0][];
  rowTwo: Parameters<typeof ActionKpiCard>[0][];
  rowThree: Parameters<typeof ActionKpiCard>[0][];
}) {
  return (
    <>
      <Box sx={{ ...kpiGridSx, mb: 2 }}>
        {rowOne.map((card) => (
          <ActionKpiCard key={card.title} {...card} />
        ))}
      </Box>
      <Box sx={{ ...kpiGridSx, mb: rowThree.length ? 2 : 3 }}>
        {rowTwo.map((card) => (
          <ActionKpiCard key={card.title} {...card} />
        ))}
      </Box>
      {rowThree.length ? (
        <Box sx={{ ...kpiGridSx, mb: 3 }}>
          {rowThree.map((card) => (
            <ActionKpiCard key={card.title} {...card} />
          ))}
        </Box>
      ) : null}
    </>
  );
}
