import { Chip, type ChipProps } from '@mui/material';
import type { MilestoneStatus, ProjectHealth, ProjectStatus, TimesheetStatus } from '../../types';
import { formatStatus } from '../../utils/format';

const projectStatusLabels: Record<ProjectStatus, string> = {
  not_started: 'Not Started',
  in_progress: 'In Progress',
  waiting_for_customer: 'On Hold',
  completed: 'Completed',
};

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

const healthLabels: Record<ProjectHealth, string> = {
  green: 'Green',
  yellow: 'Yellow',
  red: 'Red',
};

export function StatusChip({ status }: { status: ProjectStatus }) {
  return (
    <Chip
      size="small"
      label={projectStatusLabels[status]}
      color={projectStatusColors[status]}
    />
  );
}

export function HealthChip({ health }: { health: ProjectHealth }) {
  return (
    <Chip
      size="small"
      label={healthLabels[health]}
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

const timesheetStatusColors: Record<TimesheetStatus, ChipProps['color']> = {
  draft: 'default',
  submitted: 'info',
  approved: 'success',
  rejected: 'error',
};

const timesheetStatusLabels: Record<TimesheetStatus, string> = {
  draft: 'Draft',
  submitted: 'Submitted',
  approved: 'Approved',
  rejected: 'Rejected',
};

export function TimesheetStatusChip({ status }: { status: TimesheetStatus }) {
  return (
    <Chip
      size="small"
      label={timesheetStatusLabels[status]}
      color={timesheetStatusColors[status]}
    />
  );
}
