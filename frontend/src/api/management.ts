import type {
  ActionList,
  ActionStatus,
  Cockpit,
  CockpitFilterValues,
  CustomerProfile,
  CustomerTable,
  Efficiency,
  FilterOptions,
  Initiative,
  KpiOption,
  ManagementAction,
  ManagementReport,
  Objective,
  ReviewComparison,
  ReviewDetail,
  ReviewSummary,
} from '../types/Management';
import { apiClient, buildQuery } from './client';
import { downloadReportExcel } from './engineeringPerformance';

const BASE = '/management';

function query(filters: CockpitFilterValues, extra: Record<string, string | number | boolean | undefined> = {}): string {
  return buildQuery({ ...filters, ...extra } as Record<string, string | number | boolean | undefined>);
}

export async function fetchManagementFilters(): Promise<FilterOptions> {
  const { data } = await apiClient.get<FilterOptions>(`${BASE}/filters`);
  return data;
}

export async function fetchCockpit(filters: CockpitFilterValues): Promise<Cockpit> {
  const { data } = await apiClient.get<Cockpit>(`${BASE}/cockpit${query(filters)}`);
  return data;
}

export async function fetchCustomerTable(filters: CockpitFilterValues): Promise<CustomerTable> {
  const { data } = await apiClient.get<CustomerTable>(`${BASE}/customers${query(filters)}`);
  return data;
}

export async function fetchCustomerProfile(customerId: string, filters: CockpitFilterValues): Promise<CustomerProfile> {
  const { data } = await apiClient.get<CustomerProfile>(`${BASE}/customers/${customerId}${query(filters)}`);
  return data;
}

export async function fetchEfficiency(filters: CockpitFilterValues, compareBy: string): Promise<Efficiency> {
  const { data } = await apiClient.get<Efficiency>(`${BASE}/efficiency${query(filters, { compare_by: compareBy })}`);
  return data;
}

export async function fetchKpiOptions(): Promise<KpiOption[]> {
  const { data } = await apiClient.get<{ kpis: KpiOption[] }>(`${BASE}/kpis`);
  return data.kpis;
}

export async function fetchObjectives(fyStartYear?: number): Promise<Objective[]> {
  const { data } = await apiClient.get<{ objectives: Objective[] }>(
    `${BASE}/objectives${buildQuery({ fy_start_year: fyStartYear })}`,
  );
  return data.objectives;
}

export async function fetchObjective(id: string): Promise<Objective> {
  const { data } = await apiClient.get<Objective>(`${BASE}/objectives/${id}`);
  return data;
}

export interface ObjectiveInput {
  title: string;
  description?: string | null;
  fy_start_year: number;
  period_type: 'annual' | 'quarterly' | 'monthly';
  period_index?: number | null;
  category: string;
  unit: string;
  direction: 'increase' | 'decrease';
  measurement: 'automatic' | 'manual';
  metric_key?: string | null;
  target_value: string;
  baseline_value?: string | null;
  baseline_note?: string | null;
  owner_id?: string | null;
}

export async function createObjective(body: ObjectiveInput): Promise<Objective> {
  const { data } = await apiClient.post<Objective>(`${BASE}/objectives`, body);
  return data;
}

export async function updateObjective(
  id: string,
  body: { status?: string; status_reason?: string | null; description?: string | null },
): Promise<Objective> {
  const { data } = await apiClient.patch<Objective>(`${BASE}/objectives/${id}`, body);
  return data;
}

export async function changeObjectiveTarget(
  id: string,
  body: { target_value?: string | null; baseline_value?: string | null; reason: string },
): Promise<Objective> {
  const { data } = await apiClient.post<Objective>(`${BASE}/objectives/${id}/target`, body);
  return data;
}

export async function approveObjectiveTarget(id: string, note?: string): Promise<Objective> {
  const { data } = await apiClient.post<Objective>(`${BASE}/objectives/${id}/approve-target`, { note: note || null });
  return data;
}

export async function recordObjectiveMeasurement(
  id: string,
  body: { value: string; period_start: string; period_end: string; evidence: string; note?: string | null },
): Promise<Objective> {
  const { data } = await apiClient.post<Objective>(`${BASE}/objectives/${id}/measurements`, body);
  return data;
}

export async function commentOnObjective(id: string, text: string, kind: 'comment' | 'decision' = 'comment'): Promise<void> {
  await apiClient.post(`${BASE}/objectives/${id}/comments`, { text, kind });
}

export async function fetchInitiatives(): Promise<Initiative[]> {
  const { data } = await apiClient.get<{ initiatives: Initiative[] }>(`${BASE}/initiatives`);
  return data.initiatives;
}

