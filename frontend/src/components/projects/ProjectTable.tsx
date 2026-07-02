import { memo, useMemo } from 'react';
import { Box, Chip, IconButton, Tooltip } from '@mui/material';
import RestoreIcon from '@mui/icons-material/Restore';
import type { GridColDef } from '@mui/x-data-grid';
import type { Customer, Project, Stream, Team, User } from '../../types';
import { PriorityBadge, ProsohmDataGrid, TableRowActions, HealthBadge } from '../ui/design-system';
import { formatCellValue, formatDate, formatNumber, userDisplayName } from '../../utils/format';
import {
  formatExecutionStatusShort,
  formatProjectStageDisplay,
} from '../../utils/projectCommandCenter';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';

export interface ProjectTableRow extends Project {
  customerName: string;
  teamName: string;
  designLeaderName: string;
  designerName: string;
  surfacerName: string;
  streamName: string;
}

interface ProjectTableProps {
  projects: Project[];
  customers: Customer[];
  users: User[];
  streams: Stream[];
  teams: Team[];
  compact?: boolean;
  onRowOpen?: (row: ProjectTableRow) => void;
  onEdit?: (row: ProjectTableRow) => void;
  onArchive?: (projectId: string) => void;
  onRestore?: (projectId: string) => void;
}

function buildNameMap<T extends { id: string }>(
  items: T[],
  getLabel: (item: T) => string,
): Map<string, string> {
  const map = new Map<string, string>();
  items.forEach((item) => map.set(item.id, getLabel(item)));
  return map;
}

export function buildProjectTableRows(
  projects: Project[],
  customers: Customer[],
  users: User[],
  streams: Stream[],
  teams: Team[],
): ProjectTableRow[] {
  const customerMap = buildNameMap(customers, (item) => item.name);
  const userMap = buildNameMap(users, (item) => userDisplayName(item));
  const streamMap = buildNameMap(streams, (item) => item.name);
  const teamMap = buildNameMap(teams, (item) => item.name);

  return projects.map((project) => ({
    ...project,
    customerName: formatCellValue(customerMap.get(project.customer_id)),
    teamName: project.team_id ? formatCellValue(teamMap.get(project.team_id)) : '',
    designLeaderName: formatCellValue(userMap.get(project.design_leader_id)),
    designerName: project.designer_id ? formatCellValue(userMap.get(project.designer_id)) : '',
    surfacerName: project.surfacer_id ? formatCellValue(userMap.get(project.surfacer_id)) : '',
    streamName: formatCellValue(streamMap.get(project.stream_id)),
  }));
}

