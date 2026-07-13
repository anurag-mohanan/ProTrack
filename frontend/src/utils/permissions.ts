import type { SvgIconComponent } from '@mui/icons-material';
import AssessmentRoundedIcon from '@mui/icons-material/AssessmentRounded';
import ArchiveRoundedIcon from '@mui/icons-material/ArchiveRounded';
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded';
import FolderRoundedIcon from '@mui/icons-material/FolderRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import CalendarMonthRoundedIcon from '@mui/icons-material/CalendarMonthRounded';
import AccountBalanceRoundedIcon from '@mui/icons-material/AccountBalanceRounded';
import BadgeRoundedIcon from '@mui/icons-material/BadgeRounded';
import InsightsRoundedIcon from '@mui/icons-material/InsightsRounded';
import type { CurrentUser } from '../types';
import {
  ALL_MODULES,
  MODULE_ARCHIVED_PROJECTS,
  MODULE_DASHBOARD,
  MODULE_FINANCIAL_PLANNING,
  MODULE_HUMAN_RESOURCES,
  MODULE_PROJECTS,
  MODULE_REPORTS,
  MODULE_REPORTS_ANALYTICS,
  MODULE_RESOURCE_PLANNING,
  MODULE_SYSTEM_ADMINISTRATION,
  MODULE_TIMESHEETS,
  MODULE_WORKLOAD,
  MODULE_PLANNING_BOARD,
  SPECIAL_APPROVE_TIMESHEETS,
  SPECIAL_ARCHIVE_PROJECTS,
  SPECIAL_CREATE_PROJECTS,
  SPECIAL_DELETE_PROJECTS,
  SPECIAL_EDIT_PROJECTS,
  SPECIAL_EXPORT_REPORTS,
  SPECIAL_IMPORT_TIMESHEETS,
  SPECIAL_MANAGE_COMPANY_SETTINGS,
  SPECIAL_MANAGE_CONTACTS,
  SPECIAL_MANAGE_CUSTOMERS,
  SPECIAL_MANAGE_TEAMS,
  SPECIAL_MANAGE_USERS,
  SPECIAL_VIEW_REPORTS,
  SPECIAL_VIEW_RESOURCE_PLANNING,
  type ModuleKey,
  type SpecialPermissionKey,
} from '../config/accessControl';

export const ROLES = {
  ADMIN: 'Admin',
  ENGINEERING_MANAGER: 'Engineering Manager',
  PROJECT_MANAGER: 'Project Manager',
  DESIGN_LEADER: 'Design Leader',
  SENIOR_DESIGNER: 'Senior Designer',
  DESIGNER: 'Designer',
  JUNIOR_DESIGNER: 'Junior Designer',
  SURFACER: 'Surfacer',
  READ_ONLY: 'Read Only',
  PLANNING_BOARD: 'Planning Board',
  HR: 'HR',
  OFFICE_ADMINISTRATOR: 'Office Administrator',
} as const;

export type DashboardRoleGroup =
  | 'admin'
  | 'engineering_manager'
  | 'design_leader'
  | 'staff'
  | 'read_only'
  | 'planning_board';

export interface MainNavItem {
  label: string;
  path: string;
  icon: SvgIconComponent;
  module: ModuleKey;
}

export interface AccessContext {
  role_name: string;
  resolved_modules?: string[];
  resolved_special_permissions?: string[];
}

