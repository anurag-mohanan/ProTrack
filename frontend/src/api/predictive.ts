import type {
  AccuracyReport,
  PatternReport,
  PredictionList,
  PredictionOverview,
  PredictionRunRead,
  PredictionTypeKey,
  ProjectPredictionDetail,
  SavedScenario,
  ScenarioAssumptions,
  ScenarioList,
  ScenarioResult,
} from '../types/Predictive';
import { apiClient, buildQuery } from './client';

export async function fetchPredictionOverview(): Promise<PredictionOverview> {
  const { data } = await apiClient.get<PredictionOverview>('/predictions/overview');
  return data;
}

export async function fetchPredictions(params: {
  prediction_type: PredictionTypeKey;
  status?: 'predicted' | 'insufficient_data';
  subject_type?: string;
  weeks?: number;
}): Promise<PredictionList> {
  const { data } = await apiClient.get<PredictionList>(`/predictions${buildQuery({ ...params })}`);
  return data;
}

export async function fetchProjectPredictions(projectId: string): Promise<ProjectPredictionDetail> {
  const { data } = await apiClient.get<ProjectPredictionDetail>(`/predictions/projects/${projectId}`);
  return data;
}

export async function fetchPredictionAccuracy(): Promise<AccuracyReport> {
  const { data } = await apiClient.get<AccuracyReport>('/predictions/accuracy');
  return data;
}

export async function fetchPredictionPatterns(kind: 'project' | 'payment'): Promise<PatternReport> {
  const { data } = await apiClient.get<PatternReport>(`/predictions/patterns${buildQuery({ kind })}`);
  return data;
}

export async function runPredictions(): Promise<PredictionRunRead> {
  const { data } = await apiClient.post<PredictionRunRead>('/predictions/run');
  return data;
}

export async function updatePredictionSetting(
  predictionType: PredictionTypeKey,
  body: { enabled: boolean; reason?: string },
): Promise<void> {
  await apiClient.put(`/predictions/settings/${predictionType}`, body);
}

export async function activatePredictionModel(
  predictionType: PredictionTypeKey,
  version: string,
  note?: string,
): Promise<void> {
  await apiClient.post(`/predictions/models/${predictionType}/${encodeURIComponent(version)}/activate`, { note });
}

export async function fetchScenarios(projectId: string): Promise<ScenarioList> {
  const { data } = await apiClient.get<ScenarioList>(`/predictions/projects/${projectId}/scenarios`);
  return data;
}

export async function previewScenario(projectId: string, assumptions: ScenarioAssumptions): Promise<ScenarioResult> {
  const { data } = await apiClient.post<ScenarioResult>(`/predictions/projects/${projectId}/scenarios/preview`, assumptions);
  return data;
}

export async function createScenario(
  projectId: string,
  body: { name: string; assumptions: ScenarioAssumptions },
): Promise<SavedScenario> {
  const { data } = await apiClient.post<SavedScenario>(`/predictions/projects/${projectId}/scenarios`, body);
  return data;
}

export async function updateScenario(
  scenarioId: string,
  body: { name: string; assumptions: ScenarioAssumptions },
): Promise<SavedScenario> {
  const { data } = await apiClient.put<SavedScenario>(`/predictions/scenarios/${scenarioId}`, body);
  return data;
}

export async function deleteScenario(scenarioId: string): Promise<void> {
  await apiClient.delete(`/predictions/scenarios/${scenarioId}`);
}

export const predictiveQueryKeys = {
  all: ['predictions'] as const,
  overview: ['predictions', 'overview'] as const,
  list: (type: PredictionTypeKey, weeks?: number) => ['predictions', 'list', type, weeks ?? null] as const,
  project: (id: string) => ['predictions', 'project', id] as const,
  accuracy: ['predictions', 'accuracy'] as const,
  patterns: (kind: 'project' | 'payment') => ['predictions', 'patterns', kind] as const,
  scenarios: (projectId: string) => ['predictions', 'scenarios', projectId] as const,
};
