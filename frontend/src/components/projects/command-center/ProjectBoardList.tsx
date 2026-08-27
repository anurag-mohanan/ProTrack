import {
  Box,
  Chip,
  IconButton,
  LinearProgress,
  Menu,
  MenuItem,
  Stack,
  Typography,
} from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { useMemo, useState, type MouseEvent, type ReactNode } from 'react';
import type { Customer, Project, Stream, Team, User } from '../../../types';
import { designTokens } from '../../../theme/designTokens';
import { formatDate, formatDisplayValue, formatNumber } from '../../../utils/format';
import { buildProjectTableRows, type ProjectTableRow } from '../ProjectTable';

/**
 * Full-bleed board: project column absorbs leftover width;
 * metric columns stay compact and readable.
 */
const BOARD_COLUMNS =
  'minmax(64px, 88px) minmax(0, 1fr) minmax(120px, 160px) minmax(96px, 120px) minmax(88px, 110px) 40px';
const BOARD_COLUMN_GAP = 2;
const BOARD_ROW_PY = 1.1;
const BOARD_ROW_PX = 1.75;

const boardGridSx = {
  display: 'grid',
  gridTemplateColumns: BOARD_COLUMNS,
  columnGap: BOARD_COLUMN_GAP,
  alignItems: 'center',
  width: '100%',
  minWidth: '100%',
  boxSizing: 'border-box',
} as const;

function healthTone(health?: string | null) {
  if (health === 'red') return designTokens.health.red;
  if (health === 'yellow') return designTokens.health.yellow;
  return designTokens.health.green;
}

