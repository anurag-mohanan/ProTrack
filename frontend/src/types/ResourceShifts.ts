export type ShiftAssignmentType = 'permanent' | 'rotational';

export type ShiftRotationPattern = 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'custom';

export interface Shift {
  id: string;
  code: string;
  name: string;
  start_time: string;
  end_time: string;
  break_minutes: number;
  is_overnight: boolean;
  is_active: boolean;
  notes: string | null;
  display_window?: string;
  display_label?: string;
}

export interface ShiftPayload {
  code: string;
  name: string;
  start_time: string;
  end_time: string;
  break_minutes: number;
  is_overnight: boolean;
  is_active?: boolean;
  notes?: string | null;
}

export interface ShiftAssignment {
  id: string;
  user_id: string;
  shift_id: string;
  assignment_type: ShiftAssignmentType;
  rotation_pattern: ShiftRotationPattern | null;
  /** 0 = Monday … 6 = Sunday. */
  rotation_weekdays: number[];
  rotation_sequence?: string[];
  rotation_segments?: Array<{ shift_id: string | null; days: number }>;
  slot_days?: number | null;
  effective_from: string;
  effective_to: string | null;
  is_active: boolean;
  notes: string | null;
  user_name: string | null;
  shift_code: string | null;
  shift_name: string | null;
  shift_display?: string | null;
}

export interface ShiftAssignmentPayload {
  user_id: string;
  shift_id: string;
  assignment_type: ShiftAssignmentType;
  rotation_pattern?: ShiftRotationPattern | null;
  rotation_weekdays?: number[];
  rotation_sequence?: string[];
  rotation_segments?: Array<{ shift_id: string | null; days: number }>;
  slot_days?: number | null;
  effective_from: string;
  effective_to?: string | null;
  notes?: string | null;
  end_date_existing?: boolean;
}

export interface ShiftAssignmentBulkPayload extends Omit<ShiftAssignmentPayload, 'user_id'> {
  user_ids: string[];
}

export interface ShiftAssignmentConflict {
  user_id: string;
  user_name: string | null;
  reason: string;
}

export interface ShiftAssignmentBulkResult {
  created: ShiftAssignment[];
  conflicts: ShiftAssignmentConflict[];
}

export interface ShiftForUser {
  user_id: string;
  on_date: string;
  shift: Shift | null;
  shift_hours: number | null;
  next_change_date?: string | null;
  next_shift?: Shift | null;
}

export interface ShiftOverview {
  on_date: string;
  total_employees: number;
  assigned: number;
  unassigned: number;
  permanent: number;
  rotational: number;
  by_shift: Array<{
    shift_id: string;
    shift_code: string;
    shift_name: string;
    display_label?: string;
    employee_count: number;
  }>;
}

export interface ShiftBoard {
  on_date: string;
  columns: Array<{
    shift_id: string;
    shift_code: string;
    shift_name: string;
    display_label?: string;
    start_time: string;
    end_time: string;
    employee_count: number;
    employees: Array<{
      user_id: string;
      user_name: string;
      team_name?: string | null;
      computer_name?: string | null;
      next_change_date?: string | null;
      next_shift_code?: string | null;
    }>;
  }>;
  unassigned: Array<{
    user_id: string;
    user_name: string;
    team_name?: string | null;
    computer_name?: string | null;
  }>;
}

export interface ShiftCalendarDay {
  day: string;
  shift_id: string | null;
  shift_code: string | null;
  shift_name: string | null;
  is_overnight: boolean;
  shift_hours: number | null;
}

export interface ShiftCalendarRow {
  user_id: string;
  user_name: string;
  team_name: string | null;
  days: ShiftCalendarDay[];
}

export interface ShiftCalendar {
  start_date: string;
  end_date: string;
  shifts: Shift[];
  rows: ShiftCalendarRow[];
}

export type EmployeeShiftState = 'ASSIGNED' | 'NOT_ASSIGNED' | 'INACTIVE';

export interface EmployeeRosterRow {
  user_id: string;
  name: string;
  email: string;
  employee_code: string | null;
  department: string | null;
  org_department_id: string | null;
  department_id: string | null;
  designation: string | null;
  role_name: string | null;
  manager_name: string | null;
  is_active: boolean;
  shift_state: EmployeeShiftState;
  shift_id: string | null;
  shift_code: string | null;
  shift_name: string | null;
  shift_start: string | null;
  shift_end: string | null;
  shift_display: string | null;
  assignment_id: string | null;
  assignment_type: string | null;
  effective_from: string | null;
  effective_to: string | null;
  shift_history_count: number;
}

export interface EmployeeRoster {
  on_date: string;
  counts: {
    total: number;
    assigned: number;
    not_assigned: number;
    inactive: number;
    by_shift: Record<string, number>;
  };
  rows: EmployeeRosterRow[];
}

export interface EmployeeRosterParams {
  date?: string;
  status?: 'active' | 'inactive' | 'all';
  shift?: string;
  department_id?: string;
  q?: string;
}

export interface ShiftCapacityCounts {
  assigned: number;
  available: number;
  blocked: number;
}

export interface ShiftCapacityLicense {
  license_pool_id: string;
  software_name: string | null;
  entitlement_code: string | null;
  rights: number;
  scheduled: number;
  available: number;
}

export interface ShiftCapacityRow {
  shift_id: string | null;
  shift_code: string;
  shift_display: string;
  window: string;
  employees: number;
  workstations: ShiftCapacityCounts;
  laptops: ShiftCapacityCounts;
  licenses: ShiftCapacityLicense[];
}

export interface ShiftCapacity {
  on_date: string;
  employees_total: number;
  employees_without_shift: number;
  shifts: ShiftCapacityRow[];
}
