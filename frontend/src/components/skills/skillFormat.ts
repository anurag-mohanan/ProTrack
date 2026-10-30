import type { SkLevel, SkMatrixCell, SkState } from '../../types/Skills';
import { formatDate } from '../../utils/format';

export const STATE_LABELS: Record<SkState, string> = {
  no_record: 'No record',
  claimed: 'Self-declared / unverified',
  verified: 'Verified',
  reassessment: 'Needs reassessment',
  rejected: 'Not confirmed',
  archived: 'Archived',
};

export const STATE_COLOR: Record<SkState, 'default' | 'success' | 'warning' | 'info' | 'error'> = {
  no_record: 'default',
  claimed: 'info',
  verified: 'success',
  reassessment: 'warning',
  rejected: 'default',
  archived: 'default',
};

export function levelText(levels: SkLevel[], level: number | null | undefined): string {
  if (level === null || level === undefined) return '—';
  const name = levels.find((l) => l.level === level)?.name;
  return name ? `L${level} ${name}` : `L${level}`;
}

const VERIFIED_SHADES = ['#e8f5e9', '#c8e6c9', '#81c784', '#43a047', '#1b5e20'];

/** Heat colour: verified levels in green shades; claims and reassessments are outlined, never filled as coverage. */
export function cellStyle(cell: SkMatrixCell) {
  if (cell.state === 'verified' && cell.verified_level) {
    const shade = VERIFIED_SHADES[cell.verified_level - 1];
    return { bgcolor: shade, color: cell.verified_level >= 4 ? '#fff' : 'text.primary', border: '1px solid transparent' };
  }
  if (cell.state === 'reassessment') return { bgcolor: '#fff3e0', color: 'warning.dark', border: '1px solid #ffb74d' };
  if (cell.state === 'claimed') return { bgcolor: 'transparent', color: 'info.dark', border: '1px dashed #64b5f6' };
  if (cell.state === 'rejected') return { bgcolor: '#f5f5f5', color: 'text.disabled', border: '1px solid #e0e0e0' };
  return { bgcolor: 'transparent', color: 'text.disabled', border: '1px dashed #e0e0e0' };
}

export function cellText(cell: SkMatrixCell): string {
  if (cell.state === 'verified' || cell.state === 'reassessment') {
    return `${cell.verified_level ?? '?'}${cell.claim_pending ? '*' : ''}`;
  }
  if (cell.state === 'claimed') return cell.declared_level ? `c${cell.declared_level}` : 'c';
  if (cell.state === 'rejected') return '×';
  return '·';
}

export function cellTooltip(cell: SkMatrixCell, levels: SkLevel[]): string {
  const parts = [STATE_LABELS[cell.state]];
  if (cell.verified_level) parts.push(`Verified ${levelText(levels, cell.verified_level)}`);
  if (cell.declared_level && cell.declared_level !== cell.verified_level) parts.push(`Claims ${levelText(levels, cell.declared_level)}`);
  if (cell.last_verified_at) parts.push(`Last verified ${formatDate(cell.last_verified_at)}`);
  if (cell.state === 'no_record') parts.push('Unknown — not level 0');
  return parts.join(' · ');
}
