import { useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MilestoneFormDialog } from './MilestoneFormDialog';
import { EmptyState } from '../common/EmptyState';
import { ErrorState } from '../common/ErrorState';
import { MilestoneStatusChip } from '../common/StatusChip';
import { LoadingState } from '../common/LoadingState';
import {
  deleteMilestone,
  getMilestones,
  milestoneQueryKeys,
} from '../../services/milestoneService';
import { invalidateProjectDetail } from '../../services/projectService';
import type { Milestone } from '../../types';
import { formatDate, formatDateTime } from '../../utils/format';

interface ProjectMilestonesTabProps {
  projectId: string;
}

export function ProjectMilestonesTab({ projectId }: ProjectMilestonesTabProps) {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editingMilestone, setEditingMilestone] = useState<Milestone | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Milestone | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: milestoneQueryKeys.byProject(projectId),
    queryFn: () => getMilestones({ project_id: projectId }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteMilestone,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: milestoneQueryKeys.byProject(projectId),
      });
      invalidateProjectDetail(queryClient, projectId);
      setDeleteTarget(null);
    },
  });

  const sortedMilestones = [...(data ?? [])].sort(
    (a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name),
  );

  if (isLoading) return <LoadingState message="Loading milestones…" />;
  if (error) return <ErrorState error={error} />;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography color="text.secondary">
          Manage project milestones and due dates
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setEditingMilestone(null);
            setFormOpen(true);
          }}
        >
          Create Milestone
        </Button>
      </Box>

      {!sortedMilestones.length ? (
        <EmptyState
          title="No milestones"
          description="Create milestones to track delivery progress."
        />
      ) : (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Milestone</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Due Date</TableCell>
                <TableCell>Completed Date</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedMilestones.map((milestone) => (
                <TableRow key={milestone.id} hover>
                  <TableCell>{milestone.name}</TableCell>
                  <TableCell>
                    <MilestoneStatusChip status={milestone.status} />
                  </TableCell>
                  <TableCell>{formatDate(milestone.due_date)}</TableCell>
                  <TableCell>{formatDateTime(milestone.completed_at)}</TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      aria-label="Edit milestone"
                      onClick={() => {
                        setEditingMilestone(milestone);
                        setFormOpen(true);
                      }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      aria-label="Delete milestone"
                      color="error"
                      onClick={() => setDeleteTarget(milestone)}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
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

      <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)}>
        <DialogTitle>Delete Milestone</DialogTitle>
        <DialogContent>
          Delete milestone <strong>{deleteTarget?.name}</strong>?
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
            onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