const DEFAULT_MODULES_BY_ROLE: Record<string, ModuleKey[]> = {
  [ROLES.ADMIN]: [...ALL_MODULES],
  [ROLES.ENGINEERING_MANAGER]: [
    MODULE_DASHBOARD,
    MODULE_PROJECTS,
    MODULE_ARCHIVED_PROJECTS,
    MODULE_TIMESHEETS,
    MODULE_WORKLOAD,
    MODULE_RESOURCE_PLANNING,
    MODULE_REPORTS,
    MODULE_FINANCIAL_PLANNING,
    MODULE_REPORTS_ANALYTICS,
  ],
  [ROLES.DESIGN_LEADER]: [
    MODULE_DASHBOARD,
    MODULE_PROJECTS,
    MODULE_ARCHIVED_PROJECTS,
    MODULE_TIMESHEETS,
    MODULE_WORKLOAD,
    MODULE_REPORTS_ANALYTICS,
  ],
  [ROLES.DESIGNER]: [MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS],
  [ROLES.SENIOR_DESIGNER]: [MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS],
  [ROLES.JUNIOR_DESIGNER]: [MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS],
  [ROLES.SURFACER]: [MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS],
  [ROLES.READ_ONLY]: [MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_REPORTS_ANALYTICS],
  [ROLES.PLANNING_BOARD]: [MODULE_PLANNING_BOARD],
  [ROLES.HR]: [
    MODULE_DASHBOARD,
    MODULE_HUMAN_RESOURCES,
    MODULE_TIMESHEETS,
    MODULE_REPORTS_ANALYTICS,
  ],
  [ROLES.OFFICE_ADMINISTRATOR]: [
    MODULE_DASHBOARD,
    MODULE_HUMAN_RESOURCES,
    MODULE_TIMESHEETS,
    MODULE_REPORTS_ANALYTICS,
  ],
};

const DEFAULT_SPECIAL_BY_ROLE: Record<string, SpecialPermissionKey[]> = {
  [ROLES.ADMIN]: [
    SPECIAL_CREATE_PROJECTS,
    SPECIAL_EDIT_PROJECTS,
    SPECIAL_ARCHIVE_PROJECTS,
    SPECIAL_DELETE_PROJECTS,
    SPECIAL_APPROVE_TIMESHEETS,
    SPECIAL_IMPORT_TIMESHEETS,
    SPECIAL_EXPORT_REPORTS,
    SPECIAL_MANAGE_CUSTOMERS,
    SPECIAL_MANAGE_CONTACTS,
    SPECIAL_MANAGE_TEAMS,
    SPECIAL_MANAGE_USERS,
    SPECIAL_MANAGE_COMPANY_SETTINGS,
    SPECIAL_VIEW_REPORTS,
    SPECIAL_VIEW_RESOURCE_PLANNING,
  ],
  [ROLES.ENGINEERING_MANAGER]: [
    SPECIAL_CREATE_PROJECTS,
    SPECIAL_EDIT_PROJECTS,
    SPECIAL_ARCHIVE_PROJECTS,
    SPECIAL_APPROVE_TIMESHEETS,
    SPECIAL_EXPORT_REPORTS,
    SPECIAL_VIEW_REPORTS,
    SPECIAL_VIEW_RESOURCE_PLANNING,
  ],
  [ROLES.DESIGN_LEADER]: [
    SPECIAL_CREATE_PROJECTS,
    SPECIAL_EDIT_PROJECTS,
    SPECIAL_ARCHIVE_PROJECTS,
    SPECIAL_APPROVE_TIMESHEETS,
    SPECIAL_VIEW_REPORTS,
    SPECIAL_EXPORT_REPORTS,
  ],
  [ROLES.SENIOR_DESIGNER]: [SPECIAL_CREATE_PROJECTS, SPECIAL_EDIT_PROJECTS],
  [ROLES.DESIGNER]: [SPECIAL_EDIT_PROJECTS],
  [ROLES.READ_ONLY]: [],
  [ROLES.PLANNING_BOARD]: [],
  [ROLES.HR]: [SPECIAL_VIEW_REPORTS, SPECIAL_EXPORT_REPORTS],
  [ROLES.OFFICE_ADMINISTRATOR]: [SPECIAL_VIEW_REPORTS, SPECIAL_EXPORT_REPORTS],
};

