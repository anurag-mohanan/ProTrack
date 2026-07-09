import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
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
import { usePagination } from '../../hooks/usePagination';
import { formatDateTime } from '../../utils/format';

export default function AuditLogsPage() {
  const pagination = usePagination();

  const query = useQuery({
    queryKey: ['audit-logs', pagination.params],
    queryFn: () => fetchAuditLogsPaginated(pagination.params),
  });

  useEffect(() => {
    if (query.data) {
      pagination.setTotal(query.data.total);
    }
  }, [query.data, pagination.setTotal]);

  if (query.isLoading && !query.data) {
    return <LoadingState message="Loading audit logs…" />;
  }

  const rows = query.data?.items ?? [];

  return (
    <Box>
      <PageHeader
        title="Audit Logs"
        subtitle="System activity including project edits, assignments, imports, and authentication events"
      />
      {rows.length === 0 ? (
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
