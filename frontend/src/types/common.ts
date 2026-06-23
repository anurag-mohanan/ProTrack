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

export type ProjectHealth = 'green' | 'yellow' | 'red';
