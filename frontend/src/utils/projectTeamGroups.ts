import type { Project, Team, User } from '../types';

export interface ProjectTeamGroup {
  teamId: string | null;
  teamName: string;
  projects: Project[];
}

export interface GroupProjectsByTeamOptions {
  /** When set, sections follow this order and include empty managed teams. */
  leaderTeamIds?: string[];
  includeEmptyLeaderTeams?: boolean;
}

function buildUsersById(users: User[]): Map<string, User> {
  return new Map(users.map((user) => [user.id, user]));
}

/** Resolve team from project.team_id or assigned designer / leader / surfacer. */
export function resolveEffectiveProjectTeamId(
  project: Project,
  usersById: Map<string, User>,
): string | null {
  if (project.team_id) return project.team_id;

  const assigneeIds = [
    project.design_leader_id,
    project.designer_id,
    project.surfacer_id,
  ];
  for (const userId of assigneeIds) {
    if (!userId) continue;
    const user = usersById.get(userId);
    if (!user) continue;
    if (user.team_id) return user.team_id;
    const primary = user.team_assignments?.find((assignment) => assignment.is_primary);
    if (primary?.team_id) return primary.team_id;
    const first = user.team_assignments?.[0];
    if (first?.team_id) return first.team_id;
  }
  return null;
}

export function groupProjectsByTeam(
  projects: Project[],
  teams: Team[],
  users: User[] = [],
  options: GroupProjectsByTeamOptions = {},
): ProjectTeamGroup[] {
  const teamNameById = new Map(teams.map((team) => [team.id, team.name]));
  const usersById = buildUsersById(users);
  const groups = new Map<string | null, Project[]>();

  for (const project of projects) {
    const key = resolveEffectiveProjectTeamId(project, usersById);
    const list = groups.get(key);
    if (list) list.push(project);
    else groups.set(key, [project]);
  }

  const baseGroups = [...groups.entries()].map(([teamId, teamProjects]) => ({
    teamId,
    teamName: teamId ? teamNameById.get(teamId) ?? 'Unknown team' : 'Unassigned',
    projects: teamProjects,
  }));

  const leaderTeamIds = options.leaderTeamIds ?? [];
  const includeEmptyLeaderTeams =
    options.includeEmptyLeaderTeams ?? leaderTeamIds.length > 0;

  if (!leaderTeamIds.length) {
    return baseGroups.sort((left, right) => left.teamName.localeCompare(right.teamName));
  }

  const byTeamId = new Map(
    baseGroups
      .filter((group) => group.teamId != null)
      .map((group) => [group.teamId as string, group]),
  );
  const unassigned = baseGroups.find((group) => group.teamId == null);

  const ordered: ProjectTeamGroup[] = leaderTeamIds.map((teamId) => {
    const existing = byTeamId.get(teamId);
    return {
      teamId,
      teamName: teamNameById.get(teamId) ?? existing?.teamName ?? 'Unknown team',
      projects: existing?.projects ?? [],
    };
  });

  if (unassigned?.projects.length) {
    ordered.push(unassigned);
  }

  if (!includeEmptyLeaderTeams) {
    return ordered.filter((group) => group.projects.length > 0);
  }

  return ordered;
}

export function filterProjectsForAccessibleTeams(
  projects: Project[],
  accessibleTeamIds: string[] | undefined,
  isAdmin: boolean,
  users: User[] = [],
  currentUserId?: string | null,
): Project[] {
  if (isAdmin || !accessibleTeamIds?.length) return projects;
  const allowed = new Set(accessibleTeamIds);
  const usersById = buildUsersById(users);
  return projects.filter((project) => {
    if (
      currentUserId &&
      (project.design_leader_id === currentUserId ||
        project.designer_id === currentUserId ||
        project.surfacer_id === currentUserId)
    ) {
      return true;
    }
    const teamId = resolveEffectiveProjectTeamId(project, usersById);
    return teamId != null && allowed.has(teamId);
  });
}

/** Sum of projects across team sections — must match KPI live count. */
export function sumProjectTeamGroupCounts(groups: ProjectTeamGroup[]): number {
  return groups.reduce((total, group) => total + group.projects.length, 0);
}
