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
import { useMemo, useState, type MouseEvent } from 'react';
import type { Customer, Project, Stream, Team, User } from '../../../types';
import { designTokens } from '../../../theme/designTokens';
import { formatDate, formatDisplayValue, formatNumber } from '../../../utils/format';
import { buildProjectTableRows, type ProjectTableRow } from '../ProjectTable';

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

function HoursMetrics({ row }: { row: ProjectTableRow }) {
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
      : 'n/a';

  return (
    <Stack
      direction="row"
      spacing={0.75}
      useFlexGap
      sx={{ flexWrap: 'wrap', alignItems: 'center', mt: 0.35 }}
    >
      <Typography
        component="span"
        variant="caption"
        color="text.secondary"
        sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums', lineHeight: 1.35 }}
      >
        Q {formatNumber(quoted, 0)}h
      </Typography>
      <Typography component="span" variant="caption" color="text.disabled" sx={{ lineHeight: 1.35 }}>
        ·
      </Typography>
      <Typography
        component="span"
        variant="caption"
        color="text.secondary"
        sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums', lineHeight: 1.35 }}
      >
        A {formatNumber(actual, 0)}h
      </Typography>
      <Typography component="span" variant="caption" color="text.disabled" sx={{ lineHeight: 1.35 }}>
        ·
      </Typography>
      <Typography
        component="span"
        variant="caption"
        sx={{ color: varianceColor, fontWeight: 800, fontVariantNumeric: 'tabular-nums', lineHeight: 1.35 }}
      >
        {varianceLabel}
      </Typography>
    </Stack>
  );
}

function SubLabel({ label, count }: { label: string; count: number }) {
  return (
    <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', pt: 0.5, pb: 0.25 }}>
      <Typography
        sx={{
          fontSize: '0.7rem',
          fontWeight: 800,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: 'text.secondary',
        }}
      >
        {label}
      </Typography>
      <Chip size="small" label={count} sx={{ height: 18, fontSize: '0.65rem', fontWeight: 800 }} />
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

  const openMenu = (event: MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setAnchor(event.currentTarget);
  };

  return (
    <Box
      onClick={() => onRowOpen?.(row)}
      sx={{
        px: 1.25,
        py: 1,
        borderRadius: 2,
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        borderLeft: `4px solid ${health.main}`,
        display: 'grid',
        gridTemplateColumns: {
          xs: '72px minmax(0, 1fr) auto',
          md: '80px minmax(0, 1.4fr) minmax(140px, 0.85fr) 96px auto',
        },
        columnGap: 1.5,
        rowGap: 0.5,
        alignItems: 'start',
        cursor: onRowOpen ? 'pointer' : 'default',
        opacity: muted ? 0.82 : 1,
        '&:hover': { bgcolor: 'action.hover' },
      }}
    >
      <Typography sx={{ fontWeight: 800, fontSize: '0.95rem', pt: 0.15 }} noWrap>
        {row.tool_number}
      </Typography>

      <Box sx={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 0.35 }}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.84rem', lineHeight: 1.35 }} noWrap>
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
          sx={{ fontWeight: 600, lineHeight: 1.4, display: 'block' }}
          noWrap
          title={people.join(' · ') || undefined}
        >
          {people.length ? people.join(' · ') : 'Unassigned'}
        </Typography>

        <HoursMetrics row={row} />
      </Box>

      <Box sx={{ display: { xs: 'none', md: 'block' }, minWidth: 0, pt: 0.35 }}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', mb: 0.35 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
            Progress
          </Typography>
          <Typography variant="caption" sx={{ fontWeight: 800, fontVariantNumeric: 'tabular-nums' }}>
            {Math.round(percent)}%
          </Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={percent}
          sx={{
            height: 7,
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
          display: { xs: 'none', md: 'block' },
          fontWeight: 700,
          textAlign: 'right',
          pt: 0.35,
          fontVariantNumeric: 'tabular-nums',
        }}
        noWrap
      >
        {row.due_date ? formatDate(row.due_date) : '—'}
      </Typography>

      <IconButton size="small" aria-label="Project actions" onClick={openMenu} sx={{ mt: -0.25 }}>
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
      <Typography variant="body2" color="text.secondary" sx={{ px: 0.5, py: 1 }}>
        No projects in this section.
      </Typography>
    );
  }

  return (
    <Stack spacing={0.75}>
      {working.length ? (
        <>
          {splitActiveHold ? <SubLabel label="Active" count={working.length} /> : null}
          {working.map((row) => (
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
          ))}
        </>
      ) : null}
      {onHold.length ? (
        <>
          <SubLabel label="On hold" count={onHold.length} />
          {onHold.map((row) => (
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
          ))}
        </>
      ) : null}
    </Stack>
  );
}
