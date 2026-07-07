import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  FormControl,
  FormControlLabel,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DeleteIcon from '@mui/icons-material/Delete';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import EditIcon from '@mui/icons-material/Edit';
import { PageHeader } from '../../components/common/PageHeader';
import { StickyFormPageLayout } from '../../components/common/StickyFormPageLayout';
import { LoadingState } from '../../components/common/LoadingState';
import { StickyRecordHeader } from '../../components/ui/design-system';
import { APP_TOP_BAR_OFFSET } from '../../components/ui/design-system/StickyRecordHeader';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { fetchCustomers } from '../../api/lookups';
import {
  createProjectTemplate,
  fetchAdminProjectTypes,
  fetchProjectTemplate,
  updateProjectTemplate,
} from '../../api/projectTemplates';
import type {
  ProjectTemplateMilestoneInput,
  ProjectType,
} from '../../types/ProjectTemplate';
import type { Customer } from '../../types';
import { formatCellValue } from '../../utils/format';

interface MilestoneRow extends ProjectTemplateMilestoneInput {
  key: string;
}

interface TemplateFormState {
  name: string;
  description: string;
  project_type_id: string;
  customer_id: string;
  is_default: boolean;
  is_active: boolean;
}

const emptyForm: TemplateFormState = {
  name: '',
  description: '',
  project_type_id: '',
  customer_id: '',
  is_default: false,
  is_active: true,
};

function createMilestoneRow(
  partial?: Partial<MilestoneRow>,
  sortOrder = 1,
): MilestoneRow {
  return {
    key: partial?.key ?? crypto.randomUUID(),
    milestone_name: partial?.milestone_name ?? '',
    description: partial?.description ?? '',
    sort_order: partial?.sort_order ?? sortOrder,
    default_due_offset_days: partial?.default_due_offset_days ?? null,
    is_required: partial?.is_required ?? true,
    project_stage: partial?.project_stage ?? '',
    estimated_hours: partial?.estimated_hours ?? null,
  };
}