const NAV_MODULE_CONFIG: Array<{
  module: ModuleKey;
  label: string | ((ctx: AccessContext) => string);
  path: string;
  icon: SvgIconComponent;
}> = [
  {
    module: MODULE_PLANNING_BOARD,
    label: 'Planning Board',
    path: '/planning-board',
    icon: CalendarMonthRoundedIcon,
  },
  { module: MODULE_DASHBOARD, label: 'Dashboard', path: '/dashboard', icon: DashboardRoundedIcon },
  {
    module: MODULE_PROJECTS,
    label: (ctx) => (getDashboardRoleGroup(ctx.role_name) === 'staff' ? 'My Projects' : 'Projects'),
    path: '/projects',
    icon: FolderRoundedIcon,
  },
  {
    module: MODULE_ARCHIVED_PROJECTS,
    label: 'Archived Projects',
    path: '/projects/archived',
    icon: ArchiveRoundedIcon,
  },
  { module: MODULE_TIMESHEETS, label: 'Timesheets', path: '/timesheets', icon: ScheduleRoundedIcon },
  { module: MODULE_WORKLOAD, label: 'Workload', path: '/workload', icon: GroupsRoundedIcon },
  {
    module: MODULE_RESOURCE_PLANNING,
    label: 'Resource Planning',
    path: '/resource-planning',
    icon: CalendarMonthRoundedIcon,
  },
  { module: MODULE_DASHBOARD, label: 'Calendar', path: '/calendar', icon: CalendarMonthRoundedIcon },
];

const EBMP_SECTION_NAV: Array<{
  module: ModuleKey;
  label: string;
  path: string;
  icon: SvgIconComponent;
}> = [
  {
    module: MODULE_FINANCIAL_PLANNING,
    label: 'Financial Planning',
    path: '/finance',
    icon: AccountBalanceRoundedIcon,
  },
  {
    module: MODULE_HUMAN_RESOURCES,
    label: 'Human Resources',
    path: '/hr',
    icon: BadgeRoundedIcon,
  },
  {
    module: MODULE_REPORTS_ANALYTICS,
    label: 'Reports & Analytics',
    path: '/analytics',
    icon: InsightsRoundedIcon,
  },
  // Keep legacy engineering reports reachable when only MODULE_REPORTS is granted
  {
    module: MODULE_REPORTS,
    label: 'Engineering Reports',
    path: '/reports',
    icon: AssessmentRoundedIcon,
  },
];

export const FUTURE_MODULE_PLACEHOLDERS = [
  { label: 'Customer Portal', path: '/future/customer-portal' },
  { label: 'Sales', path: '/future/sales' },
  { label: 'Procurement', path: '/future/procurement' },
  { label: 'Knowledge Base', path: '/future/knowledge-base' },
  { label: 'Document Management', path: '/future/document-management' },
] as const;

function normalizeRoleName(roleName: string): string {
  if (roleName === ROLES.PROJECT_MANAGER) {
    return ROLES.ENGINEERING_MANAGER;
  }
  return roleName;
}

function hasRole(roleName: string, ...roles: string[]): boolean {
  const normalized = normalizeRoleName(roleName);
  return roles.some((role) => normalizeRoleName(role) === normalized);
}

export function accessContextFromUser(user: CurrentUser | null | undefined): AccessContext {
  return {
    role_name: user?.role_name ?? '',
    resolved_modules: user?.resolved_modules ?? user?.module_access,
    resolved_special_permissions: user?.resolved_special_permissions ?? user?.special_permissions,
  };
}

export function toAccessContext(roleNameOrContext: string | AccessContext): AccessContext {
  if (typeof roleNameOrContext === 'string') {
    return { role_name: roleNameOrContext };
  }
  return roleNameOrContext;
}

export function defaultModulesForRole(roleName: string): ModuleKey[] {
  const normalized = normalizeRoleName(roleName);
  return DEFAULT_MODULES_BY_ROLE[normalized] ?? DEFAULT_MODULES_BY_ROLE[ROLES.DESIGNER];
}

export function defaultSpecialPermissionsForRole(roleName: string): SpecialPermissionKey[] {
  const normalized = normalizeRoleName(roleName);
  return DEFAULT_SPECIAL_BY_ROLE[normalized] ?? [];
}

export function resolveModules(ctx: AccessContext): ModuleKey[] {
  if (ctx.resolved_modules?.length) {
    return ctx.resolved_modules.filter((module): module is ModuleKey =>
      ALL_MODULES.includes(module as ModuleKey),
    );
  }
  return defaultModulesForRole(ctx.role_name);
}

export function resolveSpecialPermissions(ctx: AccessContext): SpecialPermissionKey[] {
  if (ctx.resolved_special_permissions?.length) {
    return ctx.resolved_special_permissions as SpecialPermissionKey[];
  }
  return defaultSpecialPermissionsForRole(ctx.role_name);
}

