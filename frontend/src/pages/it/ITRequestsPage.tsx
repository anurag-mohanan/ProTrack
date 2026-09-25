import { useMemo, useState } from 'react';
import {
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
import {
  fetchProvisioningDashboard,
  fetchProvisioningRequests,
  itProvisioningKeys,
  updateProvisioningStatus,
  type ProvisioningRequest,
} from '../../api/itProvisioning';
import { ticketsApi } from '../../api/resources';
import { getErrorMessage } from '../../api/client';
import { ContentCard } from '../../components/ui/cards';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { FormSelect } from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { FindAvailableComputerDialog } from '../../components/it/FindAvailableComputerDialog';
import { useToast } from '../../context/ToastContext';
import type { Ticket } from '../../types';
import { formatDate } from '../../utils/format';

type ChipColor = 'default' | 'primary' | 'info' | 'warning' | 'error' | 'success';

const STATUS_COLOR: Record<string, ChipColor> = {
  OPEN: 'info',
  IN_PROGRESS: 'primary',
  WAITING_FOR_ASSET: 'warning',
  WAITING_FOR_LICENSE: 'warning',
  READY: 'success',
  COMPLETED: 'success',
  REJECTED: 'error',
  CANCELLED: 'default',
};

const STATUSES = [
  'OPEN',
  'IN_PROGRESS',
  'WAITING_FOR_ASSET',
  'WAITING_FOR_LICENSE',
  'READY',
  'COMPLETED',
  'REJECTED',
  'CANCELLED',
];

export function ITRequestsPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<ProvisioningRequest | null>(null);
  const [statusDraft, setStatusDraft] = useState('OPEN');
  const [findOpen, setFindOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const overdueOnly = searchParams.get('overdue') === '1';

  const provisioningQuery = useQuery({
    queryKey: itProvisioningKeys.requests({}),
    queryFn: () => fetchProvisioningRequests(),
  });
  const dashboardQuery = useQuery({
    queryKey: itProvisioningKeys.dashboard(),
    queryFn: fetchProvisioningDashboard,
  });
  const ticketsQuery = useQuery({
    queryKey: ['tickets', 'it', 'active'],
    queryFn: () => ticketsApi.list({ category: 'it', status: 'active' }),
  });

  const statusMutation = useMutation({
    mutationFn: () =>
      updateProvisioningStatus(selected!.id, { status: statusDraft }),
    onSuccess: (row) => {
      showSuccess(`Request updated to ${row.status}`);
      setSelected(row);
      void queryClient.invalidateQueries({ queryKey: itProvisioningKeys.all });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const allRows = provisioningQuery.data ?? [];
  const rows = overdueOnly ? allRows.filter((row) => row.is_overdue) : allRows;
  const dash = dashboardQuery.data;
  const todayIso = new Date().toISOString().slice(0, 10);
  const genericTickets: Ticket[] = useMemo(() => {
    const data = ticketsQuery.data;
    const list = Array.isArray(data) ? data : ((data as { items?: Ticket[] } | undefined)?.items ?? []);
    const provisioningTickets = new Set(
      (provisioningQuery.data ?? []).map((row) => row.ticket_number).filter(Boolean),
    );
    return list
      .filter((ticket) => !provisioningTickets.has(ticket.ticket_number))
      .filter((ticket) => !overdueOnly || (ticket.due_date != null && ticket.due_date < todayIso))
      .sort((a, b) => (a.due_date ?? '9999').localeCompare(b.due_date ?? '9999'));
  }, [ticketsQuery.data, provisioningQuery.data, overdueOnly, todayIso]);

  if (provisioningQuery.isLoading) {
    return <LoadingState message="Loading IT requests…" />;
  }
  if (provisioningQuery.isError) {
    return (
      <ErrorState
        error={provisioningQuery.error}
        title="Unable to load IT requests"
        onRetry={() => void provisioningQuery.refetch()}
      />
    );
  }

  return (
    <PageContainer>
      <PageHeader
        title="IT Requests"
        subtitle="Onboarding provisioning requests and Help Desk IT tickets."
      />

      {dash ? (
        <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap', gap: 1 }}>
          <Chip label={`Open ${dash.open_it_requests}`} color="info" size="small" />
          <Chip label={`Due today ${dash.due_today}`} color="warning" size="small" />
          <Chip label={`Overdue ${dash.overdue_requests}`} color="error" size="small" />
          <Chip label={`Waiting license ${dash.waiting_for_software_license}`} size="small" />
          <Chip label={`Ready ${dash.ready_for_joining}`} color="success" size="small" />
          <Chip
            label={overdueOnly ? 'Showing overdue only — show all' : 'Show overdue only'}
            color={overdueOnly ? 'error' : 'default'}
            variant={overdueOnly ? 'filled' : 'outlined'}
            size="small"
            onClick={() =>
              setSearchParams(overdueOnly ? {} : { overdue: '1' }, { replace: true })
            }
          />
        </Stack>
      ) : null}

      <ContentCard title="Employee onboarding IT requests">
        {rows.length === 0 ? (
          <EmptyState title="No provisioning requests" description="New hires with IT requirements will appear here." />
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Request / Ticket</TableCell>
                <TableCell>Employee</TableCell>
                <TableCell>Computer</TableCell>
                <TableCell>Required by</TableCell>
                <TableCell>Status</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id} hover>
                  <TableCell>
                    {row.ticket_number || row.id.slice(0, 8)}
                    {row.is_overdue ? (
                      <Chip size="small" color="error" label="Overdue" sx={{ ml: 1 }} />
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{row.employee_name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.designation || '—'} · {row.shift_display || 'No shift'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {row.hardware?.computer_type_label || '—'}
                    {row.hardware
                      ? ` · ${row.hardware.monitor_quantity} mon`
                      : ''}
                  </TableCell>
                  <TableCell>{formatDate(row.required_by) || '—'}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      color={STATUS_COLOR[row.status] || 'default'}
                      label={row.status}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <ProsohmButton
                      buttonVariant="secondary"
                      onClick={() => {
                        setSelected(row);
                        setStatusDraft(row.status);
                      }}
                    >
                      Open
                    </ProsohmButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ContentCard>

      <ContentCard
        title="Other IT Help Desk tickets"
        subtitle="Open, in progress and on hold — sorted by due date."
      >
        {genericTickets.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {overdueOnly ? 'No overdue IT tickets.' : 'No other active IT tickets.'}
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Ticket</TableCell>
                <TableCell>Title</TableCell>
                <TableCell>Requester</TableCell>
                <TableCell>Assignee</TableCell>
                <TableCell>Priority</TableCell>
                <TableCell>Due</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {genericTickets.map((ticket) => {
                const overdue = ticket.due_date != null && ticket.due_date < todayIso;
                return (
                  <TableRow key={ticket.id}>
                    <TableCell>
                      <Link component={RouterLink} to={`/help-desk/${ticket.id}`}>
                        {ticket.ticket_number}
                      </Link>
                    </TableCell>
                    <TableCell>{ticket.title}</TableCell>
                    <TableCell>{ticket.requester_name || '—'}</TableCell>
                    <TableCell>{ticket.assignee_name || 'Unassigned'}</TableCell>
                    <TableCell sx={{ textTransform: 'capitalize' }}>{ticket.priority}</TableCell>
                    <TableCell>
                      {formatDate(ticket.due_date) || '—'}
                      {overdue ? (
                        <Chip size="small" color="error" label="Overdue" sx={{ ml: 1 }} />
                      ) : null}
                    </TableCell>
                    <TableCell>{ticket.status_label || ticket.status}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </ContentCard>

      <Dialog
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>
          {selected?.ticket_number || 'Provisioning request'} · {selected?.employee_name}
        </DialogTitle>
        <DialogContent>
          {selected ? (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Typography variant="body2">
                Joining {formatDate(selected.joining_date) || '—'} · Required by{' '}
                {formatDate(selected.required_by) || '—'} · Shift{' '}
                {selected.shift_display || '—'}
              </Typography>

              <Typography variant="subtitle2">Hardware</Typography>
              <Typography variant="body2">
                Computer: {selected.hardware?.computer_type_label || 'Not required'}
              </Typography>
              <Typography variant="body2">
                Monitors: {selected.hardware?.monitor_quantity ?? 0}
              </Typography>
              <Typography variant="body2">
                3D Mouse: {selected.hardware?.mouse_3d_required ? 'Yes' : 'No'}
              </Typography>
              <Typography variant="body2">
                Wireless Mouse: {selected.hardware?.wireless_mouse_required ? 'Yes' : 'No'}
              </Typography>

              <Typography variant="subtitle2">Software</Typography>
              {(selected.software || []).length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No software requirements.
                </Typography>
              ) : (
                (selected.software || []).map((line) => (
                  <Typography key={line.id || line.software_id} variant="body2">
                    {line.software_name || line.software_id} · License:{' '}
                    {line.license_required ? 'Yes' : 'No'} · {line.status}
                  </Typography>
                ))
              )}

              <FormSelect
                label="Request status"
                value={statusDraft}
                options={STATUSES.map((s) => ({ value: s, label: s }))}
                onChange={(e) => setStatusDraft(String(e.target.value))}
              />
              <Typography variant="caption" color="text.secondary">
                Assign assets and licenses from Assets / Software pages for this employee, then update
                status here.
              </Typography>
              {selected.hardware?.computer_required ? (
                <ProsohmButton buttonVariant="primary" onClick={() => setFindOpen(true)}>
                  Find Available Computer
                </ProsohmButton>
              ) : null}
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="secondary" onClick={() => setSelected(null)}>
            Close
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            disabled={statusMutation.isPending}
            onClick={() => statusMutation.mutate()}
          >
            Save status
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <FindAvailableComputerDialog
        open={findOpen}
        onClose={() => setFindOpen(false)}
        defaults={{
          on_date: selected?.required_by || selected?.joining_date || undefined,
          shift_id: selected?.shift_id || undefined,
          computer_type: selected?.hardware?.computer_type || undefined,
          monitor_quantity: selected?.hardware?.monitor_quantity ?? 0,
          mouse_3d_required: selected?.hardware?.mouse_3d_required ?? false,
          user_id: selected?.user_id,
          employee_name: selected?.employee_name || undefined,
          provisioning_request_id: selected?.id,
        }}
      />
    </PageContainer>
  );
}
