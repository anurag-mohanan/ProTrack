import type { Project, Team } from '../types';

export interface ProjectTeamGroup {
  teamId: string | null;
  teamName: string;
  projects: Project[];
}

export function groupProjectsByTeam(projects: Project[], teams: Team[]): ProjectTeamGroup[] {
  const teamNameById = new Map(teams.map((team) => [team.id, team.name]));
  const groups = new Map<string | null, Project[]>();

  for (const project of projects) {
    const key = project.team_id ?? null;
    const list = groups.get(key);
    if (list) list.push(project);
    else groups.set(key, [project]);
  }

  return [...groups.entries()]
    .map(([teamId, teamProjects]) => ({
      teamId,
      teamName: teamId ? teamNameById.get(teamId) ?? 'Unknown team' : 'Unassigned',
      projects: teamProjects,
    }))
    .sort((left, right) => left.teamName.localeCompare(right.teamName));
}

export function filterProjectsForAccessibleTeams(
  projects: Project[],
  accessibleTeamIds: string[] | undefined,
  isAdmin: boolean,
): Project[] {
  if (isAdmin || !accessibleTeamIds?.length) return projects;
  const allowed = new Set(accessibleTeamIds);
  return projects.filter((project) => project.team_id != null && allowed.has(project.team_id));
}
