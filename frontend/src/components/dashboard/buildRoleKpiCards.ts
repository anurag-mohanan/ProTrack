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
import type { RoleKpiSnapshot } from '../../api/dashboard';
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
  roleKpis: RoleKpiSnapshot | undefined;
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
  roleKpis,
  unavailable,
  navigate,
}: BuildRoleKpiCardsOptions): DashboardKpiItem[] {
  const profile = roleKpis?.dashboard_profile;
  if (roleGroup === 'admin' || profile === 'administration') {
    return buildAdminKpiCards({ systemHealth, summary, roleKpis, unavailable, navigate });
  }
  if (roleGroup === 'engineering_manager' || profile === 'management') {
    return buildManagementKpiCards({ summary, roleKpis, unavailable, navigate });
  }
  if (roleGroup === 'staff') {
    return buildStaffKpiCards({ summary, unavailable, navigate });
  }
  if (roleGroup === 'design_leader') {
    return buildDesignLeaderKpiCards({ summary, roleKpis, unavailable, navigate });
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
      title: 'Engineering Productivity',
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

function buildManagementKpiCards({
  summary,
  roleKpis,
  unavailable,
  navigate,
}: {
  summary: DashboardSummary | undefined;
  roleKpis: RoleKpiSnapshot | undefined;
  unavailable: boolean;
  navigate: NavigateFunction;
}): DashboardKpiItem[] {
  const mgmt = roleKpis?.management;
  const highRisk = mgmt?.high_risk_projects ?? (summary?.red_projects ?? 0) + (summary?.yellow_projects ?? 0);
  const missingTs = mgmt?.timesheet_compliance_pending ?? summary?.missing_timesheets?.length ?? 0;

  return [
    {
      title: 'Projects Managed',
      value: n(mgmt?.projects_managed ?? summary?.active_projects ?? 0, unavailable),
      icon: FolderOpenRoundedIcon,
      accent: 'primary',
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?lifecycle=active'),
    },
    {
      title: 'Projects Delivered',
      value: n(mgmt?.projects_delivered ?? summary?.completed_this_month ?? 0, unavailable),
      icon: CheckCircleOutlineRoundedIcon,
      accent: 'success',
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?completed=month'),
    },
    {
      title: 'Overdue Projects',
      value: n(mgmt?.overdue_projects ?? summary?.overdue_projects ?? 0, unavailable),
      icon: WarningAmberRoundedIcon,
      accent: (mgmt?.overdue_projects ?? summary?.overdue_projects ?? 0) > 0 ? 'error' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=overdue'),
    },
    {
      title: 'Pending Reviews',
      value: n(mgmt?.pending_reviews ?? 0, unavailable),
      icon: CheckCircleOutlineRoundedIcon,
      accent: (mgmt?.pending_reviews ?? 0) > 0 ? 'warning' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/timesheets'),
    },
    {
      title: 'Milestone Approvals',
      value: n(mgmt?.pending_milestone_approvals ?? summary?.late_milestones ?? 0, unavailable),
      icon: ScheduleRoundedIcon,
      accent: (mgmt?.pending_milestone_approvals ?? 0) > 0 ? 'warning' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects'),
    },
    {
      title: 'Upcoming Deliveries',
      value: n(mgmt?.upcoming_deliveries ?? summary?.projects_due_this_week ?? 0, unavailable),
      icon: TrendingUpRoundedIcon,
      accent: 'info',
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?due=week'),
    },
    {
      title: 'High Risk Projects',
      value: n(highRisk, unavailable),
      icon: ErrorOutlineRoundedIcon,
      accent: highRisk > 0 ? 'error' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/projects?health=red'),
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
      title: 'Team Utilization',
      value: dash(
        mgmt?.team_utilization_percent != null
          ? `${Math.round(mgmt.team_utilization_percent)}%`
          : `${designerUtilizationPercent(summary)}%`,
        unavailable,
      ),
      icon: GroupsRoundedIcon,
      accent: 'info',
      trend: STABLE_TREND,
      onClick: () => navigate('/resource-planning'),
    },
    {
      title: 'Engineering Members',
      value: n(roleKpis?.engineering_productivity_user_count ?? 0, unavailable),
      icon: PeopleRoundedIcon,
      accent: 'primary',
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/users'),
    },
  ];
}

function buildAdminKpiCards({
  systemHealth,
  summary,
  roleKpis,
  unavailable,
  navigate,
}: Pick<BuildRoleKpiCardsOptions, 'summary' | 'systemHealth' | 'roleKpis' | 'unavailable' | 'navigate'>): DashboardKpiItem[] {
  const admin = roleKpis?.administration;
  const dbOk = (admin?.database_status ?? systemHealth?.database_status) === 'ok';
  const svcOk =
    (admin?.backend_status ?? systemHealth?.backend_status) === 'ok' &&
    systemHealth?.api_status === 'ok';
  return [
    {
      title: 'Active Users',
      value: n(admin?.active_users ?? systemHealth?.active_users ?? 0, unavailable),
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
      value: n(admin?.import_queue ?? systemHealth?.import_queue ?? summary?.operational_metrics?.pending_import_jobs ?? 0, unavailable),
      icon: ScheduleRoundedIcon,
      accent: (systemHealth?.import_queue ?? 0) > 0 ? 'warning' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/imports/historical-timesheets'),
    },
    {
      title: 'Failed Emails',
      value: n(admin?.failed_emails ?? systemHealth?.failed_emails ?? 0, unavailable),
      icon: EmailRoundedIcon,
      accent: (systemHealth?.failed_emails ?? 0) > 0 ? 'error' : undefined,
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/settings/email-queue'),
    },
    {
      title: 'Backups',
      value: n(admin?.backups_count ?? 0, unavailable),
      icon: StorageRoundedIcon,
      accent: (admin?.last_backup ?? systemHealth?.last_backup) ? 'success' : 'warning',
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/settings/backup'),
    },
    {
      title: 'Emails Sent',
      value: n(admin?.emails_sent ?? 0, unavailable),
      icon: EmailRoundedIcon,
      accent: 'info',
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/settings/email-queue'),
    },
    {
      title: 'Audit Actions (7d)',
      value: n(admin?.audit_actions_7d ?? 0, unavailable),
      icon: DnsRoundedIcon,
      accent: 'primary',
      trend: STABLE_TREND,
      onClick: () => navigate('/admin/audit/logs'),
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
  roleKpis,
  unavailable,
  navigate,
}: {
  summary: DashboardSummary | undefined;
  roleKpis: RoleKpiSnapshot | undefined;
  unavailable: boolean;
  navigate: NavigateFunction;
}): DashboardKpiItem[] {
  const pendingReviews = roleKpis?.management?.pending_reviews ?? summary?.my_tasks.pending_reviews?.length ?? 0;
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
