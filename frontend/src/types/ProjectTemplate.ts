import type { Timestamped } from './common';

export interface ProjectType extends Timestamped {
  name: string;
  description: string | null;
  is_active: boolean;
  default_workstream_id?: string | null;
}

export interface ProjectTemplateMilestone extends Timestamped {
  project_template_id: string;
  milestone_name: string;
  description: string | null;
  sort_order: number;
  default_due_offset_days: number | null;
  is_required: boolean;
  is_visible?: boolean;
  project_stage?: string | null;
  estimated_hours?: number | null;
  assigned_role?: string | null;
  default_assigned_user_id?: string | null;
  depends_on?: string[];
}

export type TemplateSchedulingMode = 'sequential' | 'dependencies';

export interface ProjectTemplate extends Timestamped {
  name: string;
  description: string | null;
  project_type_id: string;
  customer_id: string | null;
  default_team_id?: string | null;
  is_default: boolean;
  is_active: boolean;
  milestone_count: number;
  projects_using_count?: number;
  project_type_name?: string | null;
  customer_name?: string | null;
  scheduling_mode?: TemplateSchedulingMode;
  revision_note?: string | null;
  template_family_id?: string | null;
  version?: number;
  version_count?: number;
  activated_at?: string | null;
}

export interface ProjectTemplateDetail extends ProjectTemplate {
  milestones: ProjectTemplateMilestone[];
  created_new_version?: boolean;
}

export interface ProjectTemplateVersion {
  id: string;
  version: number;
  is_active: boolean;
  revision_note: string | null;
  milestone_count: number;
  projects_using_count: number;
  created_at: string | null;
  activated_at: string | null;
}

export interface TemplatePreviewMilestone {
  name: string;
  project_stage: string | null;
  sort_order: number;
  planned_hours: number | string;
  estimate_basis: string | null;
  start_date: string | null;
  finish_date: string | null;
  depends_on: string[];
}

export interface TemplatePreview {
  template_id: string;
  version: number;
  start_date: string;
  completion_date: string | null;
  forecast_status: string;
  forecast_note: string;
  milestones: TemplatePreviewMilestone[];
  warnings: string[];
}

export interface ProjectTemplateMatch {
  id: string;
  name: string;
  description: string | null;
  project_type_id: string;
  customer_id: string | null;
  is_default: boolean;
  is_customer_specific: boolean;
  customer_name?: string | null;
  default_team_id: string | null;
  milestone_count: number;
}

export interface ProjectTemplateMilestoneInput {
  milestone_name: string;
  description?: string | null;
  sort_order: number;
  default_due_offset_days?: number | null;
  is_required?: boolean;
  is_visible?: boolean;
  project_stage?: string | null;
  estimated_hours?: number | null;
  assigned_role?: string | null;
  default_assigned_user_id?: string | null;
  id?: string | null;
  client_key?: string | null;
  depends_on?: string[];
}

export interface ProjectTemplateCreatePayload {
  name: string;
  description?: string | null;
  project_type_id: string;
  customer_id?: string | null;
  is_default?: boolean;
  is_active?: boolean;
  scheduling_mode?: TemplateSchedulingMode;
  revision_note?: string | null;
  milestones?: ProjectTemplateMilestoneInput[];
}

export interface ProjectTemplateUpdatePayload {
  name?: string;
  description?: string | null;
  project_type_id?: string;
  customer_id?: string | null;
  is_default?: boolean;
  is_active?: boolean;
  scheduling_mode?: TemplateSchedulingMode;
  revision_note?: string | null;
  milestones?: ProjectTemplateMilestoneInput[];
}

export const PROJECT_STAGE_OPTIONS = [
  { value: 'feasibility', label: 'Feasibility' },
  { value: 'preliminary', label: 'Blockout' },
  { value: 'intermediate', label: 'Intermediate Design' },
  { value: 'final', label: 'Final Design' },
] as const;

export const PLANNED_STAGE_OPTIONS = PROJECT_STAGE_OPTIONS.filter(
  (option) => option.value !== 'feasibility',
);

export function projectStageLabel(value: string | null | undefined): string {
  if (!value) return 'Unstaged';
  if (value === 'completed') return 'Completed';
  return PROJECT_STAGE_OPTIONS.find((option) => option.value === value)?.label ?? value;
}
