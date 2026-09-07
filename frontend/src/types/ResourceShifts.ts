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
  effective_from: string;
  effective_to: string | null;
  is_active: boolean;
  notes: string | null;
  user_name: string | null;
  shift_code: string | null;
  shift_name: string | null;
}

export interface ShiftAssignmentPayload {
  user_id: string;
  shift_id: string;
  assignment_type: ShiftAssignmentType;
  rotation_pattern?: ShiftRotationPattern | null;
  rotation_weekdays?: number[];
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
