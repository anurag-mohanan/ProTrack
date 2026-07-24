export interface CompanySettings {
  id: string;
  company_name: string;
  company_short_name?: string | null;
  logo_url?: string | null;
  address?: string | null;
  email?: string | null;
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

export type ThemePresetId =
  | 'prosohm_professional'
  | 'modern_light'
  | 'modern_dark'
  | 'ocean_blue'
  | 'slate_grey'
  | 'emerald'
  | 'high_contrast';

export interface BrandingSettings {
  id: string;
  theme_preset: ThemePresetId;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  success_color: string;
  warning_color: string;
  danger_color: string;
  sidebar_color: string;
  header_color: string;
  button_style: 'rounded' | 'sharp' | 'pill';
  border_radius: number;
  card_style: 'elevated' | 'flat' | 'bordered';
  density: 'default' | 'comfortable' | 'compact';
}

export interface PublicSettings {
  company: {
    company_name: string;
    company_short_name?: string | null;
    logo_url?: string | null;
    website?: string | null;
  };
  branding: BrandingSettings;
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
  email_notifications_enabled: boolean;
}

export interface TimesheetPolicySettings {
  editable_months_back: number;
  soft_lock_enabled: boolean;
  hard_lock_message: string;
  soft_lock_message: string;
}

export interface LegalEntity {
  id: string;
  code: string;
  name: string;
  currency_code: string;
  is_default: boolean;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface EmailSettings {
  id: string;
  enabled: boolean;
  provider_type: string;
  smtp_host?: string | null;
  smtp_port: number;
  smtp_username?: string | null;
  has_password: boolean;
  use_tls: boolean;
  use_ssl: boolean;
  sender_name?: string | null;
  sender_email?: string | null;
  reply_to_email?: string | null;
  company_signature?: string | null;
  connection_status?: string | null;
  connection_checked_at?: string | null;
  connection_message?: string | null;
}

export interface EmailTemplate {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  subject: string;
  body_html: string;
  body_text?: string | null;
  is_enabled: boolean;
  is_system: boolean;
}

export type ProjectPriority = 'critical' | 'high' | 'medium' | 'low';

export type EmploymentType = 'full_time' | 'part_time' | 'contract' | 'intern';

export type SkillLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert';

export type DueDateCalculationMode =
  | 'from_start'
  | 'from_previous_milestone'
  | 'business_days';
