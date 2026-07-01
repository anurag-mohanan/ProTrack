import { Chip, type ChipProps } from '@mui/material';
import type {
  ExecutionStatus,
  MilestoneStatus,
  ProjectHealth,
  ProjectStage,
  TimesheetStatus,
} from '../../types';
import {
  EXECUTION_STATUS_LABELS,
  PROJECT_STAGE_LABELS,
} from '../../types/common';
import { formatStatus } from '../../utils/format';

const executionStatusColors: Record<ExecutionStatus, ChipProps['color']> = {
  currently_being_worked_on: 'info',
  on_hold: 'warning',
  cancelled: 'default',
  completed: 'success',
};

const projectStageColors: Record<ProjectStage, ChipProps['color']> = {
  preliminary: 'default',
  intermediate: 'info',
  final: 'secondary',
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

export function ExecutionStatusChip({ status }: { status: ExecutionStatus }) {
  return (
    <Chip
      size="small"
      label={EXECUTION_STATUS_LABELS[status]}
      color={executionStatusColors[status]}
    />
  );
}

/** @deprecated Use ExecutionStatusChip */
export function StatusChip({ status }: { status: ExecutionStatus }) {
  return <ExecutionStatusChip status={status} />;
}

export function ProjectStageChip({ stage }: { stage: ProjectStage }) {
  return (
    <Chip
      size="small"
      label={PROJECT_STAGE_LABELS[stage]}
      color={projectStageColors[stage]}
      variant="outlined"
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
