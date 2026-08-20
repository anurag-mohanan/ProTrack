import { useMemo } from 'react';
import {
  Chip,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { fetchOpenItRequests, itOperationsKeys } from '../../api/itOperations';
import { ticketsApi } from '../../api/resources';
import { ContentCard } from '../../components/ui/cards';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import type { ITOpenRequest } from '../../types/itOperations';
import type { Ticket } from '../../types';

type ChipColor = 'default' | 'primary' | 'info' | 'warning' | 'error' | 'success';

const STATUS_COLOR: Record<string, ChipColor> = {
  open: 'info',
  in_progress: 'primary',
  on_hold: 'warning',
  resolved: 'success',
  closed: 'default',
  cancelled: 'default',
};

const PRIORITY_COLOR: Record<string, ChipColor> = {
  low: 'default',
  medium: 'info',
  high: 'warning',
  urgent: 'error',
};

function ticketToOpenRequest(ticket: Ticket): ITOpenRequest {
  return {
    id: ticket.id,
    ticket_number: ticket.ticket_number,
    title: ticket.title,
    status: ticket.status,
    status_label: ticket.status_label,
    priority: ticket.priority,
    requester_name: ticket.requester_name,
    assignee_name: ticket.assignee_name,
    created_at: ticket.created_at,
    category: ticket.category,
  };
}

function formatWhen(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

async function loadOpenItRequests(): Promise<ITOpenRequest[]> {
  try {
    return await fetchOpenItRequests();
  } catch {
    const tickets = await ticketsApi.list({ category: 'it', status: 'open' });
    const openish = tickets.filter((ticket) =>
      ['open', 'in_progress', 'on_hold'].includes(ticket.status),
    );
    return openish.map(ticketToOpenRequest);
  }
}

export function ITRequestsPage() {
  const query = useQuery({
    queryKey: itOperationsKeys.openRequests(),
    queryFn: loadOpenItRequests,
  });

  const rows = useMemo(() => query.data ?? [], [query.data]);

  if (query.isLoading) {
    return <LoadingState message="Loading IT requests…" />;
  }

  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        title="Unable to load IT requests"
        onRetry={() => void query.refetch()}
      />
    );
  }

  return (
    <PageContainer>
      <PageHeader
        title="IT Requests"
        subtitle="Open IT-category tickets from Help Desk."
        action={
          <ProsohmButton
            buttonVariant="outlined"
            component={RouterLink}
            to="/help-desk"
          >
            Open Help Desk
          </ProsohmButton>
        }
      />

      <ContentCard
        title="Open requests"
        subtitle={`${rows.length} open IT ticket${rows.length === 1 ? '' : 's'}`}
      >
        {rows.length === 0 ? (
          <EmptyState
            title="No open IT requests"
            description="New IT tickets appear here and in Help Desk."
          />
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Ticket</TableCell>
                <TableCell>Title</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Priority</TableCell>
                <TableCell>Requester</TableCell>
                <TableCell>Assignee</TableCell>
                <TableCell>Opened</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id} hover>
                  <TableCell>
                    <Link component={RouterLink} to="/help-desk" underline="hover">
                      {row.ticket_number || row.id.slice(0, 8)}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Typography sx={{ fontWeight: 600 }}>{row.title}</Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={row.status_label || String(row.status).replace(/_/g, ' ')}
                      color={STATUS_COLOR[row.status] ?? 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    {row.priority ? (
                      <Chip
                        size="small"
                        label={row.priority}
                        color={PRIORITY_COLOR[row.priority] ?? 'default'}
                        variant="outlined"
                      />
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell>{row.requester_name || '—'}</TableCell>
                  <TableCell>{row.assignee_name || '—'}</TableCell>
                  <TableCell>{formatWhen(row.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <Stack direction="row" justifyContent="flex-end" sx={{ mt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Manage full ticket workflows in{' '}
            <Link component={RouterLink} to="/help-desk">
              Help Desk
            </Link>
            .
          </Typography>
        </Stack>
      </ContentCard>
    </PageContainer>
  );
}
