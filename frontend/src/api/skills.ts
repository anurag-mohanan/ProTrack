import type {
  SkAccess,
  SkDecision,
  SkExperience,
  SkGapParams,
  SkGapReport,
  SkLevel,
  SkMatchRequest,
  SkMatchResult,
  SkMatrix,
  SkMatrixParams,
  SkMethod,
  SkPlan,
  SkPlanWrite,
  SkProfile,
  SkQueueItem,
  SkRequirements,
  SkSkillWrite,
  SkTaxonomy,
} from '../types/Skills';
import { apiClient, buildQuery } from './client';

export async function fetchSkillAccess(): Promise<SkAccess> {
  return (await apiClient.get<SkAccess>('/skills/access')).data;
}

export async function fetchSkillTaxonomy(includeInactive = false): Promise<SkTaxonomy> {
  return (await apiClient.get<SkTaxonomy>(`/skills/taxonomy${buildQuery({ include_inactive: includeInactive || undefined })}`)).data;
}

export async function createSkill(body: SkSkillWrite): Promise<{ id: string; name: string }> {
  return (await apiClient.post<{ id: string; name: string }>('/skills/taxonomy/skills', body)).data;
}

export async function updateSkill(skillId: string, body: SkSkillWrite): Promise<{ id: string; name: string }> {
  return (await apiClient.put<{ id: string; name: string }>(`/skills/taxonomy/skills/${skillId}`, body)).data;
}

export async function renameSkillCategory(oldName: string, newName: string): Promise<{ updated: number }> {
  return (await apiClient.post<{ updated: number }>('/skills/taxonomy/categories/rename', { old: oldName, new: newName })).data;
}

export async function addSkillRelationship(body: {
  from_skill_id: string;
  to_skill_id: string;
  relation_type: string;
  note: string | null;
}): Promise<void> {
  await apiClient.post('/skills/taxonomy/relationships', body);
}

export async function removeSkillRelationship(id: string): Promise<void> {
  await apiClient.delete(`/skills/taxonomy/relationships/${id}`);
}

export async function updateProficiencyLevel(level: number, name: string, description: string | null): Promise<SkLevel[]> {
  return (await apiClient.put<SkLevel[]>(`/skills/taxonomy/levels/${level}`, { name, description })).data;
}

export interface StandardPackResult {
  dry_run: boolean;
  created: { name: string; category: string; kind: string }[];
  already_present: { name: string; existing_name: string; existing_is_active: boolean }[];
}

export async function loadStandardPack(dryRun: boolean): Promise<StandardPackResult> {
  return (await apiClient.post<StandardPackResult>(`/skills/taxonomy/standard-pack${buildQuery({ dry_run: dryRun })}`)).data;
}

export async function fetchMySkills(): Promise<SkProfile> {
  return (await apiClient.get<SkProfile>('/skills/me')).data;
}

export async function fetchSkillProfile(userId: string): Promise<SkProfile> {
  return (await apiClient.get<SkProfile>(`/skills/profiles/${userId}`)).data;
}

export async function fetchSkillExperience(userId: string): Promise<SkExperience> {
  return (await apiClient.get<SkExperience>(`/skills/profiles/${userId}/experience`)).data;
}

export async function declareSkill(body: {
  skill_id: string;
  declared_level: number;
  years_experience: number | null;
  last_used_on: string | null;
  employee_note: string | null;
  submit_for_verification: boolean;
}): Promise<void> {
  await apiClient.post('/skills/me/declarations', body);
}

export async function submitSkillRecord(recordId: string): Promise<void> {
  await apiClient.post(`/skills/records/${recordId}/submit`);
}

export async function archiveSkillRecord(recordId: string, reason: string | null): Promise<void> {
  await apiClient.post(`/skills/records/${recordId}/archive`, { reason });
}

export async function assessSkill(
  userId: string,
  body: {
    skill_id: string;
    decision: SkDecision;
    level: number | null;
    method: SkMethod;
    feedback: string | null;
    confidential_note: string | null;
  },
): Promise<void> {
  await apiClient.post(`/skills/profiles/${userId}/assess`, body);
}

export async function addSkillEvidence(recordId: string, projectId: string, note: string | null): Promise<void> {
  await apiClient.post(`/skills/records/${recordId}/evidence`, { project_id: projectId, note });
}

export async function removeSkillEvidence(evidenceId: string): Promise<void> {
  await apiClient.delete(`/skills/evidence/${evidenceId}`);
}

export async function fetchSkillMatrix(params: SkMatrixParams): Promise<SkMatrix> {
  return (await apiClient.get<SkMatrix>(`/skills/matrix${buildQuery({ ...params })}`)).data;
}

export async function fetchSkillReviewQueue(): Promise<SkQueueItem[]> {
  return (await apiClient.get<SkQueueItem[]>('/skills/review-queue')).data;
}

export async function fetchSkillGaps(params: SkGapParams): Promise<SkGapReport> {
  return (await apiClient.get<SkGapReport>(`/skills/gaps${buildQuery({ ...params })}`)).data;
}

export async function fetchSkillPlans(params: { user_id?: string; include_closed?: boolean }): Promise<SkPlan[]> {
  return (await apiClient.get<SkPlan[]>(`/skills/plans${buildQuery({ ...params })}`)).data;
}

export async function createSkillPlan(body: SkPlanWrite): Promise<SkPlan> {
  return (await apiClient.post<SkPlan>('/skills/plans', body)).data;
}

export async function updateSkillPlan(planId: string, body: SkPlanWrite): Promise<SkPlan> {
  return (await apiClient.put<SkPlan>(`/skills/plans/${planId}`, body)).data;
}

export async function fetchProjectSkillRequirements(projectId: string): Promise<SkRequirements> {
  return (await apiClient.get<SkRequirements>(`/skills/projects/${projectId}/requirements`)).data;
}

export async function setProjectSkillRequirement(
  projectId: string,
  body: { skill_id: string; min_level: number; is_mandatory: boolean; note: string | null },
): Promise<SkRequirements> {
  return (await apiClient.put<SkRequirements>(`/skills/projects/${projectId}/requirements`, body)).data;
}

export async function removeProjectSkillRequirement(projectId: string, requirementId: string): Promise<SkRequirements> {
  return (await apiClient.delete<SkRequirements>(`/skills/projects/${projectId}/requirements/${requirementId}`)).data;
}

export async function matchSkillCandidates(body: SkMatchRequest): Promise<SkMatchResult> {
  return (await apiClient.post<SkMatchResult>('/skills/match', body)).data;
}

export const skillQueryKeys = {
  all: ['skills'] as const,
  access: ['skills', 'access'] as const,
  taxonomy: (includeInactive: boolean) => ['skills', 'taxonomy', includeInactive] as const,
  me: ['skills', 'me'] as const,
  profile: (userId: string) => ['skills', 'profile', userId] as const,
  experience: (userId: string) => ['skills', 'experience', userId] as const,
  matrix: (params: SkMatrixParams) => ['skills', 'matrix', params] as const,
  queue: ['skills', 'queue'] as const,
  gaps: (params: SkGapParams) => ['skills', 'gaps', params] as const,
  plans: (params: { user_id?: string; include_closed?: boolean }) => ['skills', 'plans', params] as const,
  requirements: (projectId: string) => ['skills', 'requirements', projectId] as const,
};
