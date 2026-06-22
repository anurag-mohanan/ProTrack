import { Chip } from '@mui/material';

const colorMap: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info'> = {
  not_started: 'default',
  in_progress: 'info',
  waiting_for_customer: 'warning',
  completed: 'success',
  not_applicable: 'default',
  draft: 'default',
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
