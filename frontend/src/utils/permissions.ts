import type { SvgIconComponent } from '@mui/icons-material';
import AssessmentRoundedIcon from '@mui/icons-material/AssessmentRounded';
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded';
import FolderRoundedIcon from '@mui/icons-material/FolderRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import CalendarMonthRoundedIcon from '@mui/icons-material/CalendarMonthRounded';
import AccountBalanceRoundedIcon from '@mui/icons-material/AccountBalanceRounded';
import BadgeRoundedIcon from '@mui/icons-material/BadgeRounded';
import AccountTreeRoundedIcon from '@mui/icons-material/AccountTreeRounded';
import InsightsRoundedIcon from '@mui/icons-material/InsightsRounded';
import SupportAgentRoundedIcon from '@mui/icons-material/SupportAgentRounded';
import HowToRegRoundedIcon from '@mui/icons-material/HowToRegRounded';
import SchoolRoundedIcon from '@mui/icons-material/SchoolRounded';
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded';
import HistoryEduRoundedIcon from '@mui/icons-material/HistoryEduRounded';
import FactCheckRoundedIcon from '@mui/icons-material/FactCheckRounded';
import DevicesOtherRoundedIcon from '@mui/icons-material/DevicesOtherRounded';
import LanRoundedIcon from '@mui/icons-material/LanRounded';
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import PeopleAltRoundedIcon from '@mui/icons-material/PeopleAltRounded';
import AppsRoundedIcon from '@mui/icons-material/AppsRounded';
import BuildRoundedIcon from '@mui/icons-material/BuildRounded';
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded';
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded';
import type { CurrentUser } from '../types';
import {
  ALL_MODULES,
  ALL_SPECIAL_PERMISSIONS,
  MODULE_ARCHIVED_PROJECTS,
  MODULE_DASHBOARD,
  MODULE_FINANCIAL_PLANNING,
  MODULE_HUMAN_RESOURCES,
  MODULE_IT_OPERATIONS,
  MODULE_PERFORMANCE,
  MODULE_PROJECTS,
  MODULE_REPORTS,
  MODULE_REPORTS_ANALYTICS,
  MODULE_RESOURCE_PLANNING,
  MODULE_SYSTEM_ADMINISTRATION,
  MODULE_TIMESHEETS,
  MODULE_WORKLOAD,
  MODULE_PLANNING_BOARD,
  MODULE_CALENDAR,
  MODULE_TICKETS,
  SPECIAL_ALLOCATE_IT_IPS,
  SPECIAL_APPROVE_TIMESHEETS,
  SPECIAL_ARCHIVE_PROJECTS,
  SPECIAL_ASSIGN_IT_ASSETS,
  SPECIAL_CREATE_PROJECTS,
  SPECIAL_DELETE_PROJECTS,
  SPECIAL_EDIT_PROJECTS,
  SPECIAL_EXPORT_REPORTS,
  SPECIAL_IMPORT_TIMESHEETS,
  SPECIAL_MANAGE_COMPANY_SETTINGS,
  SPECIAL_MANAGE_CONTACTS,
  SPECIAL_MANAGE_CUSTOMERS,
  SPECIAL_MANAGE_IT_ASSETS,
  SPECIAL_MANAGE_IT_NETWORKS,
  SPECIAL_MANAGE_IT_SETTINGS,
  SPECIAL_MANAGE_IT_SOFTWARE,
  SPECIAL_MANAGE_IT_SUPPLIERS,
  SPECIAL_MANAGE_IT_ACCOUNTS,
  SPECIAL_MANAGE_PROJECT_SETTINGS,
  SPECIAL_MANAGE_TEAMS,
  SPECIAL_MANAGE_USERS,
  SPECIAL_RETURN_CUSTOMER_ASSETS,
  SPECIAL_VIEW_IT_OPERATIONS,
  SPECIAL_VIEW_IT_REPORTS,
  SPECIAL_VIEW_REPORTS,
  SPECIAL_VIEW_RESOURCE_PLANNING,
  type ModuleKey,
  type SpecialPermissionKey,
} from '../config/accessControl';
export const ROLES = {
  ADMIN: 'Admin',
  MANAGING_DIRECTOR: 'Managing Director',
  DIRECTOR_OF_ENGINEERING: 'Director of Engineering',
  DIRECTOR_OF_SALES: 'Director of Sales',
  DIRECTOR_OF_HR: 'Director of HR',
  DIRECTOR_OF_ACCOUNTS: 'Director of Accounts',
  DIRECTOR_OF_IT: 'Director of IT',
  DIRECTOR: 'Director',
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

/** Executive / leadership tier (MD + Directors) — company-wide oversight. */
export const EXECUTIVE_ROLES: readonly string[] = [
  ROLES.MANAGING_DIRECTOR,
  ROLES.DIRECTOR_OF_ENGINEERING,
  ROLES.DIRECTOR_OF_SALES,
  ROLES.DIRECTOR_OF_HR,
  ROLES.DIRECTOR_OF_ACCOUNTS,
  ROLES.DIRECTOR_OF_IT,
  ROLES.DIRECTOR,
];

export function isExecutiveRole(roleName: string): boolean {
  return EXECUTIVE_ROLES.includes(normalizeRoleName(roleName));
}

// Roles that work help-desk queues (mirror of ticketing_service agent roles).
export const TICKET_AGENT_ROLES: readonly string[] = [
  ROLES.ADMIN,
  ...EXECUTIVE_ROLES,
  'Director of IT',
  'IT Manager',
  'System Administrator',
  'IT Executive',
  'IT Support Engineer',
  'Director of HR',
  'HR Manager',
  'HR Executive',
  ROLES.HR,
  'HR Assistant',
  ROLES.OFFICE_ADMINISTRATOR,
];

export function isTicketAgentRole(roleName?: string | null): boolean {
  if (!roleName) return false;
  return TICKET_AGENT_ROLES.some(
    (role) => normalizeRoleName(role) === normalizeRoleName(roleName),
  );
}

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
  requires_timesheet?: boolean;
  can_enter_own_timesheet?: boolean;
  can_view_organization_chart?: boolean;
}