function buildColumns(
  onEdit?: (row: ProjectTableRow) => void,
  onArchive?: (projectId: string) => void,
  onRestore?: (projectId: string) => void,
): GridColDef<ProjectTableRow>[] {
  const baseColumns: GridColDef<ProjectTableRow>[] = [
    { field: 'tool_number', headerName: 'Tool Number', flex: 0.9, minWidth: 120 },
    {
      field: 'part_description',
      headerName: 'Part Description',
      flex: 1.4,
      minWidth: 180,
      valueFormatter: (value) => formatCellValue(String(value)) || '—',
    },
    {
      field: 'customerName',
      headerName: 'Customer',
      flex: 1,
      minWidth: 130,
      valueFormatter: (value) => formatCellValue(String(value)) || '—',
    },
    {
      field: 'teamName',
      headerName: 'Team',
      flex: 0.9,
      minWidth: 110,
      valueFormatter: (value) => formatCellValue(String(value)) || '—',
    },
    {
      field: 'designLeaderName',
      headerName: 'Design Leader',
      flex: 1,
      minWidth: 130,
      valueFormatter: (value) => formatCellValue(String(value)) || '—',
    },
    {
      field: 'designerName',
      headerName: 'Designer',
      flex: 0.9,
      minWidth: 110,
      valueFormatter: (value) => formatCellValue(String(value)) || '—',
    },
    {
      field: 'current_milestone',
      headerName: 'Current Milestone',
      flex: 1,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(value ? String(value) : null) || '—',
    },
    {
      field: 'project_stage',
      headerName: 'Project Stage',
      width: 130,
      valueGetter: (_value, row) => formatProjectStageDisplay(row),
    },
    {
      field: 'execution_status',
      headerName: 'Execution Status',
      width: 130,
      renderCell: (params) => (
        <Chip
          size="small"
          label={formatExecutionStatusShort(params.value)}
          color={
            params.value === 'currently_being_worked_on'
              ? 'info'
              : params.value === 'on_hold'
                ? 'warning'
                : params.value === 'completed'
                  ? 'success'
                  : 'default'
          }
          sx={{ fontWeight: 600 }}
        />
      ),
    },
    {
      field: 'priority',
      headerName: 'Priority',
      width: 100,
      renderCell: (params) => <PriorityBadge priority={params.value as string | null} />,
    },
    {
      field: 'due_date',
      headerName: 'Due Date',
      width: 110,
      valueFormatter: (value) => formatDate(String(value)) || '—',
    },
    {
      field: 'health',
      headerName: 'Project Health',
      width: 120,
      renderCell: (params) => <HealthBadge health={params.value} />,
    },
    {
      field: 'quoted_hours',
      headerName: 'Quoted Hours',
      width: 115,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value) => formatNumber(Number(value)),
    },
    {
      field: 'actual_hours',
      headerName: 'Actual Hours',
      width: 115,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value) => formatNumber(Number(value)),
    },
  ];

  if (!onEdit && !onArchive && !onRestore) return baseColumns;

  const actionColumn: GridColDef<ProjectTableRow> = {
    field: 'actions',
    headerName: '',
    width: onArchive && onRestore ? DATA_GRID_ACTIONS_COLUMN_WIDTH + 40 : DATA_GRID_ACTIONS_COLUMN_WIDTH,
    sortable: false,
    filterable: false,
    renderCell: (params) => (
      <Box sx={{ display: 'flex', gap: 0.25, alignItems: 'center' }}>
        {onEdit ? (
          <TableRowActions
            onEdit={() => onEdit(params.row)}
            onArchive={
              onArchive && !onRestore ? () => onArchive(String(params.id)) : undefined
            }
          />
        ) : null}
        {onRestore ? (
          <Tooltip title="Restore">
            <IconButton
              size="small"
              aria-label="Restore project"
              onClick={(event) => {
                event.stopPropagation();
                onRestore(String(params.id));
              }}
            >
              <RestoreIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : null}
      </Box>
    ),
  };

  return [...baseColumns, actionColumn];
}

function ProjectTableComponent({
  projects,
  customers,
  users,
  streams,
  teams,
  compact = false,
  onRowOpen,
  onEdit,
  onArchive,
  onRestore,
}: ProjectTableProps) {
  const rows = useMemo(
    () => buildProjectTableRows(projects, customers, users, streams, teams),
    [projects, customers, users, streams, teams],
  );

  const rowMap = useMemo(() => new Map(rows.map((row) => [row.id, row])), [rows]);

  const columns = useMemo(
    () => buildColumns(onEdit, onArchive, onRestore),
    [onArchive, onEdit, onRestore],
  );

  const pageSize = compact ? 25 : 100;

  return (
    <ProsohmDataGrid
      rows={rows}
      columns={columns}
      autoHeight={rows.length <= pageSize}
      hideFooter={rows.length <= pageSize}
      paginationModel={{ pageSize, page: 0 }}
      pageSizeOptions={[25, 50, 100]}
      onRowOpen={(rowId) => {
        const row = rowMap.get(rowId);
        if (row) onRowOpen?.(row);
      }}
    />
  );
}

export const ProjectTable = memo(ProjectTableComponent);
