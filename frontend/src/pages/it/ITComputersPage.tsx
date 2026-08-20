import { useMemo, useState, type FormEvent } from 'react';
import {
  Box,
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
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DevicesOtherRoundedIcon from '@mui/icons-material/DevicesOtherRounded';
import type { GridColDef } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  assignComputer,
  createComputer,
  fetchAssetTypes,
  fetchComputersPaginated,
  fetchItPeoplePaginated,
  itOperationsKeys,
  unassignComputer,
  updateComputer,
} from '../../api/itOperations';
import { getErrorMessage } from '../../api/client';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ServerPaginatedDataGrid } from '../../components/common/ServerPaginatedDataGrid';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
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
};

const emptyForm: ComputerFormState = {
  asset_type_id: '',
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

  const [search, setSearch] = useState('');
  const [availability, setAvailability] = useState('all');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ITComputer | null>(null);
  const [form, setForm] = useState<ComputerFormState>(emptyForm);
  const [assignTarget, setAssignTarget] = useState<ITComputer | null>(null);
  const [assignUserId, setAssignUserId] = useState('');

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

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload: ITComputerCreate = {
        asset_type_id: form.asset_type_id,
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
      if (editing) {
        return updateComputer(editing.id, payload);
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

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  const openEdit = (computer: ITComputer) => {
    setEditing(computer);
    setForm({
      asset_type_id: computer.asset_type_id ?? '',
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
      valueGetter: (_value, row) =>
        row.assigned_to_name || row.assigned_to_user_name || row.current_assignee_name || '—',
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
                {canAssign && params.row.is_open ? (
                  <ProsohmButton size="small" onClick={() => setAssignTarget(params.row)}>
                    Assign
                  </ProsohmButton>
                ) : null}
                {canAssign && params.row.status === 'assigned' ? (
                  <ProsohmButton
                    size="small"
                    variant="outlined"
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
        subtitle="Named workstations. Open = Available with no employee assignment."
        action={
          canManage ? (
            <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
              Add computer
            </ProsohmButton>
          ) : undefined
        }
      />

      <SearchToolbar sticky>
        <ToggleButtonGroup
          exclusive
          size="small"
          value={availability}
          onChange={(_e, value) => value && setAvailability(value)}
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
          <ProsohmButton variant="outlined" onClick={() => setAssignTarget(null)}>
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
        subtitle="Computer names are generated by the server from IT settings."
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
              label="MAC address"
              value={form.mac_address}
              onChange={(event) =>
                setForm((current) => ({ ...current, mac_address: event.target.value }))
              }
            />
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
    </PageContainer>
  );
}
