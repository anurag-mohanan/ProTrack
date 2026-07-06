import { useState } from 'react';
import { TableCell, TableRow } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { TableSkeleton } from '../../components/common/TableSkeleton';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmTable } from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { useToast } from '../../context/ToastContext';
import {
  fetchDeletedTimesheetEntries,
  restoreTimesheetEntry,
  type TimesheetEntryDeletionLog,
} from '../../api/timesheets';
import { formatDate, formatNumber } from '../../utils/format';
import { invalidateTimesheetRelatedQueries } from '../../utils/queryInvalidation';

export default function DeletedTimesheetEntriesPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [restoreEntryId, setRestoreEntryId] = useState<string | null>(null);

  const deletedQuery = useQuery({
    queryKey: ['timesheet-entries', 'deleted'],
    queryFn: () => fetchDeletedTimesheetEntries({ limit: 500 }),
    staleTime: QUERY_STALE_TIMES.timesheetMonth,
  });

  const restoreMutation = useMutation({
    mutationFn: restoreTimesheetEntry,
    onSuccess: () => {
      invalidateTimesheetRelatedQueries(queryClient);
      void queryClient.invalidateQueries({ queryKey: ['timesheet-entries', 'deleted'] });
      showSuccess('Timesheet entry restored');
      setRestoreEntryId(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  if (deletedQuery.isLoading) {
    return (
      <PageContainer>
        <PageHeader title="Deleted Timesheet Entries" />
        <TableSkeleton rows={6} columns={7} />
      </PageContainer>
    );
  }

  if (deletedQuery.error) {
    return (
      <PageContainer>
        <ErrorState error={deletedQuery.error} onRetry={() => void deletedQuery.refetch()} />
      </PageContainer>
    );
  }

  const logs = deletedQuery.data ?? [];

  return (
    <PageContainer>
      <PageHeader
        title="Deleted Timesheet Entries"
        subtitle="Soft-deleted entries can be restored while the month is still in draft."
      />

      {!logs.length ? (
        <EmptyState
          title="No deleted entries"
          description="Deleted timesheet entries will appear here for audit and recovery."
        />
      ) : (
        <ContentCard noPadding>
          <ProsohmTable
            head={
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Designer</TableCell>
                <TableCell>Tool / NP</TableCell>
                <TableCell>Task</TableCell>
                <TableCell>Hours</TableCell>
                <TableCell>Deleted By</TableCell>
                <TableCell>Deleted</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            }
          >
            {logs.map((log: TimesheetEntryDeletionLog) => (
              <TableRow key={log.id} hover>
                <TableCell>{formatDate(log.entry_date)}</TableCell>
                <TableCell>{log.designer_name}</TableCell>
                <TableCell>{log.tool_number ?? '—'}</TableCell>
                <TableCell>{log.task_name ?? '—'}</TableCell>
                <TableCell>{formatNumber(log.hours, 1)}</TableCell>
                <TableCell>{log.deleted_by_name ?? '—'}</TableCell>
                <TableCell>{formatDate(log.deleted_at)}</TableCell>
                <TableCell>
                  <ProsohmButton
                    size="small"
                    onClick={() => setRestoreEntryId(log.entry_id)}
                  >
                    Restore
                  </ProsohmButton>
                </TableCell>
              </TableRow>
            ))}
          </ProsohmTable>
        </ContentCard>
      )}

      <ConfirmDialog
        open={Boolean(restoreEntryId)}
        title="Restore timesheet entry?"
        message="The entry will reappear in the designer's monthly timesheet."
        confirmLabel="Restore"
        onClose={() => setRestoreEntryId(null)}
        onConfirm={() => {
          if (restoreEntryId) restoreMutation.mutate(restoreEntryId);
        }}
        loading={restoreMutation.isPending}
      />
    </PageContainer>
  );
}
