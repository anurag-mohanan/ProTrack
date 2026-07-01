import type {
  ExecutionStatus,
  MilestoneStatus,
  ProjectHealth,
  ProjectStage,
  TimesheetStatus,
} from '../../types';
import {
  ExecutionStatusBadge,
  HealthBadge,
  MilestoneStatusBadge,
  ProjectStageBadge,
  TimesheetStatusBadge,
} from '../ui/design-system';

export function ExecutionStatusChip({ status }: { status: ExecutionStatus }) {
  return <ExecutionStatusBadge status={status} />;
}

export function StatusChip({ status }: { status: ExecutionStatus }) {
  return <ExecutionStatusChip status={status} />;
}

export function ProjectStageChip({ stage }: { stage: ProjectStage }) {
  return <ProjectStageBadge stage={stage} />;
}

export function HealthChip({ health }: { health: ProjectHealth }) {
  return <HealthBadge health={health} />;
}

export function MilestoneStatusChip({ status }: { status: MilestoneStatus }) {
  return <MilestoneStatusBadge status={status} />;
}

export function TimesheetStatusChip({ status }: { status: TimesheetStatus }) {
  return <TimesheetStatusBadge status={status} />;
}
