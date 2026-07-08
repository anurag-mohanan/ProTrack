import { formatDate, formatNumber } from './format';
import { EXECUTION_STATUS_LABELS, PROJECT_STAGE_LABELS } from '../types/common';
import type { ColumnAutoFitProfile } from './dataGridAutoFit';

const EXECUTION_BADGE_LABELS = ['Planning', 'Design', 'Delayed', 'Cancelled', 'Completed'];

const STAGE_BADGE_LABELS = [
  ...Object.values(PROJECT_STAGE_LABELS),
  EXECUTION_STATUS_LABELS.completed,
];

const HEALTH_BADGE_LABELS = ['Healthy', 'At Risk', 'Delayed'];

export interface ProjectTableAutoFitRow {
  tool_number?: string | null;
  customerName?: string | null;
  actual_hours?: number | null;
  quoted_hours?: number | null;
  designerName?: string | null;
  surfacerName?: string | null;
  due_date?: string | null;
}

export function projectTableAutoFitProfiles(options: {
  hasActions: boolean;
  restoreOnly: boolean;
}): ColumnAutoFitProfile[] {
  const profiles: ColumnAutoFitProfile[] = [
    {
      field: 'tool_number',
      headerName: 'Tool Number',
      kind: 'content',
      minWidth: 72,
      maxWidth: 128,
      getValue: (row) => String((row as ProjectTableAutoFitRow).tool_number ?? ''),
    },
    {
      field: 'customerName',
      headerName: 'Customer',
      kind: 'flex',
      flex: 1.25,
      minWidth: 120,
      extraPadding: 28,
      getValue: (row) => String((row as ProjectTableAutoFitRow).customerName ?? ''),
    },
    {
      field: 'hours_comparison',
      headerName: 'Hours',
      kind: 'hours',
      getValue: (row) => {
        const project = row as ProjectTableAutoFitRow;
        return `${formatNumber(project.actual_hours, 0)} / ${formatNumber(project.quoted_hours, 0)}`;
      },
    },
    {
      field: 'project_stage',
      headerName: 'Current Stage',
      kind: 'badge',
      badgeLabels: STAGE_BADGE_LABELS,
      minWidth: 88,
      maxWidth: 132,
    },
    {
      field: 'execution_status',
      headerName: 'Project Status',
      kind: 'badge',
      badgeLabels: EXECUTION_BADGE_LABELS,
      minWidth: 88,
      maxWidth: 120,
    },
    {
      field: 'health',
      headerName: 'Health',
      kind: 'badge',
      badgeLabels: HEALTH_BADGE_LABELS,
      minWidth: 72,
      maxWidth: 96,
    },
    {
      field: 'designerName',
      headerName: 'Designer',
      kind: 'flex',
      flex: 0.95,
      minWidth: 88,
      getValue: (row) => String((row as ProjectTableAutoFitRow).designerName ?? ''),
    },
    {
      field: 'surfacerName',
      headerName: 'Surfacer',
      kind: 'flex',
      flex: 0.95,
      minWidth: 88,
      getValue: (row) => String((row as ProjectTableAutoFitRow).surfacerName ?? ''),
    },
    {
      field: 'due_date',
      headerName: 'Due Date',
      kind: 'date',
      getValue: (row) => formatDate(String((row as ProjectTableAutoFitRow).due_date)) || '—',
    },
    {
      field: 'progress_percent',
      headerName: 'Progress',
      kind: 'progress',
    },
  ];

  if (options.hasActions) {
    profiles.push({
      field: 'actions',
      headerName: '',
      kind: 'actions',
      minWidth: options.restoreOnly ? 56 : 72,
      maxWidth: options.restoreOnly ? 64 : 96,
    });
  }

  return profiles;
}
