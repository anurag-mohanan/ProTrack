import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded';
import CloudDoneRoundedIcon from '@mui/icons-material/CloudDoneRounded';
import DnsRoundedIcon from '@mui/icons-material/DnsRounded';
import DomainRoundedIcon from '@mui/icons-material/DomainRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import ErrorOutlineRoundedIcon from '@mui/icons-material/ErrorOutlineRounded';
import FolderOpenRoundedIcon from '@mui/icons-material/FolderOpenRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import HandymanRoundedIcon from '@mui/icons-material/HandymanRounded';
import MemoryRoundedIcon from '@mui/icons-material/MemoryRounded';
import PauseCircleOutlineRoundedIcon from '@mui/icons-material/PauseCircleOutlineRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import SpeedRoundedIcon from '@mui/icons-material/SpeedRounded';
import StorageRoundedIcon from '@mui/icons-material/StorageRounded';
import TimerRoundedIcon from '@mui/icons-material/TimerRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import type { NavigateFunction } from 'react-router-dom';
import type { DashboardSummary } from '../../types';
import type { SystemHealth } from '../../api/system';
import type { DashboardRoleGroup } from '../../utils/permissions';
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
import type { DashboardKpiItem } from './ExecutiveKpiGrid';

interface BuildRoleKpiCardsOptions {
  roleGroup: DashboardRoleGroup;
  summary: DashboardSummary | undefined;
  systemHealth: SystemHealth | undefined;
  unavailable: boolean;
  navigate: NavigateFunction;
}

function dash(value: string, unavailable: boolean) {
  return unavailable ? '—' : value;
}

function n(value: number, unavailable: boolean, decimals = 0) {
  return dash(formatNumber(value, decimals), unavailable);
}

export function buildRoleKpiCards({
  roleGroup,
  summary,
  systemHealth,
  unavailable,
  navigate,
}: BuildRoleKpiCardsOptions): DashboardKpiItem[] {
  if (roleGroup === 'admin') {
    return buildAdminKpiCards({ systemHealth, summary, unavailable, navigate });
  }
  if (roleGroup === 'staff') {
    return buildStaffKpiCards({ summary, unavailable, navigate });
  }
  if (roleGroup === 'design_leader') {
    return buildDesignLeaderKpiCards({ summary, unavailable, navigate });
  }
  return buildExecutiveKpiCards({ summary, unavailable, navigate });
}

