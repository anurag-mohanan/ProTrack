import { memo, useMemo } from 'react';
import { Box } from '@mui/material';
import RestoreIcon from '@mui/icons-material/Restore';
import { IconButton, Tooltip } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import type { Customer, Project, Stream, Team, User } from '../../types';
import { ProsohmDataGrid, HealthBadge } from '../ui/design-system';
import { ProjectRowActions } from './ProjectRowActions';
import { formatCellValue, formatDate, userDisplayName } from '../../utils/format';
import { formatProjectStageDisplay } from '../../utils/projectCommandCenter';

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
  onRowOpen?: (row: ProjectTableRow) => void;
  onEdit?: (row: ProjectTableRow) => void;
  onArchive?: (projectId: string) => void;
  onDuplicate?: (projectId: string) => void;
  onExport?: (row: ProjectTableRow) => void;
  onDelete?: (projectId: string) => void;
  onRestore?: (projectId: string) => void;
  canDelete?: boolean;
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

const displayOrDash = (value: unknown) => formatCellValue(value) || '—';

function buildColumns(
  handlers: Pick<
    ProjectTableProps,
    'onEdit' | 'onArchive' | 'onDuplicate' | 'onExport' | 'onDelete' | 'onRestore' | 'canDelete'
  >,
): GridColDef<ProjectTableRow>[] {
  const baseColumns: GridColDef<ProjectTableRow>[] = [
    { field: 'tool_number', headerName: 'Tool Number', flex: 0.85, minWidth: 110 },
    {
      field: 'part_description',
      headerName: 'Part Description',
      flex: 1.35,
      minWidth: 160,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'customerName',
      headerName: 'Customer',
      flex: 0.95,
      minWidth: 120,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'teamName',
      headerName: 'Team',
      flex: 0.85,
      minWidth: 100,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'designLeaderName',
      headerName: 'Design Leader',
      flex: 0.95,
      minWidth: 120,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'designerName',
      headerName: 'Designer',
      flex: 0.85,
      minWidth: 100,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'surfacerName',
      headerName: 'Surfacer',
      flex: 0.85,
      minWidth: 100,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'current_milestone',
      headerName: 'Current Milestone',
      flex: 1,
      minWidth: 130,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'project_stage',
      headerName: 'Project Stage',
      width: 120,
      valueGetter: (_value, row) => formatProjectStageDisplay(row),
    },
    {
      field: 'due_date',
      headerName: 'Due Date',
      width: 105,
      valueFormatter: (value) => formatDate(String(value)) || '—',
    },
    {
      field: 'health',
      headerName: 'Health',
      width: 100,
      renderCell: (params) => <HealthBadge health={params.value} />,
    },
  ];

  const { onEdit, onArchive, onDuplicate, onExport, onDelete, onRestore, canDelete } = handlers;
  if (!onEdit && !onArchive && !onRestore) return baseColumns;

  const actionColumn: GridColDef<ProjectTableRow> = {
    field: 'actions',
    headerName: '',
    width: 96,
    sortable: false,
    filterable: false,
    renderCell: (params) => (
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
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
        ) : onEdit ? (
          <ProjectRowActions
            onEdit={() => onEdit(params.row)}
            onArchive={onArchive ? () => onArchive(String(params.id)) : undefined}
            onDuplicate={onDuplicate ? () => onDuplicate(String(params.id)) : undefined}
            onExport={onExport ? () => onExport(params.row) : undefined}
            onDelete={onDelete ? () => onDelete(String(params.id)) : undefined}
            showDelete={Boolean(canDelete && params.row.is_archived)}
          />
        ) : null}
      </Box>
    ),
  };

  return [...baseColumns, actionColumn];
}

const TABLE_HEIGHT = 520;
const PAGE_SIZE = 25;

function ProjectTableComponent({
  projects,
  customers,
  users,
  streams,
  teams,
  onRowOpen,
  onEdit,
  onArchive,
  onDuplicate,
  onExport,
  onDelete,
  onRestore,
  canDelete,
}: ProjectTableProps) {
  const rows = useMemo(
    () => buildProjectTableRows(projects, customers, users, streams, teams),
    [projects, customers, users, streams, teams],
  );

  const rowMap = useMemo(() => new Map(rows.map((row) => [row.id, row])), [rows]);

  const columns = useMemo(
    () =>
      buildColumns({
        onEdit,
        onArchive,
        onDuplicate,
        onExport,
        onDelete,
        onRestore,
        canDelete,
      }),
    [canDelete, onArchive, onDelete, onDuplicate, onEdit, onExport, onRestore],
  );

  return (
    <ProsohmDataGrid
      rows={rows}
      columns={columns}
      autoHeight={rows.length <= PAGE_SIZE}
      sx={rows.length > PAGE_SIZE ? { height: TABLE_HEIGHT } : undefined}
      paginationModel={{ pageSize: PAGE_SIZE, page: 0 }}
      pageSizeOptions={[25, 50, 100]}
      onRowOpen={(rowId) => {
        const row = rowMap.get(rowId);
        if (row) onRowOpen?.(row);
      }}
    />
  );
}

export const ProjectTable = memo(ProjectTableComponent);
