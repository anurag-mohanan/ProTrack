import { Box } from '@mui/material';
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded';
import DomainRoundedIcon from '@mui/icons-material/DomainRounded';
import FolderOpenRoundedIcon from '@mui/icons-material/FolderOpenRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import HandymanRoundedIcon from '@mui/icons-material/HandymanRounded';
import PauseCircleOutlineRoundedIcon from '@mui/icons-material/PauseCircleOutlineRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import SpeedRoundedIcon from '@mui/icons-material/SpeedRounded';
import TimerRoundedIcon from '@mui/icons-material/TimerRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import type { KpiAccent } from '../ui/design-system/KpiMetricCard';
import { formatNumber } from '../../utils/format';
import {
  activeCustomerCount,
  availableCapacityHours,
  designerUtilizationPercent,
  hoursUtilizationPercent,
  STABLE_TREND,
  surfacerUtilizationPercent,
  teamProductivityPercent,
} from '../../utils/dashboardKpiMetrics';
import { DashboardKpiCard, type DashboardKpiTrend } from './DashboardKpiCard';

export interface DashboardKpiItem {
  title: string;
  value: string;
  icon: typeof FolderOpenRoundedIcon;
  accent?: KpiAccent;
  trend?: DashboardKpiTrend;
  destination?: string;
  onClick?: () => void;
}

export interface DashboardKpiSection {
  title: string;
  cards: DashboardKpiItem[];
}

interface BuildExecutiveKpisOptions {
  summary: DashboardSummary | undefined;
  unavailable: boolean;
  navigate: NavigateFunction;
}

function trendSignal(value: number, direction: 'up' | 'down' = 'up'): DashboardKpiTrend {
  if (value === 0) return STABLE_TREND;
  const prefix = direction === 'up' ? '+' : '-';
  return { value: `${prefix}${formatNumber(value, 0)}`, direction };
}

