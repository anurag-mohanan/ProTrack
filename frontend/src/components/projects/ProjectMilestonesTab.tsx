import { useState } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ReplayIcon from '@mui/icons-material/Replay';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import { MilestoneFormDialog } from './MilestoneFormDialog';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { EmptyState } from '../common/EmptyState';
import { ErrorState } from '../common/ErrorState';
import { MilestoneStatusChip } from '../common/StatusChip';
import { LoadingState } from '../common/LoadingState';
import { useToast } from '../../context/ToastContext';
import {
  completeMilestone,
  deleteMilestone,
  getMilestones,
  milestoneQueryKeys,
  reopenMilestone,
} from '../../services/milestoneService';
import { invalidateMilestoneRelatedQueries } from '../../utils/queryInvalidation';
import type { Milestone } from '../../types';
import { formatDate, formatDateTime } from '../../utils/format';

interface ProjectMilestonesTabProps {
  projectId: string;
}

type PendingAction = {
  milestoneId: string;
  action: 'complete' | 'reopen' | 'delete';
};

export function ProjectMilestonesTab({ projectId }: ProjectMilestonesTabProps) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [formOpen, setFormOpen] = useState(false);
  const [editingMilestone, setEditingMilestone] = useState<Milestone | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Milestone | null>(null);
  const [qaCompleteTarget, setQaCompleteTarget] = useState<Milestone | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: milestoneQueryKeys.byProject(projectId),
    queryFn: () => getMilestones({ project_id: projectId }),
  });

  const refreshRelatedQueries = () => {
    invalidateMilestoneRelatedQueries(queryClient, projectId);
  };

  const completeMutation = useMutation({
    mutationFn: ({
      milestoneId,
      qaAcknowledged,
    }: {
      milestoneId: string;
      qaAcknowledged?: boolean;
    }) => completeMilestone(milestoneId, { qaAcknowledged }),
    onMutate: ({ milestoneId }) => {
      setPendingAction({ milestoneId, action: 'complete' });
    },
    onSuccess: () => {
      refreshRelatedQueries();
      showSuccess('Milestone marked as completed');
      setQaCompleteTarget(null);
    },
    onError: (err) => showError(getErrorMessage(err)),
    onSettled: () => setPendingAction(null),
  });

  const reopenMutation = useMutation({
    mutationFn: reopenMilestone,
    onMutate: (milestoneId) => {
      setPendingAction({ milestoneId, action: 'reopen' });
    },
    onSuccess: () => {
      refreshRelatedQueries();
      showSuccess('Milestone reopened');
    },
    onError: (err) => showError(getErrorMessage(err)),
    onSettled: () => setPendingAction(null),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteMilestone,
    onMutate: (milestoneId) => {
      setPendingAction({ milestoneId, action: 'delete' });
    },
    onSuccess: () => {
      refreshRelatedQueries();
      showSuccess('Milestone deleted');
      setDeleteTarget(null);
    },
    onError: (err) => showError(getErrorMessage(err)),
    onSettled: () => setPendingAction(null),
  });

  const sortedMilestones = [...(data ?? [])].sort(
    (a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name),
  );

  const isRowPending = (milestoneId: string) =>
    pendingAction?.milestoneId === milestoneId;

  const requestComplete = (milestone: Milestone) => {
    if (milestone.qa_gate_required) {
      setQaCompleteTarget(milestone);
      return;
    }
    completeMutation.mutate({ milestoneId: milestone.id });
  };

  if (isLoading) return <LoadingState message="Loading milestones…" />;
  if (error) return <ErrorState error={error} />;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, gap: 2 }}>
        <Typography color="text.secondary">
          Track delivery milestones, due dates, and completion status
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setEditingMilestone(null);
            setFormOpen(true);
          }}
        >
          Add Milestone
        </Button>
      </Box>

      {!sortedMilestones.length ? (
        <EmptyState
          title="No milestones yet"
          description="Add milestones to track project delivery progress."
        />
      ) : (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Due Date</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Completed Date</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedMilestones.map((milestone) => {
                const rowPending = isRowPending(milestone.id);
                const canComplete =
                  milestone.status !== 'completed' &&
                  milestone.status !== 'not_applicable';
                const canReopen = milestone.status === 'completed';

                return (
                  <TableRow key={milestone.id} hover>
                    <TableCell>
                      <Box>
                        <Typography sx={{ fontWeight: 600 }}>{milestone.name}</Typography>
                        {milestone.description ? (
                          <Typography variant="caption" color="text.secondary">
                            {milestone.description}
                          </Typography>
                        ) : null}
                      </Box>
                    </TableCell>
                    <TableCell>{formatDate(milestone.due_date)}</TableCell>
                    <TableCell>
                      <MilestoneStatusChip status={milestone.status} />
                    </TableCell>
                    <TableCell>{formatDateTime(milestone.completed_at)}</TableCell>
                    <TableCell align="right">
                      {rowPending ? (
                        <CircularProgress size={20} sx={{ mr: 1 }} />
                      ) : null}
                      <Stack
                        direction="row"
                        spacing={0.5}
                        sx={{ justifyContent: 'flex-end', flexWrap: 'wrap' }}
                      >
                        {canComplete ? (
                          <Tooltip
                            title={
                              milestone.qa_gate_required
                                ? 'Complete (QA acknowledgement required)'
                                : 'Complete milestone'
                            }
                          >
                            <span>
                              <Button
                                size="small"
                                color="success"
                                variant="outlined"
                                startIcon={<TaskAltIcon />}
                                disabled={Boolean(pendingAction)}
                                onClick={() => requestComplete(milestone)}
                              >
                                Complete
                              </Button>
                            </span>
                          </Tooltip>
                        ) : null}
                        {canReopen ? (
                          <Tooltip title="Reopen milestone">
                            <span>
                              <Button
                                size="small"
                                variant="outlined"
                                startIcon={<ReplayIcon />}
                                disabled={Boolean(pendingAction)}
                                onClick={() => reopenMutation.mutate(milestone.id)}
                              >
                                Reopen
                              </Button>
                            </span>
                          </Tooltip>
                        ) : null}
                        <Tooltip title="Edit milestone">
                          <span>
                            <IconButton
                              size="small"
                              aria-label="Edit milestone"
                              disabled={Boolean(pendingAction)}
                              onClick={() => {
                                setEditingMilestone(milestone);
                                setFormOpen(true);
                              }}
                            >
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                        <Tooltip title="Delete milestone">
                          <span>
                            <IconButton
                              size="small"
                              aria-label="Delete milestone"
                              color="error"
                              disabled={Boolean(pendingAction)}
                              onClick={() => setDeleteTarget(milestone)}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                      </Stack>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <MilestoneFormDialog
        open={formOpen}
        onClose={() => {
          setFormOpen(false);
          setEditingMilestone(null);
        }}
        projectId={projectId}
        milestone={editingMilestone}
      />

      <ConfirmDialog
        open={Boolean(qaCompleteTarget)}
        title="QA acknowledgement"
        message={
          qaCompleteTarget
            ? `QA gate is enabled for this project. Confirm that QA checks are complete for "${qaCompleteTarget.name}" before marking it done.`
            : ''
        }
        confirmLabel="Acknowledge & complete"
        loading={completeMutation.isPending}
        onClose={() => setQaCompleteTarget(null)}
        onConfirm={() =>
          qaCompleteTarget &&
          completeMutation.mutate({
            milestoneId: qaCompleteTarget.id,
            qaAcknowledged: true,
          })
        }
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete Milestone"
        message={
          deleteTarget
            ? `Are you sure you want to delete "${deleteTarget.name}"? This action cannot be undone.`
            : ''
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
