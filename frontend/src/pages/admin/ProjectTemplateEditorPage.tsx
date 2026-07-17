import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
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
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import AddIcon from '@mui/icons-material/Add';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DeleteIcon from '@mui/icons-material/Delete';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import EditIcon from '@mui/icons-material/Edit';
import { PageHeader } from '../../components/common/PageHeader';
import { StickyFormPageLayout } from '../../components/common/StickyFormPageLayout';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { StickyRecordHeader } from '../../components/ui/design-system';
import { FilterSelect } from '../../components/ui/design-system/FilterSelect';
import { APP_TOP_BAR_OFFSET } from '../../components/ui/design-system/StickyRecordHeader';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { fetchCustomers, fetchUsers } from '../../api/lookups';
import {
  createProjectTemplate,
  fetchAdminProjectTypes,
  fetchProjectTemplate,
  updateProjectTemplate,
} from '../../api/projectTemplates';
import { ensureArray } from '../../types/pagination';
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

const ASSIGNED_ROLE_OPTIONS = [
  'Designer',
  'Senior Designer',
  'Junior Designer',
  'Surfacer',
  'Design Leader',
  'Team Leader',
  'Engineering Manager',
] as const;

function generateRowKey(): string {
  if (typeof globalThis !== 'undefined' && globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `milestone-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createMilestoneRow(
  partial?: Partial<MilestoneRow>,
  sortOrder = 1,
): MilestoneRow {
  return {
    key: partial?.key ?? generateRowKey(),
    milestone_name: partial?.milestone_name ?? '',
    description: partial?.description ?? '',
    sort_order: partial?.sort_order ?? sortOrder,
    default_due_offset_days: partial?.default_due_offset_days ?? null,
    is_required: partial?.is_required ?? true,
    is_visible: partial?.is_visible ?? true,
    project_stage: partial?.project_stage ?? '',
    estimated_hours: partial?.estimated_hours ?? null,
    assigned_role: partial?.assigned_role ?? 'Designer',
    default_assigned_user_id: partial?.default_assigned_user_id ?? null,
  };
}

export default function ProjectTemplateEditorPage() {
  const { templateId } = useParams();
  const location = useLocation();
  const isNew =
    templateId === 'new' || location.pathname.replace(/\/$/, '').endsWith('/new');
  const navigate = useNavigate();
  const { showSuccess, showError } = useToast();
  const [loading, setLoading] = useState(!isNew);
  const [lookupsLoading, setLookupsLoading] = useState(true);
  const [lookupsError, setLookupsError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const [projectTypes, setProjectTypes] = useState<ProjectType[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [users, setUsers] = useState<Array<{ id: string; first_name: string; last_name: string }>>([]);
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
    setLookupsLoading(true);
    setLookupsError(null);
    try {
      const [types, customerRows, userRows] = await Promise.all([
        fetchAdminProjectTypes(),
        fetchCustomers(),
        fetchUsers(),
      ]);
      const safeTypes = ensureArray<ProjectType>(types);
      const safeCustomers = ensureArray<Customer>(customerRows);
      setProjectTypes(safeTypes.filter((type) => type.is_active));
      setCustomers(safeCustomers.filter((customer) => customer.is_active));
      setUsers(ensureArray(userRows));
    } catch (error) {
      setLookupsError(error);
      showError(getErrorMessage(error));
    } finally {
      setLookupsLoading(false);
    }
  }, [showError]);

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
              is_visible: milestone.is_visible ?? true,
              project_stage: milestone.project_stage ?? '',
              estimated_hours: milestone.estimated_hours ?? null,
              assigned_role: milestone.assigned_role ?? 'Designer',
              default_assigned_user_id: milestone.default_assigned_user_id ?? null,
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
              is_visible: milestone.is_visible ?? true,
              project_stage: milestone.project_stage ?? '',
              estimated_hours: milestone.estimated_hours ?? null,
              assigned_role: milestone.assigned_role ?? 'Designer',
              default_assigned_user_id: milestone.default_assigned_user_id ?? null,
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
    if (!baselineRef.current) {
      setForm(emptyForm);
      setMilestones([]);
      return;
    }
    try {
      const parsed = JSON.parse(baselineRef.current) as {
        form: TemplateFormState;
        milestones: MilestoneRow[];
      };
      setForm(parsed.form);
      setMilestones(parsed.milestones);
    } catch {
      setForm(emptyForm);
      setMilestones([]);
    }
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

  const duplicateMilestone = (row: MilestoneRow) => {
    setMilestones((current) =>
      reindexMilestones([
        ...current,
        createMilestoneRow(
          {
            ...row,
            key: generateRowKey(),
            milestone_name: `${row.milestone_name} (Copy)`,
          },
          current.length + 1,
        ),
      ]),
    );
  };

  const moveMilestone = (index: number, direction: -1 | 1) => {
    const ordered = sortedMilestones.slice();
    const target = index + direction;
    if (target < 0 || target >= ordered.length) return;
    const [moved] = ordered.splice(index, 1);
    ordered.splice(target, 0, moved);
    setMilestones(reindexMilestones(ordered));
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
        milestones: sortedMilestones.map(({ key: _key, ...milestone }) => ({
          ...milestone,
          project_stage: milestone.project_stage || null,
          assigned_role: milestone.assigned_role || null,
          default_assigned_user_id: milestone.default_assigned_user_id || null,
        })),
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

  if (lookupsLoading || loading) {
    return <LoadingState message="Loading template editor…" />;
  }

  if (lookupsError) {
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
        <ErrorState
          error={lookupsError}
          title="Unable to load template editor"
          onRetry={() => void loadLookups()}
        />
      </Box>
    );
  }

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
            <FilterSelect
              label="Customer (optional)"
              size="medium"
              value={form.customer_id}
              onChange={(event) =>
                setForm((current) => ({ ...current, customer_id: String(event.target.value) }))
              }
            >
              <MenuItem value="">General (all customers)</MenuItem>
              {customers.map((customer) => (
                <MenuItem key={customer.id} value={customer.id}>
                  {customer.name}
                </MenuItem>
              ))}
            </FilterSelect>
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
              <TableCell width={120}>Assigned Role</TableCell>
              <TableCell width={120}>Est. Hours</TableCell>
              <TableCell width={90}>Required</TableCell>
              <TableCell width={90}>Visible</TableCell>
              <TableCell width={140}>Actions</TableCell>
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
                <TableCell>{formatCellValue(row.assigned_role)}</TableCell>
                <TableCell>{formatCellValue(row.estimated_hours)}</TableCell>
                <TableCell>{row.is_required ? 'Yes' : 'No'}</TableCell>
                <TableCell>{row.is_visible !== false ? 'Yes' : 'No'}</TableCell>
                <TableCell>
                  <Tooltip title="Move up">
                    <IconButton size="small" disabled={index === 0} onClick={() => moveMilestone(index, -1)}>
                      <ArrowUpwardIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Move down">
                    <IconButton
                      size="small"
                      disabled={index === sortedMilestones.length - 1}
                      onClick={() => moveMilestone(index, 1)}
                    >
                      <ArrowDownwardIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Duplicate">
                    <IconButton size="small" onClick={() => duplicateMilestone(row)}>
                      <ContentCopyIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
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
              <Grid size={{ xs: 12, md: 3 }}>
                <FormControl fullWidth>
                  <InputLabel>Assigned Role</InputLabel>
                  <Select
                    label="Assigned Role"
                    value={milestoneDraft.assigned_role ?? 'Designer'}
                    onChange={(event) =>
                      setMilestoneDraft((current) => ({
                        ...current,
                        assigned_role: String(event.target.value),
                      }))
                    }
                  >
                    {ASSIGNED_ROLE_OPTIONS.map((role) => (
                      <MenuItem key={role} value={role}>
                        {role}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, md: 3 }}>
                <FilterSelect
                  label="Default User (optional)"
                  size="medium"
                  value={milestoneDraft.default_assigned_user_id ?? ''}
                  onChange={(event) =>
                    setMilestoneDraft((current) => ({
                      ...current,
                      default_assigned_user_id: String(event.target.value) || null,
                    }))
                  }
                >
                  <MenuItem value="">Auto from role</MenuItem>
                  {users.map((user) => (
                    <MenuItem key={user.id} value={user.id}>
                      {user.first_name} {user.last_name}
                    </MenuItem>
                  ))}
                </FilterSelect>
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
                  label="Mandatory"
                />
              </Grid>
              <Grid size={{ xs: 12, md: 2 }} sx={{ display: 'flex', alignItems: 'center' }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={milestoneDraft.is_visible !== false}
                      onChange={(event) =>
                        setMilestoneDraft((current) => ({
                          ...current,
                          is_visible: event.target.checked,
                        }))
                      }
                    />
                  }
                  label="Visible"
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
