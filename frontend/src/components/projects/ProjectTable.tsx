import { memo, useMemo } from 'react';
import { Box, Chip, LinearProgress, Link, Tooltip, Typography, useMediaQuery } from '@mui/material';
import RestoreRoundedIcon from '@mui/icons-material/RestoreRounded';
import { IconButton } from '@mui/material';
import { useTheme, type Theme } from '@mui/material/styles';
import type { GridColDef } from '@mui/x-data-grid';
import type { Customer, Project, Stream, Team, User } from '../../types';
import { ClientPaginatedDataGrid } from '../common/ClientPaginatedDataGrid';
import {
  EntityAvatar,
  ExecutionStatusBadge,
  HealthBadge,
  HelpTooltip,
  ProjectStageBadge,
} from '../ui/design-system';
import { ProjectRowActions } from './ProjectRowActions';
import { designTokens } from '../../theme/designTokens';
import { formatCellValue, formatDate, userDisplayName } from '../../utils/format';
import { formatNumber } from '../../utils/format';
import {
  calculateEAC,
  forecastVariance,
  formatHoursOverPercent,
  hoursBurnPercent,
  hoursUtilizationTone,
  type HoursPerformanceTone,
} from '../../utils/projectHoursMetrics';
import { isActiveProjectForHealth } from '../../utils/projectHealth';
import {
  applyAutoFitToColumns,
  autoFitCellSx,
  autoFitFlexCellSx,
} from '../../utils/dataGridAutoFit';
import { projectTableAutoFitProfiles } from '../../utils/dataGridAutoFitProfiles';

const SETUP_GAP_LABELS: Record<string, string> = {
  project_type: 'type',
  team: 'team',
  design_leader: 'leader',
  due_date: 'due date',
  template: 'template',
};
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
  /** Changes when filters change — resets pagination and sort state. */
  gridSessionKey?: number;
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

function toneColor(tone: HoursPerformanceTone, palette: Theme['palette']) {
  if (tone === 'success') return palette.success.main;
  if (tone === 'warning') return palette.warning.main;
  return palette.error.main;
}

function HoursComparisonCell({
  actual,
  quoted,
  progressPercent,
}: {
  actual: number;
  quoted: number;
  progressPercent: number;
}) {
  const theme = useTheme();
  const burnPct = hoursBurnPercent(actual, quoted);
  const tone = hoursUtilizationTone(actual, quoted);
  const accent = toneColor(tone, theme.palette);
  const overLabel = formatHoursOverPercent(actual, quoted);
  const barValue = actual <= quoted ? Math.min(100, burnPct) : 100;
  const eac = calculateEAC(actual, progressPercent);
  const forecast = forecastVariance(actual, quoted, progressPercent);

  const tooltipParts = [`Quoted: ${formatNumber(quoted, 0)}`, `Actual: ${formatNumber(actual, 0)}`];
  if (eac != null) tooltipParts.push(`Projected: ${formatNumber(eac, 0)}`);
  if (forecast != null) tooltipParts.push(`Forecast: ${formatNumber(forecast, 0)}`);

  return (
    <Tooltip title={tooltipParts.join(' · ')}>
      <Box sx={{ width: '100%', py: 0.15 }}>
        <Typography
          sx={{
            fontSize: '0.7rem',
            fontWeight: 700,
            lineHeight: 1.15,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {formatNumber(actual, 0)} / {formatNumber(quoted, 0)}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4, mt: 0.2 }}>
          <LinearProgress
            variant="determinate"
            value={barValue}
            sx={{
              flex: 1,
              height: 3,
              borderRadius: designTokens.radius.pill,
              bgcolor: designTokens.semantic.neutralSoft,
              '& .MuiLinearProgress-bar': {
                borderRadius: designTokens.radius.pill,
                bgcolor: accent,
              },
            }}
          />
          <Typography
            sx={{
              fontSize: '0.65rem',
              fontWeight: 800,
              color: accent,
              minWidth: 30,
              fontVariantNumeric: 'tabular-nums',
              lineHeight: 1,
            }}
          >
            {formatNumber(Math.round(burnPct), 0)}%
          </Typography>
        </Box>
        {overLabel ? (
          <Typography sx={{ fontSize: '0.6rem', fontWeight: 700, color: accent, lineHeight: 1.1 }}>
            {overLabel}
          </Typography>
        ) : null}
      </Box>
    </Tooltip>
  );
}

