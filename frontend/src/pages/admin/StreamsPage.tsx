import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import {
  Box,
  Chip,
  FormControlLabel,
  IconButton,
  Switch,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import StreamOutlinedIcon from '@mui/icons-material/StreamOutlined';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { LoadingState } from '../../components/common/LoadingState';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { streamsApi } from '../../api/resources';
import type { Stream } from '../../types';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import { ContentCard } from '../../components/ui/cards';
import {
  FormDrawer,
  FormField,
  ModernDrawer,
  SearchToolbar,
} from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { formatCellValue } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';

interface StreamFormState {
  name: string;
  description: string;
  is_active: boolean;
}

const emptyForm: StreamFormState = {
  name: '',
  description: '',
  is_active: true,
};

export default function StreamsPage() {
  const { showSuccess, showError } = useToast();
  const [streams, setStreams] = useState<Stream[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [viewStream, setViewStream] = useState<Stream | null>(null);
  const [editingStream, setEditingStream] = useState<Stream | null>(null);
  const [form, setForm] = useState<StreamFormState>(emptyForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      setStreams(await streamsApi.list());
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredStreams = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return streams;
    return streams.filter((stream) => {
      const haystack = [stream.name, stream.description ?? ''].join(' ').toLowerCase();
      return haystack.includes(term);
    });
  }, [search, streams]);

  const openCreate = () => {
    setEditingStream(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (stream: Stream) => {
    setEditingStream(stream);
    setForm({
      name: stream.name,
      description: stream.description ?? '',
      is_active: stream.is_active,
    });
    setFormOpen(true);
  };

  const handleSave = async (event?: FormEvent) => {
    event?.preventDefault();
    const validationError = validateRequiredFields(form, [{ key: 'name', label: 'Name' }]);
    if (validationError) {
      showError(validationError);
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: optionalString(form.description),
        is_active: form.is_active,
      };
      if (editingStream) {
        await streamsApi.update(editingStream.id, payload);
        showSuccess('Stream updated successfully.');
      } else {
        await streamsApi.create(payload);
        showSuccess('Stream created successfully.');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const columns: GridColDef<Stream>[] = [
    { field: 'name', headerName: 'Name', flex: 1.2, minWidth: 140 },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 180,
      valueFormatter: (value) => formatCellValue(value as string | null),
    },
    {
      field: 'is_active',
      headerName: 'Active',
      width: 100,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Active' : 'Inactive'}
          size="small"
          color={params.value ? 'success' : 'default'}
        />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 130,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="View">
            <IconButton size="small" onClick={() => setViewStream(params.row)}>
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEdit(params.row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <AdminDeleteButton
            resource="streams"
            recordId={params.row.id}
            recordName={params.row.name}
            onDeleted={() => void loadData()}
            onDeactivate={async () => {
              await streamsApi.update(params.row.id, { is_active: false });
              showSuccess('Stream deactivated.');
              await loadData();
            }}
          />
        </Box>
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading streams…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Streams"
        subtitle="Manage engineering streams"
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create Stream
          </ProsohmButton>
        }
      />

      <SearchToolbar>
        <FormField
          label="Search by name or description"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1, maxWidth: 480 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <DataGrid
          rows={filteredStreams}
          columns={columns}
          autoHeight
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
          sx={{ border: 0 }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingStream ? 'Edit Stream' : 'Create Stream'}
        subtitle="Engineering stream configuration"
        icon={StreamOutlinedIcon}
        formId="stream-form"
        submitLabel={editingStream ? 'Save Changes' : 'Create Stream'}
        loading={saving}
        onSubmit={() => void handleSave()}
      >
        <Box
          id="stream-form"
          component="form"
          onSubmit={(event) => void handleSave(event)}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
        >
          <FormField
            label="Name"
            value={form.name}
            onChange={(event) =>
              setForm((current) => ({ ...current, name: event.target.value }))
            }
            required
          />
          <FormField
            label="Description"
            value={form.description}
            onChange={(event) =>
              setForm((current) => ({ ...current, description: event.target.value }))
            }
            multiline
            minRows={3}
          />
          <FormControlLabel
            control={
              <Switch
                checked={form.is_active}
                onChange={(event) =>
                  setForm((current) => ({ ...current, is_active: event.target.checked }))
                }
              />
            }
            label="Active"
          />
        </Box>
      </FormDrawer>

      <ModernDrawer
        open={Boolean(viewStream)}
        onClose={() => setViewStream(null)}
        title="Stream Details"
        subtitle={viewStream?.name}
        icon={StreamOutlinedIcon}
        footer={
          <ProsohmButton buttonVariant="outlined" onClick={() => setViewStream(null)}>
            Close
          </ProsohmButton>
        }
      >
        {viewStream ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormField label="Name" value={viewStream.name} slotProps={{ input: { readOnly: true } }} />
            <FormField
              label="Description"
              value={formatCellValue(viewStream.description)}
              multiline
              minRows={2}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Status"
              value={viewStream.is_active ? 'Active' : 'Inactive'}
              slotProps={{ input: { readOnly: true } }}
            />
          </Box>
        ) : null}
      </ModernDrawer>
    </PageContainer>
  );
}
