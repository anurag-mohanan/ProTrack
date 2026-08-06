import type { CurrentUser } from '../types/Auth';
import type { Project, Stream, Team, User } from '../types';
import {
  filterProjectsForAccessibleTeams,
  groupProjectsByTeam,
  type ProjectTeamGroup,
} from './projectTeamGroups';
import { getLeaderTeamScopeIds } from './projectTeamScope';

export type ProjectsPortfolioScope = 'my_streams' | 'my_teams' | 'all';

export const PROJECTS_PORTFOLIO_SCOPES: ProjectsPortfolioScope[] = [
  'my_streams',
  'my_teams',
  'all',
];

export function normalizeProjectsPortfolioScope(
  value: string | null | undefined,
): ProjectsPortfolioScope {
  if (value === 'my_teams' || value === 'all' || value === 'my_streams') {
    return value;
  }
  return 'my_streams';
}

export function canSelectAllProjectsScope(user: CurrentUser | null | undefined): boolean {
  return Boolean(user?.can_view_all_streams);
}

export function resolveRelevantStreamIds(
  user: CurrentUser | null | undefined,
  projects: Project[],
): Set<string> {
  const ids = new Set<string>(user?.relevant_stream_ids ?? []);
  if (user?.stream_id) ids.add(user.stream_id);
  if (user?.id) {
    for (const project of projects) {
      if (
        project.stream_id &&
        (project.designer_id === user.id ||
          project.design_leader_id === user.id ||
          project.surfacer_id === user.id)
      ) {
        ids.add(project.stream_id);
      }
    }
  }
  return ids;
}

export function filterProjectsByPortfolioScope(
  projects: Project[],
  scope: ProjectsPortfolioScope,
  user: CurrentUser | null | undefined,
  users: User[],
  options: { isAdmin: boolean },
): Project[] {
  const { isAdmin } = options;
  if (scope === 'all') {
    if (!canSelectAllProjectsScope(user) && !isAdmin) {
      return filterProjectsByPortfolioScope(projects, 'my_streams', user, users, {
        isAdmin,
      });
    }
    return projects;
  }

  if (scope === 'my_teams') {
    const teamIds = getLeaderTeamScopeIds(user);
    return filterProjectsForAccessibleTeams(
      projects,
      teamIds.length ? teamIds : undefined,
      isAdmin,
      users,
      user?.id,
    );
  }

  // my_streams
  const streamIds = resolveRelevantStreamIds(user, projects);
  if (!streamIds.size) {
    // No stream signal yet — fall back to personal assignments / team scope.
    return filterProjectsByPortfolioScope(projects, 'my_teams', user, users, { isAdmin });
  }
  return projects.filter(
    (project) => project.stream_id != null && streamIds.has(project.stream_id),
  );
}

export interface ProjectStreamSection {
  streamId: string | null;
  streamName: string;
  teamGroups: ProjectTeamGroup[];
  projectCount: number;
}

export function groupProjectsByStreamThenTeam(
  projects: Project[],
  streams: Stream[],
  teams: Team[],
  users: User[],
  options?: {
    leaderTeamIds?: string[];
    includeEmptyLeaderTeams?: boolean;
    /** When set, only emit these streams (plus unassigned when present). */
    preferredStreamOrder?: string[];
  },
): ProjectStreamSection[] {
  const streamNameById = new Map(streams.map((stream) => [stream.id, stream.name]));
  const byStream = new Map<string | null, Project[]>();

  for (const project of projects) {
    const key = project.stream_id;
    const list = byStream.get(key);
    if (list) list.push(project);
    else byStream.set(key, [project]);
  }

  const preferred = options?.preferredStreamOrder;
  const orderedKeys: Array<string | null> = [];
  if (preferred?.length) {
    for (const id of preferred) {
      if (byStream.has(id)) orderedKeys.push(id);
    }
    for (const key of byStream.keys()) {
      if (key != null && !orderedKeys.includes(key)) orderedKeys.push(key);
    }
    if (byStream.has(null)) orderedKeys.push(null);
  } else {
    orderedKeys.push(
      ...[...byStream.keys()].sort((left, right) => {
        if (left == null) return 1;
        if (right == null) return -1;
        const leftName = streamNameById.get(left) ?? 'Unknown stream';
        const rightName = streamNameById.get(right) ?? 'Unknown stream';
        return leftName.localeCompare(rightName);
      }),
    );
  }

  return orderedKeys.map((streamId) => {
    const streamProjects = byStream.get(streamId) ?? [];
    const teamGroups = groupProjectsByTeam(streamProjects, teams, users, {
      leaderTeamIds: options?.leaderTeamIds,
      includeEmptyLeaderTeams: options?.includeEmptyLeaderTeams,
    });
    return {
      streamId,
      streamName: streamId
        ? streamNameById.get(streamId) ?? 'Unknown stream'
        : 'Unassigned stream',
      teamGroups,
      projectCount: streamProjects.length,
    };
  });
}

export function isMoldStreamName(name: string | null | undefined): boolean {
  return Boolean(name && name.toLowerCase().includes('mold'));
}

export function projectReferenceLabel(streamName: string | null | undefined): string {
  return isMoldStreamName(streamName) ? 'Tool Number' : 'Project Reference';
}

export function projectReferenceTooltip(streamName: string | null | undefined): string {
  return isMoldStreamName(streamName)
    ? 'Customer tool or mold number used to uniquely identify the project.'
    : 'Customer or internal reference used to uniquely identify the project.';
}
