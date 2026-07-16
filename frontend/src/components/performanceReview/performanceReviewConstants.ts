export type RatingTone = 'success' | 'info' | 'primary' | 'warning' | 'error' | 'neutral';

export type RatingScaleItem = {
  value: number;
  label: string;
  short_label: string;
  guidance: string;
  tone: RatingTone;
};

export const FALLBACK_RATING_SCALE: RatingScaleItem[] = [
  {
    value: 5,
    label: 'Excellent',
    short_label: '5',
    guidance: 'Best for business — you deserve to be followed by everyone.',
    tone: 'success',
  },
  {
    value: 4,
    label: 'Good',
    short_label: '4',
    guidance: 'Good, but always try to achieve the magic number 5.',
    tone: 'info',
  },
  {
    value: 3,
    label: 'Satisfactory',
    short_label: '3',
    guidance: 'This is good, but not the best.',
    tone: 'primary',
  },
  {
    value: 2,
    label: 'Fair',
    short_label: '2',
    guidance: 'Try to focus in this field and try to improve.',
    tone: 'warning',
  },
  {
    value: 1,
    label: 'Poor',
    short_label: '1',
    guidance: 'Sit with supervisor to understand areas to improve.',
    tone: 'error',
  },
  {
    value: 0,
    label: 'N/A',
    short_label: 'N/A',
    guidance: 'Not applicable for this employee or review period.',
    tone: 'neutral',
  },
];

export function ratingLabelForValue(
  value: number | string | null | undefined,
  scale: RatingScaleItem[] = FALLBACK_RATING_SCALE,
): string | null {
  if (value === null || value === undefined || value === '') return null;
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return null;
  return scale.find((row) => row.value === numeric)?.label ?? null;
}

export function statusChipColor(status: string): 'default' | 'primary' | 'success' | 'warning' {
  switch (status) {
    case 'submitted':
      return 'primary';
    case 'acknowledged':
      return 'success';
    case 'draft':
    default:
      return 'warning';
  }
}

export function formatScore(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const numeric = Number(value);
  if (Number.isNaN(numeric) || numeric <= 0) return '—';
  return numeric.toFixed(2);
}
