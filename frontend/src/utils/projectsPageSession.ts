import type { ProjectCommandCenterFilters } from './projectCommandCenter';
import { defaultProjectCommandCenterFilters } from './projectCommandCenter';

const STORAGE_KEY = 'protrack.projects.commandCenter.v3';
const LEGACY_STORAGE_KEY = 'protrack.projects.commandCenter.v2';
const LEGACY_STORAGE_KEY_V1 = 'protrack.projects.commandCenter.v1';

export interface ProjectsPageSessionState {
  filters: ProjectCommandCenterFilters;
  /** Empty = all streams. */
  selectedStreamIds: string[];
  /** Empty = all teams. */
  selectedTeamIds: string[];
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
    workstreamIds: Array.isArray(raw.workstreamIds)
      ? raw.workstreamIds.filter((id): id is string => typeof id === 'string')
      : base.workstreamIds,
    statusBucketIds: Array.isArray(raw.statusBucketIds)
      ? raw.statusBucketIds.filter((id): id is string => typeof id === 'string')
      : base.statusBucketIds,
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
    groupBy: (() => {
      const value =
        typeof raw.groupBy === 'string'
          ? (raw.groupBy as ProjectCommandCenterFilters['groupBy'])
          : base.groupBy;
      // Simplified Projects UX: prefer team sections over workstream catalogs.
      if (value === 'workstream' || value === 'customer' || value === 'health' || value === 'pm') {
        return 'team';
      }
      return value;
    })(),
    layout:
      typeof raw.layout === 'string'
        ? (raw.layout as ProjectCommandCenterFilters['layout'])
        : base.layout,
    quickFilter:
      typeof raw.quickFilter === 'string'
        ? (raw.quickFilter as ProjectCommandCenterFilters['quickFilter'])
        : base.quickFilter,
    customerId: typeof raw.customerId === 'string' ? raw.customerId : base.customerId,
    designerUserId:
      typeof raw.designerUserId === 'string' ? raw.designerUserId : base.designerUserId,
  };
}

function normalizeIdList(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter((id): id is string => typeof id === 'string' && id.length > 0);
}

function normalizeSelectedStreamIds(raw: unknown, legacyStreamTab?: unknown): string[] {
  if (Array.isArray(raw)) return normalizeIdList(raw);
  if (typeof legacyStreamTab === 'string' && legacyStreamTab && legacyStreamTab !== 'all') {
    return [legacyStreamTab];
  }
  return [];
}

export function loadProjectsPageSession(): ProjectsPageSessionState | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw =
      window.sessionStorage.getItem(STORAGE_KEY) ??
      window.sessionStorage.getItem(LEGACY_STORAGE_KEY) ??
      window.sessionStorage.getItem(LEGACY_STORAGE_KEY_V1);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!isRecord(parsed)) return null;
    return {
      filters: normalizeFilters(parsed.filters),
      selectedStreamIds: normalizeSelectedStreamIds(
        parsed.selectedStreamIds,
        parsed.streamTab,
      ),
      selectedTeamIds: normalizeIdList(parsed.selectedTeamIds),
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
        selectedStreamIds: state.selectedStreamIds,
        selectedTeamIds: state.selectedTeamIds,
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
    window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
    window.sessionStorage.removeItem(LEGACY_STORAGE_KEY_V1);
  } catch {
    // Ignore.
  }
}
