import { apiClient } from './client';

export type AutomationRuleKind = 'event' | 'sweep' | 'external';
export type ExecutionStatus = 'succeeded' | 'failed' | 'skipped' | 'pending_review' | 'dismissed';

export interface AutomationRule {
  key: string;
  name: string;
  module: string;
  kind: AutomationRuleKind;
  trigger: string;
  description: string;
  conditions: string;
  action: string;
  recipients: string;
  authorization: string;
  consequential: boolean;
  executable: boolean;
  managed_by: string | null;
  is_enabled: boolean;
  last_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  failed_count: number;
  pending_review_count: number;
  execution_count: number;
}

export interface AutomationExecution {
  id: string;
  rule_key: string;
  rule_name: string;
  trigger_event: string;
  actor_type: 'user' | 'system';
  actor_name: string | null;
  target_type: string;
  target_id: string | null;
  project_id: string | null;
  project_label: string | null;
  status: ExecutionStatus;
  summary: string | null;
  result: Record<string, unknown> | null;
  error_message: string | null;
  attempts: number;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface DecisionAuditEntry {
  kind: 'template_change' | 'lifecycle' | 'rule_change' | 'automation';
  id: string;
  time: string;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  target: string;
  target_id: string | null;
  project_id: string | null;
  project_label: string | null;
  previous_value: string | null;
  new_value: string | null;
  trigger: string | null;
  reason: string | null;
  approval_reference: string | null;
  result: string | null;
  error: string | null;
}

export interface ExecutionFilters {
  rule_key?: string;
  status?: string;
  search?: string;
  page: number;
  page_size: number;
}

export interface DecisionAuditFilters {
  search?: string;
  kind?: DecisionAuditEntry['kind'];
  date_from?: string;
  date_to?: string;
  page: number;
  page_size: number;
}

function clean<T extends object>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  ) as Partial<T>;
}

export async function fetchAutomationRules(): Promise<AutomationRule[]> {
  const { data } = await apiClient.get<AutomationRule[]>('/automation/rules');
  return data;
}

export async function setAutomationRuleEnabled(
  key: string,
  isEnabled: boolean,
  reason?: string,
): Promise<AutomationRule> {
  const { data } = await apiClient.patch<AutomationRule>(`/automation/rules/${encodeURIComponent(key)}`, {
    is_enabled: isEnabled,
    reason: reason || null,
  });
  return data;
}

export async function runAutomationSweeps(
  ruleKeys?: string[],
): Promise<Record<string, { evaluated: number; new: number; deduplicated: number; failed: number }>> {
  const { data } = await apiClient.post('/automation/run-sweeps', { rule_keys: ruleKeys ?? null });
  return data;
}

export async function fetchAutomationExecutions(filters: ExecutionFilters): Promise<Page<AutomationExecution>> {
  const { data } = await apiClient.get<Page<AutomationExecution>>('/automation/executions', {
    params: clean(filters),
  });
  return data;
}

export async function retryAutomationExecution(id: string): Promise<AutomationExecution> {
  const { data } = await apiClient.post<AutomationExecution>(`/automation/executions/${id}/retry`);
  return data;
}

export async function reviewAutomationExecution(
  id: string,
  decision: 'acknowledge' | 'dismiss',
  note?: string,
): Promise<AutomationExecution> {
  const { data } = await apiClient.post<AutomationExecution>(`/automation/executions/${id}/review`, {
    decision,
    note: note || null,
  });
  return data;
}

export async function fetchDecisionAudit(filters: DecisionAuditFilters): Promise<Page<DecisionAuditEntry>> {
  const { data } = await apiClient.get<Page<DecisionAuditEntry>>('/automation/decision-audit', {
    params: clean(filters),
  });
  return data;
}
