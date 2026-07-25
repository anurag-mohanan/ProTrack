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

/** Desktop board columns — fixed tracks so nothing leaves a dead middle gap. */
const BOARD_COLUMNS = {
  xs: '52px minmax(0, 1fr) 28px',
  md: '56px minmax(140px, 1.6fr) minmax(100px, 0.9fr) 132px 96px 72px 28px',
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
        display: { xs: 'none', md: 'grid' },
        gridTemplateColumns: BOARD_COLUMNS.md,
        columnGap: 1,
        alignItems: 'center',
        px: 1,
        py: 0.5,
        borderBottom: '1px solid',
        borderColor: 'divider',
        bgcolor: 'action.hover',
      }}
    >
      {cell('Tool')}
      {cell('Milestone / Customer')}
      {cell('People')}
      {cell('Hours')}
      {cell('Progress')}
      {cell('Due', { textAlign: 'right' })}
      <span />
    </Box>
  );
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

function HoursCell({ row }: { row: ProjectTableRow }) {
  const { quoted, actual, varianceColor, varianceLabel } = hoursVariance(row);

  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography
        variant="caption"
        sx={{
          display: 'block',
          fontWeight: 700,
          fontVariantNumeric: 'tabular-nums',
          lineHeight: 1.2,
          color: 'text.secondary',
          whiteSpace: 'nowrap',
        }}
      >
        Q {formatNumber(quoted, 0)} · A {formatNumber(actual, 0)}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          fontWeight: 800,
          fontVariantNumeric: 'tabular-nums',
          lineHeight: 1.2,
          color: varianceColor,
        }}
      >
        {varianceLabel}
      </Typography>
    </Box>
  );
}

function ProgressCell({
  percent,
  health,
}: {
  percent: number;
  health: { main: string; soft: string };
}) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', mb: 0.2, gap: 0.5 }}>
        <Typography
          variant="caption"
          sx={{ fontWeight: 800, fontVariantNumeric: 'tabular-nums', fontSize: '0.68rem', lineHeight: 1.1 }}
        >
          {Math.round(percent)}%
        </Typography>
      </Stack>
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
  );
}

function SubLabel({ label, count }: { label: string; count: number }) {
  return (
    <Stack
      direction="row"
      spacing={0.5}
      sx={{
        alignItems: 'center',
        px: 1,
        py: 0.4,
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

  const openMenu = (event: MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setAnchor(event.currentTarget);
  };

  return (
    <Box
      onClick={() => onRowOpen?.(row)}
      sx={{
        px: 1,
        py: 0.55,
        display: 'grid',
        gridTemplateColumns: BOARD_COLUMNS,
        columnGap: 1,
        alignItems: 'center',
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
      <Typography sx={{ fontWeight: 800, fontSize: '0.82rem', lineHeight: 1.2 }} noWrap>
        {row.tool_number}
      </Typography>

      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.78rem', lineHeight: 1.25 }} noWrap>
          {formatDisplayValue(stage)}
        </Typography>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', fontWeight: 600, lineHeight: 1.2, fontSize: '0.7rem' }}
          noWrap
        >
          {row.customerName || '—'}
        </Typography>
        <Box sx={{ display: { xs: 'block', md: 'none' }, mt: 0.15 }}>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ fontWeight: 600, lineHeight: 1.25, display: 'block' }}
            noWrap
          >
            {peopleLabel}
          </Typography>
          {(() => {
            const { quoted, actual, varianceColor, varianceLabel } = hoursVariance(row);
            return (
              <Typography
                variant="caption"
                sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums', lineHeight: 1.2 }}
                noWrap
              >
                Q {formatNumber(quoted, 0)} · A {formatNumber(actual, 0)} ·{' '}
                <Box component="span" sx={{ color: varianceColor, fontWeight: 800 }}>
                  {varianceLabel}
                </Box>
              </Typography>
            );
          })()}
        </Box>
      </Box>

      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          display: { xs: 'none', md: 'block' },
          fontWeight: 600,
          lineHeight: 1.25,
          fontSize: '0.72rem',
        }}
        noWrap
        title={peopleLabel}
      >
        {peopleLabel}
      </Typography>

      <Box sx={{ display: { xs: 'none', md: 'block' } }}>
        <HoursCell row={row} />
      </Box>

      <Box sx={{ display: { xs: 'none', md: 'block' } }}>
        <ProgressCell percent={percent} health={health} />
      </Box>

      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          display: { xs: 'none', md: 'block' },
          fontWeight: 700,
          textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
          fontSize: '0.72rem',
          lineHeight: 1.2,
        }}
        noWrap
      >
        {row.due_date ? formatDate(row.due_date) : '—'}
      </Typography>

      <IconButton
        size="small"
        aria-label="Project actions"
        onClick={openMenu}
        sx={{ justifySelf: 'end', p: 0.25 }}
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
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1.5,
        overflow: 'hidden',
        bgcolor: 'background.paper',
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
    <Stack spacing={1}>
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
