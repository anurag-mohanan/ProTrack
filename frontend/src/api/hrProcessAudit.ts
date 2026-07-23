import { apiClient } from './client';

export type ProcessAuditFlag =
  | 'incomplete_onboarding'
  | 'missing_exit'
  | 'orphan_placement'
  | 'exit_done_still_active';

export interface ProcessAuditItem {
  flag: ProcessAuditFlag;
  severity: 'high' | 'medium' | 'low';
  title: string;
  subject_name: string;
  subject_user_id: string | null;
  checklist_id: string | null;
  exit_interview_id: string | null;
  detail: string;
  deep_link: string;
  anchor_date: string | null;
}

export interface ProcessAudit {
  as_of: string;
  sla_days: number;
  total: number;
  counts: Record<string, number>;
  items: ProcessAuditItem[];
}

export const hrProcessAuditApi = {
  get: async (slaDays = 14): Promise<ProcessAudit> => {
    const { data } = await apiClient.get<ProcessAudit>('/hr/process-audit', {
      params: { sla_days: slaDays },
    });
    return data;
  },
};
