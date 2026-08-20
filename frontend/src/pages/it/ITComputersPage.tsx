import { useMemo, useState, type FormEvent } from 'react';
import { Box, Chip, FormControlLabel, Stack, Switch } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DevicesOtherRoundedIcon from '@mui/icons-material/DevicesOtherRounded';
import type { GridColDef } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createComputer,
  fetchAssetTypes,
  fetchComputersPaginated,
  itOperationsKeys,
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
import { accessContextFromUser, canManageItAssets } from '../../utils/permissions';

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
  const canManage = canManageItAssets(accessContextFromUser(user));
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ITComputer | null>(null);
  const [form, setForm] = useState<ComputerFormState>(emptyForm);

  const assetTypesQuery = useQuery({
    queryKey: itOperationsKeys.assetTypes(),
    queryFn: fetchAssetTypes,
  });

  const listFilters = useMemo(
    () => ({ q: search.trim() || undefined }),
    [search],
  );

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
      headerName: 'Assignee',
      flex: 1,
      minWidth: 140,
      valueGetter: (_value, row) =>
        row.assigned_to_user_name || row.current_assignee_name || '—',
    },
    ...(canManage
      ? [
          {
            field: 'actions',
            headerName: 'Actions',
            width: DATA_GRID_ACTIONS_COLUMN_WIDTH,
            sortable: false,
            filterable: false,
            renderCell: (params) => (
              <TableRowActions onEdit={() => openEdit(params.row)} />
            ),
          } as GridColDef<ITComputer>,
        ]
      : []),
  ];

  return (
    <PageContainer>
      <PageHeader
        title="Computers"
        subtitle="Named workstations linked to the asset register."
        action={
          canManage ? (
            <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
              Add computer
            </ProsohmButton>
          ) : undefined
        }
      />

      <SearchToolbar sticky>
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
          queryKey={['it', 'computers']}
          fetcher={fetchComputersPaginated}
          filters={listFilters}
          columns={columns}
          getRowId={(row) => row.id}
          autoHeight
        />
      </ContentCard>

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
