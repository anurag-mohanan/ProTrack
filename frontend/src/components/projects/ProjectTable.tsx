import { memo, useMemo } from 'react';
import { Box, LinearProgress, Tooltip, Typography } from '@mui/material';
import RestoreRoundedIcon from '@mui/icons-material/RestoreRounded';
import { IconButton } from '@mui/material';
import { useTheme, type Theme } from '@mui/material/styles';
import type { GridColDef } from '@mui/x-data-grid';
import type { Customer, Project, Stream, Team, User } from '../../types';
import {
  ProsohmDataGrid,
  EntityAvatar,
  ExecutionStatusBadge,
  HealthBadge,
  HelpTooltip,
  PriorityBadge,
  ProjectStageBadge,
} from '../ui/design-system';
import { ProjectRowActions } from './ProjectRowActions';
import { designTokens } from '../../theme/designTokens';
import { formatCellValue, formatDate, userDisplayName } from '../../utils/format';
import { formatNumber } from '../../utils/format';
import {
  calculateEAC,
  forecastVariance,
  formatHoursVariance,
  hoursPerformanceTone,
  hoursUtilizationPercent,
  hoursVariance,
} from '../../utils/projectHoursMetrics';

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
  /** Use viewport-based height for the primary live projects grid. */
  primary?: boolean;
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

function toneColor(tone: ReturnType<typeof hoursPerformanceTone>, palette: Theme['palette']) {
  if (tone === 'success') return palette.success.main;
  if (tone === 'warning') return palette.warning.main;
  return palette.error.main;
}

function HoursValueCell({ value }: { value: number }) {
  return (
    <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
      {formatNumber(value, 0)}
    </Typography>
  );
}

function VarianceCell({ actual, quoted }: { actual: number; quoted: number }) {
  const theme = useTheme();
  const variance = hoursVariance(actual, quoted);
  const tone = hoursPerformanceTone(actual, quoted);
  return (
    <Typography
      sx={{
        fontSize: '0.75rem',
        fontWeight: 800,
        fontVariantNumeric: 'tabular-nums',
        color: toneColor(tone, theme.palette),
      }}
    >
      {formatHoursVariance(variance, 0)}
    </Typography>
  );
}

