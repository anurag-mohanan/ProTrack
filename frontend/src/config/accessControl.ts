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
export const MODULE_TICKETS = 'tickets';
export const MODULE_IT_OPERATIONS = 'it_operations';

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
  | typeof MODULE_PERFORMANCE
  | typeof MODULE_TICKETS
  | typeof MODULE_IT_OPERATIONS;

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
  MODULE_TICKETS,
  MODULE_IT_OPERATIONS,
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
  [MODULE_FINANCIAL_PLANNING]: 'Finance',
  [MODULE_HUMAN_RESOURCES]: 'Human Resources',
  [MODULE_REPORTS_ANALYTICS]: 'Reports & Analytics',
  [MODULE_PLANNING_BOARD]: 'Planning Board Monitor',
  [MODULE_CALENDAR]: 'Calendar',
  [MODULE_PERFORMANCE]: 'Performance',
  [MODULE_TICKETS]: 'Help Desk',
  [MODULE_IT_OPERATIONS]: 'IT Operations',
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
export const SPECIAL_MANAGE_PROJECT_SETTINGS = 'manage_project_settings';
export const SPECIAL_VIEW_REPORTS = 'view_reports';
export const SPECIAL_VIEW_RESOURCE_PLANNING = 'view_resource_planning';
export const SPECIAL_MANAGE_RESOURCE_SHIFTS = 'manage_resource_shifts';
export const SPECIAL_ASSIGN_RESOURCE_SHIFTS = 'assign_resource_shifts';
export const SPECIAL_VIEW_IT_OPERATIONS = 'view_it_operations';
export const SPECIAL_MANAGE_IT_ASSETS = 'manage_it_assets';
export const SPECIAL_ASSIGN_IT_ASSETS = 'assign_it_assets';
export const SPECIAL_RETURN_CUSTOMER_ASSETS = 'return_customer_assets';
export const SPECIAL_MANAGE_IT_NETWORKS = 'manage_it_networks';
export const SPECIAL_ALLOCATE_IT_IPS = 'allocate_it_ips';
export const SPECIAL_MANAGE_IT_ACCOUNTS = 'manage_it_accounts';
export const SPECIAL_GENERATE_IT_CREDENTIALS = 'generate_it_credentials';
export const SPECIAL_MANAGE_IT_REQUESTS = 'manage_it_requests';
export const SPECIAL_VIEW_IT_REPORTS = 'view_it_reports';
export const SPECIAL_MANAGE_IT_SETTINGS = 'manage_it_settings';
export const SPECIAL_MANAGE_IT_DATA_IMPORTS = 'manage_it_data_imports';
export const SPECIAL_MANAGE_IT_INVENTORY = 'manage_it_inventory';
export const SPECIAL_MANAGE_IT_SOFTWARE = 'manage_it_software';
export const SPECIAL_MANAGE_IT_SUPPLIERS = 'manage_it_suppliers';
export const SPECIAL_OVERRIDE_IT_ASSET_NUMBER = 'override_it_asset_number';

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
  | typeof SPECIAL_MANAGE_PROJECT_SETTINGS
  | typeof SPECIAL_VIEW_REPORTS
  | typeof SPECIAL_VIEW_RESOURCE_PLANNING
  | typeof SPECIAL_MANAGE_RESOURCE_SHIFTS
  | typeof SPECIAL_ASSIGN_RESOURCE_SHIFTS
  | typeof SPECIAL_VIEW_IT_OPERATIONS
  | typeof SPECIAL_MANAGE_IT_ASSETS
  | typeof SPECIAL_ASSIGN_IT_ASSETS
  | typeof SPECIAL_RETURN_CUSTOMER_ASSETS
  | typeof SPECIAL_MANAGE_IT_NETWORKS
  | typeof SPECIAL_ALLOCATE_IT_IPS
  | typeof SPECIAL_MANAGE_IT_ACCOUNTS
  | typeof SPECIAL_GENERATE_IT_CREDENTIALS
  | typeof SPECIAL_MANAGE_IT_REQUESTS
  | typeof SPECIAL_VIEW_IT_REPORTS
  | typeof SPECIAL_MANAGE_IT_SETTINGS
  | typeof SPECIAL_MANAGE_IT_DATA_IMPORTS
  | typeof SPECIAL_MANAGE_IT_INVENTORY
  | typeof SPECIAL_MANAGE_IT_SOFTWARE
  | typeof SPECIAL_MANAGE_IT_SUPPLIERS
  | typeof SPECIAL_OVERRIDE_IT_ASSET_NUMBER;

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
  SPECIAL_MANAGE_PROJECT_SETTINGS,
  SPECIAL_VIEW_REPORTS,
  SPECIAL_VIEW_RESOURCE_PLANNING,
  SPECIAL_MANAGE_RESOURCE_SHIFTS,
  SPECIAL_ASSIGN_RESOURCE_SHIFTS,
  SPECIAL_VIEW_IT_OPERATIONS,
  SPECIAL_MANAGE_IT_ASSETS,
  SPECIAL_ASSIGN_IT_ASSETS,
  SPECIAL_RETURN_CUSTOMER_ASSETS,
  SPECIAL_MANAGE_IT_NETWORKS,
  SPECIAL_ALLOCATE_IT_IPS,
  SPECIAL_MANAGE_IT_ACCOUNTS,
  SPECIAL_GENERATE_IT_CREDENTIALS,
  SPECIAL_MANAGE_IT_REQUESTS,
  SPECIAL_VIEW_IT_REPORTS,
  SPECIAL_MANAGE_IT_SETTINGS,
  SPECIAL_MANAGE_IT_DATA_IMPORTS,
  SPECIAL_MANAGE_IT_INVENTORY,
  SPECIAL_MANAGE_IT_SOFTWARE,
  SPECIAL_MANAGE_IT_SUPPLIERS,
  SPECIAL_OVERRIDE_IT_ASSET_NUMBER,
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
  [SPECIAL_MANAGE_PROJECT_SETTINGS]: 'Manage Project Settings',
  [SPECIAL_VIEW_REPORTS]: 'View Reports',
  [SPECIAL_VIEW_RESOURCE_PLANNING]: 'View Resource Planning',
  [SPECIAL_MANAGE_RESOURCE_SHIFTS]: 'Manage Resource Shifts',
  [SPECIAL_ASSIGN_RESOURCE_SHIFTS]: 'Assign Resource Shifts',
  [SPECIAL_VIEW_IT_OPERATIONS]: 'View IT Operations',
  [SPECIAL_MANAGE_IT_ASSETS]: 'Manage IT Assets',
  [SPECIAL_ASSIGN_IT_ASSETS]: 'Assign IT Assets',
  [SPECIAL_RETURN_CUSTOMER_ASSETS]: 'Return Customer Assets',
  [SPECIAL_MANAGE_IT_NETWORKS]: 'Manage IT Networks',
  [SPECIAL_ALLOCATE_IT_IPS]: 'Allocate IT IPs',
  [SPECIAL_MANAGE_IT_ACCOUNTS]: 'Manage IT Accounts',
  [SPECIAL_GENERATE_IT_CREDENTIALS]: 'Generate IT Credentials',
  [SPECIAL_MANAGE_IT_REQUESTS]: 'Manage IT Requests',
  [SPECIAL_VIEW_IT_REPORTS]: 'View IT Reports',
  [SPECIAL_MANAGE_IT_SETTINGS]: 'Manage IT Settings',
  [SPECIAL_MANAGE_IT_DATA_IMPORTS]: 'Manage IT Data Imports',
  [SPECIAL_MANAGE_IT_INVENTORY]: 'Manage IT Inventory',
  [SPECIAL_MANAGE_IT_SOFTWARE]: 'Manage IT Software',
  [SPECIAL_MANAGE_IT_SUPPLIERS]: 'Manage IT Suppliers',
  [SPECIAL_OVERRIDE_IT_ASSET_NUMBER]: 'Override IT Asset Number',
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
  '/help-desk': MODULE_TICKETS,
  '/it': MODULE_IT_OPERATIONS,
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
