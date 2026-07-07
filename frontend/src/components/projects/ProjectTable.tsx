import { memo, useMemo } from 'react';
import { Box, LinearProgress } from '@mui/material';
import RestoreRoundedIcon from '@mui/icons-material/RestoreRounded';
import { IconButton, Tooltip } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import type { Customer, Project, Stream, Team, User } from '../../types';
import {
  ProsohmDataGrid,
  EntityAvatar,
  ExecutionStatusBadge,
  HealthBadge,
  PriorityBadge,
  ProjectStageBadge,
} from '../ui/design-system';
import { ProjectRowActions } from './ProjectRowActions';
import { designTokens } from '../../theme/designTokens';
import { formatCellValue, formatDate, userDisplayName } from '../../utils/format';
import { formatNumber } from '../../utils/format';

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
    customerName: formatCellValue(
      customerMap.get(project.customer_id) ?? project.customer_name,
    ),
    teamName: project.team_id
      ? formatCellValue(teamMap.get(project.team_id) ?? project.team_name)
      : formatCellValue(project.team_name),
    designLeaderName: project.design_leader_id
      ? formatCellValue(
          userMap.get(project.design_leader_id) ?? project.design_leader_name,
        )
      : formatCellValue(project.design_leader_name),
    designerName: project.designer_id
      ? formatCellValue(userMap.get(project.designer_id) ?? project.designer_name)
      : formatCellValue(project.designer_name),
    surfacerName: project.surfacer_id
      ? formatCellValue(userMap.get(project.surfacer_id) ?? project.surfacer_name)
      : formatCellValue(project.surfacer_name),
    streamName: project.stream_id
      ? formatCellValue(streamMap.get(project.stream_id))
      : '',
  }));
}

const displayOrDash = (value: unknown) => formatCellValue(value) || '—';

function ProgressCell({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <Box sx={{ width: '100%', minWidth: 72 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
        <Box component="span" sx={{ fontSize: '0.75rem', fontWeight: 700 }}>
          {formatNumber(pct, 0)}%
        </Box>
      </Box>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          height: 6,
          borderRadius: designTokens.radius.pill,
          bgcolor: designTokens.semantic.neutralSoft,
          '& .MuiLinearProgress-bar': {
            borderRadius: designTokens.radius.pill,
            bgcolor:
              pct >= 90
                ? designTokens.semantic.success
                : pct >= 50
                  ? designTokens.semantic.primary
                  : designTokens.semantic.warning,
          },
        }}
      />
    </Box>
  );
}

function buildColumns(
  handlers: Pick<
    ProjectTableProps,
    'onEdit' | 'onArchive' | 'onDuplicate' | 'onExport' | 'onDelete' | 'onRestore' | 'canDelete'
  >,
): GridColDef<ProjectTableRow>[] {
  const baseColumns: GridColDef<ProjectTableRow>[] = [
    {
      field: 'tool_number',
      headerName: 'Tool Number',
      width: 128,
      minWidth: 110,
      renderCell: (params) => (
        <Box sx={{ fontWeight: 800, color: designTokens.semantic.primary }}>{params.value}</Box>
      ),
    },
    {
      field: 'part_description',
      headerName: 'Part Description',
      flex: 1.2,
      minWidth: 160,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'customerName',
      headerName: 'Customer',
      flex: 1,
      minWidth: 140,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
          <EntityAvatar label={String(params.value || '?')} size={26} />
          <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {displayOrDash(params.value)}
          </Box>
        </Box>
      ),
    },
    {
      field: 'project_stage',
      headerName: 'Current Stage',
      width: 130,
      renderCell: (params) => {
        const row = params.row;
        if (row.is_archived) return <ProjectStageBadge stage="preliminary" />;
        if (row.execution_status === 'completed') {
          return <ExecutionStatusBadge status="completed" />;
        }
        return <ProjectStageBadge stage={row.project_stage} />;
      },
    },
    {
      field: 'execution_status',
      headerName: 'Project Status',
      width: 140,
      renderCell: (params) => <ExecutionStatusBadge status={params.value} />,
    },
    {
      field: 'health',
      headerName: 'Health',
      width: 108,
      renderCell: (params) => <HealthBadge health={params.value} />,
    },
    {
      field: 'designerName',
      headerName: 'Assigned Designer',
      flex: 0.9,
      minWidth: 120,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'due_date',
      headerName: 'Due Date',
      width: 108,
      valueFormatter: (value) => formatDate(String(value)) || '—',
    },
    {
      field: 'progress_percent',
      headerName: 'Progress',
      width: 120,
      renderCell: (params) => <ProgressCell value={Number(params.value)} />,
    },
    {
      field: 'priority',
      headerName: 'Priority',
      width: 100,
      renderCell: (params) => <PriorityBadge priority={params.value ?? 'medium'} />,
    },
  ];

  const { onEdit, onArchive, onDuplicate, onExport, onDelete, onRestore, canDelete } = handlers;
  if (!onEdit && !onArchive && !onRestore) return baseColumns;

  const actionColumn: GridColDef<ProjectTableRow> = {
    field: 'actions',
    headerName: '',
    width: 108,
    sortable: false,
    filterable: false,
    disableColumnMenu: true,
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
              <RestoreRoundedIcon fontSize="small" />
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

const TABLE_HEIGHT = 560;
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
      pinLeftFields={['tool_number']}
      autoHeight={rows.length <= PAGE_SIZE}
      sx={rows.length > PAGE_SIZE ? { height: TABLE_HEIGHT } : undefined}
      paginationModel={{ pageSize: PAGE_SIZE, page: 0 }}
      pageSizeOptions={[25, 50, 100]}
      disableColumnMenu={false}
      initialState={{
        columns: {
          columnVisibilityModel: {
            teamName: false,
            designLeaderName: false,
            surfacerName: false,
            current_milestone: false,
          },
        },
      }}
      onRowOpen={(rowId) => {
        const row = rowMap.get(rowId);
        if (row) onRowOpen?.(row);
      }}
    />
  );
}

export const ProjectTable = memo(ProjectTableComponent);
