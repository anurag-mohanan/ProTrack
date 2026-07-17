/** Module and special-permission keys (mirrors backend app/core/access_control.py). */

export const MODULE_DASHBOARD = 'dashboard';
export const MODULE_PROJECTS = 'projects';
export const MODULE_ARCHIVED_PROJECTS = 'archived_projects';
export const MODULE_TIMESHEETS = 'timesheets';
export const MODULE_WORKLOAD = 'workload';
export const MODULE_RESOURCE_PLANNING = 'resource_planning';
export const MODULE_REPORTS = 'reports';
export const MODULE_SYSTEM_ADMINISTRATION = 'system_administration';
export const MODULE_FINANCIAL_PLANNING = 'financial_planning';
export const MODULE_HUMAN_RESOURCES = 'human_resources';
export const MODULE_REPORTS_ANALYTICS = 'reports_analytics';
export const MODULE_PLANNING_BOARD = 'planning_board';
export const MODULE_CALENDAR = 'calendar';
export const MODULE_PERFORMANCE = 'performance';

export type ModuleKey =
  | typeof MODULE_DASHBOARD
  | typeof MODULE_PROJECTS
  | typeof MODULE_ARCHIVED_PROJECTS
  | typeof MODULE_TIMESHEETS
  | typeof MODULE_WORKLOAD
  | typeof MODULE_RESOURCE_PLANNING
  | typeof MODULE_REPORTS
  | typeof MODULE_SYSTEM_ADMINISTRATION
  | typeof MODULE_FINANCIAL_PLANNING
  | typeof MODULE_HUMAN_RESOURCES
  | typeof MODULE_REPORTS_ANALYTICS
  | typeof MODULE_PLANNING_BOARD
  | typeof MODULE_CALENDAR
  | typeof MODULE_PERFORMANCE;

export const ALL_MODULES: ModuleKey[] = [
  MODULE_DASHBOARD,
  MODULE_PROJECTS,
  MODULE_ARCHIVED_PROJECTS,
  MODULE_TIMESHEETS,
  MODULE_WORKLOAD,
  MODULE_RESOURCE_PLANNING,
  MODULE_REPORTS,
  MODULE_SYSTEM_ADMINISTRATION,
  MODULE_FINANCIAL_PLANNING,
  MODULE_HUMAN_RESOURCES,
  MODULE_REPORTS_ANALYTICS,
  MODULE_PLANNING_BOARD,
  MODULE_CALENDAR,
  MODULE_PERFORMANCE,
];

export const MODULE_LABELS: Record<ModuleKey, string> = {
  [MODULE_DASHBOARD]: 'Dashboard',
  [MODULE_PROJECTS]: 'Projects',
  [MODULE_ARCHIVED_PROJECTS]: 'Archived Projects',
  [MODULE_TIMESHEETS]: 'Timesheets',
  [MODULE_WORKLOAD]: 'Workload',
  [MODULE_RESOURCE_PLANNING]: 'Resource Planning',
  [MODULE_REPORTS]: 'Reports',
  [MODULE_SYSTEM_ADMINISTRATION]: 'System Administration',
  [MODULE_FINANCIAL_PLANNING]: 'Financial Planning',
  [MODULE_HUMAN_RESOURCES]: 'Human Resources',
  [MODULE_REPORTS_ANALYTICS]: 'Reports & Analytics',
  [MODULE_PLANNING_BOARD]: 'Planning Board Monitor',
  [MODULE_CALENDAR]: 'Calendar',
  [MODULE_PERFORMANCE]: 'Performance',
};

export const SPECIAL_CREATE_PROJECTS = 'create_projects';
export const SPECIAL_EDIT_PROJECTS = 'edit_projects';
export const SPECIAL_ARCHIVE_PROJECTS = 'archive_projects';
export const SPECIAL_DELETE_PROJECTS = 'delete_projects';
export const SPECIAL_APPROVE_PROJECTS = 'approve_projects';
export const SPECIAL_APPROVE_TIMESHEETS = 'approve_timesheets';
export const SPECIAL_IMPORT_TIMESHEETS = 'import_timesheets';
export const SPECIAL_EXPORT_REPORTS = 'export_reports';
export const SPECIAL_MANAGE_CUSTOMERS = 'manage_customers';
export const SPECIAL_MANAGE_CONTACTS = 'manage_contacts';
export const SPECIAL_MANAGE_TEAMS = 'manage_teams';
export const SPECIAL_MANAGE_USERS = 'manage_users';
export const SPECIAL_MANAGE_COMPANY_SETTINGS = 'manage_company_settings';
export const SPECIAL_VIEW_REPORTS = 'view_reports';
export const SPECIAL_VIEW_RESOURCE_PLANNING = 'view_resource_planning';

