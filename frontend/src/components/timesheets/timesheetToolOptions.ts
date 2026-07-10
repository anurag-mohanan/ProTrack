import type { NonProductiveCode, NonProductiveCodeCategory } from '../../types';
import type { TimesheetProjectLookup } from '../../types/TimesheetEntry';
import { PROJECT_STAGE_LABELS, EXECUTION_STATUS_LABELS } from '../../types/common';
import type { ExecutionStatus, ProjectStage } from '../../types/common';

export type TimesheetToolGroup =
  | 'MY ASSIGNED PROJECTS'
  | 'RECENTLY USED'
  | 'ALL ACTIVE PROJECTS'
  | 'NON PRODUCTIVE';

export interface TimesheetToolOption {
  value: string;
  label: string;
  group: TimesheetToolGroup;
  kind: 'project' | 'np';
  projectId?: string;
  npCodeId?: string;
  npCategory?: NonProductiveCodeCategory;
  toolNumber: string;
  searchText: string;
  partDescription?: string;
  customerName?: string;
  designerName?: string;
  surfacerName?: string;
  projectStage?: string;
  executionStatus?: string;
  workingModelName?: string;
  streamId?: string | null;
  isAssigned?: boolean;
}

export const RECENT_TOOLS_KEY = 'protrack.timesheet.recentTools';
export const LAST_TOOL_KEY = 'protrack.timesheet.lastTool';
export const LAST_TASK_KEY = 'protrack.timesheet.lastTask';
export const LAST_BILLABLE_KEY = 'protrack.timesheet.lastBillable';
export const MAX_RECENT_TOOLS = 15;

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
  const next = [value, ...readRecentTools().filter((item) => item !== value)].slice(
    0,
    MAX_RECENT_TOOLS,
  );
  try {
    localStorage.setItem(RECENT_TOOLS_KEY, JSON.stringify(next));
  } catch {
    // ignore storage failures
  }
}

function stageLabel(stage: string): string {
  return PROJECT_STAGE_LABELS[stage as ProjectStage] ?? stage;
}

function statusLabel(status: string): string {
  return EXECUTION_STATUS_LABELS[status as ExecutionStatus] ?? status;
}

function mapProjectOption(
  project: TimesheetProjectLookup,
  group: TimesheetToolGroup,
): TimesheetToolOption {
  return {
    value: `project:${project.id}`,
    label: `${project.tool_number} — ${project.part_description}`,
    group,
    kind: 'project',
    projectId: project.id,
    toolNumber: project.tool_number,
    partDescription: project.part_description,
    customerName: project.customer_name ?? undefined,
    designerName: project.designer_name ?? undefined,
    surfacerName: project.surfacer_name ?? undefined,
    projectStage: stageLabel(project.project_stage),
    executionStatus: statusLabel(project.execution_status),
    workingModelName: project.working_model_name ?? undefined,
    streamId: project.stream_id ?? null,
    isAssigned: project.is_assigned_to_user,
    searchText: [
      project.tool_number,
      project.part_description,
      project.customer_name,
      project.designer_name,
      project.surfacer_name,
      project.team_name,
      project.design_leader_name,
      project.project_stage,
      project.execution_status,
      project.working_model_name,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase(),
  };
}

export function buildProjectToolOptions(projects: TimesheetProjectLookup[]): TimesheetToolOption[] {
  return [...projects]
    .sort((left, right) => left.tool_number.localeCompare(right.tool_number))
    .map((project) => mapProjectOption(project, 'ALL ACTIVE PROJECTS'));
}

export function buildNpToolOptions(codes: NonProductiveCode[]): TimesheetToolOption[] {
  return [...codes]
    .filter((code) => code.is_active && !code.is_archived)
    .sort((left, right) => left.sort_order - right.sort_order || left.code.localeCompare(right.code))
    .map((code) => ({
      value: `np:${code.id}`,
      label:
        code.category === 'leave'
          ? `${code.code} - Leave`
          : `${code.code} - ${code.description ?? code.code}`,
      group: 'NON PRODUCTIVE' as const,
      kind: 'np' as const,
      npCodeId: code.id,
      npCategory: code.category ?? 'non_productive',
      toolNumber: code.code,
      searchText: [code.code, code.description].filter(Boolean).join(' ').toLowerCase(),
    }));
}

export function buildToolOptions(
  projects: TimesheetProjectLookup[],
  npCodes: NonProductiveCode[],
  recentValues: string[] = readRecentTools(),
): TimesheetToolOption[] {
  const byValue = new Map<string, TimesheetToolOption>();

  const assigned = projects
    .filter((project) => project.is_assigned_to_user)
    .map((project) => mapProjectOption(project, 'MY ASSIGNED PROJECTS'));
  for (const option of assigned) {
    byValue.set(option.value, option);
  }

  const recent = recentValues
    .map((value) => {
      const projectId = value.replace('project:', '');
      const project = projects.find((row) => row.id === projectId);
      if (!project || byValue.has(value)) return null;
      return mapProjectOption(project, 'RECENTLY USED');
    })
    .filter((option): option is TimesheetToolOption => option !== null);
  for (const option of recent) {
    byValue.set(option.value, option);
  }

  const placed = new Set(byValue.keys());
  const remaining = projects
    .filter((project) => !placed.has(`project:${project.id}`))
    .map((project) => mapProjectOption(project, 'ALL ACTIVE PROJECTS'));
  for (const option of remaining) {
    byValue.set(option.value, option);
  }

  const npOptions = buildNpToolOptions(npCodes);
  return [...byValue.values(), ...npOptions];
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
  if (option.npCategory === 'leave') return 'Leave';
  const parts = option.label.split(' - ');
  return parts.slice(1).join(' - ').trim() || option.toolNumber;
}

export function isLeaveToolOption(option: TimesheetToolOption | null): boolean {
  return option?.kind === 'np' && option.npCategory === 'leave';
}

export function isProjectOwner(
  project: TimesheetProjectLookup | null | undefined,
  userId: string | undefined,
): boolean {
  if (!project || !userId) return false;
  return userId === project.designer_id || userId === project.surfacer_id;
}
