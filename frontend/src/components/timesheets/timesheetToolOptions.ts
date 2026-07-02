import type { NonProductiveCode, Project } from '../../types';

export type TimesheetToolGroup = 'LIVE PROJECTS' | 'NON PRODUCTIVE';

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

export function buildProjectToolOptions(projects: Project[]): TimesheetToolOption[] {
  return [...projects]
    .sort((left, right) => left.tool_number.localeCompare(right.tool_number))
    .map((project) => ({
      value: `project:${project.id}`,
      label: project.tool_number,
      group: 'LIVE PROJECTS' as const,
      kind: 'project' as const,
      projectId: project.id,
      toolNumber: project.tool_number,
      searchText: [
        project.tool_number,
        project.customer_name,
        project.part_description,
        project.team_name,
        project.design_leader_name,
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
      label: `${code.code} — ${code.description ?? code.code}`,
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
): TimesheetToolOption[] {
  return [...buildProjectToolOptions(projects), ...buildNpToolOptions(npCodes)];
}

export function toolOptionFromEntry(
  entry: {
    work_category: string;
    project_id: string | null;
    non_productive_code_id: string | null;
    project_tool_number?: string | null;
    non_productive_code?: string | null;
  },
): string {
  if (entry.work_category === 'non_productive' && entry.non_productive_code_id) {
    return `np:${entry.non_productive_code_id}`;
  }
  if (entry.project_id) {
    return `project:${entry.project_id}`;
  }
  return '';
}
