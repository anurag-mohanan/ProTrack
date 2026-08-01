import { apiClient } from './client';

export type ExitInterviewStatus = 'draft' | 'in_progress' | 'completed' | 'cancelled';
export type ExitQuestionInput = 'text' | 'textarea' | 'choice' | 'rating';

export interface ExitInterviewQuestion {
  id: string;
  section: string;
  prompt: string;
  input: ExitQuestionInput;
  required: boolean;
  options: string[];
  min?: number | null;
  max?: number | null;
  hr_only?: boolean;
}

export interface ExitInterview {
  id: string;
  form_code: string;
  form_title: string;
  employee_user_id: string | null;
  employee_name: string;
  employee_code: string | null;
  designation: string | null;
  department_name: string | null;
  org_department_id: string | null;
  team_id: string | null;
  team_name: string | null;
  role_id: string | null;
  role_name: string | null;
  reporting_manager_id: string | null;
  reporting_manager_name: string | null;
  last_working_date: string | null;
  resignation_date: string | null;
  interview_date: string | null;
  interviewer_user_id: string | null;
  interviewer_name: string | null;
  status: ExitInterviewStatus;
  status_label: string;
  answers: Record<string, string | number>;
  notes: string | null;
  attitude_was_good: boolean | null;
  skillset_rating: number | null;
  eligible_for_rehire: 'yes' | 'no' | 'conditional' | null;
  created_by_id: string | null;
  completed_at: string | null;
  is_published: boolean;
  published_at: string | null;
  published_by_id: string | null;
  questions: ExitInterviewQuestion[];
  created_at: string;
  updated_at: string;
}

export interface ExitInterviewCreate {
  employee_name: string;
  employee_user_id?: string | null;
  employee_code?: string | null;
  designation?: string | null;
  department_name?: string | null;
  org_department_id?: string | null;
  team_id?: string | null;
  role_id?: string | null;
  reporting_manager_id?: string | null;
  reporting_manager_name?: string | null;
  last_working_date?: string | null;
  resignation_date?: string | null;
  interview_date?: string | null;
  interviewer_user_id?: string | null;
  interviewer_name?: string | null;
  notes?: string | null;
  attitude_was_good?: boolean | null;
  skillset_rating?: number | null;
  eligible_for_rehire?: 'yes' | 'no' | 'conditional' | null;
  answers?: Record<string, string | number>;
}

export type ExitInterviewUpdate = Partial<ExitInterviewCreate> & {
  status?: ExitInterviewStatus;
  confirm_left_organisation?: boolean;
};

export const exitProcessApi = {
  form: async () => {
    const { data } = await apiClient.get<ExitInterviewQuestion[]>('/hr/exit-process/form');
    return data;
  },
  list: async (params?: { status?: string }) => {
    const { data } = await apiClient.get<ExitInterview[]>('/hr/exit-process', { params });
    return data;
  },
  get: async (id: string) => {
    const { data } = await apiClient.get<ExitInterview>(`/hr/exit-process/${id}`);
    return data;
  },
  create: async (payload: ExitInterviewCreate) => {
    const { data } = await apiClient.post<ExitInterview>('/hr/exit-process', payload);
    return data;
  },
  update: async (id: string, payload: ExitInterviewUpdate) => {
    const { data } = await apiClient.patch<ExitInterview>(`/hr/exit-process/${id}`, payload);
    return data;
  },
  remove: async (id: string) => {
    await apiClient.delete(`/hr/exit-process/${id}`);
  },
  publish: async (id: string) => {
    const { data } = await apiClient.post<ExitInterview>(`/hr/exit-process/${id}/publish`);
    return data;
  },
};