function HoursProgressCell({
  actual,
  quoted,
  progressPercent,
}: {
  actual: number;
  quoted: number;
  progressPercent: number;
}) {
  const theme = useTheme();
  const utilization = hoursUtilizationPercent(actual, quoted);
  const tone = hoursPerformanceTone(actual, quoted);
  const barColor = toneColor(tone, theme.palette);
  const eac = calculateEAC(actual, progressPercent);
  const forecast = forecastVariance(actual, quoted, progressPercent);

  const tooltipLines = [
    `Quoted: ${formatNumber(quoted, 0)} hrs`,
    `Actual: ${formatNumber(actual, 0)} hrs`,
    `Milestone progress: ${formatNumber(progressPercent, 0)}%`,
  ];
  if (eac != null) {
    tooltipLines.push(`Projected final: ${formatNumber(eac, 0)} hrs`);
  }
  if (forecast != null) {
    tooltipLines.push(`Forecast variance: ${formatHoursVariance(forecast, 0)} hrs`);
  }

  return (
    <Tooltip title={tooltipLines.join(' · ')}>
      <Box sx={{ width: '100%', minWidth: 88, py: 0.25 }}>
        <Typography
          sx={{
            fontSize: '0.7rem',
            fontWeight: 700,
            lineHeight: 1.2,
            fontVariantNumeric: 'tabular-nums',
            mb: 0.25,
          }}
        >
          {formatNumber(actual, 0)} / {formatNumber(quoted, 0)} hrs
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <LinearProgress
            variant="determinate"
            value={utilization}
            sx={{
              flex: 1,
              height: 4,
              borderRadius: designTokens.radius.pill,
              bgcolor: designTokens.semantic.neutralSoft,
              '& .MuiLinearProgress-bar': {
                borderRadius: designTokens.radius.pill,
                bgcolor: barColor,
              },
            }}
          />
          <Typography
            sx={{
              fontSize: '0.65rem',
              fontWeight: 700,
              color: 'text.secondary',
              minWidth: 28,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {formatNumber(utilization, 0)}%
          </Typography>
        </Box>
      </Box>
    </Tooltip>
  );
}

function ProgressCell({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <Box sx={{ width: '100%', minWidth: 64 }}>
      <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, lineHeight: 1.2, mb: 0.25 }}>
        {formatNumber(pct, 0)}%
      </Typography>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          height: 4,
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
      headerName: 'Tool No.',
      width: 96,
      minWidth: 88,
      renderHeader: () => (
        <Box sx={{ display: 'inline-flex', alignItems: 'center' }}>
          Tool No.
          <HelpTooltip title="Customer tool or mold number used to uniquely identify the project." />
        </Box>
      ),
      renderCell: (params) => (
        <Box sx={{ fontWeight: 800, color: designTokens.semantic.primary, fontSize: '0.8rem' }}>
          {params.value}
        </Box>
      ),
    },
    {
      field: 'part_description',
      headerName: 'Part',
      flex: 1.4,
      minWidth: 180,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'customerName',
      headerName: 'Customer',
      flex: 1,
      minWidth: 150,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
          <EntityAvatar label={String(params.value || '?')} size={22} />
          <Box
            component="span"
            sx={{ overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '0.8rem' }}
          >
            {displayOrDash(params.value)}
          </Box>
        </Box>
      ),
    },
    {
      field: 'quoted_hours',
      headerName: 'Quoted',
      width: 72,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => <HoursValueCell value={Number(params.value)} />,
    },
    {
      field: 'actual_hours',
      headerName: 'Actual',
      width: 72,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => <HoursValueCell value={Number(params.value)} />,
    },
    {
      field: 'hours_variance',
      headerName: 'Variance',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      valueGetter: (_value, row) => hoursVariance(Number(row.actual_hours), Number(row.quoted_hours)),
      renderCell: (params) => (
        <VarianceCell
          actual={Number(params.row.actual_hours)}
          quoted={Number(params.row.quoted_hours)}
        />
      ),
    },
    {
      field: 'project_stage',
      headerName: 'Stage',
      width: 112,
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
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Tooltip title="Current execution state for planning, delivery, and reporting.">
          <Box component="span">
            <ExecutionStatusBadge status={params.value} />
          </Box>
        </Tooltip>
      ),
    },
    {
      field: 'due_date',
      headerName: 'Due Date',
      width: 96,
      valueFormatter: (value) => formatDate(String(value)) || '—',
    },
    {
      field: 'hours_progress',
      headerName: 'Hours',
      width: 128,
      sortable: false,
      valueGetter: (_value, row) =>
        hoursUtilizationPercent(Number(row.actual_hours), Number(row.quoted_hours)),
      renderCell: (params) => (
        <HoursProgressCell
          actual={Number(params.row.actual_hours)}
          quoted={Number(params.row.quoted_hours)}
          progressPercent={Number(params.row.progress_percent)}
        />
      ),
    },
    {
      field: 'progress_percent',
      headerName: 'Progress',
      width: 88,
      renderCell: (params) => (
        <Tooltip title="Completion percentage based on milestone progress.">
          <Box sx={{ width: '100%' }}>
            <ProgressCell value={Number(params.value)} />
          </Box>
        </Tooltip>
      ),
    },
    {
      field: 'designerName',
      headerName: 'Designer',
      width: 108,
      valueFormatter: (value) => displayOrDash(value),
    },
    {
      field: 'health',
      headerName: 'Health',
      width: 96,
      renderHeader: () => (
        <Box sx={{ display: 'inline-flex', alignItems: 'center' }}>
          Health
          <HelpTooltip title="Current overall health of the project based on progress, due dates, and milestones." />
        </Box>
      ),
      renderCell: (params) => (
        <Tooltip title="Project health summarizes progress, timeline risk, and execution quality.">
          <Box component="span">
            <HealthBadge health={params.value} />
          </Box>
        </Tooltip>
      ),
    },
    {
      field: 'priority',
      headerName: 'Priority',
      width: 92,
      renderHeader: () => (
        <Box sx={{ display: 'inline-flex', alignItems: 'center' }}>
          Priority
          <HelpTooltip title="Higher priority projects are highlighted in planning and dashboards." />
        </Box>
      ),
      renderCell: (params) => (
        <Tooltip title="Priority influences planning focus and workload balancing.">
          <Box component="span">
            <PriorityBadge priority={params.value ?? 'medium'} />
          </Box>
        </Tooltip>
      ),
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

const LIVE_TABLE_HEIGHT = 'calc(100vh - 300px)';
const COMPLETED_TABLE_HEIGHT = 360;
const PAGE_SIZE = 25;

function ProjectTableComponent({
  projects,
  customers,
  users,
  streams,
  teams,
  primary = false,
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

  const tableHeight = primary
    ? LIVE_TABLE_HEIGHT
    : rows.length > PAGE_SIZE
      ? COMPLETED_TABLE_HEIGHT
      : undefined;

  return (
    <ProsohmDataGrid
      rows={rows}
      columns={columns}
      pinLeftFields={['tool_number']}
      autoHeight={!tableHeight}
      dense
      sx={
        tableHeight
          ? {
              height: tableHeight,
              minHeight: 320,
              '& .MuiDataGrid-main': { overflow: 'hidden' },
              '& .MuiDataGrid-virtualScroller': { overflow: 'auto !important' },
              '& .MuiDataGrid-columnHeaders': {
                position: 'sticky',
                top: 0,
                zIndex: 3,
              },
            }
          : undefined
      }
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