function humanizeStage(value?: string | null) {
  if (!value) return '—';
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function isOnHold(project: ProjectTableRow) {
  return project.execution_status === 'on_hold';
}

function cleanName(value?: string | null) {
  const trimmed = (value ?? '').trim();
  return trimmed && trimmed !== '—' ? trimmed : '';
}

function hoursVariance(row: ProjectTableRow) {
  const quoted = Number(row.quoted_hours ?? 0);
  const actual = Number(row.actual_hours ?? 0);
  const variancePct = quoted > 0 ? ((actual - quoted) / quoted) * 100 : null;
  const over = typeof variancePct === 'number' && variancePct > 0;
  const under = typeof variancePct === 'number' && variancePct < 0;
  const varianceColor = over
    ? designTokens.semantic.danger
    : under
      ? designTokens.semantic.success
      : 'text.secondary';
  const varianceLabel =
    typeof variancePct === 'number'
      ? `${variancePct > 0 ? '+' : ''}${Math.round(variancePct)}%`
      : '—';
  return { quoted, actual, varianceColor, varianceLabel };
}

function BoardHeader() {
  const cell = (label: string, sx?: object) => (
    <Typography
      sx={{
        fontSize: '0.62rem',
        fontWeight: 800,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        color: 'text.secondary',
        lineHeight: 1.2,
        ...sx,
      }}
    >
      {label}
    </Typography>
  );

  return (
    <Box
      sx={{
        ...boardGridSx,
        px: BOARD_ROW_PX,
        py: 0.85,
        borderBottom: '1px solid',
        borderColor: 'divider',
        bgcolor: 'action.hover',
      }}
    >
      {cell('Tool')}
      {cell('Project')}
      {cell('Hours')}
      {cell('Progress')}
      {cell('Due', { textAlign: 'right' })}
      <span />
    </Box>
  );
}

function SubLabel({ label, count }: { label: string; count: number }) {
  return (
    <Stack
      direction="row"
      spacing={0.75}
      sx={{
        alignItems: 'center',
        px: BOARD_ROW_PX,
        py: 0.65,
        bgcolor: 'action.hover',
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Typography
        sx={{
          fontSize: '0.65rem',
          fontWeight: 800,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          color: 'text.secondary',
        }}
      >
        {label}
      </Typography>
      <Chip size="small" label={count} sx={{ height: 16, fontSize: '0.62rem', fontWeight: 800 }} />
    </Stack>
  );
}

function ProjectBoardRow({
  row,
  onRowOpen,
  onEdit,
  onArchive,
  onDuplicate,
  onExport,
  onDelete,
  canDelete,
}: {
  row: ProjectTableRow;
  onRowOpen?: (row: ProjectTableRow) => void;
  onEdit?: (row: ProjectTableRow) => void;
  onArchive?: (projectId: string) => void;
  onDuplicate?: (projectId: string) => void;
  onExport?: (row: ProjectTableRow) => void;
  onDelete?: (projectId: string) => void;
  canDelete?: boolean;
}) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const health = healthTone(row.health);
  const stage = row.current_milestone || humanizeStage(row.project_stage);
  const percent = Math.max(0, Math.min(100, Number(row.progress_percent ?? 0)));
  const muted = isOnHold(row);
  const designer = cleanName(row.designerName);
  const surfacer = cleanName(row.surfacerName);
  const people = [designer, surfacer].filter(Boolean);
  const peopleLabel = people.length ? people.join(' · ') : 'Unassigned';
  const { quoted, actual, varianceColor, varianceLabel } = hoursVariance(row);

  const openMenu = (event: MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setAnchor(event.currentTarget);
  };

  return (
    <Box
      onClick={() => onRowOpen?.(row)}
      sx={{
        ...boardGridSx,
        px: BOARD_ROW_PX,
        py: BOARD_ROW_PY,
        rowGap: 0.35,
        borderBottom: '1px solid',
        borderColor: 'divider',
        borderLeft: `3px solid ${health.main}`,
        cursor: onRowOpen ? 'pointer' : 'default',
        opacity: muted ? 0.78 : 1,
        bgcolor: 'background.paper',
        '&:last-of-type': { borderBottom: 'none' },
        '&:hover': { bgcolor: 'action.hover' },
      }}
    >
      <Typography sx={{ fontWeight: 800, fontSize: '0.85rem', lineHeight: 1.35 }} noWrap>
        {row.tool_number}
      </Typography>

      <Box sx={{ minWidth: 0, pr: 0.5 }}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.8rem', lineHeight: 1.35 }} noWrap>
          {formatDisplayValue(stage)}
          {row.customerName ? (
            <Box component="span" sx={{ color: 'text.secondary', fontWeight: 600 }}>
              {' · '}
              {row.customerName}
            </Box>
          ) : null}
        </Typography>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', fontWeight: 600, lineHeight: 1.35, fontSize: '0.7rem', mt: 0.25 }}
          noWrap
          title={peopleLabel}
        >
          {peopleLabel}
        </Typography>
      </Box>

      <Box sx={{ minWidth: 0, pr: 0.5 }}>
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            fontWeight: 700,
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.35,
            color: 'text.secondary',
            whiteSpace: 'nowrap',
          }}
        >
          Q {formatNumber(quoted, 0)} · A {formatNumber(actual, 0)}
        </Typography>
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            fontWeight: 800,
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.35,
            color: varianceColor,
            mt: 0.25,
          }}
        >
          {varianceLabel}
        </Typography>
      </Box>

      <Box sx={{ minWidth: 0, pr: 0.5 }}>
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            fontWeight: 800,
            fontVariantNumeric: 'tabular-nums',
            fontSize: '0.72rem',
            lineHeight: 1.3,
            mb: 0.4,
          }}
        >
          {Math.round(percent)}%
        </Typography>
        <LinearProgress
          variant="determinate"
          value={percent}
          sx={{
            height: 6,
            borderRadius: 999,
            bgcolor: health.soft,
            '& .MuiLinearProgress-bar': { bgcolor: health.main, borderRadius: 999 },
          }}
        />
      </Box>

      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          fontWeight: 700,
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          fontSize: '0.75rem',
          lineHeight: 1.35,
          pr: 0.25,
        }}
        noWrap
      >
        {row.due_date ? formatDate(row.due_date) : '—'}
      </Typography>

      <IconButton
        size="small"
        aria-label="Project actions"
        onClick={openMenu}
        sx={{ justifySelf: 'end', p: 0.5 }}
      >
        <MoreVertIcon fontSize="small" />
      </IconButton>

      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}>
        {onRowOpen ? (
          <MenuItem
            onClick={() => {
              setAnchor(null);
              onRowOpen(row);
            }}
          >
            Open
          </MenuItem>
        ) : null}
        {onEdit ? (
          <MenuItem
            onClick={() => {
              setAnchor(null);
              onEdit(row);
            }}
          >
            Edit
          </MenuItem>
        ) : null}
        {onDuplicate ? (
          <MenuItem
            onClick={() => {
              setAnchor(null);
              onDuplicate(row.id);
            }}
          >
            Duplicate
          </MenuItem>
        ) : null}
        {onExport ? (
          <MenuItem
            onClick={() => {
              setAnchor(null);
              onExport(row);
            }}
          >
            Export
          </MenuItem>
        ) : null}
        {onArchive ? (
          <MenuItem
            onClick={() => {
              setAnchor(null);
              onArchive(row.id);
            }}
          >
            Archive
          </MenuItem>
        ) : null}
        {canDelete && onDelete ? (
          <MenuItem
            onClick={() => {
              setAnchor(null);
              onDelete(row.id);
            }}
            sx={{ color: 'error.main' }}
          >
            Delete
          </MenuItem>
        ) : null}
      </Menu>
    </Box>
  );
}

