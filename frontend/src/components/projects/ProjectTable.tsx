import { memo, useMemo } from 'react';
import { Box, IconButton, useTheme } from '@mui/material';
import ArchiveIcon from '@mui/icons-material/Archive';
import RestoreIcon from '@mui/icons-material/Restore';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { useNavigate } from 'react-router-dom';
import type { Customer, Project, Stream, Team, User } from '../../types';
import { prosohmDataGridSx } from '../../theme/componentStyles';
import { ProjectStageChip, ExecutionStatusChip } from '../common/StatusChip';
import { formatDate, formatNumber, userDisplayName } from '../../utils/format';

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
    customerName: customerMap.get(project.customer_id) ?? '—',
    teamName: project.team_id ? (teamMap.get(project.team_id) ?? '—') : 'Unassigned',
    designLeaderName: userMap.get(project.design_leader_id) ?? '—',
    designerName: project.designer_id
      ? (userMap.get(project.designer_id) ?? '—')
      : '—',
    surfacerName: project.surfacer_id
      ? (userMap.get(project.surfacer_id) ?? '—')
      : '—',
    streamName: streamMap.get(project.stream_id) ?? '—',
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
  onArchive,
  onRestore,
}: ProjectTableProps) {
  const navigate = useNavigate();
  const theme = useTheme();
  const gridSx = useMemo(() => prosohmDataGridSx(theme), [theme]);

  const columns = useMemo(() => {
    if (!onArchive && !onRestore) return PROJECT_TABLE_COLUMNS;

    const actionColumn: GridColDef<ProjectTableRow> = {
      field: 'actions',
      headerName: 'Actions',
      width: onArchive && onRestore ? 110 : 90,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          {onRestore ? (
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
          ) : null}
          {onArchive ? (
            <IconButton
              size="small"
              aria-label="Archive project"
              onClick={(event) => {
                event.stopPropagation();
                onArchive(String(params.id));
              }}
            >
              <ArchiveIcon fontSize="small" />
            </IconButton>
          ) : null}
        </Box>
      ),
    };
    return [...PROJECT_TABLE_COLUMNS, actionColumn];
  }, [onArchive, onRestore]);

  const rows = useMemo(
    () => buildProjectTableRows(projects, customers, users, streams, teams),
    [projects, customers, users, streams, teams],
  );

  const handleRowClick = useMemo(
    () => (params: { id: string | number }) => navigate(`/projects/${params.id}`),
    [navigate],
  );

  // MIT DataGrid caps pageSize at 100; use footer pagination when the list is larger.
  const needsPagination = rows.length > 100;

  return (
    <Box sx={{ width: '100%' }}>
      <DataGrid
        rows={rows}
        columns={columns}
        autoHeight
        hideFooter={!needsPagination}
        disableRowSelectionOnClick
        paginationModel={{ pageSize: 100, page: 0 }}
        pageSizeOptions={[25, 50, 100]}
        onRowClick={handleRowClick}
        sx={gridSx}
      />
    </Box>
  );
}

export const ProjectTable = memo(ProjectTableComponent);
