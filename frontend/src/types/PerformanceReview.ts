import type { RatingScaleItem } from '../components/performanceReview/performanceReviewConstants';
import type { ReviewProjectRow } from '../components/performanceReview/PerformanceReviewProjectsPanel';

export type PerformanceReviewItem = {
  id?: string;
  prompt: string;
  guidance?: string | null;
  rating?: number | string | null;
  rating_label?: string | null;
  employee_comment?: string | null;
  manager_comment?: string | null;
  sort_order: number;
};

export type PerformanceReviewSection = {
  id?: string;
  title: string;
  description?: string | null;
  employee_notes?: string | null;
  reviewer_notes?: string | null;
  employee_notes_label?: string | null;
  average_score?: number | string | null;
  rated_count?: number;
  total_count?: number;
  sort_order: number;
  items: PerformanceReviewItem[];
};

export type PerformanceReview = {
  id: string;
  employee_id: string;
  employee_name: string;
  employee_department?: string | null;
  employee_designation?: string | null;
  employee_role?: string | null;
  employee_joining_date?: string | null;
  employee_first_job_date?: string | null;
  company_experience?: string | null;
  reviewer_id: string;
  reviewer_name: string;
  team_id?: string | null;
  team_name?: string | null;
  cycle_id?: string | null;
  cycle_title?: string | null;
  period_label: string;
  status: string;
  review_date?: string | null;
  due_date?: string | null;
  total_experience?: string | null;
  industry_experience?: string | null;
  overall_score?: number | string | null;
  overall_score_label?: string | null;
  completion_percent?: number;
  employee_summary?: string | null;
  manager_summary?: string | null;
  strengths_summary?: string | null;
  improvement_summary?: string | null;
  career_goals?: string | null;
  submitted_at?: string | null;
  acknowledged_at?: string | null;
  stage?: string;
  cycle_kind?: string | null;
  calibration_required?: boolean;
  calibration_notes?: string | null;
  acknowledgement_signature?: string | null;
  sections: PerformanceReviewSection[];
  projects?: ReviewProjectRow[];
  review_period_start?: string | null;
  review_period_end?: string | null;
  is_editable: boolean;
  can_edit_employee_section?: boolean;
  can_edit_manager_section?: boolean;
  can_acknowledge: boolean;
  can_submit_self?: boolean;
  can_submit_manager?: boolean;
  can_calibrate?: boolean;
  is_published?: boolean;
  published_at?: string | null;
  can_publish?: boolean;
  can_delete?: boolean;
  updated_at?: string | null;
};

export type PerformanceReviewTeamMember = {
  user_id: string;
  name: string;
  email: string;
  team_id: string;
  team_name: string;
  review_count: number;
};

export type PerformanceReviewCycle = {
  id: string;
  title: string;
  review_year: number;
  kind?: string;
  template_id?: string | null;
  calibration_required?: boolean;
  due_date?: string | null;
  status: string;
};

export type PerformanceReviewTemplate = {
  form_code: string;
  form_title: string;
  form_revision?: string;
  review_cycle_month?: number;
  review_cycle_note?: string;
  rating_scale: RatingScaleItem[];
  kind?: string;
  template_id?: string;
};

export type PerformanceReviewEditorState = {
  period_label: string;
  review_date: string;
  due_date: string;
  total_experience: string;
  industry_experience: string;
  overall_score: string;
  employee_summary: string;
  manager_summary: string;
  strengths_summary: string;
  improvement_summary: string;
  career_goals: string;
  sections: PerformanceReviewSection[];
  projects: ReviewProjectRow[];
};

export type FormStatusCategory =
  | 'not_started'
  | 'in_progress'
  | 'pending_review'
  | 'completed'
  | 'overdue';
