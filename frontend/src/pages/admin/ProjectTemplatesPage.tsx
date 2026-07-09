import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Chip, IconButton, Stack, Tooltip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ViewKanbanOutlinedIcon from '@mui/icons-material/ViewKanbanOutlined';
import type { GridColDef } from '@mui/x-data-grid';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
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
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  DrawerQuickActions,
  FormField,
  FormSection,
  ProsohmDataGrid,
  RecordDetailDrawer,
  SearchToolbar,
  TableRowActions,
} from '../../components/ui/design-system';
import { formatCellValue } from '../../utils/format';
import { canDeleteRecords } from '../../utils/permissions';
import { useAuth } from '../../context/AuthContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';

export default function ProjectTemplatesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const [templates, setTemplates] = useState<ProjectTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<ProjectTemplate | null>(null);
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

  const openEdit = (template: ProjectTemplate) => {
    navigate(`/admin/project-templates/${template.id}`);
  };

  const actionsColumnWidth = isAdmin
    ? DATA_GRID_ACTIONS_COLUMN_WIDTH + 80
    : DATA_GRID_ACTIONS_COLUMN_WIDTH + 40;

  const columns: GridColDef<ProjectTemplate>[] = [
    { field: 'name', headerName: 'Template Name', flex: 1.4, minWidth: 180 },
    {
      field: 'project_type_name',
      headerName: 'Project Type',
      flex: 1,
      minWidth: 140,
      valueGetter: (_value, row) => formatCellValue(row.project_type_name),
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
      field: 'projects_using_count',
      headerName: 'Projects Using',
      width: 130,
      valueGetter: (_value, row) => row.projects_using_count ?? 0,
    },
    {
      field: 'is_default',
      headerName: 'Default',
      width: 90,
      renderCell: (params) =>
        params.value ? <Chip label="Default" size="small" color="primary" /> : null,
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
      headerName: '',
      width: actionsColumnWidth,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
          <Tooltip title="Duplicate">
            <IconButton
              size="small"
              onClick={(event) => {
                event.stopPropagation();
                void handleDuplicate(params.row);
              }}
              disabled={actionLoading}
            >
              <ContentCopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <TableRowActions
            onEdit={() => openEdit(params.row)}
            deleteAction={
              isAdmin ? (
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
              ) : undefined
            }
          />
          </Box>
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading project templates…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Project Templates"
        subtitle="Configure milestone workflows by project type and customer"
        action={
          <ProsohmButton
            buttonVariant="primary"
            startIcon={<AddIcon />}
            onClick={() => navigate('/admin/project-templates/new')}
          >
            Create Template
          </ProsohmButton>
        }
      />

      <SearchToolbar>
        <FormField
          label="Search templates"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1, maxWidth: 480 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ProsohmDataGrid
          rows={filteredTemplates}
          columns={columns}
          autoHeight
          pageSizeOptions={[25, 50, 100]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          onRowOpen={(rowId) => {
            navigate(`/admin/project-templates/${rowId}`);
          }}
        />
      </ContentCard>

      <RecordDetailDrawer
        open={Boolean(selectedTemplate)}
        onClose={() => setSelectedTemplate(null)}
        title={selectedTemplate?.name ?? 'Template'}
        subtitle="Project template"
        icon={ViewKanbanOutlinedIcon}
        status={
          selectedTemplate ? (
            <Stack direction="row" spacing={1}>
              <Chip
                label={selectedTemplate.is_active ? 'Active' : 'Inactive'}
                size="small"
                color={selectedTemplate.is_active ? 'success' : 'default'}
              />
              {selectedTemplate.is_default ? (
                <Chip label="Default" size="small" color="primary" />
              ) : null}
            </Stack>
          ) : null
        }
        quickActions={
          selectedTemplate ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  openEdit(selectedTemplate);
                  setSelectedTemplate(null);
                }}
              >
                Edit
              </ProsohmButton>
              {isAdmin ? (
                <AdminDeleteButton
                  mode="button"
                  resource="project-templates"
                  recordId={selectedTemplate.id}
                  recordName={selectedTemplate.name}
                  onDeleted={() => {
                    setSelectedTemplate(null);
                    void loadData();
                  }}
                  onDeactivate={async () => {
                    await deactivateProjectTemplate(selectedTemplate.id);
                    showSuccess('Template deactivated successfully.');
                    setSelectedTemplate(null);
                    await loadData();
                  }}
                />
              ) : null}
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedTemplate ? (
          <FormSection title="Overview" icon={ViewKanbanOutlinedIcon}>
            <FormField label="Template Name" value={selectedTemplate.name} slotProps={{ input: { readOnly: true } }} />
            <FormField
              label="Project Type"
              value={formatCellValue(selectedTemplate.project_type_name) || '—'}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Customer"
              value={selectedTemplate.customer_name ?? 'General'}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Milestones"
              value={String(selectedTemplate.milestone_count ?? 0)}
              slotProps={{ input: { readOnly: true } }}
            />
          </FormSection>
        ) : null}
      </RecordDetailDrawer>
    </PageContainer>
  );
}
