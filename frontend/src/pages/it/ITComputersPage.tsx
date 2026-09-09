import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DevicesOtherRoundedIcon from '@mui/icons-material/DevicesOtherRounded';
import FactCheckRoundedIcon from '@mui/icons-material/FactCheckRounded';
import type { GridColDef } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  assignComputer,
  createComputer,
  createComputerInterface,
  deleteComputerInterface,
  fetchAssetTypes,
  fetchComputerInterfaces,
  fetchComputersPaginated,
  fetchItPeoplePaginated,
  fetchSuggestedComputerName,
  fetchSuggestedIp,
  itOperationsKeys,
  reconcileOrphanAssignedComputers,
  unassignComputer,
  updateComputer,
} from '../../api/itOperations';
import { getErrorMessage } from '../../api/client';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ITSectionSubnav, IT_INVENTORY_TABS } from '../../components/it/ITSectionSubnav';
import { ServerPaginatedDataGrid } from '../../components/common/ServerPaginatedDataGrid';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { ResourcePlanningDataQualityPanel } from '../../components/resource-planning/ResourcePlanningDataQualityPanel';
import {
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
  SearchToolbar,
  TableRowActions,
} from '../../components/ui/design-system';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';
import type { ITComputer, ITComputerCreate } from '../../types/itOperations';
import { formatCellValue } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import {
  accessContextFromUser,
  canAssignItAssets,
  canManageItAssets,
} from '../../utils/permissions';

const STORAGE_TYPE_OPTIONS = [
  { value: 'SSD', label: 'SSD' },
  { value: 'HDD', label: 'HDD' },
  { value: 'NVMe', label: 'NVMe' },
];

type ComputerFormState = {
  asset_type_id: string;
  computer_name: string;
  make: string;
  model: string;
  serial_number: string;
  os: string;
  processor: string;
  ram_gb: string;
  storage_type: string;
  storage_gb: string;
  domain_joined: boolean;
  mac_address: string;
  location: string;
  notes: string;
  allocate_ip: boolean;
};

const emptyForm: ComputerFormState = {
  asset_type_id: '',
  computer_name: '',
  make: '',
  model: '',
  serial_number: '',
  os: '',
  processor: '',
  ram_gb: '',
  storage_type: 'SSD',
  storage_gb: '',
  domain_joined: false,
  mac_address: '',
  location: '',
  notes: '',
  allocate_ip: true,
};

function statusColor(status: string): 'default' | 'success' | 'info' | 'warning' {
  switch (status) {
    case 'available':
      return 'success';
    case 'assigned':
      return 'info';
    case 'maintenance':
      return 'warning';
    default:
      return 'default';
  }
}

