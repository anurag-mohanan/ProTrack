import { Chip } from '@mui/material';

const colorMap: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info'> = {
  draft: 'default',
  active: 'primary',
  on_hold: 'warning',
  completed: 'success',
  cancelled: 'error',
  pending: 'default',
  in_progress: 'info',
  delayed: 'error',
  submitted: 'info',
  approved: 'success',
  rejected: 'error',
};

interface StatusChipProps {
  value: string;
}

export default function StatusChip({ value }: StatusChipProps) {
  const label = value.replace(/_/g, ' ');
  return (
    <Chip
      size="small"
      label={label}
      color={colorMap[value] ?? 'default'}
      sx={{ textTransform: 'capitalize' }}
    />
  );
}
