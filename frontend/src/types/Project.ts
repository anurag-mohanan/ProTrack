import type { ProjectHealth, ProjectStatus, Timestamped } from './common';

export interface Project extends Timestamped {
  tool_number: string;
  part_description: string;
  customer_id: string;
  customer_contact_id: string;
  design_leader_id: string;
  designer_id: string | null;
  surfacer_id: string | null;
  stream_id: string;
  project_type_id?: string | null;
  project_template_id?: string | null;
  code: string;
  quoted_hours: number;
  actual_hours: number;
  progress_percent: number;
  health: ProjectHealth;
  due_date: string;
  status: ProjectStatus;
  notes: string | null;
}

export interface ProjectCreate {
  tool_number: string;
  part_description: string;
  customer_id: string;
  customer_contact_id: string;
  design_leader_id: string;
  designer_id?: string | null;
  surfacer_id?: string | null;
  stream_id: string;
  project_type_id: string;
  project_template_id?: string | null;
  code: string;
  quoted_hours: number;
  due_date: string;
  status?: ProjectStatus;
  notes?: string | null;
}

export interface ProjectUpdate {
  tool_number?: string;
  part_description?: string;
  customer_id?: string;
  customer_contact_id?: string;
  design_leader_id?: string;
  designer_id?: string | null;
  surfacer_id?: string | null;
  stream_id?: string;
  code?: string;
  quoted_hours?: number;
  due_date?: string;
  status?: ProjectStatus;
  notes?: string | null;
}

export function projectLabel(
  project: Pick<Project, 'code' | 'tool_number' | 'part_description'>,
) {
  return `${project.code} — ${project.tool_number}`;
}
