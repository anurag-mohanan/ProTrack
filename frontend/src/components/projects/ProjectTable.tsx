import { memo, useMemo } from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import RestoreIcon from '@mui/icons-material/Restore';
import type { GridColDef } from '@mui/x-data-grid';
import type { Customer, Project, Stream, Team, User } from '../../types';
import { ProjectStageChip, ExecutionStatusChip } from '../common/StatusChip';
import { PriorityBadge, ProsohmDataGrid, TableRowActions } from '../ui/design-system';
import { formatCellValue, formatDate, formatNumber, userDisplayName } from '../../utils/format';
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

const PROJECT_TABLE_COLUMNS: GridColDef<ProjectTableRow>[] = [
  { field: 'tool_number', headerName: 'Tool Number', flex: 1, minWidth: 130 },
  {
    field: 'part_description',
    headerName: 'Part Description',
    flex: 1.5,
    minWidth: 180,
  },
  { field: 'customerName', headerName: 'Customer', flex: 1, minWidth: 140 },
  { field: 'teamName', headerName: 'Team', flex: 1, minWidth: 130 },
  {
    field: 'designLeaderName',
    headerName: 'Design Leader',
    flex: 1,
    minWidth: 140,
  },
  { field: 'designerName', headerName: 'Designer', flex: 1, minWidth: 120 },
  { field: 'surfacerName', headerName: 'Surfacer', flex: 1, minWidth: 120 },
  { field: 'streamName', headerName: 'Stream', flex: 1, minWidth: 120 },
  {
    field: 'priority',
    headerName: 'Priority',
    width: 110,
    renderCell: (params) => <PriorityBadge priority={params.value as string | null} />,
  },
  {
    field: 'due_date',
    headerName: 'Due Date',
    width: 120,
    valueFormatter: (value) => formatDate(String(value)),
  },
  {
    field: 'project_stage',
    headerName: 'Project Stage',
    width: 140,
    renderCell: (params) => <ProjectStageChip stage={params.value} />,
  },
  {
    field: 'execution_status',
    headerName: 'Execution Status',
    width: 190,
    renderCell: (params) => <ExecutionStatusChip status={params.value} />,
  },
  {
    field: 'quoted_hours',
    headerName: 'Quoted Hours',
    width: 130,
    align: 'right',
    headerAlign: 'right',
    valueFormatter: (value) => formatNumber(Number(value)),
  },
];

function ProjectTableComponent({
  projects,
  customers,
  users,
  streams,
  teams,
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

  const columns = useMemo(() => {
    if (!onEdit && !onArchive && !onRestore) return PROJECT_TABLE_COLUMNS;

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
                onArchive && !onRestore
                  ? () => onArchive(String(params.id))
                  : undefined
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
    return [...PROJECT_TABLE_COLUMNS, actionColumn];
  }, [onArchive, onEdit, onRestore]);

  const needsPagination = rows.length > 100;

  return (
    <ProsohmDataGrid
      rows={rows}
      columns={columns}
      autoHeight
      hideFooter={!needsPagination}
      paginationModel={{ pageSize: 100, page: 0 }}
      pageSizeOptions={[25, 50, 100]}
      onRowOpen={(rowId) => {
        const row = rowMap.get(rowId);
        if (row) onRowOpen?.(row);
      }}
    />
  );
}

export const ProjectTable = memo(ProjectTableComponent);
