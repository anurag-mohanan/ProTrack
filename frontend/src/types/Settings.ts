export interface CompanySettings {
  id: string;
  company_name: string;
  logo_url?: string | null;
  address?: string | null;
  phone?: string | null;
  website?: string | null;
  gst_number?: string | null;
  currency: string;
  timezone: string;
  financial_year_start_month: number;
  default_working_hours_per_day: number;
  default_working_days: string;
  created_at?: string;
  updated_at?: string;
}

export interface Holiday {
  id: string;
  name: string;
  holiday_date: string;
  region?: string | null;
  is_working_day: boolean;
  is_recurring: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Department {
  id: string;
  name: string;
  code?: string | null;
  description?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Skill {
  id: string;
  name: string;
  category?: string | null;
  is_active: boolean;
}

export interface EngineeringDiscipline {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
}

export interface FilePathSettings {
  id: string;
  project_root_folder?: string | null;
  customer_folder_template?: string | null;
  drawing_folder_template?: string | null;
  design_folder_template?: string | null;
  backup_folder?: string | null;
}

export interface ContactType {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
}

export interface NotificationSettings {
  id: string;
  projects_due_enabled: boolean;
  overdue_enabled: boolean;
  pending_approvals_enabled: boolean;
  new_assignments_enabled: boolean;
  imports_completed_enabled: boolean;
}

export type ProjectPriority = 'critical' | 'high' | 'medium' | 'low';

export type EmploymentType = 'full_time' | 'part_time' | 'contract' | 'intern';

export type SkillLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert';

export type DueDateCalculationMode =
  | 'from_start'
  | 'from_previous_milestone'
  | 'business_days';
