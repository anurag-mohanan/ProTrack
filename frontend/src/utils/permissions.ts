export const ROLES = {
  ADMIN: 'Admin',
  ENGINEERING_MANAGER: 'Engineering Manager',
  DESIGN_LEADER: 'Design Leader',
  SENIOR_DESIGNER: 'Senior Designer',
  DESIGNER: 'Designer',
  JUNIOR_DESIGNER: 'Junior Designer',
  SURFACER: 'Surfacer',
} as const;

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
export function canManageUsers(roleName: string): boolean {
  return roleName === ROLES.ADMIN;
}

export function canDeleteRecords(roleName: string): boolean {
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
  return (
    roleName === ROLES.ADMIN ||
    roleName === ROLES.ENGINEERING_MANAGER ||
    roleName === ROLES.DESIGN_LEADER
  );
}

export function canViewWorkload(roleName: string): boolean {
  return canViewReports(roleName);
}
