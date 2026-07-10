import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ScheduleIcon from '@mui/icons-material/Schedule';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import { Box } from '@mui/material';
import { formatNumber } from '../../../utils/format';
import type { ProjectQuickFilter, ProjectPortfolioMetrics } from '../../../utils/projectCommandCenter';
import { KpiMetricCard } from '../../ui/design-system/KpiMetricCard';
import { ProjectHoursPerformanceCard } from './ProjectHoursPerformanceCard';

interface ProjectKpiBarProps {
  metrics?: ProjectPortfolioMetrics;
  loading?: boolean;
  activeFilter?: ProjectQuickFilter;
  onFilter: (filter: ProjectQuickFilter) => void;
}

export function ProjectKpiBar({
  metrics,
  loading,
  activeFilter = 'none',
  onFilter,
}: ProjectKpiBarProps) {
  const unavailable = loading || !metrics;

  const countKpis = [
    {
      key: 'active' as const,
      title: 'Active Projects',
      value: unavailable ? '—' : formatNumber(metrics!.liveCount, 0),
      icon: FolderOpenIcon,
      accent: !unavailable && metrics!.liveCount > 0 ? ('primary' as const) : undefined,
      onClick: () => onFilter('active'),
    },
    {
      key: 'due_week' as const,
      title: 'Due This Week',
      value: unavailable ? '—' : formatNumber(metrics!.dueThisWeekCount, 0),
      icon: ScheduleIcon,
      accent: !unavailable && metrics!.dueThisWeekCount > 0 ? ('warning' as const) : undefined,
      onClick: () => onFilter('due_week'),
    },
    {
      key: 'overdue' as const,
      title: 'Overdue',
      value: unavailable ? '—' : formatNumber(metrics!.overdueCount, 0),
      icon: WarningAmberIcon,
      accent: !unavailable && metrics!.overdueCount > 0 ? ('error' as const) : undefined,
      onClick: () => onFilter('overdue'),
    },
    {
      key: 'completed_month' as const,
      title: 'Completed',
      value: unavailable ? '—' : formatNumber(metrics!.completedThisMonthCount, 0),
      icon: TaskAltIcon,
      accent: !unavailable && metrics!.completedThisMonthCount > 0 ? ('success' as const) : undefined,
      onClick: () => onFilter('completed_month'),
    },
  ];

  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'stretch',
        gap: 0.75,
        mb: 0.75,
      }}
    >
      {countKpis.map((kpi) => (
        <Box key={kpi.key} sx={{ flex: '1 1 140px', maxWidth: 168, minWidth: 120 }}>
          <KpiMetricCard
            title={kpi.title}
            value={kpi.value}
            icon={kpi.icon}
            accent={kpi.accent}
            dense
            onClick={kpi.onClick}
            selected={activeFilter === kpi.key}
          />
        </Box>
      ))}
      <Box sx={{ flex: '0 0 auto' }}>
        <ProjectHoursPerformanceCard
          quotedHours={metrics?.quotedHours}
          actualHours={metrics?.actualHours}
          loading={loading}
        />
      </Box>
    </Box>
  );
}
