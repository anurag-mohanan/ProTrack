import { apiClient } from '../api/client';

export type AssignmentFitCheck = {
  ok: boolean;
  requires_confirmation: boolean;
  warnings: string[];
  message: string;
  user_id?: string;
  user_name?: string;
  complexity?: string;
  complexity_label?: string;
  role?: string;
  skill_name?: string | null;
  proficiency?: string | null;
  proficiency_label?: string | null;
  required_proficiency?: string;
  required_proficiency_label?: string;
  checks?: AssignmentFitCheck[];
};

export async function fetchAssignmentSkillFit(params: {
  complexity?: string | null;
  designer_id?: string | null;
  surfacer_id?: string | null;
  design_leader_id?: string | null;
  user_id?: string | null;
  role?: string;
}): Promise<AssignmentFitCheck> {
  const query = new URLSearchParams();
  if (params.complexity) query.set('complexity', params.complexity);
  if (params.designer_id) query.set('designer_id', params.designer_id);
  if (params.surfacer_id) query.set('surfacer_id', params.surfacer_id);
  if (params.design_leader_id) query.set('design_leader_id', params.design_leader_id);
  if (params.user_id) query.set('user_id', params.user_id);
  if (params.role) query.set('role', params.role);
  const qs = query.toString();
  return (await apiClient.get<AssignmentFitCheck>(`/hr/performance/assignment-fit${qs ? `?${qs}` : ''}`))
    .data;
}
