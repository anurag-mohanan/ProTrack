import type { Timestamped } from './common';

export interface TimesheetEntry extends Timestamped {
  timesheet_id: string;
  project_id: string;
  task_type_id: string | null;
  milestone_id: string | null;
  entry_date: string;
  hours: number;
  description: string | null;
}

export interface TimesheetEntryCreate {
  timesheet_id: string;
  project_id: string;
  task_type_id?: string | null;
  milestone_id?: string | null;
  entry_date: string;
  hours: number;
  description?: string | null;
}