export function buildExecutiveKpiSections({
  summary,
  unavailable,
  navigate,
}: BuildExecutiveKpisOptions): DashboardKpiSection[] {
  const dash = (value: string) => (unavailable ? '—' : value);
  const n = (value: number, decimals = 0) => dash(formatNumber(value, decimals));

  const active = summary?.active_projects ?? 0;
  const dueWeek = summary?.projects_due_this_week ?? 0;
  const overdue = summary?.overdue_projects ?? 0;
  const onHold = summary?.on_hold_projects ?? 0;
  const completedMonth = summary?.completed_this_month ?? 0;
  const quoted = summary?.total_quoted_hours_active ?? 0;
  const actual = summary?.total_actual_hours_productive ?? 0;
  const utilPct = hoursUtilizationPercent(summary);
  const capacityHrs = availableCapacityHours(summary);
  const customers = activeCustomerCount(summary);
  const inProgress = summary?.being_worked_on_projects ?? summary?.in_progress_projects ?? 0;
  const designerUtil = designerUtilizationPercent(summary);
  const surfacerUtil = surfacerUtilizationPercent(summary);
  const productivity = teamProductivityPercent(summary);

  return [
    {
      title: 'Project Health',
      cards: [
        {
          title: 'Active Projects',
          value: n(active, 0),
          icon: FolderOpenRoundedIcon,
          accent: active > 0 ? 'primary' : undefined,
          trend: STABLE_TREND,
          onClick: () => navigate('/projects?lifecycle=active'),
        },
        {
          title: 'Due This Week',
          value: n(dueWeek, 0),
          icon: ScheduleRoundedIcon,
          accent: dueWeek > 0 ? 'warning' : undefined,
          trend: trendSignal(dueWeek),
          onClick: () => navigate('/projects?due=week'),
        },
        {
          title: 'Overdue',
          value: n(overdue, 0),
          icon: WarningAmberRoundedIcon,
          accent: overdue > 0 ? 'error' : undefined,
          trend: overdue > 0 ? trendSignal(overdue) : STABLE_TREND,
          onClick: () => navigate('/projects?due=overdue'),
        },
        {
          title: 'On Hold',
          value: n(onHold, 0),
          icon: PauseCircleOutlineRoundedIcon,
          accent: onHold > 0 ? 'warning' : undefined,
          trend: STABLE_TREND,
          onClick: () => navigate('/projects?execution_status=on_hold'),
        },
        {
          title: 'Completed',
          value: n(completedMonth, 0),
          icon: CheckCircleOutlineRoundedIcon,
          accent: completedMonth > 0 ? 'success' : undefined,
          trend: completedMonth > 0 ? trendSignal(completedMonth) : STABLE_TREND,
          onClick: () => navigate('/projects?completed=month'),
        },
      ],
    },
    {
      title: 'Post-Completion Work',
      cards: [
        {
          title: 'Additional Work',
          value: n(summary?.completed_with_additional_work ?? 0, 0),
          icon: HandymanRoundedIcon,
          accent: (summary?.completed_with_additional_work ?? 0) > 0 ? 'warning' : undefined,
          trend: STABLE_TREND,
          onClick: () => navigate('/projects?lifecycle=completed'),
        },
        {
          title: 'Rework Projects',
          value: n(summary?.completed_with_rework ?? 0, 0),
          icon: WarningAmberRoundedIcon,
          accent: (summary?.completed_with_rework ?? 0) > 0 ? 'error' : undefined,
          trend: STABLE_TREND,
          onClick: () => navigate('/projects?lifecycle=completed'),
        },
        {
          title: 'Hours After Completion',
          value: n(summary?.post_completion_hours_this_month ?? 0, 1),
          icon: TimerRoundedIcon,
          accent: 'info',
          trend: STABLE_TREND,
          onClick: () => navigate('/reports?tab=project-hours'),
        },
        {
          title: 'Customers With Rework',
          value: n(summary?.customers_with_rework ?? 0, 0),
          icon: DomainRoundedIcon,
          accent: (summary?.customers_with_rework ?? 0) > 0 ? 'warning' : undefined,
          trend: STABLE_TREND,
          onClick: () => navigate('/reports?tab=customer'),
        },
        {
          title: 'High Post-Completion',
          value: n(summary?.projects_high_post_completion_hours ?? 0, 0),
          icon: WarningAmberRoundedIcon,
          accent: (summary?.projects_high_post_completion_hours ?? 0) > 0 ? 'error' : undefined,
          trend: STABLE_TREND,
          onClick: () => navigate('/reports?tab=project-hours'),
        },
      ],
    },
    {
      title: 'Engineering Performance',
      cards: [
        {
          title: 'Quoted Hours',
          value: n(quoted, 0),
          icon: TimerRoundedIcon,
          accent: 'info',
          trend: STABLE_TREND,
          onClick: () => navigate('/reports?tab=project-hours'),
        },
        {
          title: 'Actual Hours',
          value: n(actual, 0),
          icon: TimerRoundedIcon,
          accent: 'primary',
          trend: STABLE_TREND,
          onClick: () => navigate('/reports?tab=project-hours'),
        },
        {
          title: 'Utilization',
          value: dash(`${utilPct}%`),
          icon: SpeedRoundedIcon,
          accent: utilPct > 100 ? 'error' : utilPct >= 90 ? 'warning' : 'success',
          trend: STABLE_TREND,
          onClick: () => navigate('/resource-planning'),
        },
        {
          title: 'Available Capacity',
          value: n(capacityHrs, 0),
          icon: GroupsRoundedIcon,
          accent: 'success',
          trend: STABLE_TREND,
          onClick: () => navigate('/resource-planning'),
        },
      ],
    },
    {
      title: 'Business Snapshot',
      cards: [
        {
          title: 'Active Customers',
          value: n(customers, 0),
          icon: DomainRoundedIcon,
          accent: 'info',
          trend: STABLE_TREND,
          onClick: () => navigate('/admin/customers'),
        },
        {
          title: 'In Progress',
          value: n(inProgress, 0),
          icon: TrendingUpRoundedIcon,
          accent: 'primary',
          trend: STABLE_TREND,
          onClick: () => navigate('/projects?execution_status=currently_being_worked_on'),
        },
        {
          title: 'Delivered',
          value: n(completedMonth, 0),
          icon: CheckCircleOutlineRoundedIcon,
          accent: 'success',
          trend: STABLE_TREND,
          onClick: () => navigate('/projects?completed=month'),
        },
        {
          title: 'Designers Util',
          value: dash(`${designerUtil}%`),
          icon: GroupsRoundedIcon,
          accent: designerUtil >= 90 ? 'error' : designerUtil >= 75 ? 'warning' : 'success',
          trend: STABLE_TREND,
          onClick: () => navigate('/workload'),
        },
        {
          title: 'Surfacers Util',
          value: dash(`${surfacerUtil}%`),
          icon: HandymanRoundedIcon,
          accent: surfacerUtil >= 90 ? 'error' : surfacerUtil >= 75 ? 'warning' : 'success',
          trend: STABLE_TREND,
          onClick: () => navigate('/workload'),
        },
        {
          title: 'Engineering Productivity',
          value: dash(`${productivity}%`),
          icon: SpeedRoundedIcon,
          accent: productivity >= 80 ? 'success' : 'warning',
          trend: STABLE_TREND,
          onClick: () => navigate('/reports'),
        },
      ],
    },
  ];
}

export function buildFlatKpiSections(cards: DashboardKpiItem[]): DashboardKpiSection[] {
  return [{ title: 'Overview', cards }];
}

const kpiGridSx = {
  display: 'grid',
  gridTemplateColumns: {
    xs: 'repeat(2, minmax(0, 1fr))',
    sm: 'repeat(3, minmax(0, 1fr))',
    md: 'repeat(4, minmax(0, 1fr))',
    lg: 'repeat(5, minmax(0, 1fr))',
    xl: 'repeat(6, minmax(180px, 1fr))',
  },
  gap: 1,
};

export function ExecutiveKpiGrid({
  sections,
  cards,
}: {
  sections?: DashboardKpiSection[];
  cards?: DashboardKpiItem[];
}) {
  const flatCards = cards ?? sections?.flatMap((section) => section.cards) ?? [];
  return (
    <Box sx={{ mb: 1 }}>
      <Box sx={kpiGridSx}>
        {flatCards.map((card) => (
          <DashboardKpiCard key={card.title} {...card} />
        ))}
      </Box>
    </Box>
  );
}

/** @deprecated Use buildExecutiveKpiSections */
export function buildExecutiveKpis(options: BuildExecutiveKpisOptions): DashboardKpiItem[] {
  return buildExecutiveKpiSections(options).flatMap((section) => section.cards);
}
