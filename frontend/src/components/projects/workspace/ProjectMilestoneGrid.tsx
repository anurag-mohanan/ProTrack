import { useMemo, useState } from 'react';
import {
  Box,
  IconButton,
  MenuItem,
  Select,
  Slider,
  Stack,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog } from '../../common/ConfirmDialog';
import { EmptyState } from '../../common/EmptyState';
import { ErrorState } from '../../common/ErrorState';
import { LoadingState } from '../../common/LoadingState';
import { MilestoneStatusChip } from '../../common/StatusChip';
import { ProsohmButton } from '../../ui/ProsohmButton';
import {
  FormSelect,
  OperationalDataTable,
  StickyHeaderCell,
  StickyTableCell,
} from '../../ui/design-system';
import { useToast } from '../../../context/ToastContext';
import { fetchUsers } from '../../../api/lookups';
import {
  deleteMilestone,
  getMilestoneSummary,
  getMilestones,
  milestoneQueryKeys,
  reorderMilestones,
  updateMilestone,
} from '../../../services/milestoneService';
import { invalidateMilestoneRelatedQueries } from '../../../utils/queryInvalidation';
import type { Milestone, MilestoneStatus } from '../../../types';
import { MILESTONE_STATUS_LABELS } from '../../../types/common';
import { formatDate, formatNumber } from '../../../utils/format';
import { ProjectMilestoneSummaryCard } from './ProjectMilestoneSummaryCard';
import { MilestoneAddDialog } from './MilestoneAddDialog';

const STATUS_OPTIONS: MilestoneStatus[] = [
  'not_started',
  'in_progress',
  'waiting',
  'on_hold',
  'completed',
  'cancelled',
];

const PROGRESS_STEPS = [0, 25, 50, 75, 100];

interface ProjectMilestoneGridProps {
  projectId: string;
  canEdit: boolean;
  canEditProgress: boolean;
}

