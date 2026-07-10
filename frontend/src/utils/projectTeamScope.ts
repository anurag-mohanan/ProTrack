import type { CurrentUser } from '../types/Auth';
import { canDeleteRecords, getDashboardRoleGroup } from './permissions';

/** Team IDs used to scope project portfolio metrics for leaders (not full-access admins). */
export function getLeaderTeamScopeIds(user: CurrentUser | null | undefined): string[] {
  if (!user) return [];
  if (user.team_ids?.length) return user.team_ids;
  if (user.team_id) return [user.team_id];
  return [];
}

/** Scope portfolio UI for non-admins who have team memberships (backend remains authoritative). */
export function shouldScopeProjectsByLeaderTeams(
  roleName: string,
  user: CurrentUser | null | undefined,
): boolean {
  if (canDeleteRecords(roleName)) return false;
  const roleGroup = getDashboardRoleGroup(roleName);
  if (
    roleGroup !== 'engineering_manager' &&
    roleGroup !== 'design_leader' &&
    roleName !== 'Read Only'
  ) {
    // Staff: do not hide cross-util assignments via client-side team filter.
    return false;
  }
  return getLeaderTeamScopeIds(user).length > 0;
}

/** Leaders with assigned teams always get per-team sections; others group when multiple teams exist. */
export function shouldGroupProjectsByTeamForUser(
  roleName: string,
  user: CurrentUser | null | undefined,
  distinctTeamGroupCount: number,
): boolean {
  const leaderTeamIds = getLeaderTeamScopeIds(user);
  if (shouldScopeProjectsByLeaderTeams(roleName, user) && leaderTeamIds.length > 0) {
    return true;
  }
  const roleGroup = getDashboardRoleGroup(roleName);
  if (
    (roleGroup === 'engineering_manager' || roleGroup === 'design_leader') &&
    distinctTeamGroupCount > 1
  ) {
    return true;
  }
  return distinctTeamGroupCount > 1;
}
