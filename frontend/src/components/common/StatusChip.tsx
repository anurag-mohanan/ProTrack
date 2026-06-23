import { Chip, type ChipProps } from '@mui/material';
import type { MilestoneStatus, ProjectHealth, ProjectStatus } from '../../types';
import { formatStatus } from '../../utils/format';

const projectStatusColors: Record<ProjectStatus, ChipProps['color']> = {
  not_started: 'default',
  in_progress: 'info',
  waiting_for_customer: 'warning',
  completed: 'success',
};

const healthColors: Record<ProjectHealth, ChipProps['color']> = {
  green: 'success',
  yellow: 'warning',
  red: 'error',
};

export function StatusChip({ status }: { status: ProjectStatus }) {
  return (
    <Chip
      size="small"
      label={formatStatus(status)}
      color={projectStatusColors[status]}
      sx={{ textTransform: 'capitalize' }}
    />
  );
}

export function HealthChip({ health }: { health: ProjectHealth }) {
  return (
    <Chip
      size="small"
      label={health.toUpperCase()}
      color={healthColors[health]}
    />
  );
}

export function MilestoneStatusChip({ status }: { status: MilestoneStatus }) {
  return (
    <Chip
      size="small"
      label={formatStatus(status)}
      variant="outlined"
      sx={{ textTransform: 'capitalize' }}
    />
  );
}
