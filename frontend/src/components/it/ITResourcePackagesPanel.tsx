import { useMemo, useState, type FormEvent } from 'react';
import { Checkbox, FormControlLabel, Stack, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import type { GridColDef } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createResourcePackage,
  deactivateResourcePackage,
  fetchMasterTypes,
  fetchResourcePackages,
  fetchSoftwareCatalog,
  itOperationsKeys,
  updateResourcePackage,
} from '../../api/itOperations';
import { getErrorMessage } from '../../api/client';
import { ClientPaginatedDataGrid } from '../common/ClientPaginatedDataGrid';
import { EmptyState } from '../common/EmptyState';
import { LoadingState } from '../common/LoadingState';
import { ContentCard } from '../ui/cards';
import { ProsohmButton } from '../ui/ProsohmButton';
import {
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
} from '../ui/design-system';
import { useToast } from '../../context/ToastContext';
import type { ResourcePackage } from '../../types/itOperations';
import { optionalString } from '../../utils/formValues';

type LineForm = { asset_type_id: string; quantity: string; is_required: boolean };
type SwLineForm = { software_id: string; requirement_level: string; seats: string };

type PackageForm = {
  code: string;
  name: string;
  description: string;
  requires_ip: boolean;
  hardware: LineForm[];
  software: SwLineForm[];
};

const emptyForm = (): PackageForm => ({
  code: '',
  name: '',
  description: '',
  requires_ip: false,
  hardware: [{ asset_type_id: '', quantity: '1', is_required: true }],
  software: [{ software_id: '', requirement_level: 'required', seats: '1' }],
});

function fromPackage(row: ResourcePackage): PackageForm {
  return {
    code: row.code,
    name: row.name,
    description: row.description ?? '',
    requires_ip: row.requires_ip,
    hardware:
      row.hardware_lines.length > 0
        ? row.hardware_lines.map((line) => ({
            asset_type_id: line.asset_type_id,
            quantity: String(line.quantity),
            is_required: line.is_required,
          }))
        : [{ asset_type_id: '', quantity: '1', is_required: true }],
    software:
      row.software_lines.length > 0
        ? row.software_lines.map((line) => ({
            software_id: line.software_id,
            requirement_level: line.requirement_level,
            seats: String(line.seats),
          }))
        : [{ software_id: '', requirement_level: 'required', seats: '1' }],
  };
}

