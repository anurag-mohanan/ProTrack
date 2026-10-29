import { apiClient } from './client';
import type { StageHoursInput } from '../types/Project';
import type { ProjectEngineeringMetrics, ProjectStagePlan } from '../types/projectPlanning';

export const projectPlanningQueryKeys = {
  stagePlan: (projectId: string) => ['projects', projectId, 'stage-plan'] as const,
  engineeringMetrics: (projectId: string) =>
    ['projects', projectId, 'engineering-metrics'] as const,
};

export async function fetchProjectStagePlan(projectId: string): Promise<ProjectStagePlan> {
  const { data } = await apiClient.get<ProjectStagePlan>(`/projects/${projectId}/stage-plan`);
  return data;
}

export async function fetchProjectEngineeringMetrics(
  projectId: string,
): Promise<ProjectEngineeringMetrics> {
  const { data } = await apiClient.get<ProjectEngineeringMetrics>(
    `/projects/${projectId}/engineering-metrics`,
  );
  return data;
}

export async function configureStageEstimates(
  projectId: string,
  stageHours: StageHoursInput,
): Promise<ProjectStagePlan> {
  const { data } = await apiClient.post<ProjectStagePlan>(
    `/projects/${projectId}/stage-estimates`,
    { stage_hours: stageHours },
  );
  return data;
}

export async function reviseStageEstimate(
  projectId: string,
  payload: { stage: string; new_hours: number; reason: string },
): Promise<ProjectStagePlan> {
  const { data } = await apiClient.post<ProjectStagePlan>(
    `/projects/${projectId}/stage-estimates/revisions`,
    payload,
  );
  return data;
}

export async function reviseProjectBaseline(
  projectId: string,
  payload: { reason: string; new_start_date: string | null },
): Promise<ProjectStagePlan> {
  const { data } = await apiClient.post<ProjectStagePlan>(
    `/projects/${projectId}/baseline-revisions`,
    payload,
  );
  return data;
}

export async function setMilestoneScheduleOverride(
  projectId: string,
  milestoneId: string,
  payload: {
    override_start_date: string | null;
    override_finish_date: string | null;
    reason: string | null;
  },
): Promise<ProjectStagePlan> {
  const { data } = await apiClient.put<ProjectStagePlan>(
    `/projects/${projectId}/milestones/${milestoneId}/schedule-override`,
    payload,
  );
  return data;
}
