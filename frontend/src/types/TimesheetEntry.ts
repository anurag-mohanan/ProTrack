import type { Timestamped } from './common';

export type WorkCategory = 'productive' | 'non_productive';

export interface TimesheetEntry extends Timestamped {
  timesheet_id: string;
  work_category: WorkCategory;
  project_id: string | null;
  customer_id: string | null;
  task_type_id: string | null;
  milestone_id: string | null;
  non_productive_code_id: string | null;
  entry_date: string;
  hours: number;
  is_billable: boolean;
  description: string | null;
  project_tool_number?: string | null;
  project_code?: string | null;
  customer_name?: string | null;
  task_type_name?: string | null;
  milestone_name?: string | null;
  non_productive_code?: string | null;
  non_productive_description?: string | null;
}

export interface TimesheetEntryCreate {
  timesheet_id: string;
  work_category?: WorkCategory;
  project_id?: string | null;
  customer_id?: string | null;
  task_type_id?: string | null;
  milestone_id?: string | null;
  non_productive_code_id?: string | null;
  entry_date: string;
  hours: number;
  is_billable?: boolean;
  description?: string | null;
}

export interface NonProductiveCode extends Timestamped {
  code: string;
  description: string;
  is_active: boolean;
  is_archived: boolean;
  sort_order: number;
}

export interface NonProductiveCodeCreate {
  code: string;
  description: string;
  is_active?: boolean;
  sort_order?: number;
}

export interface NonProductiveCodeUpdate {
  code?: string;
  description?: string;
  is_active?: boolean;
  is_archived?: boolean;
  sort_order?: number;
}
