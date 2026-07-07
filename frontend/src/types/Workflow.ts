import type { Timestamped } from './common';

export type ActivityAction =
  | 'project_created'
  | 'project_updated'
  | 'milestone_completed'
  | 'milestone_reopened'
  | 'milestone_created'
  | 'milestone_updated'
  | 'milestone_deleted'
  | 'milestone_reordered'
  | 'timesheet_submitted'
  | 'timesheet_approved'
  | 'timesheet_rejected'
  | 'user_logged_in';

export type EntityType = 'project' | 'milestone' | 'timesheet' | 'user';

export type NotificationType =
  | 'project_assigned'
  | 'milestone_due_tomorrow'
  | 'timesheet_approved'
  | 'timesheet_rejected'
  | 'project_overdue'
  | 'timesheet_submitted';

export interface Activity extends Timestamped {
  id: string;
  user_id?: string | null;
  user_name?: string | null;
  entity_type: EntityType;
  entity_id: string;
  action: ActivityAction;
  old_value?: string | null;
  new_value?: string | null;
}

export interface Notification extends Timestamped {
  id: string;
  user_id: string;
  notification_type: NotificationType;
  title: string;
  message: string;
  entity_type?: EntityType | null;
  entity_id?: string | null;
  is_read: boolean;
  read_at?: string | null;
}

export interface NotificationSummary {
  unread_count: number;
}

export interface MyTaskItem {
  id: string;
  title: string;
  task_type: string;
  due_date?: string | null;
  project_code?: string | null;
}

export interface WorkflowDashboard {
  my_tasks: MyTaskItem[];
  projects_due_this_week: number;
  overdue_milestones: number;
  pending_timesheet_approvals: number;
  unread_notifications: number;
  recent_activity: Activity[];
}
