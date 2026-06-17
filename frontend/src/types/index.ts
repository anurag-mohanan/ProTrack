export interface Timestamped {
  id: string;
  created_at: string;
  updated_at: string;
}

export type ProjectStatus = 'draft' | 'active' | 'on_hold' | 'completed' | 'cancelled';
export type MilestoneStatus = 'pending' | 'in_progress' | 'completed' | 'delayed';
export type TimesheetStatus = 'draft' | 'submitted' | 'approved' | 'rejected';

export interface Role extends Timestamped {
  name: string;
  description: string | null;
}

export interface User extends Timestamped {
  role_id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
}

export interface Stream extends Timestamped {
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface Customer extends Timestamped {
  name: string;
  code: string | null;
  address: string | null;
  is_active: boolean;
}

export interface Contact extends Timestamped {
  customer_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  job_title: string | null;
  is_primary: boolean;
}

export interface TaskType extends Timestamped {
  stream_id: string;
  name: string;
  description: string | null;
  is_billable: boolean;
  is_active: boolean;
}

export interface Project extends Timestamped {
  customer_id: string;
  stream_id: string;
  created_by: string;
  name: string;
  code: string;
  description: string | null;
  status: ProjectStatus;
  planned_start: string | null;
  planned_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
}

export interface ProjectMember extends Timestamped {
  project_id: string;
  user_id: string;
  role_on_project: string;
  allocation_percent: number;
  start_date: string | null;
  end_date: string | null;
}

export interface Milestone extends Timestamped {
  project_id: string;
  name: string;
  description: string | null;
  status: MilestoneStatus;
  due_date: string | null;
  completed_at: string | null;
  sort_order: number;
}

export interface Timesheet extends Timestamped {
  user_id: string;
  week_start: string;
  status: TimesheetStatus;
  submitted_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
}

export interface TimesheetEntry extends Timestamped {
  timesheet_id: string;
  project_id: string;
  task_type_id: string | null;
  milestone_id: string | null;
  entry_date: string;
  hours: number;
  description: string | null;
}
