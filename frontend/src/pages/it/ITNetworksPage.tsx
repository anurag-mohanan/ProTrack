import { useMemo, useState, type FormEvent } from 'react';
import {
  Box,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import LanRoundedIcon from '@mui/icons-material/LanRounded';
import type { GridColDef } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  allocateIp,
  createNetwork,
  fetchNetworkIps,
  fetchNetworks,
  itOperationsKeys,
  releaseIp,
} from '../../api/itOperations';
import { fetchUsers } from '../../api/lookups';
import { getErrorMessage } from '../../api/client';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
} from '../../components/ui/design-system';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type { ITIpAddress, ITNetwork, ITNetworkCreate } from '../../types/itOperations';
import { formatCellValue, userDisplayName } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import {
  accessContextFromUser,
  canAllocateItIps,
  canManageItNetworks,
} from '../../utils/permissions';

type NetworkFormState = {
  name: string;
  cidr: string;
  gateway: string;
  dns_primary: string;
  dns_secondary: string;
  vlan_id: string;
  description: string;
};

const emptyForm: NetworkFormState = {
  name: '',
  cidr: '',
  gateway: '',
  dns_primary: '',
  dns_secondary: '',
  vlan_id: '',
  description: '',
};

function ipStatusColor(
  status: string,
): 'default' | 'success' | 'info' | 'warning' | 'error' {
  switch (status) {
    case 'available':
      return 'success';
    case 'allocated':
      return 'info';
    case 'reserved':
      return 'warning';
    case 'disabled':
      return 'default';
    default:
      return 'default';
  }
}

function utilizationLabel(network: ITNetwork): string {
  const total = network.total_ips;
  const available = network.available_ips;
  if (total != null && available != null) {
    return `${available} / ${total} available`;
  }
  if (network.allocated_ips != null && total != null) {
    return `${network.allocated_ips} / ${total} allocated`;
  }
  return '—';
}

