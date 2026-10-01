import type { AllocationCheckResult, AllocationWindowInput } from '../../../types/itAllocation';

export type OverrideState = { enabled: boolean; reason: string };

export const NO_OVERRIDE: OverrideState = { enabled: false, reason: '' };

/** Save is allowed when the engine says available, or an overridable conflict has a reason. */
export function checkAllowsSave(result: AllocationCheckResult | undefined, override?: OverrideState): boolean {
  if (!result) return false;
  if (result.available) return true;
  return Boolean(result.overridable && override?.enabled && override.reason.trim());
}

export function overridePayload(result: AllocationCheckResult | undefined, override: OverrideState) {
  const forcing = Boolean(result && !result.available && override.enabled);
  return { force_override: forcing, override_reason: forcing ? override.reason.trim() : null };
}

export type WindowMode = 'shift' | 'custom' | 'all';

export interface AllocationWindowState {
  mode: WindowMode;
  shiftId: string;
  startTime: string;
  endTime: string;
  startDate: string;
  endDate: string;
}

export function emptyWindow(mode: WindowMode = 'shift'): AllocationWindowState {
  return { mode, shiftId: '', startTime: '', endTime: '', startDate: '', endDate: '' };
}

/** True when the window is complete enough to check / save. */
export function windowReady(state: AllocationWindowState): boolean {
  if (state.mode === 'shift') return Boolean(state.shiftId);
  if (state.mode === 'custom') return Boolean(state.startTime && state.endTime);
  return true;
}

export function windowToInput(state: AllocationWindowState): AllocationWindowInput {
  return {
    shift_id: state.mode === 'shift' ? state.shiftId || null : null,
    start_time: state.mode === 'custom' ? state.startTime || null : null,
    end_time: state.mode === 'custom' ? state.endTime || null : null,
    start_date: state.startDate || null,
    end_date: state.endDate || null,
  };
}

export const WINDOW_MODE_OPTIONS: { value: WindowMode; label: string }[] = [
  { value: 'shift', label: 'Shift' },
  { value: 'custom', label: 'Custom time window' },
  { value: 'all', label: 'All hours (exclusive)' },
];
