import { useState } from 'react';
import { Grid, TableCell, TableRow } from '@mui/material';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { DeleteRecordDialog, type DeleteCheckResult } from '../../components/ui/design-system/DeleteRecordDialog';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { TableSkeleton } from '../../components/common/TableSkeleton';
import { ContentCard } from '../../components/ui/cards';
import {
  ClickableTableRow,
  DrawerQuickActions,
  FormField,
  FormSection,
  ProsohmTable,
  RecordDetailDrawer,
} from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { useToast } from '../../context/ToastContext';
import {
  getDeletedProjects,
  getProjectDeleteCheck,
  permanentDeleteProject,
  projectQueryKeys,
  restoreDeletedProject,
} from '../../services/projectService';
import type { Project } from '../../types';
import { formatDate, formatDisplayValue } from '../../utils/format';
import { EXECUTION_STATUS_LABELS } from '../../types/common';

export default function DeletedProjectsPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [restoreId, setRestoreId] = useState<string | null>(null);
  const [permanentId, setPermanentId] = useState<string | null>(null);
  const [permanentCheck, setPermanentCheck] = useState<DeleteCheckResult | null>(null);

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
      setSelectedProject(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const permanentMutation = useMutation({
    mutationFn: permanentDeleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      showSuccess('Project permanently deleted');
      setPermanentId(null);
      setPermanentCheck(null);
      setSelectedProject(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  async function openPermanentDelete(projectId: string, projectCode: string) {
    try {
      const check = await getProjectDeleteCheck(projectId);
      setPermanentCheck({
        can_delete: check.can_permanently_delete,
        blockers: check.blockers,
        record_name: projectCode,
        record_type: 'Project',
        related_records: check.blockers,
      });
      setPermanentId(projectId);
    } catch (error) {
      showError(
        error instanceof Error ? error.message : 'Unable to check delete eligibility',
      );
    }
  }

  if (deletedQuery.error) return <ErrorState error={deletedQuery.error} />;

  return (
    <PageContainer>
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
          <ProsohmTable
            head={
              <TableRow>
                <TableCell>Tool Number</TableCell>
                <TableCell>Code</TableCell>
                <TableCell>Deleted Date</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            }
          >
            {deletedQuery.data.map((project) => (
              <ClickableTableRow
                key={project.id}
                selected={selectedProject?.id === project.id}
                onClick={() => setSelectedProject(project)}
              >
                <TableCell>{formatDisplayValue(project.tool_number)}</TableCell>
                <TableCell>{formatDisplayValue(project.code)}</TableCell>
                <TableCell>
                  {project.deleted_at ? formatDate(project.deleted_at) : '—'}
                </TableCell>
                <TableCell>
                  {EXECUTION_STATUS_LABELS[project.execution_status]}
                </TableCell>
              </ClickableTableRow>
            ))}
          </ProsohmTable>
        </ContentCard>
      )}

      <RecordDetailDrawer
        open={Boolean(selectedProject)}
        onClose={() => setSelectedProject(null)}
        title={selectedProject?.tool_number ?? 'Deleted Project'}
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
              <ProsohmButton
                buttonVariant="danger"
                size="small"
                onClick={() => openPermanentDelete(selectedProject.id, selectedProject.code)}
              >
                Delete Permanently
              </ProsohmButton>
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedProject ? (
          <FormSection title="Overview" icon={FolderOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Project Code"
                value={selectedProject.code}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Deleted Date"
                value={selectedProject.deleted_at ? formatDate(selectedProject.deleted_at) : '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormField
                label="Status"
                value={EXECUTION_STATUS_LABELS[selectedProject.execution_status]}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
          </FormSection>
        ) : null}
      </RecordDetailDrawer>

      <ConfirmDialog
        open={restoreId !== null}
        title="Restore deleted project?"
        message="The project will be visible again in normal project lists."
        confirmLabel="Restore"
        loading={restoreMutation.isPending}
        onClose={() => setRestoreId(null)}
        onConfirm={() => restoreId && restoreMutation.mutate(restoreId)}
      />

      <DeleteRecordDialog
        open={permanentId !== null}
        check={permanentCheck}
        loading={permanentMutation.isPending}
        onClose={() => {
          setPermanentId(null);
          setPermanentCheck(null);
        }}
        onConfirm={() => {
          if (permanentCheck && !permanentCheck.can_delete) {
            setPermanentId(null);
            return;
          }
          if (permanentId) permanentMutation.mutate(permanentId);
        }}
        showDeactivate={false}
      />
    </PageContainer>
  );
}
