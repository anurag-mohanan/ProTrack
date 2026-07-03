import type { NonProductiveCode, Project } from '../../types';

export type TimesheetToolGroup = 'RECENTLY USED' | 'LIVE PROJECTS' | 'NON PRODUCTIVE';

export interface TimesheetToolOption {
  value: string;
  label: string;
  group: TimesheetToolGroup;
  kind: 'project' | 'np';
  projectId?: string;
  npCodeId?: string;
  toolNumber: string;
  searchText: string;
}

export const RECENT_TOOLS_KEY = 'protrack.timesheet.recentTools';
export const LAST_TOOL_KEY = 'protrack.timesheet.lastTool';
export const LAST_TASK_KEY = 'protrack.timesheet.lastTask';

export function readRecentTools(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_TOOLS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : [];
  } catch {
    return [];
  }
}

export function pushRecentTool(value: string) {
  if (!value) return;
  const next = [value, ...readRecentTools().filter((item) => item !== value)].slice(0, 8);
  try {
    localStorage.setItem(RECENT_TOOLS_KEY, JSON.stringify(next));
  } catch {
    // ignore storage failures
  }
}

function projectLabel(project: Project): string {
  const description = project.part_description?.trim();
  if (description) {
    return `${project.tool_number} - ${description}`;
  }
  return project.tool_number;
}

export function buildProjectToolOptions(projects: Project[]): TimesheetToolOption[] {
  return [...projects]
    .sort((left, right) => left.tool_number.localeCompare(right.tool_number))
    .map((project) => ({
      value: `project:${project.id}`,
      label: projectLabel(project),
      group: 'LIVE PROJECTS' as const,
      kind: 'project' as const,
      projectId: project.id,
      toolNumber: project.tool_number,
      searchText: [
        project.tool_number,
        project.part_description,
        project.customer_name,
        project.team_name,
        project.design_leader_name,
        project.project_type_name,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase(),
    }));
}

export function buildNpToolOptions(codes: NonProductiveCode[]): TimesheetToolOption[] {
  return [...codes]
    .filter((code) => code.is_active && !code.is_archived)
    .sort((left, right) => left.sort_order - right.sort_order || left.code.localeCompare(right.code))
    .map((code) => ({
      value: `np:${code.id}`,
      label: `${code.code} - ${code.description ?? code.code}`,
      group: 'NON PRODUCTIVE' as const,
      kind: 'np' as const,
      npCodeId: code.id,
      toolNumber: code.code,
      searchText: [code.code, code.description].filter(Boolean).join(' ').toLowerCase(),
    }));
}

export function buildToolOptions(
  projects: Project[],
  npCodes: NonProductiveCode[],
  recentValues: string[] = readRecentTools(),
): TimesheetToolOption[] {
  const all = [...buildProjectToolOptions(projects), ...buildNpToolOptions(npCodes)];
  const byValue = new Map(all.map((option) => [option.value, option]));
  const recent = recentValues
    .map((value) => byValue.get(value))
    .filter((option): option is TimesheetToolOption => option !== undefined);
  const recentSet = new Set(recent.map((option) => option.value));
  const remaining = all.filter((option) => !recentSet.has(option.value));
  return [
    ...recent.map((option) => ({ ...option, group: 'RECENTLY USED' as const })),
    ...remaining,
  ];
}

export function toolOptionFromEntry(entry: {
  work_category: string;
  project_id: string | null;
  non_productive_code_id: string | null;
}): string {
  if (entry.work_category === 'non_productive' && entry.non_productive_code_id) {
    return `np:${entry.non_productive_code_id}`;
  }
  if (entry.project_id) {
    return `project:${entry.project_id}`;
  }
  return '';
}

export function npTaskLabel(option: TimesheetToolOption | null): string {
  if (!option || option.kind !== 'np') return '';
  const parts = option.label.split(' - ');
  return parts.slice(1).join(' - ').trim() || option.toolNumber;
}
