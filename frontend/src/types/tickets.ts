export type TicketCategory = 'it' | 'facility' | 'admin' | 'hr' | 'other';
export type TicketPriority = 'low' | 'normal' | 'medium' | 'high' | 'urgent';
export type TicketStatus =
  | 'new'
  | 'open'
  | 'in_progress'
  | 'pending_requester'
  | 'pending_internal'
  | 'pending_vendor'
  | 'on_hold'
  | 'resolved'
  | 'closed'
  | 'cancelled';

export interface TicketComment {
  id: string;
  ticket_id: string;
  author_id: string;
  author_name: string | null;
  body: string;
  is_internal: boolean;
  created_at: string;
  updated_at: string;
}

export interface Ticket {
  id: string;
  ticket_number: string;
  title: string;
  description: string | null;
  category: TicketCategory;
  category_label: string;
  subcategory: string | null;
  subcategory_label: string | null;
  family: string | null;
  priority: TicketPriority;
  priority_label: string;
  status: TicketStatus;
  status_label: string;
  requester_id: string;
  requester_name: string | null;
  assignee_id: string | null;
  assignee_name: string | null;
  affected_user_id: string | null;
  affected_user_name: string | null;
  org_department_id: string | null;
  location: string | null;
  due_date: string | null;
  sla_due_at: string | null;
  is_overdue: boolean;
  resolution: string | null;
  work_performed: string | null;
  resolution_category: string | null;
  closure_reason: string | null;
  cancellation_reason: string | null;
  pending_reason: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  assigned_at: string | null;
  started_at: string | null;
  first_response_at: string | null;
  last_activity_at: string | null;
  source_module: string | null;
  source_label: string | null;
  source_record_id: string | null;
  onboarding_item_id: string | null;
  related_asset_id: string | null;
  related_license_pool_id: string | null;
  related_stock_item_id: string | null;
  assignment_group: string | null;
  needs_owner: boolean;
  needs_review: boolean;
  review_note: string | null;
  escalation_level: number;
  comment_count: number;
  can_manage: boolean;
  allowed_transitions: TicketStatus[];
  created_at: string;
  updated_at: string;
}

export interface TicketTimelineEvent {
  at: string | null;
  kind: string;
  actor_name: string | null;
  summary: string;
  detail: string | null;
  is_internal: boolean;
}

export interface TicketAssignmentEntry {
  at: string | null;
  previous_assignee_name: string | null;
  new_assignee_name: string | null;
  previous_group: string | null;
  new_group: string | null;
  changed_by_name: string | null;
  change_type: string;
  reason: string | null;
}

export interface TicketLinkedTask {
  checklist_id: string;
  item_id: string;
  employee_name: string | null;
  item_text: string;
  status: string;
  status_label: string;
  execution_type: string;
}

export interface TicketRelatedRecord {
  kind: string;
  id: string;
  label: string;
  href: string | null;
}

export interface TicketNotificationEntry {
  at: string | null;
  event_key: string;
  user_name: string | null;
  status: string;
  error: string | null;
  attempts: number;
}

export interface TicketDetail extends Ticket {
  comments: TicketComment[];
  timeline: TicketTimelineEvent[];
  assignment_history: TicketAssignmentEntry[];
  linked_tasks: TicketLinkedTask[];
  related_records: TicketRelatedRecord[];
  notifications: TicketNotificationEntry[];
  can_comment_internal: boolean;
  provisioning_request_id: string | null;
}

export interface TicketCreate {
  title: string;
  description?: string | null;
  category: TicketCategory;
  subcategory?: string | null;
  priority?: TicketPriority;
  location?: string | null;
  due_date?: string | null;
  org_department_id?: string | null;
  affected_user_id?: string | null;
  related_asset_id?: string | null;
  related_license_pool_id?: string | null;
}

export interface TicketUpdate {
  title?: string;
  description?: string | null;
  subcategory?: string | null;
  priority?: TicketPriority;
  location?: string | null;
  due_date?: string | null;
}

