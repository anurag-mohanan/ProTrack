import type { AccessContext } from './permissions';
import {
  canAccessAdministration,
  canEnterOwnTimesheet,
  canViewAiInsights,
  canViewArchivedProjects,
  canViewReports,
  canViewResourcePlanning,
  canViewWorkload,
  isAdminRole,
  isOperationalManagerRole,
  userHasModule,
} from './permissions';
import {
  MODULE_CALENDAR,
  MODULE_DASHBOARD,
  MODULE_FINANCIAL_PLANNING,
  MODULE_HUMAN_RESOURCES,
  MODULE_PROJECTS,
  MODULE_REPORTS_ANALYTICS,
  MODULE_TIMESHEETS,
} from '../config/accessControl';

/** Whether the user can open a destination in the engineering or admin portal. */
export function canAccessPortalPath(ctx: AccessContext, path: string): boolean {
  const normalized = path.split('?')[0]?.split('#')[0] ?? path;

  if (normalized.startsWith('/admin')) {
    return canAccessAdminPortalPath(ctx, normalized);
  }

  if (normalized === '/dashboard') {
    return userHasModule(ctx, MODULE_DASHBOARD);
  }
  if (normalized === '/calendar') {
    return userHasModule(ctx, MODULE_CALENDAR);
  }
  if (normalized.startsWith('/projects/archived')) {
    return canViewArchivedProjects(ctx);
  }
  if (normalized.startsWith('/projects')) {
    return userHasModule(ctx, MODULE_PROJECTS);
  }
  if (normalized.startsWith('/timesheets')) {
    return userHasModule(ctx, MODULE_TIMESHEETS);
  }
  if (normalized.startsWith('/workload')) {
    return canViewWorkload(ctx);
  }
  if (normalized.startsWith('/resource-planning')) {
    return canViewResourcePlanning(ctx);
  }
  if (
    normalized.startsWith('/reports') ||
    normalized.startsWith('/knowledge') ||
    normalized.startsWith('/executive-wall')
  ) {
    return canViewReports(ctx);
  }
  if (normalized.startsWith('/finance')) {
    return userHasModule(ctx, MODULE_FINANCIAL_PLANNING);
  }
  if (normalized.startsWith('/hr')) {
    return userHasModule(ctx, MODULE_HUMAN_RESOURCES);
  }
  if (normalized.startsWith('/analytics')) {
    return userHasModule(ctx, MODULE_REPORTS_ANALYTICS);
  }

  return true;
}

/** Admin API routes are Admin-role only; hide all admin destinations for others. */
export function canAccessAdminPortalPath(ctx: AccessContext, path: string): boolean {
  if (!canAccessAdministration(ctx) || !isAdminRole(ctx.role_name)) {
    return false;
  }

  if (path === '/admin/dashboard') {
    return true;
  }
  if (path.startsWith('/admin/system/diagnostics')) {
    return isAdminRole(ctx.role_name);
  }
  if (path.startsWith('/admin/system')) {
    return isAdminRole(ctx.role_name);
  }
  if (path.startsWith('/admin/imports/historical')) {
    return isAdminRole(ctx.role_name);
  }
  if (path.startsWith('/admin/rebuild-timesheet-stats')) {
    return isAdminRole(ctx.role_name);
  }
  if (path.startsWith('/admin/deleted-')) {
    return isAdminRole(ctx.role_name);
  }
  if (path.startsWith('/admin/audit')) {
    return isAdminRole(ctx.role_name);
  }
  if (path.startsWith('/admin/settings')) {
    return isAdminRole(ctx.role_name);
  }

  return isAdminRole(ctx.role_name);
}

export function canViewDashboardAiPanel(ctx: AccessContext): boolean {
  return canViewAiInsights(ctx);
}

export function canViewDashboardEngineeringCharts(ctx: AccessContext): boolean {
  return (
    isOperationalManagerRole(ctx.role_name) ||
    canViewReports(ctx) ||
    canViewWorkload(ctx) ||
    canViewResourcePlanning(ctx)
  );
}

export function canViewDashboardMissingTimesheets(ctx: AccessContext): boolean {
  return (
    userHasModule(ctx, MODULE_TIMESHEETS) &&
    (isOperationalManagerRole(ctx.role_name) || canViewReports(ctx))
  );
}

export function canViewDashboardMyProjects(ctx: AccessContext): boolean {
  return userHasModule(ctx, MODULE_PROJECTS);
}

export function canViewDashboardCollaboration(ctx: AccessContext): boolean {
  return userHasModule(ctx, MODULE_PROJECTS) || userHasModule(ctx, MODULE_TIMESHEETS);
}

export function canViewDashboardMyTasks(ctx: AccessContext): boolean {
  return canEnterOwnTimesheet(ctx) && userHasModule(ctx, MODULE_TIMESHEETS);
}

export function canViewDashboardProjectsAttention(ctx: AccessContext): boolean {
  return userHasModule(ctx, MODULE_PROJECTS);
}

export function canViewDashboardCustomerWorkload(ctx: AccessContext): boolean {
  return userHasModule(ctx, MODULE_PROJECTS) && canViewWorkload(ctx);
}

export function canViewDashboardSystemActivity(ctx: AccessContext): boolean {
  return isAdminRole(ctx.role_name);
}