function buildExecutiveKpiCards({
  summary,
  unavailable,
  navigate,
}: Omit<BuildRoleKpiCardsOptions, 'roleGroup' | 'systemHealth'>): DashboardKpiItem[] {
  const quoted = Number(summary?.total_quoted_hours_active ?? 0);
  const actual = Number(summary?.total_actual_hours_productive ?? 0);
  const quotedVsActual =
    quoted > 0 ? Math.round((actual / quoted) * 100) : 0;
  const highRisk = (summary?.red_projects ?? 0) + (summary?.yellow_projects ?? 0);
  const missingTs = summary?.missing_timesheets?.length ?? 0;

  return [
    {
      title: 'Active Projects',
      value: n(summary?.active_projects ?? 0, unavailable),
      icon: FolderOpenRoundedIcon,
      accent: 'primary',
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?lifecycle=active'),
    },
    {
      title: 'Due This Week',
      value: n(summary?.projects_due_this_week ?? 0, unavailable),
      icon: ScheduleRoundedIcon,
      accent: (summary?.projects_due_this_week ?? 0) > 0 ? 'warning' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=week'),
    },
    {
      title: 'Overdue',
      value: n(summary?.overdue_projects ?? 0, unavailable),
      icon: WarningAmberRoundedIcon,
      accent: (summary?.overdue_projects ?? 0) > 0 ? 'error' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'On Hold',
      value: n(summary?.on_hold_projects ?? 0, unavailable),
      icon: PauseCircleOutlineRoundedIcon,
      accent: (summary?.on_hold_projects ?? 0) > 0 ? 'warning' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?execution_status=on_hold'),
    },
    {
      title: 'Completed This Month',
      value: n(summary?.completed_this_month ?? 0, unavailable),
      icon: CheckCircleOutlineRoundedIcon,
      accent: 'success',
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?completed=month'),
    },
    {
      title: 'Quoted Hours',
      value: n(quoted, unavailable),
      icon: TimerRoundedIcon,
      accent: 'info',
      trend: STABLE_TREND,
      onClick: () => navigate('/reports?tab=project-hours'),
    },
    {
      title: 'Actual Hours',
      value: n(actual, unavailable),
      icon: TimerRoundedIcon,
      accent: 'primary',
      trend: STABLE_TREND,
      onClick: () => navigate('/reports?tab=project-hours'),
    },
    {
      title: 'Quoted vs Actual',
      value: dash(`${quotedVsActual}%`, unavailable),
      icon: SpeedRoundedIcon,
      accent: quotedVsActual > 100 ? 'error' : quotedVsActual >= 90 ? 'warning' : 'success',
      trend: STABLE_TREND,
      onClick: () => navigate('/reports?tab=project-hours'),
    },
    {
      title: 'Utilization',
      value: dash(`${hoursUtilizationPercent(summary)}%`, unavailable),
      icon: SpeedRoundedIcon,
      accent: hoursUtilizationPercent(summary) > 100 ? 'error' : 'success',
      trend: STABLE_TREND,
      onClick: () => navigate('/resource-planning'),
    },
    {
      title: 'Available Capacity',
      value: n(availableCapacityHours(summary), unavailable),
      icon: GroupsRoundedIcon,
      accent: 'success',
      trend: STABLE_TREND,
      onClick: () => navigate('/resource-planning'),
    },
    {
      title: 'Designers Util',
      value: dash(`${designerUtilizationPercent(summary)}%`, unavailable),
      icon: GroupsRoundedIcon,
      accent: designerUtilizationPercent(summary) >= 90 ? 'error' : 'success',
      trend: STABLE_TREND,
      onClick: () => navigate('/workload'),
    },
    {
      title: 'Surfacers Util',
      value: dash(`${surfacerUtilizationPercent(summary)}%`, unavailable),
      icon: HandymanRoundedIcon,
      accent: surfacerUtilizationPercent(summary) >= 90 ? 'error' : 'success',
      trend: STABLE_TREND,
      onClick: () => navigate('/workload'),
    },
    {
      title: 'Team Productivity',
      value: dash(`${teamProductivityPercent(summary)}%`, unavailable),
      icon: SpeedRoundedIcon,
      accent: 'info',
      trend: STABLE_TREND,
      onClick: () => navigate('/reports'),
    },
    {
      title: 'Missing Timesheets',
      value: n(missingTs, unavailable),
      icon: ScheduleRoundedIcon,
      accent: missingTs > 0 ? 'warning' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Late Milestones',
      value: n(summary?.late_milestones ?? 0, unavailable),
      icon: WarningAmberRoundedIcon,
      accent: (summary?.late_milestones ?? 0) > 0 ? 'error' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Active Customers',
      value: n(activeCustomerCount(summary), unavailable),
      icon: DomainRoundedIcon,
      accent: 'info',
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/customers'),
    },
    {
      title: 'In Progress',
      value: n(summary?.being_worked_on_projects ?? summary?.in_progress_projects ?? 0, unavailable),
      icon: TrendingUpRoundedIcon,
      accent: 'primary',
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?execution_status=currently_being_worked_on'),
    },
    {
      title: 'High Risk',
      value: n(highRisk, unavailable),
      icon: ErrorOutlineRoundedIcon,
      accent: highRisk > 0 ? 'error' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?health=red'),
    },
  ];
}