function BoardShell({ children }: { children: ReactNode }) {
  return (
    <Box
      sx={{
        width: '100%',
        minWidth: '100%',
        maxWidth: '100%',
        display: 'block',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1.5,
        overflow: 'hidden',
        bgcolor: 'background.paper',
        boxSizing: 'border-box',
      }}
    >
      {children}
    </Box>
  );
}

type ProjectBoardListProps = {
  projects: Project[];
  customers: Customer[];
  users: User[];
  streams: Stream[];
  teams: Team[];
  splitActiveHold?: boolean;
  onRowOpen?: (row: ProjectTableRow) => void;
  onEdit?: (row: ProjectTableRow) => void;
  onArchive?: (projectId: string) => void;
  onDuplicate?: (projectId: string) => void;
  onExport?: (row: ProjectTableRow) => void;
  onDelete?: (projectId: string) => void;
  canDelete?: boolean;
};

export function ProjectBoardList({
  projects,
  customers,
  users,
  streams,
  teams,
  splitActiveHold = true,
  onRowOpen,
  onEdit,
  onArchive,
  onDuplicate,
  onExport,
  onDelete,
  canDelete,
}: ProjectBoardListProps) {
  const rows = useMemo(
    () => buildProjectTableRows(projects, customers, users, streams, teams),
    [projects, customers, users, streams, teams],
  );

  const working = splitActiveHold ? rows.filter((row) => !isOnHold(row)) : rows;
  const onHold = splitActiveHold ? rows.filter((row) => isOnHold(row)) : [];

  if (!rows.length) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ px: 0.5, py: 0.75 }}>
        No projects in this section.
      </Typography>
    );
  }

  const renderRows = (list: ProjectTableRow[]) =>
    list.map((row) => (
      <ProjectBoardRow
        key={row.id}
        row={row}
        onRowOpen={onRowOpen}
        onEdit={onEdit}
        onArchive={onArchive}
        onDuplicate={onDuplicate}
        onExport={onExport}
        onDelete={onDelete}
        canDelete={canDelete}
      />
    ));

  return (
    <Stack spacing={1} sx={{ width: '100%', minWidth: '100%', display: 'flex', alignItems: 'stretch' }}>
      {working.length ? (
        <BoardShell>
          {splitActiveHold ? <SubLabel label="Active" count={working.length} /> : null}
          <BoardHeader />
          {renderRows(working)}
        </BoardShell>
      ) : null}
      {onHold.length ? (
        <BoardShell>
          <SubLabel label="On hold" count={onHold.length} />
          <BoardHeader />
          {renderRows(onHold)}
        </BoardShell>
      ) : null}
    </Stack>
  );
}
