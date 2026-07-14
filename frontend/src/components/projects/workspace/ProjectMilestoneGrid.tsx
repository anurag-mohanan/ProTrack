import { useMemo, useState } from 'react';
import { Box, TableRow, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog } from '../../common/ConfirmDialog';
import { EmptyState } from '../../common/EmptyState';
import { ErrorState } from '../../common/ErrorState';
import { LoadingState } from '../../common/LoadingState';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { OperationalDataTable, StickyHeaderCell } from '../../ui/design-system';
import { useToast } from '../../../context/ToastContext';
import { fetchUsers } from '../../../api/lookups';
import {
  createMilestone,
  deleteMilestone,
  getMilestoneSummary,
  getMilestones,
  milestoneQueryKeys,
  reorderMilestones,
  updateMilestone,
} from '../../../services/milestoneService';
import { invalidateMilestoneRelatedQueries } from '../../../utils/queryInvalidation';
import type { Milestone } from '../../../types';
import { ProjectMilestoneSummaryCard } from './ProjectMilestoneSummaryCard';
import { MilestoneAddDialog } from './MilestoneAddDialog';
import { ProjectMilestoneGridRow } from './ProjectMilestoneGridRow';

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

  const duplicateMutation = useMutation({
    mutationFn: (row: Milestone) =>
      createMilestone({
        project_id: projectId,
        name: `${row.name} (copy)`,
        description: row.description,
        planned_hours: row.planned_hours,
        assigned_user_id: row.assigned_user_id,
        due_date: row.due_date,
        status: 'not_started',
        progress_percent: 0,
        sort_order: row.sort_order + 1,
      }),
    onSuccess: () => {
      showSuccess('Milestone duplicated');
      refresh();
    },
    onError: (error: Error) => showError(error.message),
  });

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

  return (
    <Box>
      <ProjectMilestoneSummaryCard summary={summaryQuery.data} />

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          Set a Target date per milestone. Completion date is recorded when status becomes Completed.
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
          maxHeight="calc(100vh - 300px)"
          head={
            <TableRow>
              <StickyHeaderCell pinned>Milestone</StickyHeaderCell>
              <StickyHeaderCell>Assigned To</StickyHeaderCell>
              <StickyHeaderCell align="right">Hours</StickyHeaderCell>
              <StickyHeaderCell>Target date</StickyHeaderCell>
              <StickyHeaderCell>Status / Progress</StickyHeaderCell>
              {canEdit ? <StickyHeaderCell align="center">Actions</StickyHeaderCell> : null}
            </TableRow>
          }
        >
          {sortedMilestones.map((row, index) => (
            <ProjectMilestoneGridRow
              key={row.id}
              row={row}
              isFirst={index === 0}
              isLast={index === sortedMilestones.length - 1}
              canEdit={canEdit}
              canEditProgress={canEditProgress}
              userOptions={userOptions}
              reorderPending={reorderMutation.isPending}
              onSave={async (patch) => {
                await saveMutation.mutateAsync({ id: row.id, patch });
              }}
              onMove={(direction) => moveRow(index, direction)}
              onDuplicate={() => duplicateMutation.mutate(row)}
              onDelete={() => setDeleteTarget(row)}
            />
          ))}
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
        message={
          deleteTarget
            ? `Are you sure you want to delete "${deleteTarget.name}"? This cannot be undone.`
            : 'This cannot be undone.'
        }
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
      />
    </Box>
  );
}
