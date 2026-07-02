export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export interface ChangePasswordResponse {
  message: string;
  must_change_password: boolean;
}

export interface CurrentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role_id: string;
  role_name: string;
  is_active: boolean;
  must_change_password: boolean;
  password_changed?: boolean;
  last_login?: string | null;
  impersonator_id?: string | null;
  impersonator_name?: string | null;
  working_hours_per_day?: number;
  module_access?: string[];
  special_permissions?: string[];
  resolved_modules?: string[];
  resolved_special_permissions?: string[];
}
