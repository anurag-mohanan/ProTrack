import type {
  ControlTowerParams,
  ControlTowerResponse,
  CtConvertResult,
  CtEvaluationRun,
  CtFindingDetail,
  CtTriageAction,
} from '../types/ControlTower';
import { apiClient, buildQuery } from './client';

export async function fetchControlTower(params: ControlTowerParams): Promise<ControlTowerResponse> {
  const { data } = await apiClient.get<ControlTowerResponse>(`/control-tower${buildQuery({ ...params })}`);
  return data;
}

export async function fetchControlTowerFinding(findingId: string): Promise<CtFindingDetail> {
  const { data } = await apiClient.get<CtFindingDetail>(`/control-tower/findings/${findingId}`);
  return data;
}

export async function evaluateControlTower(): Promise<CtEvaluationRun> {
  const { data } = await apiClient.post<CtEvaluationRun>('/control-tower/evaluate');
  return data;
}

export async function acknowledgeControlTowerFinding(findingId: string, note: string): Promise<CtFindingDetail> {
  const { data } = await apiClient.post<CtFindingDetail>(`/control-tower/findings/${findingId}/acknowledge`, {
    note: note.trim() || null,
  });
  return data;
}

export async function triageControlTowerFinding(
  findingId: string,
  action: CtTriageAction,
  note: string,
): Promise<CtFindingDetail> {
  const { data } = await apiClient.post<CtFindingDetail>(`/control-tower/findings/${findingId}/triage`, {
    action,
    note: note.trim() || null,
  });
  return data;
}

export async function convertControlTowerFinding(findingId: string, note: string): Promise<CtConvertResult> {
  const { data } = await apiClient.post<CtConvertResult>(`/control-tower/findings/${findingId}/convert`, {
    note: note.trim() || null,
  });
  return data;
}

export const controlTowerQueryKeys = {
  all: ['control-tower'] as const,
  list: (params: ControlTowerParams) => ['control-tower', 'list', params] as const,
  finding: (findingId: string) => ['control-tower', 'finding', findingId] as const,
};