export function ProjectMilestoneGrid({
  projectId,
  canEdit,
  canEditProgress,
}: ProjectMilestoneGridProps) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [addOpen, setAddOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Milestone | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Partial<Milestone>>>({});

  const milestonesQuery = useQuery({
    queryKey: milestoneQueryKeys.byProject(projectId),
    queryFn: () => getMilestones({ project_id: projectId, limit: 500 }),
  });

  const summaryQuery = useQuery({
    queryKey: [...milestoneQueryKeys.byProject(projectId), 'summary'],
    queryFn: () => getMilestoneSummary(projectId),
  });

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: fetchUsers,
  });

  const userOptions = useMemo(
    () =>
      (usersQuery.data ?? [])
        .filter((user) => user.is_active !== false)
        .map((user) => ({
          value: user.id,
          label: `${user.first_name} ${user.last_name}`.trim() || user.email,
        })),
    [usersQuery.data],
  );

  const sortedMilestones = useMemo(
    () =>
      [...(milestonesQuery.data ?? [])].sort(
        (a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name),
      ),
    [milestonesQuery.data],
  );

  const refresh = () => {
    invalidateMilestoneRelatedQueries(queryClient, projectId);
    void queryClient.invalidateQueries({
      queryKey: [...milestoneQueryKeys.byProject(projectId), 'summary'],
    });
  };

  const saveMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Parameters<typeof updateMilestone>[1] }) =>
      updateMilestone(id, patch),
    onSuccess: () => {
      refresh();
    },
    onError: (error: Error) => showError(error.message),
  });

  const reorderMutation = useMutation({
    mutationFn: (items: { id: string; sort_order: number }[]) =>
      reorderMilestones(projectId, items),
    onSuccess: () => refresh(),
    onError: (error: Error) => showError(error.message),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteMilestone,
    onSuccess: () => {
      showSuccess('Milestone deleted');
      setDeleteTarget(null);
      refresh();
    },
    onError: (error: Error) => showError(error.message),
  });

  const getDraftValue = <K extends keyof Milestone>(row: Milestone, key: K): Milestone[K] =>
    (drafts[row.id]?.[key] as Milestone[K] | undefined) ?? row[key];

  const setDraft = (id: string, patch: Partial<Milestone>) => {
    setDrafts((current) => ({ ...current, [id]: { ...current[id], ...patch } }));
  };

  const commitRow = async (row: Milestone) => {
    const draft = drafts[row.id];
    if (!draft || !Object.keys(draft).length) return;
    await saveMutation.mutateAsync({ id: row.id, patch: draft });
    setDrafts((current) => {
      const next = { ...current };
      delete next[row.id];
      return next;
    });
  };

  const moveRow = (index: number, direction: -1 | 1) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= sortedMilestones.length) return;
    const reordered = [...sortedMilestones];
    const [item] = reordered.splice(index, 1);
    reordered.splice(nextIndex, 0, item);
    reorderMutation.mutate(
      reordered.map((row, order) => ({ id: row.id, sort_order: order + 1 })),
    );
  };

  if (milestonesQuery.isLoading) return <LoadingState message="Loading milestones…" />;
  if (milestonesQuery.error) return <ErrorState error={milestonesQuery.error} />;
  if (!summaryQuery.data) return <LoadingState message="Loading summary…" />;

  const readOnly = !canEdit && !canEditProgress;

  return (
    <Box>
      {summaryQuery.data ? <ProjectMilestoneSummaryCard summary={summaryQuery.data} /> : null}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          Edit planned hours, assignments, and schedule inline. Press Enter or blur to save.
        </Typography>
        {canEdit ? (
          <ProsohmButton
            buttonVariant="primary"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setAddOpen(true)}
          >
            Add Milestone
          </ProsohmButton>
        ) : null}
      </Box>

      {!sortedMilestones.length ? (
        <EmptyState
          title="No milestones yet"
          description="Add milestones to build the project execution plan."
        />
      ) : (
        <OperationalDataTable
          maxHeight={560}
          head={
            <TableRow>
              <StickyHeaderCell pinned>#</StickyHeaderCell>
              <StickyHeaderCell pinned>Milestone</StickyHeaderCell>
              <StickyHeaderCell>Assigned To</StickyHeaderCell>
              <StickyHeaderCell align="right">Planned</StickyHeaderCell>
              <StickyHeaderCell align="right">Actual</StickyHeaderCell>
              <StickyHeaderCell>Target Date</StickyHeaderCell>
              <StickyHeaderCell>Completed</StickyHeaderCell>
              <StickyHeaderCell>Status</StickyHeaderCell>
              <StickyHeaderCell>Progress</StickyHeaderCell>
              {canEdit ? <StickyHeaderCell>Actions</StickyHeaderCell> : null}
            </TableRow>
          }
        >
          {sortedMilestones.map((row, index) => {
            const name = getDraftValue(row, 'name');
            const plannedHours = getDraftValue(row, 'planned_hours');
            const dueDate = getDraftValue(row, 'due_date');
            const status = getDraftValue(row, 'status');
            const progress = getDraftValue(row, 'progress_percent');
            const assignedUserId = getDraftValue(row, 'assigned_user_id');

            return (
              <TableRow key={row.id} hover>
                <StickyTableCell pinned>{index + 1}</StickyTableCell>
                <StickyTableCell pinned>
                  <TextField
                    size="small"
                    value={name}
                    disabled={readOnly || (!canEdit && !canEditProgress)}
                    onChange={(event) => setDraft(row.id, { name: event.target.value })}
                    onBlur={() => void commitRow(row)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') void commitRow(row);
                    }}
                    sx={{ minWidth: 180 }}
                  />
                </StickyTableCell>
                <StickyTableCell>
                  <FormSelect
                    label=""
                    size="small"
                    searchable
                    disabled={!canEdit}
                    value={assignedUserId ?? ''}
                    options={[{ value: '', label: 'Unassigned' }, ...userOptions]}
                    onChange={(event) => {
                      const value = String(event.target.value);
                      const patch = { assigned_user_id: value || null };
                      setDraft(row.id, patch);
                      void saveMutation.mutateAsync({
                        id: row.id,
                        patch: { assigned_user_id: value || null },
                      });
                    }}
                    sx={{ minWidth: 150 }}
                  />
                </StickyTableCell>
                <StickyTableCell align="right">
                  <TextField
                    size="small"
                    type="number"
                    disabled={!canEdit}
                    value={plannedHours}
                    onChange={(event) =>
                      setDraft(row.id, { planned_hours: Number(event.target.value) })
                    }
                    onBlur={() => void commitRow(row)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') void commitRow(row);
                    }}
                    slotProps={{ htmlInput: { min: 0, step: 0.5 } }}
                    sx={{ width: 90 }}
                  />
                </StickyTableCell>
                <StickyTableCell align="right">{formatNumber(row.actual_hours)}</StickyTableCell>
                <StickyTableCell>
                  <TextField
                    size="small"
                    type="date"
                    disabled={!canEdit}
                    value={dueDate ?? ''}
                    onChange={(event) =>
                      setDraft(row.id, { due_date: event.target.value || null })
                    }
                    onBlur={() => void commitRow(row)}
                    sx={{ width: 130 }}
                  />
                </StickyTableCell>
                <StickyTableCell>{formatDate(row.completed_date ?? row.completed_at)}</StickyTableCell>
                <StickyTableCell>
                  <Select
                    size="small"
                    disabled={!canEdit && !canEditProgress}
                    value={status}
                    onChange={(event) => {
                      const nextStatus = event.target.value as MilestoneStatus;
                      void saveMutation.mutateAsync({
                        id: row.id,
                        patch: { status: nextStatus },
                      });
                    }}
                    sx={{ minWidth: 120, fontSize: '0.8125rem' }}
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <MenuItem key={option} value={option}>
                        {MILESTONE_STATUS_LABELS[option]}
                      </MenuItem>
                    ))}
                  </Select>
                </StickyTableCell>
                <StickyTableCell>
                  <Stack spacing={0.5}>
                    <Slider
                      size="small"
                      disabled={!canEdit && !canEditProgress}
                      value={progress}
                      step={25}
                      marks={PROGRESS_STEPS.map((value) => ({ value, label: `${value}` }))}
                      onChange={(_, value) => {
                        const next = Array.isArray(value) ? value[0] : value;
                        setDraft(row.id, { progress_percent: next });
                      }}
                      onChangeCommitted={(_, value) => {
                        const next = Array.isArray(value) ? value[0] : value;
                        void saveMutation.mutateAsync({
                          id: row.id,
                          patch: { progress_percent: next },
                        });
                      }}
                    />
                    <MilestoneStatusChip status={status} />
                  </Stack>
                </StickyTableCell>
                {canEdit ? (
                  <StickyTableCell>
                    <Stack direction="row" spacing={0.25}>
                      <Tooltip title="Move up">
                        <span>
                          <IconButton
                            size="small"
                            disabled={index === 0 || reorderMutation.isPending}
                            onClick={() => moveRow(index, -1)}
                          >
                            <ArrowUpwardIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Move down">
                        <span>
                          <IconButton
                            size="small"
                            disabled={
                              index === sortedMilestones.length - 1 || reorderMutation.isPending
                            }
                            onClick={() => moveRow(index, 1)}
                          >
                            <ArrowDownwardIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Delete milestone">
                        <span>
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => setDeleteTarget(row)}
                          >
                            <DeleteOutlinedIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Stack>
                  </StickyTableCell>
                ) : null}
              </TableRow>
            );
          })}
        </OperationalDataTable>
      )}

      <MilestoneAddDialog
        open={addOpen}
        projectId={projectId}
        nextSortOrder={sortedMilestones.length + 1}
        userOptions={userOptions}
        onClose={() => setAddOpen(false)}
        onCreated={() => {
          setAddOpen(false);
          refresh();
        }}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete milestone?"
        message="This cannot be undone."
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
      />
    </Box>
  );
}
