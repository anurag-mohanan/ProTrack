import { Chip, type ChipProps } from '@mui/material';
import type {
  ExecutionStatus,
  MilestoneStatus,
  ProjectHealth,
  ProjectStage,
  TimesheetStatus,
} from '../../../types';
import {
  EXECUTION_STATUS_LABELS,
  PROJECT_STAGE_LABELS,
} from '../../../types/common';
import { formatStatus } from '../../../utils/format';

type BadgeVariant = 'filled' | 'outlined';

const executionColors: Record<ExecutionStatus, ChipProps['color']> = {
  currently_being_worked_on: 'info',
  on_hold: 'warning',
  cancelled: 'default',
  completed: 'success',
};

const stageColors: Record<ProjectStage, ChipProps['color']> = {
  preliminary: 'default',
  intermediate: 'info',
  final: 'secondary',
};

const healthColors: Record<ProjectHealth, ChipProps['color']> = {
  green: 'success',
  yellow: 'warning',
  red: 'error',
};

const lifecycleColors = {
  archived: 'default' as const,
  deleted: 'error' as const,
};

function BadgeShell({
  label,
  color = 'default',
  variant = 'filled',
}: {
  label: string;
  color?: ChipProps['color'];
  variant?: BadgeVariant;
}) {
  return (
    <Chip
      size="small"
      label={label}
      color={color}
      variant={variant === 'outlined' ? 'outlined' : 'filled'}
      sx={{ fontWeight: 600, letterSpacing: '0.01em' }}
    />
  );
}

export function ExecutionStatusBadge({
  status,
  variant = 'filled',
}: {
  status: ExecutionStatus;
  variant?: BadgeVariant;
}) {
  return (
    <BadgeShell
      label={EXECUTION_STATUS_LABELS[status]}
      color={executionColors[status]}
      variant={variant}
    />
  );
}

export function ProjectStageBadge({
  stage,
  variant = 'outlined',
}: {
  stage: ProjectStage;
  variant?: BadgeVariant;
}) {
  return (
    <BadgeShell
      label={PROJECT_STAGE_LABELS[stage]}
      color={stageColors[stage]}
      variant={variant}
    />
  );
}

export function HealthBadge({
  health,
  variant = 'filled',
}: {
  health: ProjectHealth;
  variant?: BadgeVariant;
}) {
  const labels: Record<ProjectHealth, string> = {
    green: 'Green',
    yellow: 'Yellow',
    red: 'Red',
  };
  return (
    <BadgeShell label={labels[health]} color={healthColors[health]} variant={variant} />
  );
}

export function MilestoneStatusBadge({ status }: { status: MilestoneStatus }) {
  return (
    <Chip
      size="small"
      label={formatStatus(status)}
      variant="outlined"
      sx={{ textTransform: 'capitalize', fontWeight: 600 }}
    />
  );
}

export function LifecycleBadge({
  kind,
}: {
  kind: keyof typeof lifecycleColors;
}) {
  return (
    <BadgeShell
      label={kind.charAt(0).toUpperCase() + kind.slice(1)}
      color={lifecycleColors[kind]}
      variant="outlined"
    />
  );
}

export function TimesheetStatusBadge({ status }: { status: TimesheetStatus }) {
  const colors: Record<TimesheetStatus, ChipProps['color']> = {
    draft: 'default',
    submitted: 'info',
    approved: 'success',
    rejected: 'error',
  };
  const labels: Record<TimesheetStatus, string> = {
    draft: 'Draft',
    submitted: 'Submitted',
    approved: 'Approved',
    rejected: 'Rejected',
  };
  return <BadgeShell label={labels[status]} color={colors[status]} />;
}