export type SpecialPermissionKey =
  | typeof SPECIAL_CREATE_PROJECTS
  | typeof SPECIAL_EDIT_PROJECTS
  | typeof SPECIAL_ARCHIVE_PROJECTS
  | typeof SPECIAL_DELETE_PROJECTS
  | typeof SPECIAL_APPROVE_PROJECTS
  | typeof SPECIAL_APPROVE_TIMESHEETS
  | typeof SPECIAL_IMPORT_TIMESHEETS
  | typeof SPECIAL_EXPORT_REPORTS
  | typeof SPECIAL_MANAGE_CUSTOMERS
  | typeof SPECIAL_MANAGE_CONTACTS
  | typeof SPECIAL_MANAGE_TEAMS
  | typeof SPECIAL_MANAGE_USERS
  | typeof SPECIAL_MANAGE_COMPANY_SETTINGS
  | typeof SPECIAL_VIEW_REPORTS
  | typeof SPECIAL_VIEW_RESOURCE_PLANNING;

export const ALL_SPECIAL_PERMISSIONS: SpecialPermissionKey[] = [
  SPECIAL_CREATE_PROJECTS,
  SPECIAL_EDIT_PROJECTS,
  SPECIAL_ARCHIVE_PROJECTS,
  SPECIAL_DELETE_PROJECTS,
  SPECIAL_APPROVE_PROJECTS,
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
];

export const SPECIAL_PERMISSION_LABELS: Record<SpecialPermissionKey, string> = {
  [SPECIAL_CREATE_PROJECTS]: 'Create Projects',
  [SPECIAL_EDIT_PROJECTS]: 'Edit Projects',
  [SPECIAL_ARCHIVE_PROJECTS]: 'Archive Projects',
  [SPECIAL_DELETE_PROJECTS]: 'Delete Projects',
  [SPECIAL_APPROVE_PROJECTS]: 'Approve Projects',
  [SPECIAL_APPROVE_TIMESHEETS]: 'Approve Timesheets',
  [SPECIAL_IMPORT_TIMESHEETS]: 'Import Timesheets',
  [SPECIAL_EXPORT_REPORTS]: 'Export Reports',
  [SPECIAL_MANAGE_CUSTOMERS]: 'Manage Customers',
  [SPECIAL_MANAGE_CONTACTS]: 'Manage Contacts',
  [SPECIAL_MANAGE_TEAMS]: 'Manage Teams',
  [SPECIAL_MANAGE_USERS]: 'Manage Users',
  [SPECIAL_MANAGE_COMPANY_SETTINGS]: 'Manage Company Settings',
  [SPECIAL_VIEW_REPORTS]: 'View Reports',
  [SPECIAL_VIEW_RESOURCE_PLANNING]: 'View Resource Planning',
};

export const PATH_MODULE_MAP: Record<string, ModuleKey> = {
  '/dashboard': MODULE_DASHBOARD,
  '/projects/archived': MODULE_ARCHIVED_PROJECTS,
  '/projects': MODULE_PROJECTS,
  '/timesheets/month': MODULE_TIMESHEETS,
  '/timesheets': MODULE_TIMESHEETS,
  '/workload': MODULE_WORKLOAD,
  '/resource-planning': MODULE_RESOURCE_PLANNING,
  '/reports': MODULE_REPORTS,
  '/calendar': MODULE_CALENDAR,
  '/finance': MODULE_FINANCIAL_PLANNING,
  '/hr': MODULE_HUMAN_RESOURCES,
  '/analytics': MODULE_REPORTS_ANALYTICS,
  '/planning-board': MODULE_PLANNING_BOARD,
  '/performance': MODULE_PERFORMANCE,
};

export function moduleForPath(pathname: string): ModuleKey | null {
  if (pathname.startsWith('/admin')) {
    return MODULE_SYSTEM_ADMINISTRATION;
  }
  const sorted = Object.entries(PATH_MODULE_MAP).sort(
    (left, right) => right[0].length - left[0].length,
  );
  for (const [prefix, module] of sorted) {
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) {
      return module;
    }
  }
  return null;
}
