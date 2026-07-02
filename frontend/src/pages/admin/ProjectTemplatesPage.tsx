import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  Chip,
  IconButton,
  TextField,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import EditIcon from '@mui/icons-material/Edit';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import {
  deactivateProjectTemplate,
  duplicateProjectTemplate,
  fetchProjectTemplates,
} from '../../api/projectTemplates';
import type { ProjectTemplate } from '../../types/ProjectTemplate';

export default function ProjectTemplatesPage() {
  const navigate = useNavigate();
  const { showSuccess, showError } = useToast();
  const [templates, setTemplates] = useState<ProjectTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      setTemplates(await fetchProjectTemplates());
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredTemplates = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return templates;
    return templates.filter((template) => {
      const haystack = [
        template.name,
        template.project_type_name ?? '',
        template.customer_name ?? '',
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [search, templates]);

  const handleDuplicate = async (template: ProjectTemplate) => {
    setActionLoading(true);
    try {
      const duplicate = await duplicateProjectTemplate(template.id);
      showSuccess('Template duplicated successfully.');
      await loadData();
      navigate(`/admin/project-templates/${duplicate.id}`);
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionLoading(false);
    }
  };

  const columns: GridColDef<ProjectTemplate>[] = [
    { field: 'name', headerName: 'Template Name', flex: 1.4, minWidth: 180 },
    {
      field: 'project_type_name',
      headerName: 'Project Type',
      flex: 1,
      minWidth: 140,
      valueGetter: (_value, row) => row.project_type_name ?? '—',
    },
    {
      field: 'customer_name',
      headerName: 'Customer',
      flex: 1,
      minWidth: 120,
      valueGetter: (_value, row) => row.customer_name ?? 'General',
    },
    {
      field: 'milestone_count',
      headerName: 'Milestones',
      width: 110,
    },
    {
      field: 'is_default',
      headerName: 'Default',
      width: 90,
      renderCell: (params) =>
        params.value ? <Chip label="Default" size="small" color="primary" /> : '—',
    },
    {
      field: 'is_active',
      headerName: 'Active',
      width: 90,
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
      width: 180,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="Edit">
            <IconButton
              size="small"
              onClick={() => navigate(`/admin/project-templates/${params.row.id}`)}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Duplicate">
            <IconButton
              size="small"
              onClick={() => void handleDuplicate(params.row)}
              disabled={actionLoading}
            >
              <ContentCopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <AdminDeleteButton
            resource="project-templates"
            recordId={params.row.id}
            recordName={params.row.name}
            onDeleted={() => void loadData()}
            onDeactivate={async () => {
              await deactivateProjectTemplate(params.row.id);
              showSuccess('Template deactivated successfully.');
              await loadData();
            }}
          />
        </Box>
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading project templates…" />;

  return (
    <Box>
      <PageHeader
        title="Project Templates"
        subtitle="Configure milestone workflows by project type and customer"
        action={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => navigate('/admin/project-templates/new')}
          >
            Create Template
          </Button>
        }
      />

      <Card sx={{ p: 2, mb: 2 }}>
        <TextField
          label="Search templates"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, width: '100%', maxWidth: 480 }}
        />
      </Card>

      <Card sx={{ p: 1 }}>
        <DataGrid
          rows={filteredTemplates}
          columns={columns}
          autoHeight
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25, 50]}
          initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
          sx={{ border: 0 }}
        />
      </Card>

    </Box>
  );
}
