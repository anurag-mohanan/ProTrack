export * from './common';
export * from './Project';
export * from './Milestone';
export * from './Timesheet';
export * from './TimesheetEntry';
export * from './Workflow';
export * from './Dashboard';
export * from './Auth';

export * from './Reports';
export * from './ProjectTemplate';
export * from './Team';

export interface Role {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserTeamAssignment {
  id?: string;
  team_id: string;
  team_name?: string;
  relationship_type: 'member' | 'team_leader' | 'engineering_manager' | 'reviewer';
  is_primary: boolean;
  include_in_timesheet_reports?: boolean;
  created_at?: string;
}

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role_id: string;
  role_name?: string;
  team_id?: string | null;
  team_name?: string | null;
  team_names?: string[];
  team_assignments?: UserTeamAssignment[];
  department_id?: string | null;
  department_name?: string | null;
  working_hours_per_day?: number;
  working_days?: string;
  employment_type?: 'full_time' | 'part_time' | 'contract' | 'intern' | null;
  skill_level?: 'beginner' | 'intermediate' | 'advanced' | 'expert' | null;
  joining_date?: string | null;
  first_job_date?: string | null;
  leaving_date?: string | null;
  phone?: string | null;
  designation?: string | null;
  manager_id?: string | null;
  manager_name?: string | null;
  availability_status?: 'available' | 'allocated' | 'on_leave' | 'unavailable';
  max_allocation_percent?: number;
  active_projects_count?: number;
  is_active: boolean;
  must_change_password?: boolean;
  password_changed?: boolean;
  last_login?: string | null;
  is_archived?: boolean;
  is_locked?: boolean;
  failed_login_count?: number;
  module_access?: string[] | null;
  special_permissions?: string[] | null;
  resolved_modules?: string[];
  resolved_special_permissions?: string[];
  operational_role_type_id?: string | null;
  kpi_engineering_productivity?: boolean;
  kpi_capacity_planning?: boolean;
  kpi_utilization?: boolean;
  kpi_workload_planning?: boolean;
  kpi_dashboard_productivity?: boolean;
  default_working_model_id?: string | null;
  requires_timesheet?: boolean;
  requires_salary?: boolean;
  kpi_configuration?: {
    operational_role_type_id?: string | null;
    operational_role_name?: string | null;
    dashboard_profile?: string;
    kpi_engineering_productivity?: boolean;
    kpi_capacity_planning?: boolean;
    kpi_utilization?: boolean;
    kpi_workload_planning?: boolean;
    kpi_dashboard_productivity?: boolean;
  };
  created_at?: string;
  updated_at?: string;
}

export interface Customer {
  id: string;
  name: string;
  code: string | null;
  notes?: string | null;
  address?: string | null;
  is_active: boolean;
  default_project_template_id?: string | null;
  default_team_id?: string | null;
  default_project_type_id?: string | null;
  default_working_model_id?: string | null;
  default_folder_structure?: string | null;
  due_date_calculation?: 'from_start' | 'from_previous_milestone' | 'business_days';
  project_number_format?: string | null;
  project_number_prefix?: string | null;
  default_currency_code?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface TaskType {
  id: string;
  stream_id: string;
  name: string;
  description: string | null;
  is_billable: boolean;
  is_active: boolean;
  function_category?: 'engineering' | 'management' | 'administration' | 'non_productive';
}

export interface Stream {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export type WorkingModelStrategyKey =
  | 'project_based'
  | 'time_materials'
  | 'retainer'
  | 'overheads';

export interface WorkingModel {
  id: string;
  code: string;
  strategy_key: WorkingModelStrategyKey;
  name: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
  is_archived: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Contact {
  id: string;
  customer_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  job_title: string | null;
  contact_type_id?: string | null;
  is_primary: boolean;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}