export default function ProjectTemplateEditorPage() {
  const { templateId } = useParams();
  const isNew = templateId === 'new';
  const navigate = useNavigate();
  const { showSuccess, showError } = useToast();
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [projectTypes, setProjectTypes] = useState<ProjectType[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [form, setForm] = useState<TemplateFormState>(emptyForm);
  const [milestones, setMilestones] = useState<MilestoneRow[]>([]);
  const [editingMilestoneKey, setEditingMilestoneKey] = useState<string | null>(null);
  const [milestoneDraft, setMilestoneDraft] = useState<MilestoneRow>(createMilestoneRow());
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const baselineRef = useRef('');

  const serializeEditorState = (templateForm: TemplateFormState, rows: MilestoneRow[]) =>
    JSON.stringify({ form: templateForm, milestones: rows });

  const captureBaseline = (templateForm: TemplateFormState, rows: MilestoneRow[]) => {
    baselineRef.current = serializeEditorState(templateForm, rows);
  };

  const loadLookups = useCallback(async () => {
    const [types, customerRows] = await Promise.all([
      fetchAdminProjectTypes(),
      fetchCustomers(),
    ]);
    setProjectTypes(types.filter((type) => type.is_active));
    setCustomers(customerRows.filter((customer) => customer.is_active));
  }, []);

  const loadTemplate = useCallback(async () => {
    if (isNew || !templateId) return;
    setLoading(true);
    try {
      const template = await fetchProjectTemplate(templateId);
      setForm({
        name: template.name,
        description: template.description ?? '',
        project_type_id: template.project_type_id,
        customer_id: template.customer_id ?? '',
        is_default: template.is_default,
        is_active: template.is_active,
      });
      setMilestones(
        template.milestones
          .slice()
          .sort((left, right) => left.sort_order - right.sort_order)
          .map((milestone) =>
            createMilestoneRow({
              key: milestone.id,
              milestone_name: milestone.milestone_name,
              description: milestone.description,
              sort_order: milestone.sort_order,
              default_due_offset_days: milestone.default_due_offset_days,
              is_required: milestone.is_required,
              project_stage: milestone.project_stage ?? '',
              estimated_hours: milestone.estimated_hours ?? null,
            }),
          ),
      );
      captureBaseline(
        {
          name: template.name,
          description: template.description ?? '',
          project_type_id: template.project_type_id,
          customer_id: template.customer_id ?? '',
          is_default: template.is_default,
          is_active: template.is_active,
        },
        template.milestones
          .slice()
          .sort((left, right) => left.sort_order - right.sort_order)
          .map((milestone) =>
            createMilestoneRow({
              key: milestone.id,
              milestone_name: milestone.milestone_name,
              description: milestone.description,
              sort_order: milestone.sort_order,
              default_due_offset_days: milestone.default_due_offset_days,
              is_required: milestone.is_required,
              project_stage: milestone.project_stage ?? '',
              estimated_hours: milestone.estimated_hours ?? null,
            }),
          ),
      );
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [isNew, showError, templateId]);

  useEffect(() => {
    void loadLookups();
  }, [loadLookups]);

  useEffect(() => {
    void loadTemplate();
  }, [loadTemplate]);

  useEffect(() => {
    if (isNew) {
      captureBaseline(emptyForm, []);
    }
  }, [isNew]);

  const isDirty = useMemo(
    () => serializeEditorState(form, milestones) !== baselineRef.current,
    [form, milestones],
  );

  const handleDiscard = () => {
    const parsed = JSON.parse(baselineRef.current) as {
      form: TemplateFormState;
      milestones: MilestoneRow[];
    };
    setForm(parsed.form);
    setMilestones(parsed.milestones);
  };

  const sortedMilestones = useMemo(
    () => milestones.slice().sort((left, right) => left.sort_order - right.sort_order),
    [milestones],
  );

  const reindexMilestones = (rows: MilestoneRow[]) =>
    rows.map((row, index) => ({ ...row, sort_order: index + 1 }));

  const openCreateMilestone = () => {
    setEditingMilestoneKey(null);
    setMilestoneDraft(createMilestoneRow({}, milestones.length + 1));
  };

  const openEditMilestone = (row: MilestoneRow) => {
    setEditingMilestoneKey(row.key);
    setMilestoneDraft({ ...row });
  };

  const saveMilestoneDraft = () => {
    if (!milestoneDraft.milestone_name.trim()) {
      showError('Milestone name is required.');
      return;
    }
    if (editingMilestoneKey) {
      setMilestones((current) =>
        reindexMilestones(
          current.map((row) => (row.key === editingMilestoneKey ? milestoneDraft : row)),
        ),
      );
    } else {
      setMilestones((current) => reindexMilestones([...current, milestoneDraft]));
    }
    setEditingMilestoneKey(null);
    setMilestoneDraft(createMilestoneRow({}, milestones.length + 2));
  };

  const deleteMilestone = (key: string) => {
    setMilestones((current) =>
      reindexMilestones(current.filter((row) => row.key !== key)),
    );
  };

  const handleDragStart = (index: number) => {
    setDragIndex(index);
  };

  const handleDrop = (index: number) => {
    if (dragIndex === null || dragIndex === index) {
      setDragIndex(null);
      return;
    }
    setMilestones(() => {
      const ordered = sortedMilestones.slice();
      const [moved] = ordered.splice(dragIndex, 1);
      ordered.splice(index, 0, moved);
      return reindexMilestones(ordered);
    });
    setDragIndex(null);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.project_type_id) {
      showError('Template name and project type are required.');
      return;
    }
    if (milestones.length === 0) {
      showError('Add at least one milestone to the template.');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description || null,
        project_type_id: form.project_type_id,
        customer_id: form.customer_id || null,
        is_default: form.is_default,
        is_active: form.is_active,
        milestones: sortedMilestones.map(({ key: _key, ...milestone }) => milestone),
      };

      if (isNew) {
        const created = await createProjectTemplate(payload);
        showSuccess('Template created successfully.');
        navigate(`/admin/project-templates/${created.id}`, { replace: true });
      } else if (templateId) {
        await updateProjectTemplate(templateId, payload);
        showSuccess('Template updated successfully.');
        captureBaseline(form, sortedMilestones);
        await loadTemplate();
      }
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState message="Loading template editor…" />;

  return (
    <Box>
      <PageHeader
        title={isNew ? 'Create Project Template' : 'Edit Project Template'}
        subtitle="Define milestone workflow steps for project creation"
        action={
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/admin/project-templates')}
          >
            Back
          </Button>
        }
      />

      <StickyFormPageLayout
        dirty={isDirty}
        onSave={() => void handleSave()}
        onDiscard={handleDiscard}
        saving={saving}
        saveLabel="Save Template"
        header={
          <StickyRecordHeader
            compact
            primaryLabel={form.name || 'New Project Template'}
            secondaryLabel={
              projectTypes.find((type) => type.id === form.project_type_id)?.name ??
              'Milestone workflow template'
            }
            stickyTop={APP_TOP_BAR_OFFSET}
          />
        }
      >

      <Card sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              label="Template Name"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              required
              fullWidth
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControl fullWidth required>
              <InputLabel>Project Type</InputLabel>
              <Select
                label="Project Type"
                value={form.project_type_id}
                onChange={(event) =>
                  setForm((current) => ({ ...current, project_type_id: event.target.value }))
                }
              >
                {projectTypes.map((projectType) => (
                  <MenuItem key={projectType.id} value={projectType.id}>
                    {projectType.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12 }}>
            <TextField
              label="Description"
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({ ...current, description: event.target.value }))
              }
              multiline
              minRows={2}
              fullWidth
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControl fullWidth>
              <InputLabel>Customer (optional)</InputLabel>
              <Select
                label="Customer (optional)"
                value={form.customer_id}
                onChange={(event) =>
                  setForm((current) => ({ ...current, customer_id: event.target.value }))
                }
              >
                <MenuItem value="">General (all customers)</MenuItem>
                {customers.map((customer) => (
                  <MenuItem key={customer.id} value={customer.id}>
                    {customer.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_default}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, is_default: event.target.checked }))
                  }
                  disabled={Boolean(form.customer_id)}
                />
              }
              label="Default Template"
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
          </Grid>
        </Grid>
      </Card>

      <Card sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Milestones</Typography>
          <Button startIcon={<AddIcon />} onClick={openCreateMilestone}>
            Add Milestone
          </Button>
        </Box>

        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell width={48} />
              <TableCell width={70}>Order</TableCell>
              <TableCell>Milestone Name</TableCell>
              <TableCell>Description</TableCell>
              <TableCell width={120}>Due Offset</TableCell>
              <TableCell width={120}>Stage</TableCell>
              <TableCell width={120}>Est. Hours</TableCell>
              <TableCell width={90}>Required</TableCell>
              <TableCell width={100}>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sortedMilestones.map((row, index) => (
              <TableRow
                key={row.key}
                hover
                draggable
                onDragStart={() => handleDragStart(index)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => handleDrop(index)}
                sx={{ cursor: 'grab' }}
              >
                <TableCell>
                  <DragIndicatorIcon fontSize="small" color="action" />
                </TableCell>
                <TableCell>{row.sort_order}</TableCell>
                <TableCell>{row.milestone_name}</TableCell>
                <TableCell>{formatCellValue(row.description)}</TableCell>
                <TableCell>{formatCellValue(row.default_due_offset_days)}</TableCell>
                <TableCell>{formatCellValue(row.project_stage)}</TableCell>
                <TableCell>{formatCellValue(row.estimated_hours)}</TableCell>
                <TableCell>{row.is_required ? 'Yes' : 'No'}</TableCell>
                <TableCell>
                  <Tooltip title="Edit">
                    <IconButton size="small" onClick={() => openEditMilestone(row)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton size="small" onClick={() => deleteMilestone(row.key)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {(editingMilestoneKey !== null || milestoneDraft.milestone_name || !milestones.length) && (
          <Box sx={{ mt: 3, p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 2 }}>
              {editingMilestoneKey ? 'Edit Milestone' : 'Add Milestone'}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField
                  label="Milestone Name"
                  value={milestoneDraft.milestone_name}
                  onChange={(event) =>
                    setMilestoneDraft((current) => ({
                      ...current,
                      milestone_name: event.target.value,
                    }))
                  }
                  fullWidth
                  required
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField
                  label="Description"
                  value={milestoneDraft.description ?? ''}
                  onChange={(event) =>
                    setMilestoneDraft((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                  fullWidth
                />
              </Grid>
              <Grid size={{ xs: 12, md: 2 }}>
                <TextField
                  label="Due Offset (days)"
                  type="number"
                  value={milestoneDraft.default_due_offset_days ?? ''}
                  onChange={(event) =>
                    setMilestoneDraft((current) => ({
                      ...current,
                      default_due_offset_days: event.target.value
                        ? Number(event.target.value)
                        : null,
                    }))
                  }
                  fullWidth
                />
              </Grid>
              <Grid size={{ xs: 12, md: 2 }}>
                <FormControl fullWidth>
                  <InputLabel>Stage</InputLabel>
                  <Select
                    label="Stage"
                    value={milestoneDraft.project_stage ?? ''}
                    onChange={(event) =>
                      setMilestoneDraft((current) => ({
                        ...current,
                        project_stage: String(event.target.value),
                      }))
                    }
                  >
                    <MenuItem value="">None</MenuItem>
                    <MenuItem value="preliminary">Preliminary</MenuItem>
                    <MenuItem value="intermediate">Intermediate</MenuItem>
                    <MenuItem value="final">Final</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, md: 2 }}>
                <TextField
                  label="Est. Hours"
                  type="number"
                  value={milestoneDraft.estimated_hours ?? ''}
                  onChange={(event) =>
                    setMilestoneDraft((current) => ({
                      ...current,
                      estimated_hours: event.target.value
                        ? Number(event.target.value)
                        : null,
                    }))
                  }
                  fullWidth
                />
              </Grid>
              <Grid size={{ xs: 12, md: 2 }} sx={{ display: 'flex', alignItems: 'center' }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={milestoneDraft.is_required ?? true}
                      onChange={(event) =>
                        setMilestoneDraft((current) => ({
                          ...current,
                          is_required: event.target.checked,
                        }))
                      }
                    />
                  }
                  label="Required"
                />
              </Grid>
              <Grid size={{ xs: 12 }}>
                <Button variant="contained" onClick={saveMilestoneDraft}>
                  {editingMilestoneKey ? 'Update Milestone' : 'Add Milestone'}
                </Button>
              </Grid>
            </Grid>
          </Box>
        )}
      </Card>
      </StickyFormPageLayout>
    </Box>
  );
}
