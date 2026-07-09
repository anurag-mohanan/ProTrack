import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { EmptyState } from '../../components/common/EmptyState';
import { ProTrackPagination } from '../../components/common/ProTrackPagination';
import { fetchAuditLogsPaginated } from '../../api/activities';
import { usePaginatedQuery } from '../../hooks/usePaginatedQuery';
import { formatDateTime } from '../../utils/format';

export default function AuditLogsPage() {
  const { pagination, query, items: rows, isEmpty } = usePaginatedQuery({
    queryKey: ['audit-logs'],
    fetcher: fetchAuditLogsPaginated,
  });

  if (query.isLoading && !query.data) {
    return <LoadingState message="Loading audit logs…" />;
  }

  return (
    <Box>
      <PageHeader
        title="Audit Logs"
        subtitle="System activity including project edits, assignments, imports, and authentication events"
      />
      {isEmpty ? (
        <EmptyState
          title="No audit logs found"
          description="Activity will appear here as users work in ProTrack."
        />
      ) : (
        <>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>When</TableCell>
                  <TableCell>User</TableCell>
                  <TableCell>Action</TableCell>
                  <TableCell>Entity</TableCell>
                  <TableCell>Old value</TableCell>
                  <TableCell>New value</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{formatDateTime(row.created_at)}</TableCell>
                    <TableCell>{row.user_name ?? '—'}</TableCell>
                    <TableCell>{row.action}</TableCell>
                    <TableCell>{row.entity_type ?? '—'}</TableCell>
                    <TableCell sx={{ maxWidth: 240, whiteSpace: 'pre-wrap' }}>
                      {row.old_value ?? '—'}
                    </TableCell>
                    <TableCell sx={{ maxWidth: 240, whiteSpace: 'pre-wrap' }}>
                      {row.new_value ?? '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <ProTrackPagination
            page={pagination.page}
            pageSize={pagination.pageSize}
            total={pagination.total}
            pages={pagination.pages}
            rangeStart={pagination.rangeStart}
            rangeEnd={pagination.rangeEnd}
            loading={query.isFetching}
            onPageChange={pagination.goToPage}
            onPageSizeChange={pagination.setPageSize}
          />
        </>
      )}
    </Box>
  );
}
