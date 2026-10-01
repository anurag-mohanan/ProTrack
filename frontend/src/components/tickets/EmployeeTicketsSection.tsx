import { Alert, Chip, Link, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { ticketsApi } from '../../api/tickets';
import { getErrorMessage } from '../../api/client';
import { formatDate } from '../../utils/format';
import { LoadingState } from '../common/LoadingState';
import { STATUS_COLOR, ticketHref } from './ticketConstants';

/** Tickets raised by or about an employee. Rows the viewer may not open are shown status-only. */
export function EmployeeTicketsSection({ userId, emptyMessage = 'No tickets for this employee.' }: { userId: string; emptyMessage?: string }) {
  const query = useQuery({
    queryKey: ['tickets', 'employee', userId],
    queryFn: () => ticketsApi.employee(userId),
    retry: false,
  });

  if (query.isLoading) return <LoadingState message="Loading tickets…" />;
  if (query.isError) {
    const status = (query.error as { response?: { status?: number } }).response?.status;
    if (status === 403) {
      return (
        <Typography variant="body2" color="text.secondary">
          You don&apos;t have access to this employee&apos;s tickets.
        </Typography>
      );
    }
    return <Alert severity="error">{getErrorMessage(query.error)}</Alert>;
  }
  const rows = query.data ?? [];
  if (rows.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        {emptyMessage}
      </Typography>
    );
  }

  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>Ticket</TableCell>
          <TableCell>Category</TableCell>
          <TableCell>Status</TableCell>
          <TableCell>Owner</TableCell>
          <TableCell>Due</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell sx={{ maxWidth: 320 }}>
              {row.can_open ? (
                <Link component={RouterLink} to={ticketHref(row.id)} sx={{ fontWeight: 600 }}>
                  {row.ticket_number}
                </Link>
              ) : (
                <Typography component="span" variant="body2" sx={{ fontWeight: 600 }}>
                  {row.ticket_number}
                </Typography>
              )}
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                {row.title}
                {row.relation === 'requester' ? ' · raised by employee' : ''}
              </Typography>
            </TableCell>
            <TableCell>{row.category_label}</TableCell>
            <TableCell>
              <Chip size="small" color={STATUS_COLOR[row.status] ?? 'default'} label={row.status_label} />
            </TableCell>
            <TableCell>{row.assignee_name ?? '—'}</TableCell>
            <TableCell>
              <Typography variant="body2" color={row.is_overdue ? 'error.main' : 'inherit'}>
                {row.due_date ? formatDate(row.due_date) : '—'}
                {row.is_overdue ? ' · overdue' : ''}
              </Typography>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
