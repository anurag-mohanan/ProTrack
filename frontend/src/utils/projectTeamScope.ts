import type { CurrentUser } from '../types/Auth';
import { canDeleteRecords } from './permissions';

/** Team IDs used to scope project portfolio metrics for leaders (not full-access admins). */
export function getLeaderTeamScopeIds(user: CurrentUser | null | undefined): string[] {
  if (!user) return [];
  if (user.team_ids?.length) return user.team_ids;
  if (user.team_id) return [user.team_id];
  return [];
}

export function shouldScopeProjectsByLeaderTeams(
  roleName: string,
  user: CurrentUser | null | undefined,
): boolean {
  if (canDeleteRecords(roleName)) return false;
  return getLeaderTeamScopeIds(user).length > 0;
}