export function userHasModule(ctx: AccessContext, module: ModuleKey): boolean {
  return resolveModules(ctx).includes(module);
}

export function userHasSpecial(ctx: AccessContext, permission: SpecialPermissionKey): boolean {
  return resolveSpecialPermissions(ctx).includes(permission);
}

export function getDashboardRoleGroup(roleName: string): DashboardRoleGroup {
  const normalized = normalizeRoleName(roleName);
  if (normalized === ROLES.ADMIN) return 'admin';
  if (normalized === ROLES.ENGINEERING_MANAGER) return 'engineering_manager';
  if (normalized === ROLES.DESIGN_LEADER) return 'design_leader';
  if (normalized === ROLES.READ_ONLY) return 'read_only';
  if (normalized === ROLES.PLANNING_BOARD) return 'planning_board';
  return 'staff';
}

export function isAdminRole(roleName: string): boolean {
  return hasRole(roleName, ROLES.ADMIN);
}

export function isEngineeringManagerRole(roleName: string): boolean {
  return hasRole(roleName, ROLES.ENGINEERING_MANAGER);
}

export function isDesignLeaderRole(roleName: string): boolean {
  return hasRole(roleName, ROLES.DESIGN_LEADER);
}

export function isProjectStaffRole(roleName: string): boolean {
  return (PROJECT_STAFF_ROLES as readonly string[]).includes(normalizeRoleName(roleName));
}

export function isSurfacerRole(roleName: string): boolean {
  return hasRole(roleName, ROLES.SURFACER);
}

export function isReadOnlyRole(roleName: string): boolean {
  return hasRole(roleName, ROLES.READ_ONLY);
}

export function isPlanningBoardRole(roleName: string): boolean {
  return hasRole(roleName, ROLES.PLANNING_BOARD);
}

export function getDefaultLandingPath(roleName: string | null | undefined): string {
  if (roleName && isPlanningBoardRole(roleName)) {
    return '/planning-board';
  }
  return '/dashboard';
}

export function isOperationalManagerRole(roleName: string): boolean {
  return hasRole(roleName, ROLES.ADMIN, ROLES.ENGINEERING_MANAGER);
}

export const PROJECT_STAFF_ROLES = [
  ROLES.SENIOR_DESIGNER,
  ROLES.DESIGNER,
  ROLES.JUNIOR_DESIGNER,
  ROLES.SURFACER,
] as const;

export function canSubmitTimesheet(
  status: string,
  ownerId: string,
  currentUserId: string,
  roleName: string,
): boolean {
  if (status !== 'draft') return false;
  if (ownerId === currentUserId) return true;
  return isOperationalManagerRole(roleName);
}

export function canApproveTimesheet(status: string, roleNameOrContext: string | AccessContext): boolean {
  if (status !== 'submitted') return false;
  const ctx = toAccessContext(roleNameOrContext);
  if (userHasSpecial(ctx, SPECIAL_APPROVE_TIMESHEETS)) return true;
  return isOperationalManagerRole(ctx.role_name) || isDesignLeaderRole(ctx.role_name);
}

export function canRejectTimesheet(status: string, roleNameOrContext: string | AccessContext): boolean {
  return canApproveTimesheet(status, roleNameOrContext);
}

/**
 * Whether the user can view other people's timesheets (team/all overview).
 * Admins always can; managers/leaders with the "approve timesheets" permission
 * (assignable per-user at creation) can view the timesheets they oversee.
 */
export function canViewAllTimesheets(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  if (isAdminRole(ctx.role_name)) return true;
  if (userHasSpecial(ctx, SPECIAL_APPROVE_TIMESHEETS)) return true;
  return isOperationalManagerRole(ctx.role_name) || isDesignLeaderRole(ctx.role_name);
}

/**
 * Whether the user should get the personal timesheet-entry form.
 * System admins only oversee others' entries, so they don't get the form.
 */
export function canEnterOwnTimesheet(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return !isAdminRole(ctx.role_name);
}

export function canReturnToDraft(
  status: string,
  ownerId: string,
  currentUserId: string,
  roleName: string,
): boolean {
  if (status === 'rejected' && ownerId === currentUserId) return true;
  if (status === 'submitted') {
    return isOperationalManagerRole(roleName) || isDesignLeaderRole(roleName);
  }
  return false;
}

