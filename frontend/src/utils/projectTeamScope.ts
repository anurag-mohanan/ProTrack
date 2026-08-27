import type { CurrentUser } from '../types/Auth';
import { canDeleteRecords, getDashboardRoleGroup } from './permissions';

/** Team IDs used to scope project portfolio for members and leaders (not full-access admins). */
export function getLeaderTeamScopeIds(user: CurrentUser | null | undefined): string[] {
  if (!user) return [];
  if (user.team_ids?.length) return user.team_ids;
  if (user.team_id) return [user.team_id];
  return [];
}

/**
 * Scope portfolio UI to the user's team memberships.
 * Staff and leaders both see only their team(s); Admin / unrestricted roles stay unscoped.
 */
export function shouldScopeProjectsByLeaderTeams(
  roleName: string,
  user: CurrentUser | null | undefined,
): boolean {
  if (canDeleteRecords(roleName)) return false;
  return getLeaderTeamScopeIds(user).length > 0;
}

/** True when the user belongs to more than one team. */
export function userHasMultipleTeams(user: CurrentUser | null | undefined): boolean {
  return getLeaderTeamScopeIds(user).length > 1;
}

/**
 * Multi-team members/leaders get per-team sections.
 * Single-team users stay flat unless the filtered result spans multiple teams.
 */
export function shouldGroupProjectsByTeamForUser(
  roleName: string,
  user: CurrentUser | null | undefined,
  distinctTeamGroupCount: number,
): boolean {
  if (userHasMultipleTeams(user)) return true;
  if (distinctTeamGroupCount > 1) {
    const roleGroup = getDashboardRoleGroup(roleName);
    if (
      roleGroup === 'engineering_manager' ||
      roleGroup === 'design_leader' ||
      roleGroup === 'staff' ||
      roleName === 'Read Only'
    ) {
      return true;
    }
  }
  return false;
}
