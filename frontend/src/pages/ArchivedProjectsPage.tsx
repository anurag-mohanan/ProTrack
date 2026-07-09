import { useState } from 'react';
import { Grid, TableCell, TableRow } from '@mui/material';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { PageHeader } from '../components/common/PageHeader';
import { PageContainer } from '../components/common/PageContainer';
import { TableSkeleton } from '../components/common/TableSkeleton';
import { ContentCard } from '../components/ui/cards';
import {
  ClickableTableRow,
  DrawerQuickActions,
  FormField,
  FormSection,
  ProsohmTable,
  RecordDetailDrawer,
} from '../components/ui/design-system';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ProTrackPagination } from '../components/common/ProTrackPagination';
import { usePaginatedQuery } from '../hooks/usePaginatedQuery';
import {
  getArchivedProjectsPaginated,
  projectQueryKeys,
  restoreProject,
  softDeleteProject,
} from '../services/projectService';
import type { ArchivedProjectListItem } from '../types';
import { canSoftDeleteProject } from '../utils/permissions';
import { formatCellValue, formatDate } from '../utils/format';

export function ArchivedProjectsPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();
  const [selectedProject, setSelectedProject] = useState<ArchivedProjectListItem | null>(null);
  const [restoreId, setRestoreId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { pagination, query: archivedQuery, items: rows } = usePaginatedQuery({
    queryKey: projectQueryKeys.archived,
    fetcher: getArchivedProjectsPaginated,
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const restoreMutation = useMutation({
    mutationFn: restoreProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      showSuccess('Project restored to active list');
      setRestoreId(null);
      setSelectedProject(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const deleteMutation = useMutation({
    mutationFn: softDeleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      showSuccess('Project moved to Deleted Projects');
      setDeleteId(null);
      setSelectedProject(null);
    },
    onError: (error: Error) => showError(error.message),
  });

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
          <ProsohmTable
            head={
              <TableRow>
                <TableCell>Tool Number</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell>Project Type</TableCell>
                <TableCell>Completed Date</TableCell>
                <TableCell>Archived Date</TableCell>
                <TableCell>Design Leader</TableCell>
              </TableRow>
            }
          >
            {rows.map((project) => (
              <ClickableTableRow
                key={project.id}
                selected={selectedProject?.id === project.id}
                onClick={() => setSelectedProject(project)}
              >
                <TableCell>{project.tool_number}</TableCell>
                <TableCell>{project.customer_name}</TableCell>
                <TableCell>{formatCellValue(project.project_type_name) || '—'}</TableCell>
                <TableCell>
                  {project.completed_at ? formatDate(project.completed_at) : '—'}
                </TableCell>
                <TableCell>
                  {project.archived_at ? formatDate(project.archived_at) : '—'}
                </TableCell>
                <TableCell>{formatCellValue(project.design_leader_name) || '—'}</TableCell>
              </ClickableTableRow>
            ))}
          </ProsohmTable>
          <ProTrackPagination
            page={pagination.page}
            pageSize={pagination.pageSize}
            total={pagination.total}
            pages={pagination.pages}
            rangeStart={pagination.rangeStart}
            rangeEnd={pagination.rangeEnd}
            loading={archivedQuery.isFetching}
            onPageChange={pagination.goToPage}
            onPageSizeChange={pagination.setPageSize}
          />
        </ContentCard>
      )}

      <RecordDetailDrawer
        open={Boolean(selectedProject)}
        onClose={() => setSelectedProject(null)}
        title={selectedProject?.tool_number ?? 'Archived Project'}
        subtitle={selectedProject?.part_description}
        icon={FolderOutlinedIcon}
        quickActions={
          selectedProject ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => setRestoreId(selectedProject.id)}
              >
                Restore
              </ProsohmButton>
              {canDelete ? (
                <ProsohmButton
                  buttonVariant="danger"
                  size="small"
                  onClick={() => setDeleteId(selectedProject.id)}
                >
                  Delete
                </ProsohmButton>
              ) : null}
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedProject ? (
          <FormSection title="Overview" icon={FolderOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Customer"
                value={selectedProject.customer_name}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Project Type"
                value={formatCellValue(selectedProject.project_type_name) || '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Completed Date"
                value={selectedProject.completed_at ? formatDate(selectedProject.completed_at) : '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Archived Date"
                value={selectedProject.archived_at ? formatDate(selectedProject.archived_at) : '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormField
                label="Design Leader"
                value={formatCellValue(selectedProject.design_leader_name) || '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
          </FormSection>
        ) : null}
      </RecordDetailDrawer>

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