export function ITComputersPage() {
  const { user } = useAuth();
  const ctx = accessContextFromUser(user);
  const canManage = canManageItAssets(ctx);
  const canAssign = canAssignItAssets(ctx);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [search, setSearch] = useState('');
  const availability = searchParams.get('availability') || 'all';
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ITComputer | null>(null);
  const [form, setForm] = useState<ComputerFormState>(emptyForm);
  const [assignTarget, setAssignTarget] = useState<ITComputer | null>(null);
  const [assignUserId, setAssignUserId] = useState('');
  const [qualityOpen, setQualityOpen] = useState(false);
  const [nicTarget, setNicTarget] = useState<ITComputer | null>(null);
  const [nicName, setNicName] = useState('Wi-Fi');
  const [nicRole, setNicRole] = useState('wifi');
  const [nicMac, setNicMac] = useState('');

  const assetTypesQuery = useQuery({
    queryKey: itOperationsKeys.assetTypes(),
    queryFn: fetchAssetTypes,
  });

  const listFilters = useMemo(
    () => ({
      search: search.trim() || undefined,
      availability: availability === 'all' ? undefined : availability,
    }),
    [search, availability],
  );

  const peopleQuery = useQuery({
    queryKey: itOperationsKeys.people({ status: 'active', page_size: 200 }),
    queryFn: () => fetchItPeoplePaginated({ status: 'active', page_size: 200 }),
    enabled: canAssign && Boolean(assignTarget),
  });

  const interfacesQuery = useQuery({
    queryKey: itOperationsKeys.computerInterfaces(nicTarget?.id ?? ''),
    queryFn: () => fetchComputerInterfaces(nicTarget!.id),
    enabled: Boolean(nicTarget?.id),
  });

  const addInterfaceMutation = useMutation({
    mutationFn: () =>
      createComputerInterface(nicTarget!.id, {
        name: nicName.trim(),
        role: nicRole,
        mac_address: optionalString(nicMac),
        is_primary: false,
      }),
    onSuccess: () => {
      showSuccess('Network interface added.');
      setNicMac('');
      void queryClient.invalidateQueries({
        queryKey: itOperationsKeys.computerInterfaces(nicTarget?.id ?? ''),
      });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const deleteInterfaceMutation = useMutation({
    mutationFn: (interfaceId: string) => deleteComputerInterface(nicTarget!.id, interfaceId),
    onSuccess: () => {
      showSuccess('Interface removed.');
      void queryClient.invalidateQueries({
        queryKey: itOperationsKeys.computerInterfaces(nicTarget?.id ?? ''),
      });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const computerTypeOptions = useMemo(
    () =>
      (assetTypesQuery.data ?? [])
        .filter(
          (type) =>
            type.is_active !== false &&
            (type.category === 'computer' ||
              type.code.toLowerCase().includes('laptop') ||
              type.code.toLowerCase().includes('desktop') ||
              type.code.toLowerCase().includes('server')),
        )
        .map((type) => ({ value: type.id, label: `${type.name} (${type.code})` })),
    [assetTypesQuery.data],
  );

  const typeOptions =
    computerTypeOptions.length > 0
      ? computerTypeOptions
      : (assetTypesQuery.data ?? [])
          .filter((type) => type.is_active !== false)
          .map((type) => ({ value: type.id, label: `${type.name} (${type.code})` }));

  const selectedType = (assetTypesQuery.data ?? []).find((type) => type.id === form.asset_type_id);

  const nameSuggestQuery = useQuery({
    queryKey: itOperationsKeys.suggestComputerName(selectedType?.code),
    queryFn: () => fetchSuggestedComputerName(selectedType?.code),
    enabled: formOpen && !editing,
  });

  const ipSuggestQuery = useQuery({
    queryKey: itOperationsKeys.suggestIp(form.computer_name || nameSuggestQuery.data?.computer_name),
    queryFn: () =>
      fetchSuggestedIp({
        computer_name: form.computer_name || nameSuggestQuery.data?.computer_name,
      }),
    enabled: formOpen && !editing,
  });

  useEffect(() => {
    if (editing || !nameSuggestQuery.data?.computer_name) return;
    setForm((current) =>
      current.computer_name
        ? current
        : { ...current, computer_name: nameSuggestQuery.data!.computer_name },
    );
  }, [editing, nameSuggestQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (editing) {
        return updateComputer(editing.id, {
          computer_name: optionalString(form.computer_name),
          make: optionalString(form.make),
          model: optionalString(form.model),
          serial_number: optionalString(form.serial_number),
          os: optionalString(form.os),
          processor: optionalString(form.processor),
          ram_gb: form.ram_gb.trim() ? Number(form.ram_gb) : null,
          storage_type: optionalString(form.storage_type),
          storage_gb: form.storage_gb.trim() ? Number(form.storage_gb) : null,
          domain_joined: form.domain_joined,
          mac_address: optionalString(form.mac_address),
          location: optionalString(form.location),
          notes: optionalString(form.notes),
        });
      }
      const payload: ITComputerCreate = {
        asset_type_id: form.asset_type_id,
        computer_name: optionalString(form.computer_name),
        make: optionalString(form.make),
        model: optionalString(form.model),
        serial_number: optionalString(form.serial_number),
        os: optionalString(form.os),
        processor: optionalString(form.processor),
        ram_gb: form.ram_gb.trim() ? Number(form.ram_gb) : null,
        storage_type: optionalString(form.storage_type),
        storage_gb: form.storage_gb.trim() ? Number(form.storage_gb) : null,
        domain_joined: form.domain_joined,
        mac_address: optionalString(form.mac_address),
        location: optionalString(form.location),
        notes: optionalString(form.notes),
      };
      if (form.allocate_ip && ipSuggestQuery.data?.available && ipSuggestQuery.data.ip_address_id) {
        payload.ip_address_id = ipSuggestQuery.data.ip_address_id;
      }
      return createComputer(payload);
    },
    onSuccess: () => {
      showSuccess(editing ? 'Computer updated.' : 'Computer created.');
      setFormOpen(false);
      setEditing(null);
      setForm(emptyForm);
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const assignMutation = useMutation({
    mutationFn: async () => {
      if (!assignTarget || !assignUserId) throw new Error('Select an employee.');
      return assignComputer(assignTarget.id, { user_id: assignUserId });
    },
    onSuccess: () => {
      showSuccess('Computer assigned.');
      setAssignTarget(null);
      setAssignUserId('');
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const unassignMutation = useMutation({
    mutationFn: (id: string) => unassignComputer(id, { reason: 'Returned to IT pool' }),
    onSuccess: () => {
      showSuccess('Computer unassigned — now Open/Available.');
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const reconcileMutation = useMutation({
    mutationFn: reconcileOrphanAssignedComputers,
    onSuccess: (data) => {
      showSuccess(
        data.repaired_count
          ? `Repaired ${data.repaired_count} orphan assigned status(es).`
          : 'No orphan assigned statuses found.',
      );
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  const openEdit = (computer: ITComputer) => {
    setEditing(computer);
    setForm({
      asset_type_id: computer.asset_type_id ?? '',
      computer_name: computer.computer_name ?? '',
      make: computer.make ?? '',
      model: computer.model ?? '',
      serial_number: computer.serial_number ?? '',
      os: computer.os ?? '',
      processor: computer.processor ?? '',
      ram_gb: computer.ram_gb != null ? String(computer.ram_gb) : '',
      storage_type: computer.storage_type ?? 'SSD',
      storage_gb: computer.storage_gb != null ? String(computer.storage_gb) : '',
      domain_joined: Boolean(computer.domain_joined),
      mac_address: computer.mac_address ?? '',
      location: computer.location ?? '',
      notes: computer.notes ?? '',
      allocate_ip: false,
    });
    setFormOpen(true);
  };

  const handleSave = (event?: FormEvent) => {
    event?.preventDefault();
    if (!editing) {
      const validationError = validateRequiredFields(
        { asset_type_id: form.asset_type_id },
        [{ key: 'asset_type_id', label: 'Asset type' }],
      );
      if (validationError) {
        showError(validationError);
        return;
      }
    }
    saveMutation.mutate();
  };

  const columns: GridColDef<ITComputer>[] = [
    {
      field: 'computer_name',
      headerName: 'Computer name',
      flex: 1,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'asset_number',
      headerName: 'Asset #',
      flex: 0.8,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'primary_ip',
      headerName: 'IP',
      width: 130,
      valueFormatter: (value) => formatCellValue(value) || '—',
    },
    {
      field: 'mac_address',
      headerName: 'MAC',
      width: 140,
      valueFormatter: (value) => formatCellValue(value) || '—',
    },
    {
      field: 'os',
      headerName: 'OS',
      flex: 0.9,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'ram_gb',
      headerName: 'RAM (GB)',
      width: 110,
      valueFormatter: (value) => (value == null ? '—' : String(value)),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 130,
      renderCell: (params) => (
        <Chip
          size="small"
          label={String(params.value || '—').replace(/_/g, ' ')}
          color={statusColor(String(params.value || ''))}
          variant="outlined"
        />
      ),
    },
    {
      field: 'assignee',
      headerName: 'Employee',
      flex: 1,
      minWidth: 140,
      renderCell: (params) => {
        const name =
          params.row.assigned_to_name ||
          params.row.assigned_to_user_name ||
          params.row.current_assignee_name;
        const flags = params.row.data_quality_flags ?? [];
        const orphan = flags.includes('status_assigned_without_employee');
        return (
          <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
            <span>{name || '—'}</span>
            {orphan ? (
              <Chip size="small" color="warning" variant="outlined" label="needs link" />
            ) : null}
          </Stack>
        );
      },
    },
    {
      field: 'assigned_to_team',
      headerName: 'Team',
      flex: 0.8,
      minWidth: 110,
      valueFormatter: (value) => formatCellValue(value) || '—',
    },
    {
      field: 'location',
      headerName: 'Location',
      flex: 0.8,
      minWidth: 110,
      valueFormatter: (value) => formatCellValue(value) || '—',
    },
    {
      field: 'current_shift_display',
      headerName: 'Shift',
      flex: 1,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(value) || '—',
    },
    ...(canManage || canAssign
      ? [
          {
            field: 'actions',
            headerName: 'Actions',
            width: DATA_GRID_ACTIONS_COLUMN_WIDTH + 40,
            sortable: false,
            filterable: false,
            renderCell: (params) => (
              <Stack direction="row" spacing={0.5}>
                {canManage ? (
                  <TableRowActions onEdit={() => openEdit(params.row)} />
                ) : null}
                {canManage ? (
                  <ProsohmButton size="small" onClick={() => setNicTarget(params.row)}>
                    NICs
                  </ProsohmButton>
                ) : null}
                {canAssign && params.row.is_open ? (
                  <ProsohmButton size="small" onClick={() => setAssignTarget(params.row)}>
                    Assign
                  </ProsohmButton>
                ) : null}
                {canAssign && params.row.status === 'assigned' ? (
                  <ProsohmButton
                    size="small"
                    buttonVariant="outlined"
                    onClick={() => {
                      unassignMutation.mutate(params.row.id);
                    }}
                  >
                    Unassign
                  </ProsohmButton>
                ) : null}
              </Stack>
            ),
          } as GridColDef<ITComputer>,
        ]
      : []),
  ];

  return (
    <PageContainer>
      <PageHeader
        subtitle="NIC / MAC workspace for the same Computer records as Assets & Inventory. Day-to-day computer and IP management belongs on the inventory asset."
        action={
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
            <ProsohmButton
              buttonVariant="outlined"
              onClick={() => navigate('/it/assets?category=computer')}
            >
              View as inventory
            </ProsohmButton>
            <ProsohmButton
              buttonVariant="outlined"
              startIcon={<FactCheckRoundedIcon />}
              onClick={() => setQualityOpen(true)}
            >
              Data quality
            </ProsohmButton>
            {canManage ? (
              <>
                <ProsohmButton
                  buttonVariant="secondary"
                  loading={reconcileMutation.isPending}
                  onClick={() => reconcileMutation.mutate()}
                >
                  Fix orphan assigned
                </ProsohmButton>
                <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
                  Add computer
                </ProsohmButton>
              </>
            ) : null}
          </Stack>
        }
      />

      <ITSectionSubnav items={IT_INVENTORY_TABS} />

      <SearchToolbar sticky>
        <ToggleButtonGroup
          exclusive
          size="small"
          value={availability}
          onChange={(_e, value) => {
            if (!value) return;
            const next = new URLSearchParams(searchParams);
            if (value === 'all') next.delete('availability');
            else next.set('availability', value);
            setSearchParams(next, { replace: true });
          }}
        >
          <ToggleButton value="all">All</ToggleButton>
          <ToggleButton value="open">Open</ToggleButton>
          <ToggleButton value="assigned">Assigned</ToggleButton>
          <ToggleButton value="maintenance">Maintenance</ToggleButton>
          <ToggleButton value="retired">Retired</ToggleButton>
        </ToggleButtonGroup>
        <FormField
          label="Search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Computer name, asset number…"
          sx={{ minWidth: 240, flex: 1, maxWidth: 420 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ServerPaginatedDataGrid<ITComputer, ITComputer>
          queryKey={['it', 'computers', listFilters]}
          fetcher={fetchComputersPaginated}
          filters={listFilters}
          columns={columns}
          getRowId={(row) => row.id}
          autoHeight
        />
      </ContentCard>

      <Dialog
        open={Boolean(assignTarget)}
        onClose={() => setAssignTarget(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Assign {assignTarget?.computer_name}</DialogTitle>
        <DialogContent>
          <FormSelect
            label="Employee"
            value={assignUserId}
            onChange={(e) => setAssignUserId(String(e.target.value))}
            options={(peopleQuery.data?.items ?? []).map((p) => ({
              value: p.user_id,
              label: `${p.full_name}${p.team ? ` (${p.team})` : ''}`,
            }))}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setAssignTarget(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            disabled={!assignUserId || assignMutation.isPending}
            onClick={() => assignMutation.mutate()}
          >
            Confirm assignment
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? 'Edit computer' : 'Add computer'}
        subtitle={
          editing
            ? 'Computer name changes are recorded in history. The internal asset ID does not change.'
            : 'Computer name and IP are suggested from existing inventory. You can edit either before save.'
        }
        icon={DevicesOtherRoundedIcon}
        formId="it-computer-form"
        width={560}
        submitLabel={editing ? 'Save changes' : 'Create computer'}
        loading={saveMutation.isPending}
      >
        <Box
          component="form"
          id="it-computer-form"
          onSubmit={handleSave}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <FormSection title="Hardware">
            {!editing ? (
              <FormSelect
                label="Asset type"
                required
                value={form.asset_type_id}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    asset_type_id: String(event.target.value),
                  }))
                }
                options={typeOptions}
              />
            ) : null}
            <FormField
              label="Computer name"
              value={form.computer_name}
              onChange={(event) =>
                setForm((current) => ({ ...current, computer_name: event.target.value }))
              }
              helper={
                !editing
                  ? nameSuggestQuery.data?.message || 'Suggested from existing computer names.'
                  : 'Changing the name records a history period. The asset ID stays the same.'
              }
              placeholder={nameSuggestQuery.data?.computer_name ?? ''}
            />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <FormField
                label="Make"
                value={form.make}
                onChange={(event) =>
                  setForm((current) => ({ ...current, make: event.target.value }))
                }
                sx={{ flex: 1 }}
              />
              <FormField
                label="Model"
                value={form.model}
                onChange={(event) =>
                  setForm((current) => ({ ...current, model: event.target.value }))
                }
                sx={{ flex: 1 }}
              />
            </Stack>
            <FormField
              label="Serial number"
              value={form.serial_number}
              onChange={(event) =>
                setForm((current) => ({ ...current, serial_number: event.target.value }))
              }
            />
            <FormField
              label="OS"
              value={form.os}
              onChange={(event) =>
                setForm((current) => ({ ...current, os: event.target.value }))
              }
            />
            <FormField
              label="Processor"
              value={form.processor}
              onChange={(event) =>
                setForm((current) => ({ ...current, processor: event.target.value }))
              }
            />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <FormField
                label="RAM (GB)"
                value={form.ram_gb}
                onChange={(event) =>
                  setForm((current) => ({ ...current, ram_gb: event.target.value }))
                }
                sx={{ flex: 1 }}
              />
              <FormSelect
                label="Storage type"
                value={form.storage_type}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    storage_type: String(event.target.value),
                  }))
                }
                options={STORAGE_TYPE_OPTIONS}
                sx={{ flex: 1 }}
              />
              <FormField
                label="Storage (GB)"
                value={form.storage_gb}
                onChange={(event) =>
                  setForm((current) => ({ ...current, storage_gb: event.target.value }))
                }
                sx={{ flex: 1 }}
              />
            </Stack>
          </FormSection>
          <FormSection title="Network & location">
            <FormField
              label="Primary NIC MAC"
              value={form.mac_address}
              onChange={(event) =>
                setForm((current) => ({ ...current, mac_address: event.target.value }))
              }
              helper="Stored on the primary network interface. Extra NICs are managed from the NICs dialog."
            />
            {!editing ? (
              <>
                <FormField
                  label="Suggested IP"
                  value={
                    ipSuggestQuery.data?.address ??
                    (ipSuggestQuery.isFetching ? 'Loading…' : '')
                  }
                  slotProps={{ input: { readOnly: true } }}
                  helper={ipSuggestQuery.data?.message}
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={form.allocate_ip && Boolean(ipSuggestQuery.data?.available)}
                      disabled={!ipSuggestQuery.data?.available}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          allocate_ip: event.target.checked,
                        }))
                      }
                    />
                  }
                  label="Allocate the suggested IP on create"
                />
              </>
            ) : (
              <FormField
                label="Primary IP"
                value={editing?.primary_ip ?? ''}
                slotProps={{ input: { readOnly: true } }}
                helper="Change IP from the inventory asset so assignment history is preserved."
              />
            )}
            <FormControlLabel
              control={
                <Switch
                  checked={form.domain_joined}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      domain_joined: event.target.checked,
                    }))
                  }
                />
              }
              label="Domain joined"
            />
            <FormField
              label="Location"
              value={form.location}
              onChange={(event) =>
                setForm((current) => ({ ...current, location: event.target.value }))
              }
            />
            <FormField
              label="Notes"
              value={form.notes}
              onChange={(event) =>
                setForm((current) => ({ ...current, notes: event.target.value }))
              }
              multiline
              minRows={3}
            />
          </FormSection>
        </Box>
      </FormDrawer>

      <Dialog
        open={qualityOpen}
        onClose={() => setQualityOpen(false)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>IT / Resource data quality</DialogTitle>
        <DialogContent dividers>
          {qualityOpen ? <ResourcePlanningDataQualityPanel /> : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setQualityOpen(false)}>
            Close
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(nicTarget)}
        onClose={() => setNicTarget(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>
          Network interfaces{nicTarget ? ` — ${nicTarget.computer_name}` : ''}
        </DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Multi-NIC enables intentional multi-homing. Bind each IP to a NIC when allocating.
          </Typography>
          {(interfacesQuery.data ?? []).map((row) => (
            <Stack
              key={row.id}
              direction="row"
              spacing={1}
              sx={{ alignItems: 'center', justifyContent: 'space-between' }}
            >
              <Box>
                <Typography variant="body2">
                  {row.name} · {row.role}
                  {row.is_primary ? ' · primary' : ''}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {row.mac_address || 'No MAC'}
                </Typography>
              </Box>
              {canManage && !row.is_primary ? (
                <ProsohmButton
                  size="small"
                  buttonVariant="outlined"
                  onClick={() => deleteInterfaceMutation.mutate(row.id)}
                >
                  Remove
                </ProsohmButton>
              ) : null}
            </Stack>
          ))}
          {canManage ? (
            <Stack spacing={1.5}>
              <FormField
                label="Name"
                value={nicName}
                onChange={(event) => setNicName(event.target.value)}
              />
              <FormSelect
                label="Role"
                value={nicRole}
                onChange={(event) => setNicRole(String(event.target.value))}
                options={[
                  { value: 'lan', label: 'LAN' },
                  { value: 'wifi', label: 'Wi-Fi' },
                  { value: 'vpn', label: 'VPN' },
                  { value: 'other', label: 'Other' },
                ]}
              />
              <FormField
                label="MAC address"
                value={nicMac}
                onChange={(event) => setNicMac(event.target.value)}
              />
              <ProsohmButton
                buttonVariant="primary"
                loading={addInterfaceMutation.isPending}
                disabled={!nicName.trim()}
                onClick={() => addInterfaceMutation.mutate()}
              >
                Add interface
              </ProsohmButton>
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setNicTarget(null)}>
            Close
          </ProsohmButton>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
