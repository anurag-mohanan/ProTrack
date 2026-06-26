import type { TimesheetStatus, Timestamped } from './common';

export interface Timesheet extends Timestamped {
  user_id: string;
  week_start: string;
  status: TimesheetStatus;
  submitted_at?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  approval_comments?: string | null;
}

export interface TimesheetCreate {
  user_id: string;
  week_start: string;
}

export interface TimesheetUpdate {
  user_id?: string;
  week_start?: string;
}