export function canImportHistoricalProjects(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return isAdminRole(ctx.role_name);
}

export function canImportHistoricalTimesheets(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return isAdminRole(ctx.role_name);
}

export function canAccessAdministration(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasModule(ctx, MODULE_SYSTEM_ADMINISTRATION) && isAdminRole(ctx.role_name);
}

export function canManageUsers(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_MANAGE_USERS);
}

export function canCreateCustomer(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_MANAGE_CUSTOMERS);
}

export function canDeleteRecords(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_DELETE_PROJECTS);
}

export function canViewDeletedProjects(roleNameOrContext: string | AccessContext): boolean {
  return canAccessAdministration(roleNameOrContext);
}

export function canCreateProject(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_CREATE_PROJECTS);
}

export function canArchiveProject(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_ARCHIVE_PROJECTS);
}

export function canSoftDeleteProject(roleNameOrContext: string | AccessContext): boolean {
  return canDeleteRecords(roleNameOrContext);
}

export function canEditProject(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_EDIT_PROJECTS);
}

export function canViewReports(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  if (isReadOnlyRole(ctx.role_name) || isPlanningBoardRole(ctx.role_name)) return true;
  return userHasModule(ctx, MODULE_REPORTS) || userHasSpecial(ctx, SPECIAL_VIEW_REPORTS);
}

export function canExportReports(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_EXPORT_REPORTS);
}

export function canViewWorkload(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  if (isPlanningBoardRole(ctx.role_name)) return true;
  return userHasModule(ctx, MODULE_WORKLOAD);
}

export function canViewResourcePlanning(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  if (isPlanningBoardRole(ctx.role_name)) return true;
  return (
    userHasModule(ctx, MODULE_RESOURCE_PLANNING) ||
    userHasSpecial(ctx, SPECIAL_VIEW_RESOURCE_PLANNING)
  );
}

export function canViewArchivedProjects(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasModule(ctx, MODULE_ARCHIVED_PROJECTS);
}

export function canManageCompanySettings(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_MANAGE_COMPANY_SETTINGS);
}

export function getMainNavItems(roleNameOrContext: string | AccessContext): MainNavItem[] {
  const ctx = toAccessContext(roleNameOrContext);
  if (isPlanningBoardRole(ctx.role_name)) {
    return [
      {
        module: MODULE_PLANNING_BOARD,
        path: '/planning-board',
        icon: CalendarMonthRoundedIcon,
        label: 'Planning Board',
      },
    ];
  }
  const modules = new Set(resolveModules(ctx));

  return NAV_MODULE_CONFIG.filter((item) => modules.has(item.module)).map((item) => ({
    module: item.module,
    path: item.path,
    icon: item.icon,
    label: typeof item.label === 'function' ? item.label(ctx) : item.label,
  }));
}

export function getEbmpSectionNavItems(roleNameOrContext: string | AccessContext): MainNavItem[] {
  const ctx = toAccessContext(roleNameOrContext);
  if (isPlanningBoardRole(ctx.role_name)) {
    return [];
  }
  const modules = new Set(resolveModules(ctx));
  const items: MainNavItem[] = [];
  const seenPaths = new Set<string>();

  for (const item of EBMP_SECTION_NAV) {
    if (!modules.has(item.module)) continue;
    // Prefer analytics hub over duplicate engineering reports when both exist
    if (item.path === '/reports' && modules.has(MODULE_REPORTS_ANALYTICS)) continue;
    if (seenPaths.has(item.path)) continue;
    seenPaths.add(item.path);
    items.push({
      module: item.module,
      path: item.path,
      icon: item.icon,
      label: item.label,
    });
  }
  return items;
}

export function canOverrideBillable(roleName: string): boolean {
  return isOperationalManagerRole(roleName);
}

export function canViewAiInsights(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return isOperationalManagerRole(ctx.role_name) || isDesignLeaderRole(ctx.role_name);
}

export { defaultModulesForRole as getDefaultModulesForRole };
export { defaultSpecialPermissionsForRole as getDefaultSpecialPermissionsForRole };