// Executive tier: every business module except System Administration (Admin/IT).
const EXECUTIVE_MODULES: ModuleKey[] = ALL_MODULES.filter(
  (module) => module !== MODULE_SYSTEM_ADMINISTRATION,
);

const DEFAULT_MODULES_BY_ROLE: Record<string, ModuleKey[]> = {
  [ROLES.ADMIN]: [...ALL_MODULES],
  [ROLES.MANAGING_DIRECTOR]: EXECUTIVE_MODULES,
  [ROLES.DIRECTOR_OF_ENGINEERING]: EXECUTIVE_MODULES,
  [ROLES.DIRECTOR_OF_SALES]: EXECUTIVE_MODULES,
  [ROLES.DIRECTOR_OF_HR]: EXECUTIVE_MODULES,
  [ROLES.DIRECTOR_OF_ACCOUNTS]: EXECUTIVE_MODULES,
  [ROLES.DIRECTOR_OF_IT]: EXECUTIVE_MODULES,
  [ROLES.DIRECTOR]: EXECUTIVE_MODULES,
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
    MODULE_CALENDAR,
    MODULE_PERFORMANCE,
  ],
  [ROLES.DESIGN_LEADER]: [
    MODULE_DASHBOARD,
    MODULE_PROJECTS,
    MODULE_ARCHIVED_PROJECTS,
    MODULE_TIMESHEETS,
    MODULE_WORKLOAD,
    MODULE_REPORTS_ANALYTICS,
    MODULE_CALENDAR,
    MODULE_PERFORMANCE,
  ],
  [ROLES.DESIGNER]: [MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS, MODULE_PERFORMANCE],
  [ROLES.SENIOR_DESIGNER]: [MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS, MODULE_PERFORMANCE],
  [ROLES.JUNIOR_DESIGNER]: [MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS, MODULE_PERFORMANCE],
  [ROLES.SURFACER]: [MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_TIMESHEETS, MODULE_PERFORMANCE],
  [ROLES.READ_ONLY]: [MODULE_DASHBOARD, MODULE_PROJECTS, MODULE_REPORTS_ANALYTICS, MODULE_PERFORMANCE],
  [ROLES.PLANNING_BOARD]: [MODULE_PLANNING_BOARD],
  [ROLES.HR]: [
    MODULE_DASHBOARD,
    MODULE_HUMAN_RESOURCES,
    MODULE_TIMESHEETS,
    MODULE_REPORTS_ANALYTICS,
    MODULE_PERFORMANCE,
  ],
  [ROLES.OFFICE_ADMINISTRATOR]: [
    MODULE_DASHBOARD,
    MODULE_HUMAN_RESOURCES,
    MODULE_TIMESHEETS,
    MODULE_REPORTS_ANALYTICS,
    MODULE_PERFORMANCE,
  ],
};

