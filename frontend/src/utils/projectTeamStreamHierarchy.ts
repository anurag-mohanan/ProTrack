import type { Project, Stream, Team, User } from '../types';
import {
  groupProjectsByTeam,
  type GroupProjectsByTeamOptions,
  type ProjectTeamGroup,
} from './projectTeamGroups';
import { isCompletedProject, isLiveProject, isOverdueProject } from './projectCommandCenter';

export interface ProjectStreamStatusGroup {
  streamId: string | null;
  streamName: string;
  activeProjects: Project[];
  completedProjects: Project[];
  activeCount: number;
  completedCount: number;
  overdueCount: number;
  fullDesignCount: number;
  smallTaskCount: number;
}

export interface ProjectTeamStreamSection {
  teamId: string | null;
  teamName: string;
  streams: ProjectStreamStatusGroup[];
  activeCount: number;
  completedCount: number;
  overdueCount: number;
  fullDesignCount: number;
  smallTaskCount: number;
}

export interface TeamStreamHierarchyOptions extends GroupProjectsByTeamOptions {
  preferredStreamOrder?: string[];
}

function streamNameFor(
  streamId: string | null,
  streamNameById: Map<string, string>,
): string {
  if (!streamId) return 'Unassigned stream';
  return streamNameById.get(streamId) ?? 'Unknown stream';
}

function countClassification(projects: Project[]) {
  let fullDesign = 0;
  let smallTask = 0;
  for (const project of projects) {
    if (project.project_classification === 'full_design') fullDesign += 1;
    if (project.project_classification === 'small_task') smallTask += 1;
  }
  return { fullDesign, smallTask };
}

function groupTeamProjectsByStream(
  projects: Project[],
  streamNameById: Map<string, string>,
  preferredStreamOrder?: string[],
): ProjectStreamStatusGroup[] {
  const byStream = new Map<string | null, { active: Project[]; completed: Project[] }>();

  for (const project of projects) {
    const key = project.stream_id ?? null;
    const bucket = byStream.get(key) ?? { active: [], completed: [] };
    if (isCompletedProject(project)) bucket.completed.push(project);
    else if (isLiveProject(project)) bucket.active.push(project);
    byStream.set(key, bucket);
  }

  const orderedKeys: Array<string | null> = [];
  if (preferredStreamOrder?.length) {
    for (const id of preferredStreamOrder) {
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
        return streamNameFor(left, streamNameById).localeCompare(
          streamNameFor(right, streamNameById),
        );
      }),
    );
  }

  return orderedKeys.map((streamId) => {
    const bucket = byStream.get(streamId) ?? { active: [], completed: [] };
    const all = [...bucket.active, ...bucket.completed];
    const overdueCount = bucket.active.filter((project) => isOverdueProject(project)).length;
    const classification = countClassification(all);
    return {
      streamId,
      streamName: streamNameFor(streamId, streamNameById),
      activeProjects: bucket.active,
      completedProjects: bucket.completed,
      activeCount: bucket.active.length,
      completedCount: bucket.completed.length,
      overdueCount,
      fullDesignCount: classification.fullDesign,
      smallTaskCount: classification.smallTask,
    };
  });
}

/** Team → Stream → Active/Completed hierarchy for the command center. */
export function groupProjectsByTeamThenStream(
  projects: Project[],
  teams: Team[],
  streams: Stream[],
  users: User[] = [],
  options: TeamStreamHierarchyOptions = {},
): ProjectTeamStreamSection[] {
  const streamNameById = new Map(streams.map((stream) => [stream.id, stream.name]));
  const teamGroups = groupProjectsByTeam(projects, teams, users, options);

  return teamGroups
    .map((group: ProjectTeamGroup) => {
      const streamSections = groupProjectsByStream(
        group.projects,
        streamNameById,
        options.preferredStreamOrder,
      ).filter((section) => section.activeCount > 0 || section.completedCount > 0);

      const activeCount = streamSections.reduce((sum, section) => sum + section.activeCount, 0);
      const completedCount = streamSections.reduce(
        (sum, section) => sum + section.completedCount,
        0,
      );
      const overdueCount = streamSections.reduce((sum, section) => sum + section.overdueCount, 0);
      const fullDesignCount = streamSections.reduce(
        (sum, section) => sum + section.fullDesignCount,
        0,
      );
      const smallTaskCount = streamSections.reduce(
        (sum, section) => sum + section.smallTaskCount,
        0,
      );

      return {
        teamId: group.teamId,
        teamName: group.teamName,
        streams: streamSections,
        activeCount,
        completedCount,
        overdueCount,
        fullDesignCount,
        smallTaskCount,
      };
    })
    .filter((section) => section.streams.length > 0);
}

function groupProjectsByStream(
  projects: Project[],
  streamNameById: Map<string, string>,
  preferredStreamOrder?: string[],
): ProjectStreamStatusGroup[] {
  return groupTeamProjectsByStream(projects, streamNameById, preferredStreamOrder);
}

export function resolveProjectStreamId(
  project: Project,
  usersById: Map<string, User>,
): string | null {
  if (project.stream_id) return project.stream_id;
  const assigneeIds = [project.design_leader_id, project.designer_id, project.surfacer_id];
  for (const userId of assigneeIds) {
    if (!userId) continue;
    const user = usersById.get(userId);
    if (user?.stream_id) return user.stream_id;
  }
  return null;
}
