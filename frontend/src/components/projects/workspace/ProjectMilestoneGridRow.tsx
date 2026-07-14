import { useState, type MouseEvent } from 'react';
import {
  Box,
  IconButton,
  LinearProgress,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Popover,
  Slider,
  Stack,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import MoreVertRoundedIcon from '@mui/icons-material/MoreVertRounded';
import { EntityAvatar, StickyTableCell } from '../../ui/design-system';
import type { Milestone, MilestoneStatus } from '../../../types';
import { MILESTONE_STATUS_LABELS } from '../../../types/common';
import { designTokens } from '../../../theme/designTokens';
import { formatDate, formatNumber, toFiniteNumber } from '../../../utils/format';
import type { updateMilestone } from '../../../services/milestoneService';
import {
  PROGRESS_STEPS,
  ROW_CELL_SX,
  STATUS_COLORS,
  STATUS_EMOJI,
  STATUS_OPTIONS,
} from './milestoneGridConstants';

export type MilestoneUpdatePatch = Parameters<typeof updateMilestone>[1];

interface UserOption {
  value: string;
  label: string;
}

interface ProjectMilestoneGridRowProps {
  row: Milestone;
  isFirst: boolean;
  isLast: boolean;
  canEdit: boolean;
  canEditProgress: boolean;
  userOptions: UserOption[];
  reorderPending: boolean;
  onSave: (patch: MilestoneUpdatePatch) => Promise<void>;
  onMove: (direction: -1 | 1) => void;
  onDuplicate: () => void;
  onDelete: () => void;
}

function stopRowClick(event: MouseEvent) {
  event.stopPropagation();
}

function hoursColor(actual: number, planned: number): string {
  if (planned <= 0) return designTokens.semantic.neutral;
  const pct = (actual / planned) * 100;
  if (pct > 100) return designTokens.semantic.danger;
  if (pct >= 90) return designTokens.semantic.warning;
  return designTokens.semantic.success;
}

export function ProjectMilestoneGridRow({
  row,
  isFirst,
  isLast,
  canEdit,
  canEditProgress,
  userOptions,
  reorderPending,
  onSave,
  onMove,
  onDuplicate,
  onDelete,
}: ProjectMilestoneGridRowProps) {
  const [nameAnchor, setNameAnchor] = useState<HTMLElement | null>(null);
  const [assigneeAnchor, setAssigneeAnchor] = useState<HTMLElement | null>(null);
  const [hoursAnchor, setHoursAnchor] = useState<HTMLElement | null>(null);
  const [targetAnchor, setTargetAnchor] = useState<HTMLElement | null>(null);
  const [statusAnchor, setStatusAnchor] = useState<HTMLElement | null>(null);
  const [progressAnchor, setProgressAnchor] = useState<HTMLElement | null>(null);
  const [actionsAnchor, setActionsAnchor] = useState<HTMLElement | null>(null);

  const [nameDraft, setNameDraft] = useState(row.name);
  const [plannedDraft, setPlannedDraft] = useState(String(row.planned_hours));
  const [dueDateDraft, setDueDateDraft] = useState(row.due_date ?? '');
  const [progressDraft, setProgressDraft] = useState(row.progress_percent);

  const canEditStatus = canEdit || canEditProgress;
  const isCompleted = row.status === 'completed';
  const assigneeLabel = row.assigned_user_name ?? 'Unassigned';
  const plannedHours = toFiniteNumber(row.planned_hours);
  const actualHours = toFiniteNumber(row.actual_hours);
  const hoursPct =
    plannedHours > 0 ? Math.round((actualHours / plannedHours) * 100) : null;

  const commitName = async () => {
    const trimmed = nameDraft.trim();
    setNameAnchor(null);
    if (!trimmed || trimmed === row.name) return;
    await onSave({ name: trimmed });
  };

  const commitPlannedHours = async () => {
    setHoursAnchor(null);
    const next = Number(plannedDraft);
    if (Number.isNaN(next) || next === row.planned_hours) return;
    await onSave({ planned_hours: next });
  };

  const commitDueDate = async () => {
    setTargetAnchor(null);
    const next = dueDateDraft || null;
    if (next === row.due_date) return;
    await onSave({ due_date: next });
  };

  const handleStatusChange = async (status: MilestoneStatus) => {
    setStatusAnchor(null);
    if (status === row.status) return;
    await onSave({ status });
  };

  const handleAssigneeChange = async (userId: string) => {
    setAssigneeAnchor(null);
    const next = userId || null;
    if (next === row.assigned_user_id) return;
    await onSave({ assigned_user_id: next });
  };

  const commitProgress = async (value: number) => {
    setProgressAnchor(null);
    if (value === row.progress_percent) return;
    await onSave({ progress_percent: value });
  };

  return (
    <TableRow hover>
      <StickyTableCell pinned sx={ROW_CELL_SX}>
        <Typography
          component="span"
          onClick={(event) => {
            if (!canEdit) return;
            setNameDraft(row.name);
            setNameAnchor(event.currentTarget);
          }}
          sx={{
            fontWeight: 700,
            cursor: canEdit ? 'pointer' : 'default',
            '&:hover': canEdit ? { color: 'primary.main' } : undefined,
            display: 'block',
            maxWidth: 220,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {row.name}
        </Typography>
        <Popover
          open={Boolean(nameAnchor)}
          anchorEl={nameAnchor}
          onClose={() => void commitName()}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        >
          <Box sx={{ p: 1.5, width: 260 }}>
            <TextField
              size="small"
              fullWidth
              autoFocus
              label="Milestone name"
              value={nameDraft}
              onChange={(event) => setNameDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void commitName();
              }}
            />
          </Box>
        </Popover>
      </StickyTableCell>

      <StickyTableCell sx={ROW_CELL_SX}>
        <Box
          onClick={(event) => {
            if (!canEdit) return;
            setAssigneeAnchor(event.currentTarget);
          }}
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.75,
            cursor: canEdit ? 'pointer' : 'default',
            maxWidth: 180,
          }}
        >
          <EntityAvatar label={assigneeLabel} size={24} />
          <Typography
            variant="body2"
            sx={{
              fontWeight: 600,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {assigneeLabel}
          </Typography>
        </Box>
        <Menu
          anchorEl={assigneeAnchor}
          open={Boolean(assigneeAnchor)}
          onClose={() => setAssigneeAnchor(null)}
          onClick={stopRowClick}
        >
          <MenuItem selected={!row.assigned_user_id} onClick={() => void handleAssigneeChange('')}>
            Unassigned
          </MenuItem>
          {userOptions.map((option) => (
            <MenuItem
              key={option.value}
              selected={row.assigned_user_id === option.value}
              onClick={() => void handleAssigneeChange(option.value)}
            >
              {option.label}
            </MenuItem>
          ))}
        </Menu>
      </StickyTableCell>

      <StickyTableCell align="right" sx={ROW_CELL_SX}>
        <Typography
          component="span"
          onClick={(event) => {
            if (!canEdit) return;
            setPlannedDraft(String(row.planned_hours));
            setHoursAnchor(event.currentTarget);
          }}
          sx={{
            fontWeight: 700,
            cursor: canEdit ? 'pointer' : 'default',
            color: hoursColor(actualHours, plannedHours),
            whiteSpace: 'nowrap',
          }}
        >
          {formatNumber(actualHours, 0) || '0'}/{formatNumber(plannedHours, 0) || '0'} hrs
          {hoursPct != null && Number.isFinite(hoursPct) ? ` (${hoursPct}%)` : ''}
        </Typography>
        <Popover
          open={Boolean(hoursAnchor)}
          anchorEl={hoursAnchor}
          onClose={() => void commitPlannedHours()}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <Box sx={{ p: 1.5, width: 180 }}>
            <TextField
              size="small"
              fullWidth
              type="number"
              label="Planned hours"
              value={plannedDraft}
              onChange={(event) => setPlannedDraft(event.target.value)}
              slotProps={{ htmlInput: { min: 0, step: 0.5 } }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void commitPlannedHours();
              }}
            />
          </Box>
        </Popover>
      </StickyTableCell>

      <StickyTableCell sx={ROW_CELL_SX}>
        <Typography
          component="span"
          onClick={(event) => {
            if (!canEdit) return;
            setDueDateDraft(row.due_date ?? '');
            setTargetAnchor(event.currentTarget);
          }}
          sx={{
            fontWeight: 600,
            cursor: canEdit ? 'pointer' : 'default',
            color: row.due_date ? 'text.primary' : 'text.secondary',
          }}
        >
          {row.due_date ? formatDate(row.due_date) : '—'}
        </Typography>
        <Popover
          open={Boolean(targetAnchor)}
          anchorEl={targetAnchor}
          onClose={() => void commitDueDate()}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        >
          <Box sx={{ p: 1.5 }}>
            <TextField
              size="small"
              type="date"
              label="Target date"
              value={dueDateDraft}
              onChange={(event) => setDueDateDraft(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Box>
        </Popover>
      </StickyTableCell>

      <StickyTableCell sx={ROW_CELL_SX}>
        {isCompleted ? (
          <Box
            onClick={(event) => {
              if (!canEditStatus) return;
              setStatusAnchor(event.currentTarget);
            }}
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.5,
              cursor: canEditStatus ? 'pointer' : 'default',
            }}
          >
            <CheckCircleRoundedIcon
              fontSize="small"
              sx={{ color: designTokens.semantic.success }}
            />
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {formatDate(row.completed_date ?? row.completed_at?.slice(0, 10))}
            </Typography>
          </Box>
        ) : (
          <Stack spacing={0.5} sx={{ minWidth: 140 }}>
            <Typography
              component="span"
              onClick={(event) => {
                if (!canEditStatus) return;
                setStatusAnchor(event.currentTarget);
              }}
              sx={{
                fontWeight: 700,
                cursor: canEditStatus ? 'pointer' : 'default',
                color: STATUS_COLORS[row.status],
                display: 'inline-block',
              }}
            >
              {STATUS_EMOJI[row.status]} {MILESTONE_STATUS_LABELS[row.status]}
            </Typography>
            <Box
              onClick={(event) => {
                if (!canEditStatus) return;
                setProgressDraft(row.progress_percent);
                setProgressAnchor(event.currentTarget);
              }}
              sx={{ cursor: canEditStatus ? 'pointer' : 'default' }}
            >
              <LinearProgress
                variant="determinate"
                value={row.progress_percent}
                sx={{
                  height: 5,
                  borderRadius: designTokens.radius.pill,
                  bgcolor: designTokens.semantic.neutralSoft,
                  '& .MuiLinearProgress-bar': {
                    borderRadius: designTokens.radius.pill,
                    bgcolor: STATUS_COLORS[row.status],
                  },
                }}
              />
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
                {row.progress_percent}%
              </Typography>
            </Box>
          </Stack>
        )}

        <Menu
          anchorEl={statusAnchor}
          open={Boolean(statusAnchor)}
          onClose={() => setStatusAnchor(null)}
          onClick={stopRowClick}
        >
          {STATUS_OPTIONS.map((status) => (
            <MenuItem
              key={status}
              selected={row.status === status}
              onClick={() => void handleStatusChange(status)}
            >
              <ListItemText>
                {STATUS_EMOJI[status]} {MILESTONE_STATUS_LABELS[status]}
              </ListItemText>
            </MenuItem>
          ))}
        </Menu>

        <Popover
          open={Boolean(progressAnchor)}
          anchorEl={progressAnchor}
          onClose={() => void commitProgress(progressDraft)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        >
          <Box sx={{ p: 2, width: 240 }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700, mb: 1, display: 'block' }}>
              Progress
            </Typography>
            <Slider
              size="small"
              value={progressDraft}
              step={25}
              marks={PROGRESS_STEPS.map((value) => ({ value, label: `${value}` }))}
              onChange={(_, value) => {
                const next = Array.isArray(value) ? value[0] : value;
                setProgressDraft(next);
              }}
              onChangeCommitted={(_, value) => {
                const next = Array.isArray(value) ? value[0] : value;
                void commitProgress(next);
              }}
            />
          </Box>
        </Popover>
      </StickyTableCell>

      {canEdit ? (
        <StickyTableCell align="center" sx={ROW_CELL_SX}>
          <IconButton
            size="small"
            aria-label="Milestone actions"
            onClick={(event) => {
              stopRowClick(event);
              setActionsAnchor(event.currentTarget);
            }}
          >
            <MoreVertRoundedIcon fontSize="small" />
          </IconButton>
          <Menu
            anchorEl={actionsAnchor}
            open={Boolean(actionsAnchor)}
            onClose={() => setActionsAnchor(null)}
            onClick={stopRowClick}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            slotProps={{ paper: { sx: { minWidth: 180, borderRadius: 2 } } }}
          >
            <MenuItem disabled={isFirst || reorderPending} onClick={() => { setActionsAnchor(null); onMove(-1); }}>
              <ListItemIcon>
                <ArrowUpwardIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Move up</ListItemText>
            </MenuItem>
            <MenuItem disabled={isLast || reorderPending} onClick={() => { setActionsAnchor(null); onMove(1); }}>
              <ListItemIcon>
                <ArrowDownwardIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Move down</ListItemText>
            </MenuItem>
            <MenuItem
              onClick={() => {
                setActionsAnchor(null);
                onDuplicate();
              }}
            >
              <ListItemIcon>
                <ContentCopyRoundedIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Duplicate</ListItemText>
            </MenuItem>
            <MenuItem
              onClick={() => {
                setActionsAnchor(null);
                onDelete();
              }}
              sx={{ color: 'error.main' }}
            >
              <ListItemIcon sx={{ color: 'error.main' }}>
                <DeleteOutlineRoundedIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Delete</ListItemText>
            </MenuItem>
          </Menu>
        </StickyTableCell>
      ) : null}
    </TableRow>
  );
}