export async function createInitiative(body: {
  name: string;
  objective_id?: string | null;
  owner_id?: string | null;
  target_date?: string | null;
  priority?: string;
  description?: string | null;
}): Promise<Initiative> {
  const { data } = await apiClient.post<Initiative>(`${BASE}/initiatives`, body);
  return data;
}

export async function updateInitiative(
  id: string,
  body: { status?: string; status_reason?: string | null; progress_percent?: number; notes?: string | null },
): Promise<Initiative> {
  const { data } = await apiClient.patch<Initiative>(`${BASE}/initiatives/${id}`, body);
  return data;
}

export async function commentOn(entity: 'reviews' | 'actions' | 'initiatives', id: string, text: string): Promise<void> {
  await apiClient.post(`${BASE}/${entity}/${id}/comments`, { text, kind: 'comment' });
}

export async function fetchActions(params: { open_only?: boolean; mine?: boolean; status?: string } = {}): Promise<ActionList> {
  const { data } = await apiClient.get<ActionList>(`${BASE}/actions${buildQuery(params)}`);
  return data;
}

export async function createAction(body: {
  title: string;
  owner_id: string;
  due_date?: string | null;
  priority?: string;
  description?: string | null;
  objective_id?: string | null;
  review_id?: string | null;
}): Promise<ManagementAction> {
  const { data } = await apiClient.post<ManagementAction>(`${BASE}/actions`, body);
  return data;
}

export async function updateAction(
  id: string,
  body: { status?: ActionStatus; status_reason?: string | null; completion_evidence?: string | null; due_date?: string | null },
): Promise<ManagementAction> {
  const { data } = await apiClient.patch<ManagementAction>(`${BASE}/actions/${id}`, body);
  return data;
}

export async function fetchReviews(): Promise<ReviewSummary[]> {
  const { data } = await apiClient.get<{ reviews: ReviewSummary[] }>(`${BASE}/reviews`);
  return data.reviews;
}

export async function fetchReview(id: string): Promise<ReviewDetail> {
  const { data } = await apiClient.get<ReviewDetail>(`${BASE}/reviews/${id}`);
  return data;
}

export async function createReview(body: {
  review_type: 'monthly' | 'quarterly' | 'annual';
  fy_start_year: number;
  period_index?: number | null;
}): Promise<ReviewDetail> {
  const { data } = await apiClient.post<ReviewDetail>(`${BASE}/reviews`, body);
  return data;
}

export async function updateReview(id: string, body: { executive_summary?: string | null; title?: string }): Promise<ReviewDetail> {
  const { data } = await apiClient.patch<ReviewDetail>(`${BASE}/reviews/${id}`, body);
  return data;
}

export async function regenerateReview(id: string): Promise<ReviewDetail> {
  const { data } = await apiClient.post<ReviewDetail>(`${BASE}/reviews/${id}/regenerate`);
  return data;
}

export async function finaliseReview(id: string): Promise<ReviewDetail> {
  const { data } = await apiClient.post<ReviewDetail>(`${BASE}/reviews/${id}/finalise`);
  return data;
}

export async function recordReviewDecision(
  id: string,
  body: { text: string; action_title?: string | null; action_owner_id?: string | null; action_due_date?: string | null },
): Promise<ReviewDetail> {
  const { data } = await apiClient.post<ReviewDetail>(`${BASE}/reviews/${id}/decisions`, body);
  return data;
}

export async function compareReview(id: string): Promise<ReviewComparison> {
  const { data } = await apiClient.get<ReviewComparison>(`${BASE}/reviews/${id}/compare`);
  return data;
}

export function downloadManagementReport(
  report: ManagementReport,
  filters: CockpitFilterValues,
  extra: { compare_by?: string; review_id?: string } = {},
): Promise<void> {
  return downloadReportExcel(`${BASE}/exports/${report}.xlsx${query(filters, extra)}`, `Management_${report}.xlsx`);
}

export const managementQueryKeys = {
  all: ['management'] as const,
  filters: ['management', 'filters'] as const,
  cockpit: (f: CockpitFilterValues) => ['management', 'cockpit', f] as const,
  customers: (f: CockpitFilterValues) => ['management', 'customers', f] as const,
  customer: (id: string, f: CockpitFilterValues) => ['management', 'customer', id, f] as const,
  efficiency: (f: CockpitFilterValues, by: string) => ['management', 'efficiency', f, by] as const,
  kpis: ['management', 'kpis'] as const,
  objectives: (fy?: number) => ['management', 'objectives', fy ?? null] as const,
  objective: (id: string) => ['management', 'objective', id] as const,
  actions: (p: object) => ['management', 'actions', p] as const,
  initiatives: ['management', 'initiatives'] as const,
  reviews: ['management', 'reviews'] as const,
  review: (id: string) => ['management', 'review', id] as const,
  compare: (id: string) => ['management', 'compare', id] as const,
};
