import { Chip } from '@mui/material';
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
import { designTokens } from '../../../theme/designTokens';
import { formatStatus } from '../../../utils/format';

type BadgeVariant = 'filled' | 'outlined';

const executionStyles: Record<ExecutionStatus, { bg: string; color: string; label: string }> = {
  planning: { bg: designTokens.stage.preliminary.soft, color: designTokens.stage.preliminary.main, label: 'Planning' },
  currently_being_worked_on: { bg: designTokens.semantic.primarySoft, color: designTokens.semantic.primary, label: 'Design' },
  on_hold: { bg: designTokens.semantic.warningSoft, color: designTokens.semantic.warning, label: 'Delayed' },
  cancelled: { bg: designTokens.semantic.dangerSoft, color: designTokens.semantic.danger, label: 'Cancelled' },
  completed: { bg: designTokens.semantic.successSoft, color: designTokens.semantic.success, label: 'Completed' },
};

const stageStyles: Record<ProjectStage, { bg: string; color: string }> = {
  preliminary: { bg: designTokens.stage.preliminary.soft, color: designTokens.stage.preliminary.main },
  intermediate: { bg: designTokens.stage.intermediate.soft, color: designTokens.stage.intermediate.main },
  final: { bg: designTokens.stage.final.soft, color: designTokens.stage.final.main },
};

const healthStyles: Record<ProjectHealth, { bg: string; color: string; label: string }> = {
  green: { bg: designTokens.health.green.soft, color: designTokens.health.green.main, label: 'Healthy' },
  yellow: { bg: designTokens.health.yellow.soft, color: designTokens.health.yellow.main, label: 'At Risk' },
  red: { bg: designTokens.health.red.soft, color: designTokens.health.red.main, label: 'Delayed' },
};

function BadgeShell({
  label,
  bg,
  color,
  variant = 'filled',
}: {
  label: string;
  bg: string;
  color: string;
  variant?: BadgeVariant;
}) {
  return (
    <Chip
      size="small"
      label={label}
      variant={variant === 'outlined' ? 'outlined' : 'filled'}
      sx={{
        fontWeight: 700,
        letterSpacing: '0.02em',
        fontSize: '0.6875rem',
        bgcolor: variant === 'outlined' ? 'transparent' : bg,
        color,
        borderColor: variant === 'outlined' ? color : 'transparent',
      }}
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
  const style = executionStyles[status];
  return (
    <BadgeShell
      label={style.label || EXECUTION_STATUS_LABELS[status]}
      bg={style.bg}
      color={style.color}
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
  const style = stageStyles[stage];
  return (
    <BadgeShell
      label={PROJECT_STAGE_LABELS[stage]}
      bg={style.bg}
      color={style.color}
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
  const style = healthStyles[health];
  return (
    <BadgeShell label={style.label} bg={style.bg} color={style.color} variant={variant} />
  );
}

const lifecycleStyles = {
  archived: { bg: designTokens.semantic.neutralSoft, color: designTokens.semantic.neutral },
  deleted: { bg: designTokens.semantic.dangerSoft, color: designTokens.semantic.danger },
};

const timesheetStyles: Record<TimesheetStatus, { bg: string; color: string; label: string }> = {
  draft: { bg: designTokens.semantic.neutralSoft, color: designTokens.semantic.neutral, label: 'Draft' },
  submitted: { bg: designTokens.semantic.primarySoft, color: designTokens.semantic.primary, label: 'Submitted' },
  approved: { bg: designTokens.semantic.successSoft, color: designTokens.semantic.success, label: 'Approved' },
  rejected: { bg: designTokens.semantic.dangerSoft, color: designTokens.semantic.danger, label: 'Rejected' },
};

const priorityStyles: Record<ProjectPriority, { bg: string; color: string; label: string }> = {
  critical: { bg: designTokens.semantic.dangerSoft, color: designTokens.semantic.danger, label: 'Critical' },
  high: { bg: designTokens.semantic.warningSoft, color: designTokens.semantic.warning, label: 'High' },
  medium: { bg: designTokens.semantic.primarySoft, color: designTokens.semantic.primary, label: 'Medium' },
  low: { bg: designTokens.semantic.neutralSoft, color: designTokens.semantic.neutral, label: 'Low' },
};

export type ProjectPriority = 'critical' | 'high' | 'medium' | 'low';

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
  kind: keyof typeof lifecycleStyles;
}) {
  const style = lifecycleStyles[kind];
  return (
    <BadgeShell
      label={kind.charAt(0).toUpperCase() + kind.slice(1)}
      bg={style.bg}
      color={style.color}
      variant="outlined"
    />
  );
}

export function TimesheetStatusBadge({ status }: { status: TimesheetStatus }) {
  const style = timesheetStyles[status];
  return <BadgeShell label={style.label} bg={style.bg} color={style.color} />;
}

export function PriorityBadge({
  priority = 'medium',
  variant = 'filled',
}: {
  priority?: ProjectPriority | string | null;
  variant?: BadgeVariant;
}) {
  const key = (priority ?? 'medium') as ProjectPriority;
  const style = priorityStyles[key] ?? priorityStyles.medium;
  return (
    <BadgeShell
      label={style.label}
      bg={style.bg}
      color={style.color}
      variant={variant}
    />
  );
}