export function ITResourcePackagesPanel({ canManage }: { canManage: boolean }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ResourcePackage | null>(null);
  const [form, setForm] = useState<PackageForm>(emptyForm());

  const packagesQuery = useQuery({
    queryKey: itOperationsKeys.resourcePackages(),
    queryFn: () => fetchResourcePackages(false),
  });
  const typesQuery = useQuery({
    queryKey: itOperationsKeys.masterTypes(),
    queryFn: () => fetchMasterTypes({ active_only: true }),
  });
  const catalogQuery = useQuery({
    queryKey: itOperationsKeys.software(),
    queryFn: () => fetchSoftwareCatalog({ active_only: true }),
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        code: form.code.trim(),
        name: form.name.trim(),
        description: optionalString(form.description),
        requires_ip: form.requires_ip,
        hardware_lines: form.hardware
          .filter((line) => line.asset_type_id)
          .map((line) => ({
            asset_type_id: line.asset_type_id,
            quantity: Math.max(1, Number(line.quantity) || 1),
            is_required: line.is_required,
          })),
        software_lines: form.software
          .filter((line) => line.software_id)
          .map((line) => ({
            software_id: line.software_id,
            requirement_level: line.requirement_level,
            seats: Math.max(1, Number(line.seats) || 1),
          })),
      };
      if (editing) {
        return updateResourcePackage(editing.id, payload);
      }
      return createResourcePackage(payload);
    },
    onSuccess: () => {
      showSuccess(editing ? 'Package updated' : 'Package created');
      setOpen(false);
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.resourcePackages() });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const deactivateMutation = useMutation({
    mutationFn: deactivateResourcePackage,
    onSuccess: () => {
      showSuccess('Package deactivated');
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.resourcePackages() });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const columns = useMemo<GridColDef<ResourcePackage>[]>(
    () => [
      { field: 'code', headerName: 'Code', width: 120 },
      { field: 'name', headerName: 'Name', flex: 1, minWidth: 180 },
      {
        field: 'hardware_lines',
        headerName: 'Hardware',
        width: 100,
        valueGetter: (_value, row) => row.hardware_lines.length,
      },
      {
        field: 'software_lines',
        headerName: 'Software',
        width: 100,
        valueGetter: (_value, row) => row.software_lines.length,
      },
      {
        field: 'requires_ip',
        headerName: 'IP',
        width: 80,
        valueGetter: (_value, row) => (row.requires_ip ? 'Yes' : 'No'),
      },
      {
        field: 'is_active',
        headerName: 'Active',
        width: 90,
        valueGetter: (_value, row) => (row.is_active ? 'Yes' : 'No'),
      },
      ...(canManage
        ? [
            {
              field: 'actions',
              headerName: '',
              width: 180,
              sortable: false,
              renderCell: (params) => (
                <Stack direction="row" spacing={1}>
                  <ProsohmButton
                    size="small"
                    buttonVariant="secondary"
                    onClick={() => {
                      setEditing(params.row);
                      setForm(fromPackage(params.row));
                      setOpen(true);
                    }}
                  >
                    Edit
                  </ProsohmButton>
                  {params.row.is_active ? (
                    <ProsohmButton
                      size="small"
                      buttonVariant="secondary"
                      onClick={() => deactivateMutation.mutate(params.row.id)}
                    >
                      Deactivate
                    </ProsohmButton>
                  ) : null}
                </Stack>
              ),
            } as GridColDef<ResourcePackage>,
          ]
        : []),
    ],
    [canManage, deactivateMutation],
  );

  const typeOptions = (typesQuery.data ?? []).map((type) => ({
    value: type.id,
    label: type.name,
  }));
  const softwareOptions = (catalogQuery.data ?? []).map((item) => ({
    value: item.id,
    label: item.name,
  }));

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    saveMutation.mutate();
  };

  if (packagesQuery.isLoading) return <LoadingState message="Loading packages…" />;

  return (
    <>
      {canManage ? (
        <Stack direction="row" justifyContent="flex-end" sx={{ mb: 1 }}>
          <ProsohmButton
            startIcon={<AddIcon />}
            onClick={() => {
              setEditing(null);
              setForm(emptyForm());
              setOpen(true);
            }}
          >
            Add package
          </ProsohmButton>
        </Stack>
      ) : null}
      <ContentCard>
        {(packagesQuery.data ?? []).length === 0 ? (
          <EmptyState
            title="No resource packages"
            description="Templates describe typical hardware and software for a role. Assigning a package writes to IT inventory, not a second database."
          />
        ) : (
          <ClientPaginatedDataGrid rows={packagesQuery.data ?? []} columns={columns} />
        )}
      </ContentCard>

      <FormDrawer
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? 'Edit resource package' : 'New resource package'}
        formId="it-resource-package-form"
        submitLabel="Save"
        loading={saveMutation.isPending}
      >
        <BoxForm onSubmit={onSubmit}>
          <FormSection title="Template">
            <FormField
              label="Code"
              required
              value={form.code}
              onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
            />
            <FormField
              label="Name"
              required
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
            <FormField
              label="Description"
              multiline
              minRows={2}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.requires_ip}
                  onChange={(e) => setForm((f) => ({ ...f, requires_ip: e.target.checked }))}
                />
              }
              label="Requires IP address"
            />
          </FormSection>
          <FormSection title="Hardware">
            {form.hardware.map((line, index) => (
              <Stack key={index} direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                <FormSelect
                  label="Asset type"
                  value={line.asset_type_id}
                  options={[{ value: '', label: 'Select type' }, ...typeOptions]}
                  onChange={(e) =>
                    setForm((f) => {
                      const hardware = [...f.hardware];
                      hardware[index] = { ...hardware[index], asset_type_id: String(e.target.value) };
                      return { ...f, hardware };
                    })
                  }
                  sx={{ minWidth: 200 }}
                />
                <FormField
                  label="Qty"
                  type="number"
                  value={line.quantity}
                  onChange={(e) =>
                    setForm((f) => {
                      const hardware = [...f.hardware];
                      hardware[index] = { ...hardware[index], quantity: e.target.value };
                      return { ...f, hardware };
                    })
                  }
                  sx={{ width: 90 }}
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={line.is_required}
                      onChange={(e) =>
                        setForm((f) => {
                          const hardware = [...f.hardware];
                          hardware[index] = { ...hardware[index], is_required: e.target.checked };
                          return { ...f, hardware };
                        })
                      }
                    />
                  }
                  label="Required"
                />
              </Stack>
            ))}
            <ProsohmButton
              buttonVariant="secondary"
              size="small"
              onClick={() =>
                setForm((f) => ({
                  ...f,
                  hardware: [...f.hardware, { asset_type_id: '', quantity: '1', is_required: true }],
                }))
              }
            >
              Add hardware line
            </ProsohmButton>
          </FormSection>
          <FormSection title="Software">
            {form.software.map((line, index) => (
              <Stack key={index} direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                <FormSelect
                  label="Software"
                  value={line.software_id}
                  options={[{ value: '', label: 'Select software' }, ...softwareOptions]}
                  onChange={(e) =>
                    setForm((f) => {
                      const software = [...f.software];
                      software[index] = { ...software[index], software_id: String(e.target.value) };
                      return { ...f, software };
                    })
                  }
                  sx={{ minWidth: 200 }}
                />
                <FormSelect
                  label="Level"
                  value={line.requirement_level}
                  options={[
                    { value: 'required', label: 'Required' },
                    { value: 'optional', label: 'Optional' },
                  ]}
                  onChange={(e) =>
                    setForm((f) => {
                      const software = [...f.software];
                      software[index] = {
                        ...software[index],
                        requirement_level: String(e.target.value),
                      };
                      return { ...f, software };
                    })
                  }
                  sx={{ minWidth: 140 }}
                />
              </Stack>
            ))}
            <ProsohmButton
              buttonVariant="secondary"
              size="small"
              onClick={() =>
                setForm((f) => ({
                  ...f,
                  software: [
                    ...f.software,
                    { software_id: '', requirement_level: 'required', seats: '1' },
                  ],
                }))
              }
            >
              Add software line
            </ProsohmButton>
          </FormSection>
        </BoxForm>
      </FormDrawer>
    </>
  );
}

function BoxForm({
  onSubmit,
  children,
}: {
  onSubmit: (event: FormEvent) => void;
  children: React.ReactNode;
}) {
  return (
    <form id="it-resource-package-form" onSubmit={onSubmit}>
      <Stack spacing={2}>{children}</Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
        Packages are requirement templates. Assignment writes to IT assets, licenses, and IP.
      </Typography>
    </form>
  );
}
