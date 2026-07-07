import type {
  ExecutionStatus,
  ProjectHealth,
  ProjectStage,
  Timestamped,
} from './common';

export type ProjectLifecycleFilter =
  | 'all'
  | 'active'
  | 'completed'
  | 'cancelled'
  | 'archived'
  | 'deleted';

export interface Project extends Timestamped {
  tool_number: string;
  part_description: string;
  customer_id: string;
  customer_contact_id: string | null;
  design_leader_id: string | null;
  designer_id: string | null;
  surfacer_id: string | null;
  stream_id: string | null;
  team_id: string | null;
  project_type_id?: string | null;
  project_template_id?: string | null;
  code: string;
  quoted_hours: number;
  actual_hours: number;
  progress_percent: number;
  health: ProjectHealth;
  current_milestone?: string | null;
  priority?: 'critical' | 'high' | 'medium' | 'low';
  due_date: string | null;
  project_stage: ProjectStage;
  execution_status: ExecutionStatus;
  notes: string | null;
  completed_at?: string | null;
  is_archived?: boolean;
  archived_at?: string | null;
  archived_by_id?: string | null;
  is_deleted?: boolean;
  deleted_at?: string | null;
  deleted_by_id?: string | null;
  customer_name?: string;
  design_leader_name?: string;
  designer_name?: string | null;
  surfacer_name?: string | null;
  team_name?: string | null;
  project_type_name?: string | null;
}

export interface ArchivedProjectListItem extends Omit<Project, 'design_leader_name'> {
  customer_name: string;
  project_type_name?: string | null;
  design_leader_name: string | null;
}

export interface ProjectDeleteCheck {
  can_permanently_delete: boolean;
  blockers: string[];
}

export interface ProjectCreate {
  tool_number: string;
  part_description: string;
  customer_id: string;
  customer_contact_id?: string | null;
  design_leader_id?: string | null;
  designer_id?: string | null;
  surfacer_id?: string | null;
  stream_id?: string | null;
  team_id?: string | null;
  project_type_id?: string | null;
  project_template_id?: string | null;
  code?: string | null;
  quoted_hours?: number | null;
  due_date?: string | null;
  priority?: 'critical' | 'high' | 'medium' | 'low';
  project_stage?: ProjectStage;
  execution_status?: ExecutionStatus;
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
  team_id?: string | null;
  project_type_id?: string;
  code?: string;
  quoted_hours?: number;
  due_date?: string;
  priority?: 'critical' | 'high' | 'medium' | 'low';
  project_stage?: ProjectStage;
  execution_status?: ExecutionStatus;
  notes?: string | null;
}

export function projectLabel(
  project: Pick<Project, 'code' | 'tool_number' | 'part_description'>,
) {
  return `${project.code} — ${project.tool_number}`;
}
