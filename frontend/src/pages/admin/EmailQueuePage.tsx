import { useState } from 'react';
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { fetchEmailQueue, processEmailQueue } from '../../api/communication';
import type { EmailMessage } from '../../api/communication';
import { useToast } from '../../context/ToastContext';

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

  const query = useQuery({
    queryKey: ['emails', 'queue', statusFilter, search],
    queryFn: () => fetchEmailQueue({ status: statusFilter || undefined, search: search || undefined }),
  });

  const processMutation = useMutation({
    mutationFn: processEmailQueue,
    onSuccess: (result) => {
      showSuccess(`Processed ${result.processed} queued email(s)`);
      void queryClient.invalidateQueries({ queryKey: ['emails', 'queue'] });
    },
    onError: (error: Error) => showError(error.message),
  });

  if (query.isLoading) return <LoadingState message="Loading email queue…" />;

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
            {(query.data ?? []).map((message) => (
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