function buildAdminKpiCards({
  systemHealth,
  summary,
  unavailable,
  navigate,
}: Pick<BuildRoleKpiCardsOptions, 'summary' | 'systemHealth' | 'unavailable' | 'navigate'>): DashboardKpiItem[] {
  const dbOk = systemHealth?.database_status === 'ok';
  const svcOk = systemHealth?.backend_status === 'ok' && systemHealth?.api_status === 'ok';
  return [
    {
      title: 'Active Users',
      value: n(systemHealth?.active_users ?? 0, unavailable),
      icon: PeopleRoundedIcon,
      accent: 'primary',
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/users'),
    },
    {
      title: 'Database Health',
      value: dash(dbOk ? 'Healthy' : 'Check', unavailable),
      icon: DnsRoundedIcon,
      accent: dbOk ? 'success' : 'error',
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/system'),
    },
    {
      title: 'Services Status',
      value: dash(svcOk ? 'Online' : 'Degraded', unavailable),
      icon: CloudDoneRoundedIcon,
      accent: svcOk ? 'success' : 'warning',
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/system'),
    },
    {
      title: 'Import Queue',
      value: n(systemHealth?.import_queue ?? summary?.operational_metrics?.pending_import_jobs ?? 0, unavailable),
      icon: ScheduleRoundedIcon,
      accent: (systemHealth?.import_queue ?? 0) > 0 ? 'warning' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/imports/historical-timesheets'),
    },
    {
      title: 'Failed Emails',
      value: n(systemHealth?.failed_emails ?? 0, unavailable),
      icon: EmailRoundedIcon,
      accent: (systemHealth?.failed_emails ?? 0) > 0 ? 'error' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/settings/email-queue'),
    },
    {
      title: 'Pending Backups',
      value: dash(systemHealth?.last_backup ? 'Current' : 'Review', unavailable),
      icon: StorageRoundedIcon,
      accent: systemHealth?.last_backup ? 'success' : 'warning',
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/settings/backup'),
    },
    {
      title: 'Storage Usage',
      value: dash(systemHealth?.storage_usage_label ?? '—', unavailable),
      icon: MemoryRoundedIcon,
      accent: 'info',
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/system'),
    },
    {
      title: 'Recent Errors',
      value: n(systemHealth?.recent_errors?.length ?? 0, unavailable),
      icon: ErrorOutlineRoundedIcon,
      accent: (systemHealth?.recent_errors?.length ?? 0) > 0 ? 'error' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/audit/logs'),
    },
  ];
}

function buildStaffKpiCards({
  summary,
  unavailable,
  navigate,
}: Omit<BuildRoleKpiCardsOptions, 'roleGroup' | 'systemHealth'>): DashboardKpiItem[] {
  const metrics = summary?.staff_metrics;
  return [
    {
      title: 'My Projects',
      value: n(metrics?.my_projects ?? 0, unavailable),
      icon: FolderOpenRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Due Soon',
      value: n(metrics?.upcoming_due_dates ?? 0, unavailable),
      icon: ScheduleRoundedIcon,
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
      value: n(metrics?.pending_timesheet_submissions ?? 0, unavailable),
      icon: ScheduleRoundedIcon,
      accent: (metrics?.pending_timesheet_submissions ?? 0) > 0 ? 'warning' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: metrics?.task_label ?? 'Milestones',
      value: n(metrics?.assigned_milestones ?? 0, unavailable),
      icon: CheckCircleOutlineRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'My Tasks',
      value: n(
        (summary?.my_tasks.upcoming_milestones.length ?? 0) +
          (summary?.my_tasks.pending_reviews?.length ?? 0),
        unavailable,
      ),
      icon: TrendingUpRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/timesheets'),
    },
  ];
}

function buildDesignLeaderKpiCards({
  summary,
  unavailable,
  navigate,
}: Omit<BuildRoleKpiCardsOptions, 'roleGroup' | 'systemHealth'>): DashboardKpiItem[] {
  const pendingReviews = summary?.my_tasks.pending_reviews?.length ?? 0;
  const pendingTimesheets = summary?.my_tasks.pending_approvals.length ?? 0;
  return [
    {
      title: 'Team Projects',
      value: n(summary?.active_projects ?? 0, unavailable),
      icon: FolderOpenRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Due This Week',
      value: n(summary?.projects_due_this_week ?? 0, unavailable),
      icon: ScheduleRoundedIcon,
      accent: (summary?.projects_due_this_week ?? 0) > 0 ? 'warning' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=week'),
    },
    {
      title: 'Overdue',
      value: n(summary?.overdue_projects ?? 0, unavailable),
      icon: WarningAmberRoundedIcon,
      accent: (summary?.overdue_projects ?? 0) > 0 ? 'error' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Missing Timesheets',
      value: n(summary?.missing_timesheets?.length ?? 0, unavailable),
      icon: ScheduleRoundedIcon,
      accent: (summary?.missing_timesheets?.length ?? 0) > 0 ? 'warning' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Late Milestones',
      value: n(summary?.late_milestones ?? 0, unavailable),
      icon: WarningAmberRoundedIcon,
      accent: (summary?.late_milestones ?? 0) > 0 ? 'error' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Pending Reviews',
      value: n(pendingReviews, unavailable),
      icon: CheckCircleOutlineRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Pending Timesheets',
      value: n(pendingTimesheets, unavailable),
      icon: ScheduleRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Team Utilization',
      value: dash(`${designerUtilizationPercent(summary)}%`, unavailable),
      icon: GroupsRoundedIcon,
      trend: STABLE_TREND,
      onClick: () => navigate('/workload'),
    },
  ];
}
