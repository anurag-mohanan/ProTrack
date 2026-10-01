import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Link,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import {
  fetchProvisioningDashboard,
  fetchProvisioningRequests,
  itProvisioningKeys,
  updateProvisioningStatus,
  type ProvisioningRequest,
} from '../../api/itProvisioning';
import { ticketsApi } from '../../api/tickets';
import { getErrorMessage } from '../../api/client';
import { ContentCard } from '../../components/ui/cards';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { FormSelect, KpiMetricCard, ModernPageHeader } from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { FindAvailableComputerDialog } from '../../components/it/FindAvailableComputerDialog';
import { ProvisioningStockCheckPanel } from '../../components/it/inventory/ProvisioningStockCheckPanel';
import { NewTicketDialog } from '../../components/tickets/NewTicketDialog';
import { TicketQueue } from '../../components/tickets/TicketQueue';
import { TicketDataChecksPanel } from '../../components/tickets/TicketDataChecksPanel';
import { useTicketCapabilities } from '../../components/tickets/useTicketMeta';
import { IT_QUEUE_CARDS, IT_QUEUE_VIEWS, ticketHref } from '../../components/tickets/ticketConstants';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { formatDate } from '../../utils/format';
import { accessContextFromUser, canAssignItAssets, canManageItAssets } from '../../utils/permissions';

type ChipColor = 'default' | 'primary' | 'info' | 'warning' | 'error' | 'success';

const PROVISIONING_STATUS_COLOR: Record<string, ChipColor> = {
  OPEN: 'info',
  IN_PROGRESS: 'primary',
  WAITING_FOR_ASSET: 'warning',
  WAITING_FOR_LICENSE: 'warning',
  READY: 'success',
  COMPLETED: 'success',
  REJECTED: 'error',
  CANCELLED: 'default',
};

const PROVISIONING_STATUSES = [
  'OPEN',
  'IN_PROGRESS',
  'WAITING_FOR_ASSET',
  'WAITING_FOR_LICENSE',
  'READY',
  'COMPLETED',
  'REJECTED',
  'CANCELLED',
];

/** IT work queue: every IT ticket (onboarding, hardware, software, assets, stock) in one place. */
export function ITRequestsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);
  const capabilities = useTicketCapabilities();
  const isAgent = Boolean(capabilities.data?.is_agent);
  const requestedTab = searchParams.get('tab');
  const tab =
    requestedTab === 'provisioning' ? 'provisioning' : requestedTab === 'checks' && isAgent ? 'checks' : 'queue';
  const summaryQuery = useQuery({
    queryKey: ['tickets', 'summary', 'it'],
    queryFn: () => ticketsApi.summary('it'),
  });
  const counts = summaryQuery.data?.counts ?? {};
  const activeView = searchParams.get('view') ?? '';
  const activeStatus = searchParams.get('status') ?? '';

  const openCard = (view?: string, status?: string) => {
    const next = new URLSearchParams();
    next.set('view', view ?? 'all');
    if (status) next.set('status', status);
    setSearchParams(next, { replace: true });
  };

  const setTab = (value: string) => {
    const next = new URLSearchParams();
    if (value !== 'queue') next.set('tab', value);
    setSearchParams(next, { replace: true });
  };

  return (
    <PageContainer>
      <ModernPageHeader
        title="IT Requests"
        subtitle="One work queue for onboarding, hardware, software, asset and stock tickets."
        actions={
          <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setCreateOpen(true)}>
            New IT ticket
          </Button>
        }
        summary={
          summaryQuery.isError ? (
            <ErrorState error={summaryQuery.error} onRetry={() => summaryQuery.refetch()} />
          ) : (
            <Box
              sx={{
                display: 'grid',
                gap: 1.25,
                gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)', lg: 'repeat(6, 1fr)' },
              }}
            >
              {IT_QUEUE_CARDS.map((card) => (
                <KpiMetricCard
                  key={card.key}
                  title={card.label}
                  value={summaryQuery.isLoading ? '…' : String(counts[card.key] ?? 0)}
                  icon={card.icon}
                  accent={card.accent}
                  compact
                  onClick={() => openCard(card.view, card.status)}
                  selected={
                    tab === 'queue' &&
                    (card.view ? activeView === card.view && !activeStatus : activeStatus === card.status)
                  }
                />
              ))}
            </Box>
          )
        }
      />

      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 2 }}>
        <Tab value="queue" label="Ticket queue" />
        <Tab value="provisioning" label="Onboarding provisioning" />
        {isAgent ? <Tab value="checks" label="Data checks" /> : null}
      </Tabs>

      {tab === 'queue' ? (
        <TicketQueue
          views={IT_QUEUE_VIEWS}
          defaultView="team"
          category="it"
          emptyHint="No IT tickets match this view. Clear the filters or pick another card."
        />
      ) : tab === 'checks' ? (
        <TicketDataChecksPanel category="it" />
      ) : (
        <ProvisioningPanel />
      )}

      <NewTicketDialog
        open={createOpen}
        defaultCategory="it"
        onClose={() => setCreateOpen(false)}
        onCreated={(ticket) => {
          setCreateOpen(false);
          const next = new URLSearchParams(searchParams);
          next.delete('tab');
          next.set('ticket', ticket.id);
          setSearchParams(next);
        }}
      />
    </PageContainer>
  );
}

