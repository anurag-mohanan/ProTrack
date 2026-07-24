import { apiClient, buildQuery } from './client';

export type SkillGap = {
  stream_skill_id: string;
  skill_name: string;
  current_proficiency: string;
  target_proficiency: string;
};

export type LearningPlanItem = {
  id: string;
  plan_id: string;
  stream_skill_id: string;
  skill_name?: string | null;
  current_proficiency?: string | null;
  target_proficiency: string;
  status: string;
  due_date?: string | null;
  notes?: string | null;
  sort_order: number;
};

export type LearningPlan = {
  id: string;
  user_id: string;
  title: string;
  status: string;
  created_by_id?: string | null;
  items: LearningPlanItem[];
  created_at?: string | null;
  updated_at?: string | null;
};

export async function fetchSkillGaps(
  userId: string,
  targetProficiency = 'proficient',
): Promise<SkillGap[]> {
  const { data } = await apiClient.get<SkillGap[]>(
    `/hr/performance/skill-gaps${buildQuery({
      user_id: userId,
      target_proficiency: targetProficiency,
    })}`,
  );
  return data;
}

export async function fetchLearningPlans(userId: string): Promise<LearningPlan[]> {
  const { data } = await apiClient.get<LearningPlan[]>(
    `/hr/performance/learning-plans${buildQuery({ user_id: userId })}`,
  );
  return data;
}

export async function createLearningPlanFromGaps(payload: {
  user_id: string;
  title?: string;
  target_proficiency?: string;
}): Promise<LearningPlan> {
  const { data } = await apiClient.post<LearningPlan>(
    '/hr/performance/learning-plans/from-gaps',
    payload,
  );
  return data;
}

export async function updateLearningPlanItemStatus(
  itemId: string,
  status: string,
): Promise<LearningPlanItem> {
  const { data } = await apiClient.patch<LearningPlanItem>(
    `/hr/performance/learning-plan-items/${itemId}`,
    { status },
  );
  return data;
}
