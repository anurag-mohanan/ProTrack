import type { MilestoneStatus } from '../../../types';
import { designTokens } from '../../../theme/designTokens';

export const STATUS_OPTIONS: MilestoneStatus[] = [
  'not_started',
  'in_progress',
  'waiting',
  'on_hold',
  'completed',
  'cancelled',
];

export const STATUS_EMOJI: Record<MilestoneStatus, string> = {
  not_started: '⚪',
  in_progress: '🟢',
  waiting: '🟠',
  on_hold: '🔴',
  completed: '✔',
  cancelled: '⚪',
  not_applicable: '⚪',
};

export const STATUS_COLORS: Record<MilestoneStatus, string> = {
  not_started: designTokens.semantic.neutral,
  in_progress: designTokens.semantic.success,
  waiting: designTokens.semantic.warning,
  on_hold: designTokens.semantic.danger,
  completed: designTokens.semantic.success,
  cancelled: designTokens.semantic.neutral,
  not_applicable: designTokens.semantic.neutral,
};

export const PROGRESS_STEPS = [0, 25, 50, 75, 100];
export const ROW_CELL_SX = { py: 0.65, px: 1, fontSize: '0.8rem' };
