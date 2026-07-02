import type { SvgIconComponent } from '@mui/icons-material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import ArchiveIcon from '@mui/icons-material/Archive';
import DashboardIcon from '@mui/icons-material/Dashboard';
import FolderIcon from '@mui/icons-material/Folder';
import ScheduleIcon from '@mui/icons-material/Schedule';
import GroupsIcon from '@mui/icons-material/Groups';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';

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
} as const;

export type DashboardRoleGroup =
  | 'admin'
  | 'engineering_manager'
  | 'design_leader'
  | 'staff'
  | 'read_only';

export interface MainNavItem {
  label: string;
  path: string;
  icon: SvgIconComponent;
}

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

export function getDashboardRoleGroup(roleName: string): DashboardRoleGroup {
  const normalized = normalizeRoleName(roleName);
  if (normalized === ROLES.ADMIN) return 'admin';
  if (normalized === ROLES.ENGINEERING_MANAGER) return 'engineering_manager';
  if (normalized === ROLES.DESIGN_LEADER) return 'design_leader';
  if (normalized === ROLES.READ_ONLY) return 'read_only';
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

export function canApproveTimesheet(status: string, roleName: string): boolean {
  if (status !== 'submitted') return false;
  return (
    isOperationalManagerRole(roleName) || isDesignLeaderRole(roleName)
  );
}

export function canRejectTimesheet(status: string, roleName: string): boolean {
  return canApproveTimesheet(status, roleName);
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

export function canImportHistoricalProjects(roleName: string): boolean {
  return isAdminRole(roleName);
}

export function canImportHistoricalTimesheets(roleName: string): boolean {
  return isAdminRole(roleName);
}

export function canAccessAdministration(roleName: string): boolean {
  return isAdminRole(roleName);
}

export function canManageUsers(roleName: string): boolean {
  return isAdminRole(roleName);
}

export function canCreateCustomer(roleName: string): boolean {
  return isAdminRole(roleName);
}

export function canDeleteRecords(roleName: string): boolean {
  return isAdminRole(roleName);
}

export function canViewDeletedProjects(roleName: string): boolean {
  return isAdminRole(roleName);
}

export function canCreateProject(roleName: string): boolean {
  return hasRole(
    roleName,
    ROLES.ADMIN,
    ROLES.ENGINEERING_MANAGER,
    ROLES.DESIGN_LEADER,
  );
}

export function canArchiveProject(roleName: string): boolean {
  return canCreateProject(roleName);
}

export function canSoftDeleteProject(roleName: string): boolean {
  return isAdminRole(roleName);
}

export function canEditProject(roleName: string): boolean {
  return canCreateProject(roleName);
}

export function canViewReports(roleName: string): boolean {
  return hasRole(
    roleName,
    ROLES.ADMIN,
    ROLES.ENGINEERING_MANAGER,
    ROLES.DESIGN_LEADER,
    ROLES.READ_ONLY,
  );
}

export function canViewWorkload(roleName: string): boolean {
  return hasRole(
    roleName,
    ROLES.ADMIN,
    ROLES.ENGINEERING_MANAGER,
    ROLES.DESIGN_LEADER,
  );
}

export function canViewResourcePlanning(roleName: string): boolean {
  return hasRole(roleName, ROLES.ADMIN, ROLES.ENGINEERING_MANAGER);
}

export function canViewArchivedProjects(roleName: string): boolean {
  return isOperationalManagerRole(roleName);
}

export function getMainNavItems(roleName: string): MainNavItem[] {
  const group = getDashboardRoleGroup(roleName);
  const projectsLabel = group === 'staff' ? 'My Projects' : 'Projects';

  if (group === 'read_only') {
    return [
      { label: 'Dashboard', path: '/dashboard', icon: DashboardIcon },
      { label: 'Projects', path: '/projects', icon: FolderIcon },
      { label: 'Reports', path: '/reports', icon: AssessmentIcon },
    ];
  }

  if (group === 'staff') {
    return [
      { label: 'Dashboard', path: '/dashboard', icon: DashboardIcon },
      { label: 'My Projects', path: '/projects', icon: FolderIcon },
      { label: 'Timesheets', path: '/timesheets', icon: ScheduleIcon },
    ];
  }

  if (group === 'design_leader') {
    return [
      { label: 'Dashboard', path: '/dashboard', icon: DashboardIcon },
      { label: projectsLabel, path: '/projects', icon: FolderIcon },
      { label: 'Timesheets', path: '/timesheets', icon: ScheduleIcon },
      { label: 'Workload', path: '/workload', icon: GroupsIcon },
      { label: 'Reports', path: '/reports', icon: AssessmentIcon },
    ];
  }

  const items: MainNavItem[] = [
    { label: 'Dashboard', path: '/dashboard', icon: DashboardIcon },
    { label: projectsLabel, path: '/projects', icon: FolderIcon },
  ];

  if (canViewArchivedProjects(roleName)) {
    items.push({ label: 'Archived Projects', path: '/projects/archived', icon: ArchiveIcon });
  }

  items.push(
    { label: 'Timesheets', path: '/timesheets', icon: ScheduleIcon },
    { label: 'Workload', path: '/workload', icon: GroupsIcon },
    { label: 'Resource Planning', path: '/resource-planning', icon: CalendarMonthIcon },
    { label: 'Reports', path: '/reports', icon: AssessmentIcon },
  );

  return items;
}

export function canOverrideBillable(roleName: string): boolean {
  return isOperationalManagerRole(roleName);
}
