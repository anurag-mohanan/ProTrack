import { Box } from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import ScheduleIcon from '@mui/icons-material/Schedule';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import TimerIcon from '@mui/icons-material/Timer';
import EngineeringIcon from '@mui/icons-material/Engineering';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { formatNumber } from '../../utils/format';
import { ActionKpiCard } from './DashboardCards';

const kpiGridSx = {
  display: 'grid',
  gridTemplateColumns: {
    xs: '1fr',
    sm: 'repeat(2, minmax(0, 1fr))',
    lg: 'repeat(3, minmax(0, 1fr))',
  },
  gap: 3,
  mb: 3,
};

interface BuildExecutiveKpisOptions {
  summary: DashboardSummary | undefined;
  unavailable: boolean;
  navigate: NavigateFunction;
}

export function buildExecutiveKpis({ summary, unavailable, navigate }: BuildExecutiveKpisOptions) {
  const designersAvailable = summary?.designer_availability_summary?.available ?? 0;

  return [
    {
      title: 'Active Projects',
      value: unavailable ? '—' : formatNumber(summary!.active_projects ?? 0, 0),
      subtitle: 'In progress or on hold',
      icon: FolderOpenIcon,
      statusColor: !unavailable && (summary!.active_projects ?? 0) > 0 ? ('primary' as const) : undefined,
      onClick: () => navigate('/projects?lifecycle=active'),
    },
    {
      title: 'Projects Due This Week',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      subtitle: 'Due within 7 days',
      icon: ScheduleIcon,
      statusColor: !unavailable && (summary!.projects_due_this_week ?? 0) > 0 ? ('warning' as const) : undefined,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Delayed Projects',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      subtitle: 'Past due date',
      icon: WarningAmberIcon,
      statusColor: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? ('error' as const) : undefined,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Designers Available',
      value: unavailable ? '—' : formatNumber(designersAvailable, 0),
      subtitle: 'Ready for assignment',
      icon: GroupsOutlinedIcon,
      statusColor: !unavailable && designersAvailable > 0 ? ('success' as const) : undefined,
      onClick: () => navigate('/workload'),
    },
    {
      title: 'Hours Logged Today',
      value: unavailable ? '—' : formatNumber(summary!.hours_logged_today ?? 0, 1),
      subtitle: 'Across all designers',
      icon: TimerIcon,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Open Engineering Changes',
      value: unavailable ? '—' : formatNumber(summary!.open_engineering_changes ?? 0, 0),
      subtitle: 'Awaiting resolution',
      icon: EngineeringIcon,
      statusColor:
        !unavailable && (summary!.open_engineering_changes ?? 0) > 0 ? ('warning' as const) : undefined,
      onClick: () => navigate('/projects'),
    },
  ];
}

export function ExecutiveKpiGrid({
  cards,
}: {
  cards: Parameters<typeof ActionKpiCard>[0][];
}) {
  return (
    <Box sx={kpiGridSx}>
      {cards.map((card) => (
        <ActionKpiCard key={card.title} {...card} />
      ))}
    </Box>
  );
}
