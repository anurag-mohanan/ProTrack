import { useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { EmptyState } from '../../components/common/EmptyState';
import { ProTrackPagination } from '../../components/common/ProTrackPagination';
import { fetchEmailQueuePaginated, processEmailQueue } from '../../api/communication';
import type { EmailMessage } from '../../api/communication';
import { useToast } from '../../context/ToastContext';
import { usePaginatedQuery } from '../../hooks/usePaginatedQuery';

const STATUS_COLORS: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  queued: 'warning',
  sending: 'info',
  sent: 'success',
  failed: 'error',
};

export default function EmailQueuePage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selected, setSelected] = useState<EmailMessage | null>(null);

  const listFilters = useMemo(
    () => ({
      status: statusFilter || undefined,
      search: search || undefined,
    }),
    [search, statusFilter],
  );

  const { pagination, query, items: rows, isEmpty } = usePaginatedQuery({
    queryKey: ['emails', 'queue'],
    fetcher: fetchEmailQueuePaginated,
    filters: listFilters,
  });

  const processMutation = useMutation({
    mutationFn: processEmailQueue,
    onSuccess: (result) => {
      showSuccess(`Processed ${result.processed} queued email(s)`);
      void queryClient.invalidateQueries({ queryKey: ['emails', 'queue'] });
    },
    onError: (error: Error) => showError(error.message),
  });

  if (query.isLoading && !query.data) {
    return <LoadingState message="Loading email queue…" />;
  }

  return (
    <Box>
      <PageHeader
        title="Outgoing Mail Queue"
        subtitle="Queued, sending, sent, and failed messages with retry status"
      />
      <ContentCard title="Queue">
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 2 }}>
          <TextField
            size="small"
            label="Search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <TextField
            size="small"
            label="Status filter"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            placeholder="queued, sent, failed"
          />
          <ProsohmButton
            buttonVariant="outlined"
            onClick={() => processMutation.mutate()}
            loading={processMutation.isPending}
          >
            Process Queue / Retry
          </ProsohmButton>
        </Stack>
        {isEmpty ? (
          <EmptyState
            title="No emails in queue"
            description="Try adjusting your filters or process the queue to send pending messages."
          />
        ) : (
          <>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Recipient</TableCell>
                  <TableCell>Subject</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Retries</TableCell>
                  <TableCell>Last error</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((message) => (
                  <TableRow
                    key={message.id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => setSelected(message)}
                  >
                    <TableCell>{new Date(message.created_at).toLocaleString()}</TableCell>
                    <TableCell>{message.recipients_display}</TableCell>
                    <TableCell>{message.subject}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={message.status}
                        color={STATUS_COLORS[message.status] ?? 'default'}
                      />
                    </TableCell>
                    <TableCell>
                      {message.retry_count}/{message.max_retries}
                    </TableCell>
                    <TableCell>{message.last_error ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
      </ContentCard>

      <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} maxWidth="md" fullWidth>
        <DialogTitle>{selected?.subject}</DialogTitle>
        <DialogContent>
          {selected ? (
            <Box>
              <Typography variant="body2" sx={{ mb: 1 }}>
                To: {selected.recipients_display}
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                SMTP: {selected.smtp_response ?? '—'}
              </Typography>
              <Box
                sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 2 }}
                dangerouslySetInnerHTML={{ __html: selected.body_html }}
              />
            </Box>
          ) : null}
        </DialogContent>
      </Dialog>
    </Box>
  );
}
