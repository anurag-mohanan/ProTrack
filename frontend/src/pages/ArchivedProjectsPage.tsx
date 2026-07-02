import { useMemo, useState } from 'react';
import {
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import RestoreIcon from '@mui/icons-material/Restore';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { PageHeader } from '../components/common/PageHeader';
import { PageContainer } from '../components/common/PageContainer';
import { TableSkeleton } from '../components/common/TableSkeleton';
import { ContentCard } from '../components/ui/cards';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import {
  getArchivedProjects,
  projectQueryKeys,
  restoreProject,
  softDeleteProject,
} from '../services/projectService';
import { canSoftDeleteProject } from '../utils/permissions';
import { formatDate } from '../utils/format';

export function ArchivedProjectsPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();
  const [restoreId, setRestoreId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const archivedQuery = useQuery({
    queryKey: projectQueryKeys.archived,
    queryFn: () => getArchivedProjects({ limit: 500 }),
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const restoreMutation = useMutation({
    mutationFn: restoreProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      showSuccess('Project restored to active list');
      setRestoreId(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const deleteMutation = useMutation({
    mutationFn: softDeleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      showSuccess('Project moved to Deleted Projects');
      setDeleteId(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const rows = useMemo(() => archivedQuery.data ?? [], [archivedQuery.data]);
  const canDelete = canSoftDeleteProject(user?.role_name ?? '');

  if (archivedQuery.error) return <ErrorState error={archivedQuery.error} />;

  return (
    <PageContainer>
      <PageHeader
        title="Archived Projects"
        subtitle="Completed or closed projects kept for history and reporting"
      />

      {archivedQuery.isPending ? (
        <ContentCard noPadding>
          <TableSkeleton rows={8} columns={7} />
        </ContentCard>
      ) : !rows.length ? (
        <EmptyState title="No archived projects" />
      ) : (
        <ContentCard noPadding>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Tool Number</TableCell>
                  <TableCell>Customer</TableCell>
                  <TableCell>Project Type</TableCell>
                  <TableCell>Completed Date</TableCell>
                  <TableCell>Archived Date</TableCell>
                  <TableCell>Design Leader</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((project) => (
                  <TableRow key={project.id} hover>
                    <TableCell>{project.tool_number}</TableCell>
                    <TableCell>{project.customer_name}</TableCell>
                    <TableCell>{project.project_type_name ?? '—'}</TableCell>
                    <TableCell>
                      {project.completed_at ? formatDate(project.completed_at) : '—'}
                    </TableCell>
                    <TableCell>
                      {project.archived_at ? formatDate(project.archived_at) : '—'}
                    </TableCell>
                    <TableCell>{project.design_leader_name}</TableCell>
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
                      {canDelete ? (
                        <Tooltip title="Delete">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => setDeleteId(project.id)}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      ) : null}
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
        title="Restore project?"
        message="This project will return to the active projects list."
        confirmLabel="Restore"
        loading={restoreMutation.isPending}
        onClose={() => setRestoreId(null)}
        onConfirm={() => restoreId && restoreMutation.mutate(restoreId)}
      />

      <ConfirmDialog
        open={deleteId !== null}
        title="Delete project?"
        message="The project will be soft-deleted and hidden from normal views. Admins can restore it from Deleted Projects."
        confirmLabel="Delete"
        loading={deleteMutation.isPending}
        onClose={() => setDeleteId(null)}
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
      />
    </PageContainer>
  );
}
