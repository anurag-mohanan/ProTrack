import type { MilestoneStatus, Timestamped } from './common';

export interface Milestone extends Timestamped {
  project_id: string;
  name: string;
  description: string | null;
  status: MilestoneStatus;
  due_date: string | null;
  completed_at: string | null;
  sort_order: number;
}

export interface MilestoneUpdate {
  status?: MilestoneStatus;
  name?: string;
  description?: string | null;
  due_date?: string | null;
  completed_at?: string | null;
  sort_order?: number;
}
