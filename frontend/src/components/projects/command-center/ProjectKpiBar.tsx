import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ScheduleIcon from '@mui/icons-material/Schedule';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import ArchiveIcon from '@mui/icons-material/Archive';
import TimerIcon from '@mui/icons-material/Timer';
import BusinessIcon from '@mui/icons-material/Business';
import PersonIcon from '@mui/icons-material/Person';
import { Box } from '@mui/material';
import type { DashboardSummary } from '../../../types';
import { ActionKpiCard } from '../../dashboard/DashboardCards';
import { formatNumber } from '../../../utils/format';
import type { ProjectQuickFilter } from '../../../utils/projectCommandCenter';

interface ProjectKpiBarProps {
  summary: DashboardSummary | undefined;
  loading?: boolean;
  onFilter: (filter: ProjectQuickFilter) => void;
}

export function ProjectKpiBar({ summary, loading, onFilter }: ProjectKpiBarProps) {
  const unavailable = loading || !summary;

  const kpis = [
    {
      title: 'Active Projects',
      value: unavailable ? '—' : formatNumber(summary!.being_worked_on_projects ?? 0, 0),
      subtitle: 'In progress',
      icon: FolderOpenIcon,
      statusColor: !unavailable && (summary!.being_worked_on_projects ?? 0) > 0 ? ('primary' as const) : undefined,
      filter: 'in_progress' as ProjectQuickFilter,
    },
    {
      title: 'Projects On Hold',
      value: unavailable ? '—' : formatNumber(summary!.on_hold_projects, 0),
      subtitle: 'Paused work',
      icon: PauseCircleIcon,
      statusColor: !unavailable && summary!.on_hold_projects > 0 ? ('warning' as const) : undefined,
      filter: 'on_hold' as ProjectQuickFilter,
    },
    {
      title: 'Overdue Projects',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      subtitle: 'Past due date',
      icon: WarningAmberIcon,
      statusColor: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? ('error' as const) : undefined,
      filter: 'overdue' as ProjectQuickFilter,
    },
    {
      title: 'Due This Week',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      subtitle: 'Due Mon–Sun',
      icon: ScheduleIcon,
      statusColor: !unavailable && (summary!.projects_due_this_week ?? 0) > 0 ? ('warning' as const) : undefined,
      filter: 'due_week' as ProjectQuickFilter,
    },
    {
      title: 'Completed This Month',
      value: unavailable ? '—' : formatNumber(summary!.completed_this_month ?? 0, 0),
      subtitle: 'Delivered recently',
      icon: TaskAltIcon,
      statusColor: !unavailable && (summary!.completed_this_month ?? 0) > 0 ? ('success' as const) : undefined,
      filter: 'completed_month' as ProjectQuickFilter,
    },
    {
      title: 'Archived Projects',
      value: unavailable ? '—' : formatNumber(summary!.archived_projects ?? 0, 0),
      subtitle: 'Archived portfolio',
      icon: ArchiveIcon,
      filter: 'archived' as ProjectQuickFilter,
    },
    {
      title: 'Total Quoted Hours',
      value: unavailable ? '—' : formatNumber(summary!.total_quoted_hours_active ?? 0, 1),
      subtitle: 'Active projects',
      icon: ScheduleIcon,
      filter: 'active' as ProjectQuickFilter,
    },
    {
      title: 'Total Actual Hours',
      value: unavailable ? '—' : formatNumber(summary!.total_actual_hours_productive ?? 0, 1),
      subtitle: 'Approved hours',
      icon: TimerIcon,
      filter: 'none' as ProjectQuickFilter,
    },
    {
      title: 'Designers Available',
      value: unavailable
        ? '—'
        : formatNumber(summary!.designer_availability_summary?.available ?? 0, 0),
      subtitle: 'Ready for assignment',
      icon: PersonIcon,
      statusColor:
        !unavailable && (summary!.designer_availability_summary?.available ?? 0) > 0
          ? ('success' as const)
          : undefined,
      filter: 'none' as ProjectQuickFilter,
    },
    {
      title: 'Active Customers',
      value: unavailable ? '—' : formatNumber(summary!.customer_workload?.length ?? 0, 0),
      subtitle: 'With active tools',
      icon: BusinessIcon,
      filter: 'none' as ProjectQuickFilter,
    },
  ];

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: {
          xs: 'repeat(2, 1fr)',
          sm: 'repeat(3, 1fr)',
          md: 'repeat(5, 1fr)',
          xl: 'repeat(10, 1fr)',
        },
        gap: 1.5,
        mb: 2.5,
      }}
    >
      {kpis.map((kpi) => (
        <ActionKpiCard
          key={kpi.title}
          title={kpi.title}
          value={kpi.value}
          subtitle={kpi.subtitle}
          icon={kpi.icon}
          statusColor={kpi.statusColor}
          onClick={kpi.filter !== 'none' ? () => onFilter(kpi.filter) : undefined}
        />
      ))}
    </Box>
  );
}