export function ITNetworksPage() {
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canManage = canManageItNetworks(access);
  const canAllocate = canAllocateItIps(access);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<NetworkFormState>(emptyForm);
  const [selectedNetworkId, setSelectedNetworkId] = useState<string | null>(null);
  const [ipStatusFilter, setIpStatusFilter] = useState('');
  const [allocateOpen, setAllocateOpen] = useState(false);
  const [allocateIpId, setAllocateIpId] = useState('');
  const [allocateUserId, setAllocateUserId] = useState('');
  const [allocateHostname, setAllocateHostname] = useState('');
  const [allocateNotes, setAllocateNotes] = useState('');
  const [releaseTarget, setReleaseTarget] = useState<ITIpAddress | null>(null);

  const networksQuery = useQuery({
    queryKey: itOperationsKeys.networks(),
    queryFn: fetchNetworks,
  });

  const ipsQuery = useQuery({
    queryKey: itOperationsKeys.networkIps(selectedNetworkId ?? '', ipStatusFilter),
    queryFn: () =>
      fetchNetworkIps(selectedNetworkId!, {
        status: ipStatusFilter || undefined,
      }),
    enabled: Boolean(selectedNetworkId),
  });

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: () => fetchUsers(),
    enabled: canAllocate && allocateOpen,
  });

  const selectedNetwork = useMemo(
    () => (networksQuery.data ?? []).find((network) => network.id === selectedNetworkId) ?? null,
    [networksQuery.data, selectedNetworkId],
  );

  const availableIps = useMemo(
    () => (ipsQuery.data ?? []).filter((ip) => ip.status === 'available'),
    [ipsQuery.data],
  );

  const ipOptions = useMemo(
    () => [
      { value: '', label: 'Next available (sequential)' },
      ...availableIps.map((ip) => ({ value: ip.id, label: ip.address })),
    ],
    [availableIps],
  );

  const userOptions = useMemo(
    () =>
      (usersQuery.data ?? []).map((u) => ({
        value: u.id,
        label: userDisplayName(u) || u.email || u.id,
      })),
    [usersQuery.data],
  );

  const createMutation = useMutation({
    mutationFn: (payload: ITNetworkCreate) => createNetwork(payload),
    onSuccess: (network) => {
      showSuccess('Network created.');
      setFormOpen(false);
      setForm(emptyForm);
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.networks() });
      setSelectedNetworkId(network.id);
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const allocateMutation = useMutation({
    mutationFn: () =>
      allocateIp({
        network_id: selectedNetworkId ?? undefined,
        ip_address_id: optionalString(allocateIpId) ?? undefined,
        assigned_to_user_id: optionalString(allocateUserId) ?? undefined,
        hostname: optionalString(allocateHostname),
        notes: optionalString(allocateNotes),
      }),
    onSuccess: () => {
      showSuccess('IP allocated.');
      setAllocateOpen(false);
      setAllocateIpId('');
      setAllocateUserId('');
      setAllocateHostname('');
      setAllocateNotes('');
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const releaseMutation = useMutation({
    mutationFn: (id: string) => releaseIp(id),
    onSuccess: () => {
      showSuccess('IP released.');
      setReleaseTarget(null);
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const handleCreate = (event?: FormEvent) => {
    event?.preventDefault();
    const validationError = validateRequiredFields(
      { name: form.name, cidr: form.cidr },
      [
        { key: 'name', label: 'Name' },
        { key: 'cidr', label: 'CIDR' },
      ],
    );
    if (validationError) {
      showError(validationError);
      return;
    }
    createMutation.mutate({
      name: form.name.trim(),
      cidr: form.cidr.trim(),
      gateway: optionalString(form.gateway),
      dns_primary: optionalString(form.dns_primary),
      dns_secondary: optionalString(form.dns_secondary),
      vlan_id: form.vlan_id.trim() ? Number(form.vlan_id) : null,
      description: optionalString(form.description),
    });
  };

  const networkColumns: GridColDef<ITNetwork>[] = [
    {
      field: 'name',
      headerName: 'Network',
      flex: 1.1,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'cidr',
      headerName: 'CIDR',
      flex: 0.9,
      minWidth: 130,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'gateway',
      headerName: 'Gateway',
      flex: 0.8,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'utilization',
      headerName: 'IP utilization',
      flex: 1,
      minWidth: 140,
      valueGetter: (_value, row) => utilizationLabel(row),
    },
  ];

  if (networksQuery.isLoading) {
    return <LoadingState message="Loading networks…" />;
  }

  if (networksQuery.isError) {
    return (
      <ErrorState
        error={networksQuery.error}
        title="Unable to load networks"
        onRetry={() => void networksQuery.refetch()}
      />
    );
  }

  return (
    <PageContainer>
      <PageHeader
        title="Networks"
        subtitle="Manage CIDR pools and allocate IP addresses."
        action={
          canManage ? (
            <ProsohmButton
              buttonVariant="primary"
              startIcon={<AddIcon />}
              onClick={() => {
                setForm(emptyForm);
                setFormOpen(true);
              }}
            >
              Add network
            </ProsohmButton>
          ) : undefined
        }
      />

      <Stack spacing={2.5}>
        <ContentCard noPadding title="Networks">
          {(networksQuery.data ?? []).length === 0 ? (
            <Box sx={{ p: 3 }}>
              <EmptyState
                title="No networks yet"
                description="Create a network with a CIDR range to generate an IP pool."
              />
            </Box>
          ) : (
            <ClientPaginatedDataGrid
              rows={networksQuery.data ?? []}
              columns={networkColumns}
              getRowId={(row) => row.id}
              autoHeight
              onRowClick={(params) => setSelectedNetworkId(String(params.id))}
              sx={{
                '& .MuiDataGrid-row': { cursor: 'pointer' },
                ...(selectedNetworkId
                  ? {
                      [`& .MuiDataGrid-row[data-id="${selectedNetworkId}"]`]: {
                        bgcolor: 'action.selected',
                      },
                    }
                  : {}),
              }}
            />
          )}
        </ContentCard>

        {selectedNetwork ? (
          <ContentCard
            title={`${selectedNetwork.name} — IP addresses`}
            subtitle={selectedNetwork.cidr}
            action={
              canAllocate ? (
                <ProsohmButton
                  buttonVariant="primary"
                  onClick={() => {
                    setAllocateIpId('');
                    setAllocateUserId('');
                    setAllocateHostname('');
                    setAllocateNotes('');
                    setAllocateOpen(true);
                  }}
                >
                  Allocate IP
                </ProsohmButton>
              ) : undefined
            }
          >
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
              <FormSelect
                label="Status filter"
                value={ipStatusFilter}
                onChange={(event) => setIpStatusFilter(String(event.target.value))}
                options={[
                  { value: '', label: 'All statuses' },
                  { value: 'available', label: 'Available' },
                  { value: 'allocated', label: 'Allocated' },
                  { value: 'reserved', label: 'Reserved' },
                  { value: 'disabled', label: 'Disabled' },
                ]}
                sx={{ minWidth: 200 }}
              />
            </Stack>

            {ipsQuery.isLoading ? (
              <LoadingState message="Loading IP addresses…" />
            ) : ipsQuery.isError ? (
              <ErrorState
                error={ipsQuery.error}
                title="Unable to load IP addresses"
                onRetry={() => void ipsQuery.refetch()}
              />
            ) : (ipsQuery.data ?? []).length === 0 ? (
              <EmptyState title="No IP addresses" description="No IPs match this filter." />
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Address</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Hostname</TableCell>
                    <TableCell>Assignee</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(ipsQuery.data ?? []).map((ip) => (
                    <TableRow key={ip.id}>
                      <TableCell>
                        <Typography sx={{ fontWeight: 600 }}>{ip.address}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={String(ip.status).replace(/_/g, ' ')}
                          color={ipStatusColor(ip.status)}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>{ip.hostname || '—'}</TableCell>
                      <TableCell>{ip.assigned_to_user_name || '—'}</TableCell>
                      <TableCell align="right">
                        {canAllocate && ip.status === 'allocated' ? (
                          <ProsohmButton
                            buttonVariant="outlined"
                            size="small"
                            onClick={() => setReleaseTarget(ip)}
                          >
                            Release
                          </ProsohmButton>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </ContentCard>
        ) : (
          <ContentCard title="IP addresses">
            <Typography color="text.secondary">
              Select a network to view and manage its IP pool.
            </Typography>
          </ContentCard>
        )}
      </Stack>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title="Add network"
        subtitle="Creating a network generates IP rows for the usable CIDR range."
        icon={LanRoundedIcon}
        formId="it-network-form"
        width={520}
        submitLabel="Create network"
        loading={createMutation.isPending}
      >
        <Box
          component="form"
          id="it-network-form"
          onSubmit={handleCreate}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <FormSection title="Network">
            <FormField
              label="Name"
              required
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
            />
            <FormField
              label="CIDR"
              required
              value={form.cidr}
              onChange={(event) =>
                setForm((current) => ({ ...current, cidr: event.target.value }))
              }
              placeholder="192.168.1.0/24"
            />
            <FormField
              label="Gateway"
              value={form.gateway}
              onChange={(event) =>
                setForm((current) => ({ ...current, gateway: event.target.value }))
              }
            />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <FormField
                label="DNS primary"
                value={form.dns_primary}
                onChange={(event) =>
                  setForm((current) => ({ ...current, dns_primary: event.target.value }))
                }
                sx={{ flex: 1 }}
              />
              <FormField
                label="DNS secondary"
                value={form.dns_secondary}
                onChange={(event) =>
                  setForm((current) => ({ ...current, dns_secondary: event.target.value }))
                }
                sx={{ flex: 1 }}
              />
            </Stack>
            <FormField
              label="VLAN ID"
              value={form.vlan_id}
              onChange={(event) =>
                setForm((current) => ({ ...current, vlan_id: event.target.value }))
              }
            />
            <FormField
              label="Description"
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({ ...current, description: event.target.value }))
              }
              multiline
              minRows={2}
            />
          </FormSection>
        </Box>
      </FormDrawer>

      <Dialog open={allocateOpen} onClose={() => setAllocateOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Allocate IP</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <FormSelect
            label="IP address"
            value={allocateIpId}
            onChange={(event) => setAllocateIpId(String(event.target.value))}
            options={ipOptions}
            helper="Leave as sequential to take the next available address in this network."
          />
          <FormSelect
            label="Assign to user"
            value={allocateUserId}
            onChange={(event) => setAllocateUserId(String(event.target.value))}
            options={[{ value: '', label: 'None' }, ...userOptions]}
            searchable
          />
          <FormField
            label="Hostname"
            value={allocateHostname}
            onChange={(event) => setAllocateHostname(event.target.value)}
          />
          <FormField
            label="Notes"
            value={allocateNotes}
            onChange={(event) => setAllocateNotes(event.target.value)}
            multiline
            minRows={2}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setAllocateOpen(false)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={allocateMutation.isPending}
            onClick={() => allocateMutation.mutate()}
          >
            Allocate
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(releaseTarget)}
        onClose={() => setReleaseTarget(null)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Release IP</DialogTitle>
        <DialogContent>
          <Typography>
            Release <strong>{releaseTarget?.address}</strong> back to the available pool?
          </Typography>
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setReleaseTarget(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={releaseMutation.isPending}
            onClick={() => {
              if (releaseTarget) releaseMutation.mutate(releaseTarget.id);
            }}
          >
            Release
          </ProsohmButton>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
