import { Box } from '@mui/material';
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded';
import FolderOpenRoundedIcon from '@mui/icons-material/FolderOpenRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import SpeedRoundedIcon from '@mui/icons-material/SpeedRounded';
import TimerRoundedIcon from '@mui/icons-material/TimerRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import { formatNumber } from '../../utils/format';
import { ActionKpiCard } from './DashboardCards';

const kpiGridSx = {
  display: 'grid',
  gridTemplateColumns: {
    xs: '1fr',
    sm: 'repeat(2, minmax(0, 1fr))',
    lg: 'repeat(4, minmax(0, 1fr))',
  },
  gap: 2.5,
  mb: 3,
};

interface BuildExecutiveKpisOptions {
  summary: DashboardSummary | undefined;
  unavailable: boolean;
  navigate: NavigateFunction;
}

function averageTeamUtilization(summary: DashboardSummary | undefined): number {
  const teams = summary?.team_summary ?? [];
  if (!teams.length) return 0;
  const total = teams.reduce((sum, row) => {
    const capacity = Number(row.actual_hours) + Number(row.available_capacity_hours);
    if (capacity <= 0) return sum;
    return sum + (Number(row.actual_hours) / capacity) * 100;
  }, 0);
  return Math.round(total / teams.length);
}

export function buildExecutiveKpis({ summary, unavailable, navigate }: BuildExecutiveKpisOptions) {
  const designersAvailable = summary?.designer_availability_summary?.available ?? 0;
  const utilization = averageTeamUtilization(summary);

  return [
    {
      title: 'Active Projects',
      value: unavailable ? '—' : formatNumber(summary!.active_projects ?? 0, 0),
      subtitle: 'In progress or on hold',
      icon: FolderOpenRoundedIcon,
      statusColor: !unavailable && (summary!.active_projects ?? 0) > 0 ? ('primary' as const) : undefined,
      onClick: () => navigate('/projects?lifecycle=active'),
    },
    {
      title: 'Due This Week',
      value: unavailable ? '—' : formatNumber(summary!.projects_due_this_week ?? 0, 0),
      subtitle: 'Deliveries within 7 days',
      icon: ScheduleRoundedIcon,
      statusColor: !unavailable && (summary!.projects_due_this_week ?? 0) > 0 ? ('warning' as const) : undefined,
      trend: !unavailable && (summary!.projects_due_this_week ?? 0) > 0
        ? { value: 'Upcoming', direction: 'up' as const }
        : undefined,
      onClick: () => navigate('/projects?due=7days'),
    },
    {
      title: 'Delayed Projects',
      value: unavailable ? '—' : formatNumber(summary!.overdue_projects ?? 0, 0),
      subtitle: 'Past due date',
      icon: WarningAmberRoundedIcon,
      statusColor: !unavailable && (summary!.overdue_projects ?? 0) > 0 ? ('error' as const) : undefined,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Released This Month',
      value: unavailable ? '—' : formatNumber(summary!.completed_this_month ?? 0, 0),
      subtitle: 'Completed projects',
      icon: CheckCircleOutlineRoundedIcon,
      statusColor: !unavailable && (summary!.completed_this_month ?? 0) > 0 ? ('success' as const) : undefined,
      onClick: () => navigate('/projects?lifecycle=completed'),
    },
    {
      title: 'Designers Available',
      value: unavailable ? '—' : formatNumber(designersAvailable, 0),
      subtitle: 'Ready for assignment today',
      icon: GroupsRoundedIcon,
      statusColor: !unavailable && designersAvailable > 0 ? ('success' as const) : undefined,
      onClick: () => navigate('/workload'),
    },
    {
      title: 'Hours Logged Today',
      value: unavailable ? '—' : formatNumber(summary!.hours_logged_today ?? 0, 1),
      subtitle: 'Across all designers',
      icon: TimerRoundedIcon,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Resource Utilization',
      value: unavailable ? '—' : `${utilization}%`,
      subtitle: 'Average team loading',
      icon: SpeedRoundedIcon,
      statusColor:
        !unavailable && utilization >= 90
          ? ('error' as const)
          : utilization >= 75
            ? ('warning' as const)
            : ('success' as const),
      onClick: () => navigate('/resource-planning'),
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
