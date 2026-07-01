import { useState } from 'react';
import {
  Box,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from '@mui/material';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
import RestoreIcon from '@mui/icons-material/Restore';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { PageHeader } from '../../components/common/PageHeader';
import { TableSkeleton } from '../../components/common/TableSkeleton';
import { ContentCard } from '../../components/ui/cards';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { useToast } from '../../context/ToastContext';
import {
  getDeletedProjects,
  getProjectDeleteCheck,
  permanentDeleteProject,
  projectQueryKeys,
  restoreDeletedProject,
} from '../../services/projectService';
import { formatDate } from '../../utils/format';
import { EXECUTION_STATUS_LABELS } from '../../types/common';

export default function DeletedProjectsPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [restoreId, setRestoreId] = useState<string | null>(null);
  const [permanentId, setPermanentId] = useState<string | null>(null);
  const [blockers, setBlockers] = useState<string[]>([]);

  const deletedQuery = useQuery({
    queryKey: projectQueryKeys.deleted,
    queryFn: () => getDeletedProjects({ limit: 500 }),
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const restoreMutation = useMutation({
    mutationFn: restoreDeletedProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      showSuccess('Project restored');
      setRestoreId(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const permanentMutation = useMutation({
    mutationFn: permanentDeleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      showSuccess('Project permanently deleted');
      setPermanentId(null);
      setBlockers([]);
    },
    onError: (error: Error) => showError(error.message),
  });

  async function openPermanentDelete(projectId: string) {
    try {
      const check = await getProjectDeleteCheck(projectId);
      setBlockers(check.blockers);
      setPermanentId(projectId);
    } catch (error) {
      showError(
        error instanceof Error ? error.message : 'Unable to check delete eligibility',
      );
    }
  }

  if (deletedQuery.error) return <ErrorState error={deletedQuery.error} />;

  return (
    <Box>
      <PageHeader
        title="Deleted Projects"
        subtitle="Admin-only recovery and permanent deletion for soft-deleted projects"
      />

      {deletedQuery.isPending ? (
        <ContentCard noPadding>
          <TableSkeleton rows={6} columns={5} />
        </ContentCard>
      ) : !deletedQuery.data?.length ? (
        <EmptyState title="No deleted projects" />
      ) : (
        <ContentCard noPadding>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Tool Number</TableCell>
                  <TableCell>Code</TableCell>
                  <TableCell>Deleted Date</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {deletedQuery.data.map((project) => (
                  <TableRow key={project.id} hover>
                    <TableCell>{project.tool_number}</TableCell>
                    <TableCell>{project.code}</TableCell>
                    <TableCell>
                      {project.deleted_at ? formatDate(project.deleted_at) : '—'}
                    </TableCell>
                    <TableCell>
                      {EXECUTION_STATUS_LABELS[project.execution_status]}
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="View">
                        <IconButton
                          size="small"
                          component={RouterLink}
                          to={`/projects/${project.id}`}
                        >
                          <VisibilityIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Restore">
                        <IconButton
                          size="small"
                          onClick={() => setRestoreId(project.id)}
                        >
                          <RestoreIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Permanent delete">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => openPermanentDelete(project.id)}
                        >
                          <DeleteForeverIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </ContentCard>
      )}

      <ConfirmDialog
        open={restoreId !== null}
        title="Restore deleted project?"
        message="The project will be visible again in normal project lists."
        confirmLabel="Restore"
        loading={restoreMutation.isPending}
        onClose={() => setRestoreId(null)}
        onConfirm={() => restoreId && restoreMutation.mutate(restoreId)}
      />

      <ConfirmDialog
        open={permanentId !== null}
        title="Permanently delete project?"
        message={
          blockers.length
            ? `Cannot permanently delete: ${blockers.join(', ')} still exist.`
            : 'This action cannot be undone. The project record will be removed from the database.'
        }
        confirmLabel="Permanent Delete"
        loading={permanentMutation.isPending}
        onClose={() => {
          setPermanentId(null);
          setBlockers([]);
        }}
        onConfirm={() => {
          if (blockers.length) {
            setPermanentId(null);
            return;
          }
          if (permanentId) permanentMutation.mutate(permanentId);
        }}
      />
    </Box>
  );
}
