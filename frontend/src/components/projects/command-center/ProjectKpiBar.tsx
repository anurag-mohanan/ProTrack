import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ScheduleIcon from '@mui/icons-material/Schedule';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import TimerIcon from '@mui/icons-material/Timer';
import { Box } from '@mui/material';
import type { DashboardSummary } from '../../../types';
import { formatNumber } from '../../../utils/format';
import type { ProjectQuickFilter } from '../../../utils/projectCommandCenter';
import { KpiMetricCard } from '../../ui/design-system/KpiMetricCard';

interface ProjectKpiBarProps {
  summary: DashboardSummary | undefined;
  loading?: boolean;
  activeFilter?: ProjectQuickFilter;
  onFilter: (filter: ProjectQuickFilter) => void;
}

export function ProjectKpiBar({
  summary,
  loading,
  activeFilter = 'none',
  onFilter,
}: ProjectKpiBarProps) {
  const unavailable = loading || !summary;

  const kpis = [
    {
      key: 'active' as const,
      title: 'Active Projects',
      value: unavailable ? '—' : formatNumber(summary!.active_projects ?? 0, 0),
      subtitle: 'Live portfolio',
      icon: FolderOpenIcon,
      accent: !unavailable && (summary!.active_projects ?? 0) > 0 ? ('primary' as const) : undefined,
      onClick: () => onFilter('active'),
    },
    {
      key: 'due_week' as const,
      title: 'Due This Week',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      subtitle: 'Due Mon–Sun',
      icon: ScheduleIcon,
      accent: !unavailable && (summary!.projects_due_this_week ?? 0) > 0 ? ('warning' as const) : undefined,
      onClick: () => onFilter('due_week'),
    },
    {
      key: 'overdue' as const,
      title: 'Overdue',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      subtitle: 'Past due',
      icon: WarningAmberIcon,
      accent: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? ('error' as const) : undefined,
      onClick: () => onFilter('overdue'),
    },
    {
      key: 'completed_month' as const,
      title: 'Completed This Month',
      value: unavailable ? '—' : formatNumber(summary!.completed_this_month ?? 0, 0),
      subtitle: 'Delivered',
      icon: TaskAltIcon,
      accent: !unavailable && (summary!.completed_this_month ?? 0) > 0 ? ('success' as const) : undefined,
      onClick: () => onFilter('completed_month'),
    },
    {
      key: 'quoted' as const,
      title: 'Quoted Hours',
      value: unavailable ? '—' : formatNumber(summary!.total_quoted_hours_active ?? 0, 1),
      subtitle: 'Active projects',
      icon: ScheduleIcon,
    },
    {
      key: 'actual' as const,
      title: 'Actual Hours',
      value: unavailable ? '—' : formatNumber(summary!.total_actual_hours_productive ?? 0, 1),
      subtitle: 'Approved hours',
      icon: TimerIcon,
    },
  ];

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: {
          xs: 'repeat(2, minmax(0, 1fr))',
          md: 'repeat(3, minmax(0, 1fr))',
          xl: 'repeat(6, minmax(200px, 1fr))',
        },
        gap: 3,
        mb: 3,
      }}
    >
      {kpis.map((kpi) => (
        <KpiMetricCard
          key={kpi.title}
          title={kpi.title}
          value={kpi.value}
          subtitle={kpi.subtitle}
          icon={kpi.icon}
          accent={kpi.accent}
          compact
          onClick={kpi.onClick}
          selected={kpi.key !== 'quoted' && kpi.key !== 'actual' && activeFilter === kpi.key}
        />
      ))}
    </Box>
  );
}
