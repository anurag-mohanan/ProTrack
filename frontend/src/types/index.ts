export interface Timestamped {
  id: string;
  created_at: string;
  updated_at: string;
}

export type ProjectStatus =
  | 'not_started'
  | 'in_progress'
  | 'waiting_for_customer'
  | 'completed';

export type MilestoneStatus =
  | 'not_started'
  | 'in_progress'
  | 'completed'
  | 'not_applicable';

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
  tool_number: string;
  part_description: string;
  customer_id: string;
  customer_contact_id: string;
  design_leader_id: string;
  designer_id: string | null;
  surfacer_id: string | null;
  stream_id: string;
  code: string;
  quoted_hours: number;
  due_date: string;
  status: ProjectStatus;
  notes: string | null;
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

export function projectLabel(project: Pick<Project, 'code' | 'tool_number' | 'part_description'>) {
  return `${project.code} — ${project.tool_number}`;
}
