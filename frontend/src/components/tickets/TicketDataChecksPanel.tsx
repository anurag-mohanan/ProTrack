import {
  Alert,
  Box,
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { ticketsApi } from '../../api/tickets';
import { getErrorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { LoadingState } from '../common/LoadingState';
import { ContentCard } from '../ui/cards';
import { ProsohmButton } from '../ui/ProsohmButton';
import { ticketHref } from './ticketConstants';

const KIND_LABELS: Record<string, string> = {
  legacy_grouped: 'Shared legacy ticket',
  needs_owner: 'Ticket without owner',
  task_request_missing: 'Task missing its ticket',
  task_link_broken: 'Broken ticket link',
  task_request_resolved: 'Ticket done, task open',
  task_request_cancelled: 'Ticket cancelled, task open',
  task_legacy_grouped: 'Task on shared legacy ticket',
};

const TOTAL_LABELS: Record<string, string> = {
  tickets: 'Tickets',
  open: 'Open',
  overdue: 'Overdue',
  sla_breached: 'Resolved after SLA',
  avg_first_response_hours: 'Avg first response (h)',
  avg_resolution_hours: 'Avg resolution (h)',
  needs_owner: 'Needs owner',
  needs_review: 'Needs review',
};

/** Records that need repair (legacy links, ownerless tickets, out-of-sync tasks) plus workload totals. */
export function TicketDataChecksPanel({ category }: { category?: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const reconciliation = useQuery({
    queryKey: ['tickets', 'reconciliation'],
    queryFn: ticketsApi.reconciliation,
  });
  const report = useQuery({
    queryKey: ['tickets', 'report', category ?? 'all'],
    queryFn: () => ticketsApi.report({ category }),
  });
  const runSla = useMutation({
    mutationFn: ticketsApi.runSla,
    onSuccess: (counts) => {
      const sent = Object.values(counts).reduce((sum, value) => sum + value, 0);
      showSuccess(sent > 0 ? `SLA check sent ${sent} alert${sent === 1 ? '' : 's'}.` : 'SLA check complete — no new alerts.');
      void queryClient.invalidateQueries({ queryKey: ['tickets'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  return (
    <Stack spacing={2}>
      <ContentCard>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1, gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="subtitle2">Workload and SLA</Typography>
          <ProsohmButton size="small" buttonVariant="secondary" disabled={runSla.isPending} onClick={() => runSla.mutate()}>
            Run SLA check now
          </ProsohmButton>
        </Stack>
        {report.isLoading ? (
          <LoadingState message="Loading totals…" />
        ) : report.isError ? (
          <Alert severity="error">{getErrorMessage(report.error)}</Alert>
        ) : report.data ? (
          <>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
              {Object.entries(TOTAL_LABELS).map(([key, label]) => (
                <Chip
                  key={key}
                  variant="outlined"
                  label={`${label}: ${report.data.totals[key] ?? '—'}`}
                />
              ))}
            </Box>
            {report.data.by_assignee.length > 0 ? (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Owner</TableCell>
                    <TableCell align="right">Open</TableCell>
                    <TableCell align="right">Overdue</TableCell>
                    <TableCell align="right">Resolved</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.data.by_assignee.map((row) => (
                    <TableRow key={row.assignee}>
                      <TableCell>{row.assignee}</TableCell>
                      <TableCell align="right">{row.open}</TableCell>
                      <TableCell align="right" sx={{ color: row.overdue ? 'error.main' : undefined }}>
                        {row.overdue}
                      </TableCell>
                      <TableCell align="right">{row.resolved}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : null}
          </>
        ) : null}
      </ContentCard>

      <ContentCard>
        <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
          Records needing attention
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          Nothing here is changed automatically. Open the ticket or onboarding task to review it, assign an
          owner, or use Repair link on the task.
        </Typography>
        {reconciliation.isLoading ? (
          <LoadingState message="Checking records…" />
        ) : reconciliation.isError ? (
          <Alert severity="error">{getErrorMessage(reconciliation.error)}</Alert>
        ) : (reconciliation.data?.rows.length ?? 0) === 0 ? (
          <Alert severity="success">All tickets and onboarding tasks are consistent.</Alert>
        ) : (
          <>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 1 }}>
              {Object.entries(reconciliation.data?.counts ?? {}).map(([kind, count]) => (
                <Chip key={kind} size="small" color="warning" variant="outlined" label={`${KIND_LABELS[kind] ?? kind}: ${count}`} />
              ))}
            </Box>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Issue</TableCell>
                  <TableCell>Record</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Note</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(reconciliation.data?.rows ?? []).map((row, index) => (
                  <TableRow key={`${row.kind}-${row.ticket_id ?? row.item_id ?? index}`}>
                    <TableCell>{KIND_LABELS[row.kind] ?? row.kind}</TableCell>
                    <TableCell sx={{ maxWidth: 360 }}>
                      {row.ticket_id ? (
                        <Link component={RouterLink} to={ticketHref(row.ticket_id)}>
                          {row.ticket_number}
                        </Link>
                      ) : row.checklist_id ? (
                        <Link component={RouterLink} to={`/hr/onboarding?id=${row.checklist_id}&task=${row.item_id}`}>
                          {row.employee_name ?? 'Onboarding'}
                        </Link>
                      ) : null}
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        {row.title}
                        {!row.ticket_id && row.ticket_number ? ` · ${row.ticket_number}` : ''}
                      </Typography>
                    </TableCell>
                    <TableCell>{row.status.replaceAll('_', ' ')}</TableCell>
                    <TableCell>{row.note ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </>
        )}
      </ContentCard>
    </Stack>
  );
}