// Fallback specials (pre-/me only). The backend supplies the full executive set
// (approvals + financial-field visibility) via resolved_special_permissions.
const EXECUTIVE_SPECIALS: SpecialPermissionKey[] = [
  SPECIAL_VIEW_REPORTS,
  SPECIAL_EXPORT_REPORTS,
  SPECIAL_VIEW_RESOURCE_PLANNING,
];

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
    SPECIAL_MANAGE_PROJECT_SETTINGS,
    SPECIAL_VIEW_REPORTS,
    SPECIAL_VIEW_RESOURCE_PLANNING,
  ],
  [ROLES.MANAGING_DIRECTOR]: EXECUTIVE_SPECIALS,
  [ROLES.DIRECTOR_OF_ENGINEERING]: EXECUTIVE_SPECIALS,
  [ROLES.DIRECTOR_OF_SALES]: EXECUTIVE_SPECIALS,
  [ROLES.DIRECTOR_OF_HR]: EXECUTIVE_SPECIALS,
  [ROLES.DIRECTOR_OF_ACCOUNTS]: EXECUTIVE_SPECIALS,
  [ROLES.DIRECTOR_OF_IT]: EXECUTIVE_SPECIALS,
  [ROLES.DIRECTOR]: EXECUTIVE_SPECIALS,
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
  visible?: (ctx: AccessContext) => boolean;
}> = [
  { module: MODULE_DASHBOARD, label: 'Dashboard', path: '/dashboard', icon: DashboardRoundedIcon },
  {
    module: MODULE_PROJECTS,
    label: (ctx) => (getDashboardRoleGroup(ctx.role_name) === 'staff' ? 'My Projects' : 'Projects'),
    path: '/projects',
    icon: FolderRoundedIcon,
  },
  // Archived projects intentionally omitted from Engineering Operations primary nav
  // (Ops/EM: not a day-to-day strip item). Reach via Projects filters or Admin → Archived Records.
  { module: MODULE_TIMESHEETS, label: 'Timesheets', path: '/timesheets', icon: ScheduleRoundedIcon },
  { module: MODULE_WORKLOAD, label: 'Workload', path: '/workload', icon: GroupsRoundedIcon },
  {
    module: MODULE_RESOURCE_PLANNING,
    label: 'Resource Planning',
    path: '/resource-planning',
    icon: CalendarMonthRoundedIcon,
  },
  { module: MODULE_CALENDAR, label: 'Calendar', path: '/calendar', icon: CalendarMonthRoundedIcon },
  {
    module: MODULE_PLANNING_BOARD,
    label: 'Planning Board',
    path: '/planning-board',
    icon: CalendarMonthRoundedIcon,
  },
];

type SectionNavConfigItem = {
  module: ModuleKey;
  label: string | ((ctx: AccessContext) => string);
  path: string;
  icon: SvgIconComponent;
  visible?: (ctx: AccessContext) => boolean;
};

