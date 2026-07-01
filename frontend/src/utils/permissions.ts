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

export function canSubmitTimesheet(
  status: string,
  ownerId: string,
  currentUserId: string,
  roleName: string,
): boolean {
  if (status !== 'draft') return false;
  if (ownerId === currentUserId) return true;
  return roleName === ROLES.ADMIN || roleName === ROLES.ENGINEERING_MANAGER;
}

export function canApproveTimesheet(status: string, roleName: string): boolean {
  if (status !== 'submitted') return false;
  return (
    roleName === ROLES.ADMIN ||
    roleName === ROLES.ENGINEERING_MANAGER ||
    roleName === ROLES.DESIGN_LEADER
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
    return (
      roleName === ROLES.ADMIN ||
      roleName === ROLES.ENGINEERING_MANAGER ||
      roleName === ROLES.DESIGN_LEADER
    );
  }
  return false;
}

export const PROJECT_STAFF_ROLES = [
  ROLES.SENIOR_DESIGNER,
  ROLES.DESIGNER,
  ROLES.JUNIOR_DESIGNER,
  ROLES.SURFACER,
] as const;

export function isProjectStaffRole(roleName: string): boolean {
  return (PROJECT_STAFF_ROLES as readonly string[]).includes(roleName);
}

export function canImportHistoricalProjects(roleName: string): boolean {
  return roleName === ROLES.ADMIN;
}

export function canImportHistoricalTimesheets(roleName: string): boolean {
  return (
    roleName === ROLES.ADMIN || roleName === ROLES.ENGINEERING_MANAGER
  );
}
export function canAccessAdministration(roleName: string): boolean {
  return hasRole(roleName, ROLES.ADMIN, ROLES.ENGINEERING_MANAGER);
}

export function canManageUsers(roleName: string): boolean {
  return canAccessAdministration(roleName);
}

export function canDeleteRecords(roleName: string): boolean {
  return roleName === ROLES.ADMIN;
}

export function canViewDeletedProjects(roleName: string): boolean {
  return roleName === ROLES.ADMIN;
}

export function canArchiveProject(roleName: string): boolean {
  return canEditProject(roleName);
}

export function canSoftDeleteProject(roleName: string): boolean {
  return roleName === ROLES.ADMIN;
}

export function canEditProject(roleName: string): boolean {
  return (
    roleName === ROLES.ADMIN ||
    roleName === ROLES.ENGINEERING_MANAGER ||
    roleName === ROLES.DESIGN_LEADER ||
    roleName === ROLES.SENIOR_DESIGNER
  );
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
  return canViewReports(roleName);
}

export function canViewResourcePlanning(roleName: string): boolean {
  return canViewReports(roleName);
}

export function isReadOnlyRole(roleName: string): boolean {
  return hasRole(roleName, ROLES.READ_ONLY);
}

export function canOverrideBillable(roleName: string): boolean {
  return roleName === ROLES.ADMIN || roleName === ROLES.ENGINEERING_MANAGER;
}