function ProvisioningPanel() {
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canReserve = canAssignItAssets(access) || canManageItAssets(access);
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [statusDraft, setStatusDraft] = useState('OPEN');
  const [findOpen, setFindOpen] = useState(false);
  const selectedId = searchParams.get('request');

  const provisioningQuery = useQuery({
    queryKey: itProvisioningKeys.requests({}),
    queryFn: () => fetchProvisioningRequests(),
  });
  const dashboardQuery = useQuery({
    queryKey: itProvisioningKeys.dashboard(),
    queryFn: fetchProvisioningDashboard,
  });
  const rows = provisioningQuery.data ?? [];
  const selected = rows.find((row) => row.id === selectedId) ?? null;

  const select = (row: ProvisioningRequest | null) => {
    const next = new URLSearchParams(searchParams);
    if (row) {
      next.set('request', row.id);
      setStatusDraft(row.status);
    } else {
      next.delete('request');
    }
    setSearchParams(next, { replace: true });
  };

  const statusMutation = useMutation({
    mutationFn: () => updateProvisioningStatus(selected!.id, { status: statusDraft }),
    onSuccess: (row) => {
      showSuccess(`Request updated to ${row.status}`);
      void queryClient.invalidateQueries({ queryKey: itProvisioningKeys.all });
      void queryClient.invalidateQueries({ queryKey: ['tickets'] });
      void queryClient.invalidateQueries({ queryKey: ['onboarding'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  if (provisioningQuery.isLoading) return <LoadingState message="Loading provisioning requests…" />;
  if (provisioningQuery.isError) {
    return (
      <ErrorState
        error={provisioningQuery.error}
        title="Unable to load provisioning requests"
        onRetry={() => void provisioningQuery.refetch()}
      />
    );
  }
  const dash = dashboardQuery.data;

  return (
    <>
      {dash ? (
        <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap', gap: 1 }}>
          <Chip label={`Open ${dash.open_it_requests}`} color="info" size="small" />
          <Chip label={`Due today ${dash.due_today}`} color="warning" size="small" />
          <Chip label={`Overdue ${dash.overdue_requests}`} color="error" size="small" />
          <Chip label={`Waiting licence ${dash.waiting_for_software_license}`} size="small" />
          <Chip label={`Ready ${dash.ready_for_joining}`} color="success" size="small" />
        </Stack>
      ) : null}

      <ContentCard
        title="Employee onboarding IT provisioning"
        subtitle="Hardware and software requirements captured at hire. Each request shares the onboarding workstation ticket."
      >
        {rows.length === 0 ? (
          <EmptyState title="No provisioning requests" description="New hires with IT requirements will appear here." />
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Ticket</TableCell>
                <TableCell>Employee</TableCell>
                <TableCell>Computer</TableCell>
                <TableCell>Required by</TableCell>
                <TableCell>Status</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id} hover selected={row.id === selectedId}>
                  <TableCell>
                    {row.ticket_id && row.ticket_number ? (
                      <Link component={RouterLink} to={ticketHref(row.ticket_id)}>
                        {row.ticket_number}
                      </Link>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        No ticket linked
                      </Typography>
                    )}
                    {row.is_overdue ? <Chip size="small" color="error" label="Overdue" sx={{ ml: 1 }} /> : null}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{row.employee_name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.designation || '—'} · {row.shift_display || 'No shift'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {row.hardware?.computer_type_label || '—'}
                    {row.hardware ? ` · ${row.hardware.monitor_quantity} mon` : ''}
                  </TableCell>
                  <TableCell>{formatDate(row.required_by) || '—'}</TableCell>
                  <TableCell>
                    <Chip size="small" color={PROVISIONING_STATUS_COLOR[row.status] || 'default'} label={row.status} />
                  </TableCell>
                  <TableCell align="right">
                    <ProsohmButton buttonVariant="secondary" onClick={() => select(row)}>
                      Details
                    </ProsohmButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ContentCard>

      <Dialog open={Boolean(selected)} onClose={() => select(null)} fullWidth maxWidth="md">
        <DialogTitle>
          {selected?.ticket_number || 'Provisioning request'} · {selected?.employee_name}
        </DialogTitle>
        <DialogContent>
          {selected ? (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Typography variant="body2">
                Joining {formatDate(selected.joining_date) || '—'} · Required by{' '}
                {formatDate(selected.required_by) || '—'} · Shift {selected.shift_display || '—'}
              </Typography>
              {selected.ticket_id ? (
                <Typography variant="body2">
                  Ticket:{' '}
                  <Link component={RouterLink} to={ticketHref(selected.ticket_id)}>
                    {selected.ticket_number}
                  </Link>{' '}
                  — completing this request resolves the ticket and the onboarding workstation task.
                </Typography>
              ) : null}

              <Typography variant="subtitle2">Hardware</Typography>
              <Typography variant="body2">
                Computer: {selected.hardware?.computer_type_label || 'Not required'}
              </Typography>
              <Typography variant="body2">Monitors: {selected.hardware?.monitor_quantity ?? 0}</Typography>
              <Typography variant="body2">3D mouse: {selected.hardware?.mouse_3d_required ? 'Yes' : 'No'}</Typography>
              <Typography variant="body2">
                Wireless mouse: {selected.hardware?.wireless_mouse_required ? 'Yes' : 'No'}
              </Typography>
              <ProvisioningStockCheckPanel
                requestId={selected.id}
                employeeUserId={selected.user_id}
                canReserve={canReserve}
              />

              <Typography variant="subtitle2">Software</Typography>
              {(selected.software || []).length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No software requirements.
                </Typography>
              ) : (
                (selected.software || []).map((line) => (
                  <Typography key={line.id || line.software_id} variant="body2">
                    {line.software_name || line.software_id} · Licence: {line.license_required ? 'Yes' : 'No'} ·{' '}
                    {line.status}
                  </Typography>
                ))
              )}

              <FormSelect
                label="Request status"
                value={statusDraft}
                options={PROVISIONING_STATUSES.map((s) => ({ value: s, label: s }))}
                onChange={(e) => setStatusDraft(String(e.target.value))}
              />
              {selected.hardware?.computer_required ? (
                <ProsohmButton buttonVariant="primary" onClick={() => setFindOpen(true)}>
                  Find available computer
                </ProsohmButton>
              ) : null}
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="secondary" onClick={() => select(null)}>
            Close
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            disabled={statusMutation.isPending || statusDraft === selected?.status}
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
    </>
  );
}
