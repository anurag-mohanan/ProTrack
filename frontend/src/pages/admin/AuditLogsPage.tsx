import { useQuery } from '@tanstack/react-query';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { fetchAuditLogs } from '../../api/activities';
import { formatDateTime } from '../../utils/format';

export default function AuditLogsPage() {
  const query = useQuery({
    queryKey: ['audit-logs'],
    queryFn: () => fetchAuditLogs({ limit: 200 }),
  });

  if (query.isLoading) return <LoadingState message="Loading audit logs…" />;

  return (
    <Box>
      <PageHeader
        title="Audit Logs"
        subtitle="System activity including project edits, assignments, imports, and authentication events"
      />
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
            {(query.data ?? []).map((row) => (
              <TableRow key={row.id}>
                <TableCell>{formatDateTime(row.created_at)}</TableCell>
                <TableCell>{row.user_name ?? '—'}</TableCell>
                <TableCell>{row.action}</TableCell>
                <TableCell>{row.entity_type ?? '—'}</TableCell>
                <TableCell sx={{ maxWidth: 240, whiteSpace: 'pre-wrap' }}>{row.old_value ?? '—'}</TableCell>
                <TableCell sx={{ maxWidth: 240, whiteSpace: 'pre-wrap' }}>{row.new_value ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