export interface TicketStatusChange {
  status: TicketStatus;
  resolution?: string | null;
  work_performed?: string | null;
  resolution_category?: string | null;
  closure_reason?: string | null;
  reason?: string | null;
}

export interface TicketPage {
  items: Ticket[];
  total: number;
  page: number;
  page_size: number;
}

export interface TicketQueueSummary {
  category: string | null;
  counts: Record<string, number>;
}

export interface TicketCapabilities {
  is_agent: boolean;
  can_manage_all: boolean;
  can_configure: boolean;
  manageable_categories: string[];
}

export interface TicketCatalog {
  categories: Record<string, string>;
  subcategories: Record<string, Record<string, string>>;
  families: Record<string, string>;
  statuses: Record<string, string>;
  status_order: string[];
  priorities: Record<string, string>;
  sources: Record<string, string>;
  closure_reasons: Record<string, string>;
  resolution_categories: Record<string, string>;
  transitions: Record<string, string[]>;
}

export interface TicketAssignee {
  id: string;
  name: string;
  role_name: string | null;
}

export interface TicketQueueParams {
  view?: string;
  status?: string;
  category?: string;
  subcategory?: string;
  family?: string;
  priority?: string;
  assignee?: string;
  requester_id?: string;
  affected_user_id?: string;
  source_module?: string;
  due?: string;
  created_from?: string;
  created_to?: string;
  q?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export interface TicketCategoryRoute {
  category: TicketCategory;
  category_label: string;
  assignee_user_id: string | null;
  assignee_name: string | null;
  backup_user_id: string | null;
  backup_name: string | null;
  escalation_user_id: string | null;
  escalation_name: string | null;
  org_department_id: string | null;
  is_active: boolean;
  effective_from: string | null;
  fallback_roles: string[];
}

export interface TicketCategoryRouteUpdate {
  assignee_user_id?: string | null;
  backup_user_id?: string | null;
  escalation_user_id?: string | null;
  org_department_id?: string | null;
  is_active?: boolean;
  effective_from?: string | null;
}

export interface TicketRoutingRuleWrite {
  category: TicketCategory;
  subcategory: string | null;
  source_module: string | null;
  primary_user_id: string | null;
  backup_user_id: string | null;
  escalation_user_id: string | null;
  default_priority: TicketPriority | null;
  is_active: boolean;
  effective_from: string | null;
  notes: string | null;
}

export interface TicketRoutingRule extends TicketRoutingRuleWrite {
  id: string;
  primary_name: string | null;
  backup_name: string | null;
  escalation_name: string | null;
}

export interface TicketSlaPolicy {
  id?: string;
  category: string;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  response_hours: number | null;
  resolution_hours: number | null;
  due_soon_hours: number;
  escalate_after_hours: number | null;
  is_active: boolean;
}

export interface TicketStats {
  total: number;
  new: number;
  open: number;
  in_progress: number;
  pending: number;
  on_hold: number;
  resolved: number;
  closed: number;
  cancelled: number;
  active: number;
  assigned_to_me: number;
  raised_by_me: number;
}

export interface TicketReport {
  filters: Record<string, unknown>;
  totals: Record<string, number | null>;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  by_family: Record<string, number>;
  by_subcategory: Record<string, number>;
  by_source: Record<string, number>;
  by_assignee: { assignee: string; open: number; resolved: number; overdue: number }[];
}

export interface TicketReconciliationRow {
  kind: string;
  ticket_id?: string;
  ticket_number?: string | null;
  checklist_id?: string;
  item_id?: string;
  employee_name?: string | null;
  title: string;
  status: string;
  note: string | null;
}

export interface TicketReconciliation {
  counts: Record<string, number>;
  rows: TicketReconciliationRow[];
}

export interface EmployeeTicketRow {
  id: string;
  ticket_number: string;
  title: string;
  category_label: string;
  status: TicketStatus;
  status_label: string;
  priority_label: string;
  assignee_name: string | null;
  due_date: string | null;
  is_overdue: boolean;
  updated_at: string | null;
  relation: 'affected' | 'requester';
  can_open: boolean;
}
