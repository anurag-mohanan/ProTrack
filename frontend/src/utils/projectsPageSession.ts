import type { ProjectCommandCenterFilters } from './projectCommandCenter';
import { defaultProjectCommandCenterFilters } from './projectCommandCenter';

const STORAGE_KEY = 'protrack.projects.commandCenter.v1';

export interface ProjectsPageSessionState {
  filters: ProjectCommandCenterFilters;
  streamTab: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function normalizeFilters(raw: unknown): ProjectCommandCenterFilters {
  if (!isRecord(raw)) return { ...defaultProjectCommandCenterFilters };
  const base = { ...defaultProjectCommandCenterFilters };
  return {
    ...base,
    search: typeof raw.search === 'string' ? raw.search : base.search,
    customerIds: Array.isArray(raw.customerIds)
      ? raw.customerIds.filter((id): id is string => typeof id === 'string')
      : base.customerIds,
    projectTypeId: typeof raw.projectTypeId === 'string' ? raw.projectTypeId : base.projectTypeId,
    teamIds: Array.isArray(raw.teamIds)
      ? raw.teamIds.filter((id): id is string => typeof id === 'string')
      : base.teamIds,
    businessUnit: typeof raw.businessUnit === 'string' ? raw.businessUnit : base.businessUnit,
    projectStage:
      typeof raw.projectStage === 'string'
        ? (raw.projectStage as ProjectCommandCenterFilters['projectStage'])
        : base.projectStage,
    executionStatus:
      typeof raw.executionStatus === 'string'
        ? (raw.executionStatus as ProjectCommandCenterFilters['executionStatus'])
        : base.executionStatus,
    designLeaderId:
      typeof raw.designLeaderId === 'string' ? raw.designLeaderId : base.designLeaderId,
    designerId: typeof raw.designerId === 'string' ? raw.designerId : base.designerId,
    surfacerId: typeof raw.surfacerId === 'string' ? raw.surfacerId : base.surfacerId,
    priority:
      typeof raw.priority === 'string'
        ? (raw.priority as ProjectCommandCenterFilters['priority'])
        : base.priority,
    health:
      typeof raw.health === 'string'
        ? (raw.health as ProjectCommandCenterFilters['health'])
        : base.health,
    dueDate:
      typeof raw.dueDate === 'string'
        ? (raw.dueDate as ProjectCommandCenterFilters['dueDate'])
        : base.dueDate,
    showArchived: typeof raw.showArchived === 'boolean' ? raw.showArchived : base.showArchived,
    groupByTeam: typeof raw.groupByTeam === 'boolean' ? raw.groupByTeam : base.groupByTeam,
    quickFilter:
      typeof raw.quickFilter === 'string'
        ? (raw.quickFilter as ProjectCommandCenterFilters['quickFilter'])
        : base.quickFilter,
    customerId: typeof raw.customerId === 'string' ? raw.customerId : base.customerId,
    designerUserId:
      typeof raw.designerUserId === 'string' ? raw.designerUserId : base.designerUserId,
  };
}

export function loadProjectsPageSession(): ProjectsPageSessionState | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!isRecord(parsed)) return null;
    return {
      filters: normalizeFilters(parsed.filters),
      streamTab: typeof parsed.streamTab === 'string' ? parsed.streamTab : 'all',
    };
  } catch {
    return null;
  }
}

export function saveProjectsPageSession(state: ProjectsPageSessionState): void {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        filters: state.filters,
        streamTab: state.streamTab || 'all',
      }),
    );
  } catch {
    // Ignore quota / privacy errors.
  }
}

export function clearProjectsPageSession(): void {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore.
  }
}
