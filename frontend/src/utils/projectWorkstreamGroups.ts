/** Group filtered projects into configurable workstream sections (multi-appear safe). */

import type { Project, Workstream } from '../types';
import type { ProjectType } from '../types/ProjectTemplate';
import {
  isLiveProject,
  isOverdueProject,
  isDueSoonProject,
} from './projectCommandCenter';

export interface WorkstreamSectionSummary {
  activeCount: number;
  /** At-risk (health red) live projects */
  riskCount: number;
  /** Overdue live projects */
  overdueCount: number;
  dueSoonCount: number;
  estimatedHours: number;
  actualHours: number;
  completionPercent: number;
}

export interface WorkstreamProjectGroup {
  id: string;
  label: string;
  description: string | null;
  icon: string | null;
  color: string | null;
  displayOrder: number;
  projects: Project[];
  summary: WorkstreamSectionSummary;
  /** True when section was inferred from project type (not an explicit link). */
  inferredFromType?: boolean;
}

export interface WorkstreamSectionPrefs {
  /** Custom display order (workstream ids). Omitted ids follow catalog order after pinned. */
  order: string[];
  hidden: string[];
  pinned: string[];
  /** collapsed[id] === true means section starts collapsed */
  collapsed: Record<string, boolean>;
}

export const WORKSTREAM_SECTION_PREFS_KEY = 'protrack.projects.workstreamSectionPrefs.v1';
/** Legacy collapse-only key — migrated on first read. */
const LEGACY_COLLAPSE_KEY = 'protrack.projects.workstreamSectionCollapse.v1';

export const defaultWorkstreamSectionPrefs = (): WorkstreamSectionPrefs => ({
  order: [],
  hidden: [],
  pinned: [],
  collapsed: {},
});

export function loadWorkstreamSectionPrefs(): WorkstreamSectionPrefs {
  if (typeof window === 'undefined') return defaultWorkstreamSectionPrefs();
  try {
    const raw = window.localStorage.getItem(WORKSTREAM_SECTION_PREFS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<WorkstreamSectionPrefs>;
      return {
        order: Array.isArray(parsed.order) ? parsed.order.map(String) : [],
        hidden: Array.isArray(parsed.hidden) ? parsed.hidden.map(String) : [],
        pinned: Array.isArray(parsed.pinned) ? parsed.pinned.map(String) : [],
        collapsed:
          parsed.collapsed && typeof parsed.collapsed === 'object' && !Array.isArray(parsed.collapsed)
            ? (parsed.collapsed as Record<string, boolean>)
            : {},
      };
    }
    // Migrate legacy collapse map
    const legacy = window.localStorage.getItem(LEGACY_COLLAPSE_KEY);
    if (legacy) {
      const collapsed = JSON.parse(legacy) as Record<string, boolean>;
      const prefs = { ...defaultWorkstreamSectionPrefs(), collapsed };
      persistWorkstreamSectionPrefs(prefs);
      return prefs;
    }
  } catch {
    // ignore
  }
  return defaultWorkstreamSectionPrefs();
}

export function persistWorkstreamSectionPrefs(prefs: WorkstreamSectionPrefs): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(WORKSTREAM_SECTION_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    // ignore quota
  }
}

