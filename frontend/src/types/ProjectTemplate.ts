import type { Timestamped } from './common';

export interface ProjectType extends Timestamped {
  name: string;
  description: string | null;
  is_active: boolean;
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
}

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
}

export interface ProjectTemplateDetail extends ProjectTemplate {
  milestones: ProjectTemplateMilestone[];
}

export interface ProjectTemplateMatch {
  id: string;
  name: string;
  description: string | null;
  project_type_id: string;
  customer_id: string | null;
  is_default: boolean;
  is_customer_specific: boolean;
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
}

export interface ProjectTemplateCreatePayload {
  name: string;
  description?: string | null;
  project_type_id: string;
  customer_id?: string | null;
  is_default?: boolean;
  is_active?: boolean;
  milestones?: ProjectTemplateMilestoneInput[];
}

export interface ProjectTemplateUpdatePayload {
  name?: string;
  description?: string | null;
  project_type_id?: string;
  customer_id?: string | null;
  is_default?: boolean;
  is_active?: boolean;
  milestones?: ProjectTemplateMilestoneInput[];
}
