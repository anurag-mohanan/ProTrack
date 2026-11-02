export type CtSeverity = 'critical' | 'high' | 'medium' | 'info';
export type CtCategory = 'schedule' | 'effort' | 'delivery' | 'data_quality' | 'capability' | 'resource';
export type CtFindingStatus = 'active' | 'not_assessable' | 'resolved';
export type CtView = 'risks' | 'predictive' | 'data_quality' | 'resolved';
export type CtSource = 'operational' | 'predictive';
export type CtTriageStatus = 'investigating' | 'dismissed';
export type CtTriageFilter = 'untriaged' | CtTriageStatus;
export type CtTriageAction = 'investigate' | 'dismiss' | 'reopen';
export type CtState = 'never_evaluated' | 'running' | 'last_run_failed' | 'stale' | 'ok';

export interface CtEvidenceLine {
  label: string;
  value: string;
}

export interface CtFinding {
  id: string;
  finding_key: string;
  rule_id: string;
  rule_title: string;
  category: CtCategory;
  category_label: string;
  severity: CtSeverity;
  status: CtFindingStatus;
  title: string;
  explanation: string;
  recommended_action: string;
  evidence: CtEvidenceLine[];
  metrics: Record<string, unknown>;
  not_assessable_reason: string | null;
  project: {
    id: string;
    code: string | null;
    tool_number: string | null;
    part_description: string | null;
    execution_status: string;
  };
  milestone: { id: string; name: string } | null;
  owner: {
    id: string | null;
    name: string | null;
    basis: 'milestone_assignee' | 'design_leader' | null;
    basis_label: string | null;
  };
  first_detected_at: string;
  last_evaluated_at: string;
  last_changed_at: string;
  evaluation_date: string;
  resolved_at: string | null;
  resolution_note: string | null;
  acknowledged_at: string | null;
  acknowledged_by_name: string | null;
  acknowledgement_note: string | null;
  is_recurrence: boolean;
  source: CtSource;
  source_label: string;
  prediction_id: string | null;
  triage_status: CtTriageStatus | null;
  triage_note: string | null;
  triaged_at: string | null;
  triaged_by_name: string | null;
  recommendation_id: string | null;
}

export interface CtConvertResult {
  recommendation_id: string;
  status: string;
  title: string;
}

export interface CtFindingEvent {
  event: string;
  occurred_at: string;
  user_name: string | null;
  detail: string | null;
}

export interface CtFindingDetail extends CtFinding {
  events: CtFindingEvent[];
}

export interface CtEvaluationRun {
  id: string;
  status: 'running' | 'succeeded' | 'failed';
  trigger: string;
  evaluation_date: string;
  rules_version: string;
  started_at: string;
  finished_at: string | null;
  projects_evaluated: number;
  findings_opened: number;
  findings_updated: number;
  findings_resolved: number;
  findings_open: number;
  error: string | null;
}

export interface CtSummary {
  open_risks: number;
  open_data_quality: number;
  open_predictive: number;
  dismissed: number;
  not_assessable: number;
  projects_with_risks: number;
  projects_with_data_quality: number;
  resolved_last_30_days: number;
  by_severity: { severity: CtSeverity; label: string; count: number }[];
  by_category: { category: CtCategory; label: string; count: number }[];
}

export interface CtRule {
  rule_id: string;
  title: string;
  category: CtCategory;
  kind: 'risk' | 'data_quality' | 'predictive';
  severity_rule: string;
  condition: string;
  recommended_action: string;
}

export interface CtDeferredRule {
  rule_id: string;
  title: string;
  reason: string;
}

export interface CtOption {
  value: string;
  label: string;
}

export interface ControlTowerParams {
  view: CtView;
  severity?: CtSeverity;
  category?: CtCategory;
  status?: CtFindingStatus;
  project_id?: string;
  owner_id?: string;
  search?: string;
  triage?: CtTriageFilter;
  page?: number;
  page_size?: number;
}

export interface ControlTowerResponse {
  state: CtState;
  state_message: string;
  evaluation_date: string | null;
  latest_run: CtEvaluationRun | null;
  last_successful_run: CtEvaluationRun | null;
  can_evaluate: boolean;
  can_acknowledge: boolean;
  summary: CtSummary;
  findings: CtFinding[];
  total: number;
  page: number;
  page_size: number;
  owner_options: CtOption[];
  project_options: CtOption[];
  rules: CtRule[];
  deferred_rules: CtDeferredRule[];
  empty_message: string | null;
}