function todayStart(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function sectionHours(project: Project, workstreamId: string): { estimated: number; actual: number } {
  const link = (project.workstreams ?? []).find((ws) => ws.workstream_id === workstreamId);
  if (link) {
    const estimated =
      link.estimated_hours != null ? Number(link.estimated_hours) : Number(project.quoted_hours ?? 0);
    const actual =
      link.actual_hours != null ? Number(link.actual_hours) : Number(project.actual_hours ?? 0);
    return { estimated, actual };
  }
  return {
    estimated: Number(project.quoted_hours ?? 0),
    actual: Number(project.actual_hours ?? 0),
  };
}

export function computeWorkstreamSectionSummary(
  projects: Project[],
  workstreamId: string,
): WorkstreamSectionSummary {
  const today = todayStart();
  const live = projects.filter(isLiveProject);
  let estimatedHours = 0;
  let actualHours = 0;
  let progressSum = 0;
  for (const project of live) {
    const hours = sectionHours(project, workstreamId);
    estimatedHours += hours.estimated;
    actualHours += hours.actual;
    progressSum += Number(project.progress_percent ?? 0);
  }
  return {
    activeCount: live.length,
    riskCount: live.filter((p) => p.health === 'red').length,
    overdueCount: live.filter((p) => isOverdueProject(p, today)).length,
    dueSoonCount: live.filter((p) => isDueSoonProject(p, today)).length,
    estimatedHours,
    actualHours,
    completionPercent: live.length ? progressSum / live.length : 0,
  };
}

/**
 * Resolve which workstream section ids a project belongs to.
 * 1) Explicit project_workstreams links (multi-appear)
 * 2) Else project type → default_workstream_id
 * 3) Else unassigned
 */
export function resolveProjectWorkstreamIds(
  project: Project,
  typeDefaultById: Map<string, string>,
): string[] {
  const links = project.workstreams ?? [];
  if (links.length) {
    const seen = new Set<string>();
    const ids: string[] = [];
    for (const link of links) {
      if (seen.has(link.workstream_id)) continue;
      seen.add(link.workstream_id);
      ids.push(link.workstream_id);
    }
    return ids;
  }
  const typeId = project.project_type_id;
  if (typeId) {
    const fallback = typeDefaultById.get(typeId);
    if (fallback) return [fallback];
  }
  return [];
}

function buildTypeDefaultMap(projectTypes: ProjectType[] = []): Map<string, string> {
  const map = new Map<string, string>();
  for (const pt of projectTypes) {
    if (pt.default_workstream_id) {
      map.set(pt.id, pt.default_workstream_id);
    }
  }
  return map;
}

/**
 * Build sections from active workstream catalog + filtered projects.
 * Projects with multiple workstreams appear in each matching section (same object refs).
 * Empty workstreams are omitted unless includeEmpty; unassigned live projects go trailing.
 */
export function groupProjectsByWorkstream(
  projects: Project[],
  catalog: Workstream[] = [],
  options?: {
    includeEmpty?: boolean;
    projectTypes?: ProjectType[];
    prefs?: WorkstreamSectionPrefs;
  },
): WorkstreamProjectGroup[] {
  const includeEmpty = options?.includeEmpty ?? false;
  const typeDefaultById = buildTypeDefaultMap(options?.projectTypes);
  const prefs = options?.prefs ?? defaultWorkstreamSectionPrefs();
  const hidden = new Set(prefs.hidden);

  const activeCatalog = [...catalog]
    .filter((ws) => ws.is_active !== false)
    .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0) || a.name.localeCompare(b.name));

  const byId = new Map<string, Project[]>();
  const unassigned: Project[] = [];

  for (const project of projects) {
    const ids = resolveProjectWorkstreamIds(project, typeDefaultById);
    if (!ids.length) {
      unassigned.push(project);
      continue;
    }
    for (const id of ids) {
      const bucket = byId.get(id);
      if (bucket) bucket.push(project);
      else byId.set(id, [project]);
    }
  }

  const groups: WorkstreamProjectGroup[] = [];
  for (const ws of activeCatalog) {
    if (hidden.has(ws.id)) continue;
    const list = byId.get(ws.id) ?? [];
    if (!list.length && !includeEmpty) continue;
    groups.push({
      id: ws.id,
      label: ws.name,
      description: ws.description ?? null,
      icon: ws.icon ?? null,
      color: ws.color ?? null,
      displayOrder: ws.display_order ?? 0,
      projects: list,
      summary: computeWorkstreamSectionSummary(list, ws.id),
    });
    byId.delete(ws.id);
  }

  // Orphan links (inactive / deleted workstream still on projects)
  for (const [id, list] of byId.entries()) {
    if (hidden.has(id)) continue;
    if (!list.length) continue;
    const sample = list[0]?.workstreams?.find((l) => l.workstream_id === id);
    groups.push({
      id,
      label: sample?.workstream_name ?? 'Workstream',
      description: null,
      icon: null,
      color: null,
      displayOrder: 9990,
      projects: list,
      summary: computeWorkstreamSectionSummary(list, id),
    });
  }

  if (unassigned.length && !hidden.has('unassigned')) {
    groups.push({
      id: 'unassigned',
      label: 'Unassigned',
      description: 'Projects with no workstream or type mapping yet',
      icon: null,
      color: '#64748b',
      displayOrder: 9999,
      projects: unassigned,
      summary: computeWorkstreamSectionSummary(unassigned, 'unassigned'),
    });
  }

  return applyWorkstreamSectionPrefs(groups, prefs);
}

/** Pin favourites first, then custom order, then catalog display_order. */
export function applyWorkstreamSectionPrefs(
  groups: WorkstreamProjectGroup[],
  prefs: WorkstreamSectionPrefs,
): WorkstreamProjectGroup[] {
  const pinned = new Set(prefs.pinned);
  const orderIndex = new Map(prefs.order.map((id, index) => [id, index]));

  return [...groups].sort((a, b) => {
    const aPin = pinned.has(a.id) ? 0 : 1;
    const bPin = pinned.has(b.id) ? 0 : 1;
    if (aPin !== bPin) return aPin - bPin;

    const aOrd = orderIndex.has(a.id) ? orderIndex.get(a.id)! : null;
    const bOrd = orderIndex.has(b.id) ? orderIndex.get(b.id)! : null;
    if (aOrd != null && bOrd != null && aOrd !== bOrd) return aOrd - bOrd;
    if (aOrd != null && bOrd == null) return -1;
    if (aOrd == null && bOrd != null) return 1;

    if (a.displayOrder !== b.displayOrder) return a.displayOrder - b.displayOrder;
    return a.label.localeCompare(b.label);
  });
}
