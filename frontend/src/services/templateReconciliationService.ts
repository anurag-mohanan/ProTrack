import { apiClient } from '../api/client';
import type { Project } from '../types';

export type MatchClassification = 'confirmed' | 'likely' | 'possible' | 'different';
export type ExistingAction = 'retain' | 'supersede' | 'archive' | 'merge';

export interface ReconMilestoneView {
  id: string;
  name: string;
  status: string;
  lifecycle_state: string;
  project_stage: string | null;
  completed_date: string | null;
  due_date: string | null;
  assigned_user_id: string | null;
  assigned_user_name: string | null;
  is_required: boolean;
  planned_hours: string;
  actual_hours: string;
  template_milestone_id: string | null;
  created_at: string;
}

export interface ReconExistingItem extends ReconMilestoneView {
  in_new_template: boolean;
  decision: ExistingAction;
  merge_into_id: string | null;
  merge_into_name: string | null;
  allowed_actions: ExistingAction[];
}

export interface ReconMatchCandidate {
  milestone_id: string;
  milestone_name: string;
  milestone_status: string;
  classification: MatchClassification;
  classification_label: string;
  reasons: string[];
  requires_confirmation: boolean;
}

export interface ReconMatchItem {
  template_milestone_id: string;
  template_name: string;
  template_stage: string | null;
  decision: 'match' | 'add';
  milestone: ReconMilestoneView | null;
  classification: MatchClassification | null;
  reasons: string[];
  completion_retained: boolean;
  attribute_changes: string[];
  candidates: ReconMatchCandidate[];
  needs_review: boolean;
}

export interface ReconNewMilestone {
  template_milestone_id: string;
  name: string;
  stage: string | null;
  is_required: boolean;
  due_date: string | null;
  due_date_rule: string;
  assigned_user_id: string | null;
  assigned_user_name: string | null;
  assignment_rule: string;
  planned_hours: string;
  template_estimated_hours: string | null;
  depends_on_names: string[];
  sort_position: number;
}

export interface ReconDuplicate {
  milestone: ReconMilestoneView;
  canonical: ReconMilestoneView;
  classification: MatchClassification;
  classification_label: string;
  reasons: string[];
  default_action: ExistingAction;
  merge_allowed: boolean;
  requires_confirmation: boolean;
  preserved: string[];
}

export interface ReconDependencyChange {
  kind: string;
  milestone_name: string;
  depends_on_name: string | null;
  detail: string;
}

export interface ReconCounts {
  add: number;
  match: number;
  retain: number;
  merge: number;
  supersede: number;
  archive: number;
  needs_review: number;
  inactive_untouched: number;
}

export interface ReconTemplateRef {
  id: string;
  name: string;
  version: number;
}

export interface TemplateReconciliationPreview {
  method_version: string;
  project_id: string;
  fingerprint: string;
  plan_version: number;
  previous_template: ReconTemplateRef | null;
  new_template: ReconTemplateRef;
  same_template: boolean;
  options: { apply_template_hours: boolean; schedule_new: boolean };
  existing: ReconExistingItem[];
  matches: ReconMatchItem[];
  new_milestones: ReconNewMilestone[];
  duplicates: ReconDuplicate[];
  not_in_template: ReconExistingItem[];
  inactive_milestones: (ReconMilestoneView & { merged_into_id: string | null; lifecycle_reason: string | null })[];
  dependency_changes: ReconDependencyChange[];
  planned_hours: { before: string; after: string; changes: boolean; uses_stage_estimates: boolean };
  counts: ReconCounts;
  requires_confirmation: boolean;
  consequential: boolean;
  requires_estimate_acknowledgement: boolean;
  warnings: string[];
  blockers: string[];
  rules: string[];
}

export interface TemplateDecision {
  template_milestone_id: string;
  action: 'match' | 'add';
  milestone_id?: string | null;
}

export interface ExistingDecision {
  milestone_id: string;
  action: ExistingAction;
  merge_into_id?: string | null;
}

export interface TemplateReconciliationPreviewRequest {
  template_id: string;
  template_decisions: TemplateDecision[];
  existing_decisions: ExistingDecision[];
  apply_template_hours: boolean;
  schedule_new: boolean;
}

export interface TemplateReconciliationApplyRequest extends TemplateReconciliationPreviewRequest {
  preview_fingerprint: string;
  plan_version: number;
  request_key: string;
  confirm: boolean;
  acknowledge_estimate_change: boolean;
  reason?: string | null;
}

export interface TemplateReconciliationRecord {
  id: string;
  project_id: string;
  status: 'applied' | 'failed';
  previous_template: (ReconTemplateRef & { id: string }) | null;
  new_template: ReconTemplateRef;
  counts: Omit<ReconCounts, 'needs_review' | 'inactive_untouched'>;
  decisions: Record<string, unknown>;
  reason: string | null;
  error_message: string | null;
  confirmed_by_id: string | null;
  confirmed_by_name: string | null;
  confirmed_at: string;
}

export interface TemplateReconciliationApplyResult {
  reconciliation: TemplateReconciliationRecord;
  replayed: boolean;
  project: Project;
}

export function summarizeReconciliation(result: TemplateReconciliationApplyResult): string {
  const c = result.reconciliation.counts;
  const parts = [`${c.add} added`, `${c.match} matched`];
  if (c.merge) parts.push(`${c.merge} merged`);
  if (c.supersede) parts.push(`${c.supersede} superseded`);
  if (c.archive) parts.push(`${c.archive} archived`);
  const replay = result.replayed ? ' (already applied earlier)' : '';
  return `Template changed to ${result.reconciliation.new_template.name}${replay}: ${parts.join(', ')}. Completed work was kept.`;
}

export async function previewTemplateReconciliation(
  projectId: string,
  payload: TemplateReconciliationPreviewRequest,
): Promise<TemplateReconciliationPreview> {
  const { data } = await apiClient.post<TemplateReconciliationPreview>(
    `/projects/${projectId}/template-reconciliation/preview`,
    payload,
  );
  return data;
}

export async function applyTemplateReconciliation(
  projectId: string,
  payload: TemplateReconciliationApplyRequest,
): Promise<TemplateReconciliationApplyResult> {
  const { data } = await apiClient.post<TemplateReconciliationApplyResult>(
    `/projects/${projectId}/template-reconciliation/apply`,
    payload,
  );
  return data;
}

export async function fetchTemplateReconciliations(
  projectId: string,
): Promise<TemplateReconciliationRecord[]> {
  const { data } = await apiClient.get<TemplateReconciliationRecord[]>(
    `/projects/${projectId}/template-reconciliations`,
  );
  return data;
}