// Operations: cross-functional business planning, finance, and reporting.
const OPERATIONS_SECTION_NAV: SectionNavConfigItem[] = [
  {
    module: MODULE_FINANCIAL_PLANNING,
    label: 'Financial Planning',
    path: '/finance',
    icon: AccountBalanceRoundedIcon,
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

// Human Resources: people operations — HR workspace, performance, org chart, help desk.
const HR_SECTION_NAV: SectionNavConfigItem[] = [
  {
    module: MODULE_HUMAN_RESOURCES,
    label: 'HR Dashboard',
    path: '/hr',
    icon: GroupsRoundedIcon,
  },
  {
    module: MODULE_HUMAN_RESOURCES,
    label: 'Onboarding',
    path: '/hr/onboarding',
    icon: HowToRegRoundedIcon,
  },
  {
    module: MODULE_HUMAN_RESOURCES,
    label: 'Training',
    path: '/hr/training',
    icon: SchoolRoundedIcon,
  },
  {
    module: MODULE_HUMAN_RESOURCES,
    label: 'Exit process',
    path: '/hr/exit-process',
    icon: LogoutRoundedIcon,
  },
  {
    module: MODULE_HUMAN_RESOURCES,
    label: 'Past employees',
    path: '/hr/past-employees',
    icon: HistoryEduRoundedIcon,
  },
  {
    module: MODULE_HUMAN_RESOURCES,
    label: 'Process Audit',
    path: '/hr/process-audit',
    icon: FactCheckRoundedIcon,
  },
  {
    module: MODULE_PERFORMANCE,
    label: 'Performance',
    path: '/performance',
    icon: BadgeRoundedIcon,
  },
  {
    module: MODULE_DASHBOARD,
    label: 'Organization Chart',
    path: '/organization',
    icon: AccountTreeRoundedIcon,
    visible: (ctx: AccessContext) => canViewOrganizationChart(ctx),
  },
  {
    module: MODULE_TICKETS,
    label: 'Help Desk',
    path: '/help-desk',
    icon: SupportAgentRoundedIcon,
  },
];

const IT_SECTION_NAV: SectionNavConfigItem[] = [
  {
    module: MODULE_IT_OPERATIONS,
    label: 'IT Dashboard',
    path: '/it',
    icon: DevicesOtherRoundedIcon,
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'Assets & Inventory',
    path: '/it/assets',
    icon: InventoryRoundedIcon,
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'Returned Assets',
    path: '/it/returned-assets',
    icon: HistoryRoundedIcon,
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'Computers',
    path: '/it/computers',
    icon: DevicesOtherRoundedIcon,
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'Network / IP',
    path: '/it/networks',
    icon: LanRoundedIcon,
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'Users & Accounts',
    path: '/it/accounts',
    icon: PeopleAltRoundedIcon,
    visible: (ctx: AccessContext) =>
      userHasSpecial(ctx, SPECIAL_MANAGE_IT_ACCOUNTS) || canViewItOperations(ctx),
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'Software & Licenses',
    path: '/it/software',
    icon: AppsRoundedIcon,
    visible: (ctx: AccessContext) =>
      userHasSpecial(ctx, SPECIAL_MANAGE_IT_SOFTWARE) || canViewItOperations(ctx),
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'IT Requests',
    path: '/it/requests',
    icon: SupportAgentRoundedIcon,
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'Maintenance',
    path: '/it/maintenance',
    icon: BuildRoundedIcon,
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'Suppliers',
    path: '/it/suppliers',
    icon: LocalShippingRoundedIcon,
    visible: (ctx: AccessContext) =>
      userHasSpecial(ctx, SPECIAL_MANAGE_IT_SUPPLIERS) || canViewItOperations(ctx),
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'Reports',
    path: '/it/reports',
    icon: AssessmentRoundedIcon,
    visible: (ctx: AccessContext) =>
      userHasSpecial(ctx, SPECIAL_VIEW_IT_REPORTS) || canViewItOperations(ctx),
  },
  {
    module: MODULE_IT_OPERATIONS,
    label: 'IT Settings',
    path: '/it/settings',
    icon: SettingsRoundedIcon,
    visible: (ctx: AccessContext) => canManageItSettings(ctx),
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

export function hasRole(roleName: string, ...roles: string[]): boolean {
  const normalized = normalizeRoleName(roleName);
  return roles.some((role) => normalizeRoleName(role) === normalized);
}

export function accessContextFromUser(user: CurrentUser | null | undefined): AccessContext {
  return {
    role_name: user?.role_name ?? '',
    resolved_modules: user?.resolved_modules ?? user?.module_access,
    resolved_special_permissions: user?.resolved_special_permissions ?? user?.special_permissions,
    requires_timesheet: user?.requires_timesheet,
    can_enter_own_timesheet: user?.can_enter_own_timesheet,
    can_view_organization_chart: user?.can_view_organization_chart,
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
  const base = DEFAULT_MODULES_BY_ROLE[normalized] ?? DEFAULT_MODULES_BY_ROLE[ROLES.DESIGNER];
  // Help Desk is company-wide — every user can raise a ticket.
  if (!base.includes(MODULE_TICKETS)) {
    return [...base, MODULE_TICKETS];
  }
  return base;
}

export function defaultSpecialPermissionsForRole(roleName: string): SpecialPermissionKey[] {
  const normalized = normalizeRoleName(roleName);
  return DEFAULT_SPECIAL_BY_ROLE[normalized] ?? [];
}

export function resolveModules(ctx: AccessContext): ModuleKey[] {
  if (normalizeRoleName(ctx.role_name) === ROLES.ADMIN) {
    return [...ALL_MODULES];
  }
  let modules: ModuleKey[];
  if (ctx.resolved_modules?.length) {
    modules = ctx.resolved_modules.filter((module): module is ModuleKey =>
      ALL_MODULES.includes(module as ModuleKey),
    );
  } else {
    modules = defaultModulesForRole(ctx.role_name);
  }
  // Performance previously gated by Dashboard — keep nav parity for stale tokens.
  if (modules.includes(MODULE_DASHBOARD) && !modules.includes(MODULE_PERFORMANCE)) {
    modules = [...modules, MODULE_PERFORMANCE];
  }
  // Help Desk is company-wide — surface it for every user (incl. stale tokens).
  if (!modules.includes(MODULE_TICKETS)) {
    modules = [...modules, MODULE_TICKETS];
  }
  return modules;
}

export function resolveSpecialPermissions(ctx: AccessContext): SpecialPermissionKey[] {
  if (normalizeRoleName(ctx.role_name) === ROLES.ADMIN) {
    return [...ALL_SPECIAL_PERMISSIONS];
  }
  if (ctx.resolved_special_permissions != null) {
    return ctx.resolved_special_permissions.filter((permission): permission is SpecialPermissionKey =>
      Boolean(permission),
    ) as SpecialPermissionKey[];
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
  // Executive tier gets the company-wide management dashboard (no admin-only calls).
  if (isExecutiveRole(normalized)) return 'engineering_manager';
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

/** Org chart module: only when /me says so (Admin, EM, or team leaders). */
export function canViewOrganizationChart(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  if (typeof ctx.can_view_organization_chart === 'boolean') {
    return ctx.can_view_organization_chart;
  }
  // Fallback before /me loads — never expose to Design Leader without the flag.
  return (
    isAdminRole(ctx.role_name) ||
    isEngineeringManagerRole(ctx.role_name) ||
    isExecutiveRole(ctx.role_name)
  );
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
 * Admins always can; managers/leaders with approve permission can view teams they oversee.
 * HR / Office Administrator get all-teams read-only overview for completion chasing.
 */
export function canViewAllTimesheets(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  if (isAdminRole(ctx.role_name)) return true;
  if (hasRole(ctx.role_name, ROLES.HR, ROLES.OFFICE_ADMINISTRATOR)) return true;
  if (userHasSpecial(ctx, SPECIAL_APPROVE_TIMESHEETS)) return true;
  return isOperationalManagerRole(ctx.role_name) || isDesignLeaderRole(ctx.role_name);
}

/**
 * Whether the user should get the personal timesheet-entry form.
 * Driven by server policy (Admin/HR/Planning Board/Read Only never fill).
 * EM may optionally log; designers/Design Leaders fill when can_enter_own_timesheet is true.
 */
export function canEnterOwnTimesheet(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  // Role exemption wins over a stale /me flag (HR / Office Admin never fill).
  if (hasRole(ctx.role_name, ROLES.HR, ROLES.OFFICE_ADMINISTRATOR)) {
    return false;
  }
  if (typeof ctx.can_enter_own_timesheet === 'boolean') {
    return ctx.can_enter_own_timesheet;
  }
  // Fallback before /me is enriched: never Admin / Planning Board / Read Only.
  if (isAdminRole(ctx.role_name) || isReadOnlyRole(ctx.role_name) || isPlanningBoardRole(ctx.role_name)) {
    return false;
  }
  return true;
}

export function userRequiresTimesheet(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  if (typeof ctx.requires_timesheet === 'boolean') {
    return ctx.requires_timesheet;
  }
  return (
    isDesignLeaderRole(ctx.role_name) ||
    isProjectStaffRole(ctx.role_name) ||
    isSurfacerRole(ctx.role_name)
  );
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
  return isAdminRole(ctx.role_name);
}

export function canViewDeletedProjects(roleNameOrContext: string | AccessContext): boolean {
  return canAccessAdministration(roleNameOrContext);
}

export function canCreateProject(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasModule(ctx, MODULE_PROJECTS) && userHasSpecial(ctx, SPECIAL_CREATE_PROJECTS);
}

export function canArchiveProject(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_ARCHIVE_PROJECTS);
}

export function canDeleteProject(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_DELETE_PROJECTS);
}

export function canSoftDeleteProject(roleNameOrContext: string | AccessContext): boolean {
  return canDeleteProject(roleNameOrContext);
}

export function canEditProject(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasModule(ctx, MODULE_PROJECTS) && userHasSpecial(ctx, SPECIAL_EDIT_PROJECTS);
}

export function canManageProjectSettings(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_MANAGE_PROJECT_SETTINGS);
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

export function canViewItOperations(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasModule(ctx, MODULE_IT_OPERATIONS) || userHasSpecial(ctx, SPECIAL_VIEW_IT_OPERATIONS);
}

export function canManageItAssets(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_MANAGE_IT_ASSETS);
}

export function canAssignItAssets(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_ASSIGN_IT_ASSETS);
}

export function canReturnCustomerAssets(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_RETURN_CUSTOMER_ASSETS);
}

export function canManageItNetworks(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_MANAGE_IT_NETWORKS);
}

export function canAllocateItIps(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_ALLOCATE_IT_IPS);
}

export function canManageItSettings(roleNameOrContext: string | AccessContext): boolean {
  const ctx = toAccessContext(roleNameOrContext);
  return userHasSpecial(ctx, SPECIAL_MANAGE_IT_SETTINGS);
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
      {
        module: MODULE_TICKETS,
        path: '/help-desk',
        icon: SupportAgentRoundedIcon,
        label: 'Help Desk',
      },
    ];
  }
  const modules = new Set(resolveModules(ctx));

  return NAV_MODULE_CONFIG.filter((item) => modules.has(item.module))
    .filter((item) => !item.visible || item.visible(ctx))
    .map((item) => ({
    module: item.module,
    path: item.path,
    icon: item.icon,
    label: typeof item.label === 'function' ? item.label(ctx) : item.label,
  }));
}

