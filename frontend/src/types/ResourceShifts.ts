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