function ProgressCell({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <Box sx={{ width: '100%' }}>
      <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, lineHeight: 1.15, mb: 0.15 }}>
        {formatNumber(pct, 0)}%
      </Typography>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          height: 3,
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
    'onEdit' | 'onArchive' | 'onDuplicate' | 'onExport' | 'onDelete' | 'onRestore' | 'canDelete' | 'onRowOpen'
  >,
): GridColDef<ProjectTableRow>[] {
  const baseColumns: GridColDef<ProjectTableRow>[] = [
    {
      field: 'serial',
      headerName: '#',
      width: 48,
      minWidth: 44,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      headerAlign: 'center',
      align: 'center',
      renderCell: (params) => (
        <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
          {params.api.getRowIndexRelativeToVisibleRows(params.id) + 1}
        </Typography>
      ),
    },
    {
      field: 'tool_number',
      headerName: 'Tool Number',
      renderHeader: () => (
        <Box sx={{ display: 'inline-flex', alignItems: 'center' }}>
          Tool Number
          <HelpTooltip title="Customer tool or mold number — primary project identifier." />
        </Box>
      ),
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
          <Link
            component="button"
            type="button"
            underline="hover"
            onClick={(event) => {
              event.stopPropagation();
              handlers.onRowOpen?.(params.row);
            }}
            sx={{
              fontWeight: 800,
              fontSize: '0.8rem',
              color: designTokens.semantic.primary,
              textAlign: 'left',
              cursor: 'pointer',
              p: 0,
              ...autoFitCellSx,
            }}
          >
            {params.value}
          </Link>
          {params.row.needs_setup ? (
            <Tooltip
              title={`Needs setup: ${(params.row.setup_gaps ?? [])
                .map((gap: string) => SETUP_GAP_LABELS[gap] ?? gap)
                .join(', ')}`}
            >
              <Chip
                label="Needs setup"
                size="small"
                color="warning"
                variant="outlined"
                sx={{ height: 20, fontSize: '0.65rem', flexShrink: 0 }}
              />
            </Tooltip>
          ) : null}
          {(params.row.workstreams ?? []).slice(0, 3).map((ws: { workstream_id: string; workstream_name?: string | null; remaining_hours?: number | null }) => (
            <Chip
              key={ws.workstream_id}
              label={
                ws.remaining_hours != null
                  ? `${ws.workstream_name ?? 'WS'} (${ws.remaining_hours}h left)`
                  : (ws.workstream_name ?? 'WS')
              }
              size="small"
              variant="outlined"
              sx={{ height: 20, fontSize: '0.62rem', flexShrink: 0 }}
            />
          ))}
        </Box>
      ),
    },
    {
      field: 'customerName',
      headerName: 'Customer',
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0 }}>
          <EntityAvatar label={String(params.value || '?')} size={20} />
          <Box component="span" sx={{ fontSize: '0.78rem', ...autoFitFlexCellSx }}>
            {displayOrDash(params.value)}
          </Box>
        </Box>
      ),
    },
    {
      field: 'hours_comparison',
      headerName: 'Hours',
      sortable: true,
      valueGetter: (_value, row) =>
        hoursBurnPercent(
          Number(row.original_hours ?? row.actual_hours),
          Number(row.quoted_hours),
        ),
      renderCell: (params) => (
        <HoursComparisonCell
          actual={Number(params.row.original_hours ?? params.row.actual_hours)}
          quoted={Number(params.row.quoted_hours)}
          progressPercent={Number(params.row.progress_percent)}
        />
      ),
    },
    {
      field: 'project_stage',
      headerName: 'Current Stage',
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
      renderCell: (params) => (
        <Tooltip title="Current execution state for planning, delivery, and reporting.">
          <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
            <ExecutionStatusBadge status={params.value} />
            {params.row.execution_status === 'completed' && params.row.has_post_completion_activity ? (
              <Chip
                size="small"
                label="Post-Completion Activity"
                sx={{
                  fontWeight: 700,
                  fontSize: '0.65rem',
                  bgcolor: designTokens.semantic.warningSoft,
                  color: designTokens.semantic.warning,
                }}
              />
            ) : null}
          </Box>
        </Tooltip>
      ),
    },
    {
      field: 'health',
      headerName: 'Health',
      renderCell: (params) => {
        if (!isActiveProjectForHealth(params.row.execution_status, Boolean(params.row.is_archived))) {
          return '—';
        }
        return (
        <Tooltip title="Project health summarizes progress, timeline risk, and execution quality.">
          <Box component="span">
            <HealthBadge health={params.value} />
          </Box>
        </Tooltip>
        );
      },
    },
    {
      field: 'designerName',
      headerName: 'Designer',
      valueFormatter: (value) => displayOrDash(value),
      renderCell: (params) => (
        <Box component="span" sx={{ fontSize: '0.78rem', ...autoFitFlexCellSx }}>
          {displayOrDash(params.value)}
        </Box>
      ),
    },
    {
      field: 'surfacerName',
      headerName: 'Surfacer',
      valueFormatter: (value) => displayOrDash(value),
      renderCell: (params) => (
        <Box component="span" sx={{ fontSize: '0.78rem', ...autoFitFlexCellSx }}>
          {displayOrDash(params.value)}
        </Box>
      ),
    },
    {
      field: 'due_date',
      headerName: 'Due Date',
      valueFormatter: (value) => formatDate(String(value)) || '—',
    },
    {
      field: 'progress_percent',
      headerName: 'Progress',
      renderCell: (params) => (
        <Tooltip title="Completion percentage based on milestone progress.">
          <Box sx={{ width: '100%' }}>
            <ProgressCell value={Number(params.value)} />
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
    sortable: false,
    filterable: false,
    disableColumnMenu: true,
    renderCell: (params) => (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
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

const LIVE_TABLE_HEIGHT = {
  height: 'calc(100vh - 268px)',
  '@supports (height: 100dvh)': {
    height: 'calc(100dvh - 268px)',
  },
};
const COMPLETED_TABLE_HEIGHT = 360;
const PAGE_SIZE = 25;

function ProjectTableComponent({
  projects,
  customers,
  users,
  streams,
  teams,
  primary = false,
  gridSessionKey = 0,
  onRowOpen,
  onEdit,
  onArchive,
  onDuplicate,
  onExport,
  onDelete,
  onRestore,
  canDelete,
}: ProjectTableProps) {
  const isWide = useMediaQuery('(min-width:1920px)');

  const rows = useMemo(
    () => buildProjectTableRows(projects, customers, users, streams, teams),
    [projects, customers, users, streams, teams],
  );

  const rowMap = useMemo(() => new Map(rows.map((row) => [row.id, row])), [rows]);

  const baseColumns = useMemo(
    () =>
      buildColumns({
        onEdit,
        onArchive,
        onDuplicate,
        onExport,
        onDelete,
        onRestore,
        canDelete,
        onRowOpen,
      }),
    [canDelete, onArchive, onDelete, onDuplicate, onEdit, onExport, onRestore, onRowOpen],
  );

  const hasActions = Boolean(onEdit || onArchive || onRestore);
  const columns = useMemo(
    () =>
      applyAutoFitToColumns(
        baseColumns,
        rows,
        projectTableAutoFitProfiles({
          hasActions,
          restoreOnly: Boolean(onRestore && !onEdit),
        }),
        { wide: isWide },
      ),
    [baseColumns, rows, hasActions, onRestore, onEdit, isWide],
  );

  const tableHeight = primary
    ? LIVE_TABLE_HEIGHT
    : rows.length > PAGE_SIZE
      ? { height: COMPLETED_TABLE_HEIGHT }
      : undefined;

  return (
    <ClientPaginatedDataGrid
      key={`project-grid-${gridSessionKey}`}
      rows={rows}
      columns={columns}
      pinLeftFields={['tool_number']}
      autoHeight={!tableHeight}
      dense
      filterKey={gridSessionKey}
      paginationLabel="projects"
      sx={
        tableHeight
          ? {
              ...tableHeight,
              minHeight: 360,
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
      pageSizeOptions={[25, 50, 100]}
      disableColumnMenu={false}
      initialState={{
        sorting: { sortModel: [] },
        columns: {
          columnVisibilityModel: {
            teamName: false,
            designLeaderName: false,
            part_description: false,
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