function buildSectionNavItems(
  ctx: AccessContext,
  config: SectionNavConfigItem[],
): MainNavItem[] {
  if (isPlanningBoardRole(ctx.role_name)) {
    return [];
  }
  const modules = new Set(resolveModules(ctx));
  const items: MainNavItem[] = [];
  const seenPaths = new Set<string>();

  for (const item of config) {
    if (!modules.has(item.module)) continue;
    if (item.visible && !item.visible(ctx)) continue;
    // Prefer analytics hub over duplicate engineering reports when both exist
    if (item.path === '/reports' && modules.has(MODULE_REPORTS_ANALYTICS)) continue;
    if (seenPaths.has(item.path)) continue;
    seenPaths.add(item.path);
    items.push({
      module: item.module,
      path: item.path,
      icon: item.icon,
      label: typeof item.label === 'function' ? item.label(ctx) : item.label,
    });
  }
  return items;
}

export function getOperationsSectionNavItems(
  roleNameOrContext: string | AccessContext,
): MainNavItem[] {
  return buildSectionNavItems(toAccessContext(roleNameOrContext), OPERATIONS_SECTION_NAV);
}

export function getHrSectionNavItems(
  roleNameOrContext: string | AccessContext,
): MainNavItem[] {
  return buildSectionNavItems(toAccessContext(roleNameOrContext), HR_SECTION_NAV);
}

export function getItSectionNavItems(
  roleNameOrContext: string | AccessContext,
): MainNavItem[] {
  return buildSectionNavItems(toAccessContext(roleNameOrContext), IT_SECTION_NAV);
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
