export interface Timestamped {
  id: string;
  created_at: string;
  updated_at: string;
}

export type ProjectStage = 'preliminary' | 'intermediate' | 'final';

export type ExecutionStatus =
  | 'planning'
  | 'currently_being_worked_on'
  | 'on_hold'
  | 'cancelled'
  | 'completed';

/** @deprecated Use ExecutionStatus */
export type ProjectStatus = ExecutionStatus;

export type MilestoneStatus =
  | 'not_started'
  | 'in_progress'
  | 'completed'
  | 'not_applicable';

export type TimesheetStatus = 'draft' | 'submitted' | 'approved' | 'rejected';

export type ProjectHealth = 'green' | 'yellow' | 'red';

export const PROJECT_STAGE_LABELS: Record<ProjectStage, string> = {
  preliminary: 'Preliminary',
  intermediate: 'Intermediate',
  final: 'Final',
};

export const EXECUTION_STATUS_LABELS: Record<ExecutionStatus, string> = {
  planning: 'Planning',
  currently_being_worked_on: 'Currently Being Worked On',
  on_hold: 'On Hold',
  cancelled: 'Cancelled',
  completed: 'Completed',
};
