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

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role_id: string;
  team_id?: string | null;
  team_name?: string | null;
  department_id?: string | null;
  department_name?: string | null;
  working_hours_per_day?: number;
  working_days?: string;
  employment_type?: 'full_time' | 'part_time' | 'contract' | 'intern' | null;
  skill_level?: 'beginner' | 'intermediate' | 'advanced' | 'expert' | null;
  joining_date?: string | null;
  leaving_date?: string | null;
  availability_status?: 'available' | 'allocated' | 'on_leave' | 'unavailable';
  max_allocation_percent?: number;
  is_active: boolean;
  must_change_password?: boolean;
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
  default_folder_structure?: string | null;
  due_date_calculation?: 'from_start' | 'from_previous_milestone' | 'business_days';
  project_number_format?: string | null;
  project_number_prefix?: string | null;
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
}

export interface Stream {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
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
