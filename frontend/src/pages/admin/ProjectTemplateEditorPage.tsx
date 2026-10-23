import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  FormControl,
  FormControlLabel,
  FormHelperText,
  Grid,
  IconButton,
  InputLabel,
  ListItemText,
  MenuItem,
  OutlinedInput,
  Select,
  Stack,
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
  createProjectTemplateRevision,
  deactivateProjectTemplate,
  duplicateProjectTemplate,
  fetchAdminProjectTypes,
  fetchProjectTemplate,
  fetchProjectTemplates,
  fetchProjectTemplateVersions,
  previewProjectTemplate,
  reactivateProjectTemplate,
  updateProjectTemplate,
} from '../../api/projectTemplates';
import { ensureArray } from '../../types/pagination';
import {
  PLANNED_STAGE_OPTIONS,
  PROJECT_STAGE_OPTIONS,
  projectStageLabel,
  type ProjectTemplate,
  type ProjectTemplateDetail,
  type ProjectTemplateMilestoneInput,
  type ProjectTemplateVersion,
  type ProjectType,
  type TemplatePreview,
  type TemplateSchedulingMode,
} from '../../types/ProjectTemplate';
import type { Customer } from '../../types';
import { formatCellValue, formatDate, formatDateTime, formatNumber } from '../../utils/format';

interface MilestoneRow extends ProjectTemplateMilestoneInput {
  key: string;
  persisted: boolean;
  depends_on: string[];
}

interface TemplateFormState {
  name: string;
  description: string;
  project_type_id: string;
  customer_id: string;
  is_default: boolean;
  is_active: boolean;
  scheduling_mode: TemplateSchedulingMode;
  revision_note: string;
}

const emptyForm: TemplateFormState = {
  name: '',
  description: '',
  project_type_id: '',
  customer_id: '',
  is_default: false,
  is_active: true,
  scheduling_mode: 'sequential',
  revision_note: '',
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

function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function createMilestoneRow(
  partial?: Partial<MilestoneRow>,
  sortOrder = 1,
): MilestoneRow {
  return {
    key: partial?.key ?? generateRowKey(),
    persisted: partial?.persisted ?? false,
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
    depends_on: partial?.depends_on ?? [],
  };
}

function formFromTemplate(template: ProjectTemplateDetail): TemplateFormState {
  return {
    name: template.name,
    description: template.description ?? '',
    project_type_id: template.project_type_id,
    customer_id: template.customer_id ?? '',
    is_default: template.is_default,
    is_active: template.is_active,
    scheduling_mode: template.scheduling_mode ?? 'sequential',
    revision_note: '',
  };
}

function rowsFromTemplate(template: ProjectTemplateDetail): MilestoneRow[] {
  return template.milestones
    .slice()
    .sort((left, right) => left.sort_order - right.sort_order)
    .map((milestone) =>
      createMilestoneRow({
        key: milestone.id,
        persisted: true,
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
        depends_on: (milestone.depends_on ?? []).map(String),
      }),
    );
}

export default function ProjectTemplateEditorPage() {
  const { templateId } = useParams();
  // Remount per template so switching between templates (or to "new") never shows stale state.
  return <ProjectTemplateEditor key={templateId ?? 'new'} templateId={templateId} />;
}

function ProjectTemplateEditor({ templateId }: { templateId: string | undefined }) {
  const location = useLocation();
  const isNew =
    templateId === 'new' || location.pathname.replace(/\/$/, '').endsWith('/new');
  const navigate = useNavigate();
  const { showSuccess, showError } = useToast();
  const [loading, setLoading] = useState(!isNew);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [lookupsLoading, setLookupsLoading] = useState(true);
  const [lookupsError, setLookupsError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [projectTypes, setProjectTypes] = useState<ProjectType[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [users, setUsers] = useState<Array<{ id: string; first_name: string; last_name: string }>>([]);
  const [form, setForm] = useState<TemplateFormState>(emptyForm);
  const [template, setTemplate] = useState<ProjectTemplateDetail | null>(null);
  const [milestones, setMilestones] = useState<MilestoneRow[]>([]);
  const [draftOpen, setDraftOpen] = useState(false);
  const [editingMilestoneKey, setEditingMilestoneKey] = useState<string | null>(null);
  const [milestoneDraft, setMilestoneDraft] = useState<MilestoneRow>(createMilestoneRow());
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [sourceTemplates, setSourceTemplates] = useState<ProjectTemplate[]>([]);
  const [copyFromTemplateId, setCopyFromTemplateId] = useState('');
  const [copyingMilestones, setCopyingMilestones] = useState(false);
  const [versions, setVersions] = useState<ProjectTemplateVersion[]>([]);
  const [versionsError, setVersionsError] = useState<unknown>(null);
  const [revisionNote, setRevisionNote] = useState('');
  const [previewStart, setPreviewStart] = useState(todayIso());
  const [previewHours, setPreviewHours] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<TemplatePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const baselineRef = useRef('');
  const milestonesSectionRef = useRef<HTMLDivElement | null>(null);
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);

  const serializeEditorState = (templateForm: TemplateFormState, rows: MilestoneRow[]) =>
    JSON.stringify({ form: templateForm, milestones: rows });

  const captureBaseline = (templateForm: TemplateFormState, rows: MilestoneRow[]) => {
    baselineRef.current = serializeEditorState(templateForm, rows);
  };

  const openCreateMilestone = useCallback((count: number) => {
    setEditingMilestoneKey(null);
    setMilestoneDraft(createMilestoneRow({}, count + 1));
    setDraftOpen(true);
  }, []);

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

  useEffect(() => {
    if (!isNew) return;
    const prefillCustomerId = searchParams.get('customer_id') ?? '';
    const prefillProjectTypeId = searchParams.get('project_type_id') ?? '';
    if (!prefillCustomerId && !prefillProjectTypeId) return;
    setForm((current) => ({
      ...current,
      customer_id: prefillCustomerId || current.customer_id,
      project_type_id: prefillProjectTypeId || current.project_type_id,
      is_default: prefillCustomerId ? false : current.is_default,
    }));
  }, [isNew, searchParams]);

  useEffect(() => {
    if (location.hash !== '#milestones') return;
    const timer = window.setTimeout(() => {
      milestonesSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      openCreateMilestone(milestones.length);
    }, 150);
    return () => window.clearTimeout(timer);
    // Intentionally only re-run when navigation hash / load state changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.hash, loading, lookupsLoading]);

  useEffect(() => {
    if (!form.project_type_id) {
      setSourceTemplates([]);
      return;
    }
    let cancelled = false;
    void fetchProjectTemplates({
      project_type_id: form.project_type_id,
      limit: 200,
    })
      .then((rows) => {
        if (cancelled) return;
        setSourceTemplates(
          rows.filter(
            (row) =>
              row.id !== templateId && (row.milestone_count ?? 0) > 0 && row.is_active,
          ),
        );
      })
      .catch((error) => {
        if (cancelled) return;
        setSourceTemplates([]);
        showError(`Could not load templates to copy from: ${getErrorMessage(error)}`);
      });
    return () => {
      cancelled = true;
    };
  }, [form.project_type_id, templateId, showError]);

  const loadVersions = useCallback(async () => {
    if (isNew || !templateId) return;
    setVersionsError(null);
    try {
      setVersions(await fetchProjectTemplateVersions(templateId));
    } catch (error) {
      setVersionsError(error);
    }
  }, [isNew, templateId]);

  const applyTemplate = (loaded: ProjectTemplateDetail) => {
    const nextForm = formFromTemplate(loaded);
    const nextRows = rowsFromTemplate(loaded);
    setTemplate(loaded);
    setForm(nextForm);
    setMilestones(nextRows);
    setDraftOpen(false);
    setEditingMilestoneKey(null);
    captureBaseline(nextForm, nextRows);
  };

  const loadTemplate = useCallback(async () => {
    if (isNew || !templateId) return;
    setLoading(true);
    setLoadError(null);
    try {
      applyTemplate(await fetchProjectTemplate(templateId));
    } catch (error) {
      setLoadError(error);
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isNew, showError, templateId]);

  useEffect(() => {
    void loadLookups();
  }, [loadLookups]);

  useEffect(() => {
    void loadTemplate();
    void loadVersions();
    setPreview(null);
    setPreviewError(null);
  }, [loadTemplate, loadVersions]);

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
    setDraftOpen(false);
    setEditingMilestoneKey(null);
  };

  const sortedMilestones = useMemo(
    () => milestones.slice().sort((left, right) => left.sort_order - right.sort_order),
    [milestones],
  );

  const milestoneNameByKey = useMemo(
    () => new Map(milestones.map((row) => [row.key, row.milestone_name])),
    [milestones],
  );

  const reindexMilestones = (rows: MilestoneRow[]) =>
    rows.map((row, index) => ({ ...row, sort_order: index + 1 }));

  const openEditMilestone = (row: MilestoneRow) => {
    setEditingMilestoneKey(row.key);
    setMilestoneDraft({ ...row, depends_on: [...row.depends_on] });
    setDraftOpen(true);
  };

  const closeDraft = () => {
    setDraftOpen(false);
    setEditingMilestoneKey(null);
  };

  const saveMilestoneDraft = () => {
    const name = milestoneDraft.milestone_name.trim();
    if (!name) {
      showError('Milestone name is required.');
      return;
    }
    const duplicate = milestones.some(
      (row) => row.key !== milestoneDraft.key && row.milestone_name.trim().toLowerCase() === name.toLowerCase(),
    );
    if (duplicate) {
      showError(`A milestone named "${name}" already exists in this template.`);
      return;
    }
    const draft = { ...milestoneDraft, milestone_name: name };
    if (editingMilestoneKey) {
      setMilestones((current) =>
        reindexMilestones(
          current
            .slice()
            .sort((left, right) => left.sort_order - right.sort_order)
            .map((row) => (row.key === editingMilestoneKey ? draft : row)),
        ),
      );
    } else {
      setMilestones((current) => reindexMilestones([...current, draft]));
    }
    closeDraft();
  };

  const deleteMilestone = (key: string) => {
    setMilestones((current) =>
      reindexMilestones(
        current
          .filter((row) => row.key !== key)
          .sort((left, right) => left.sort_order - right.sort_order)
          .map((row) => ({ ...row, depends_on: row.depends_on.filter((dep) => dep !== key) })),
      ),
    );
    if (editingMilestoneKey === key) closeDraft();
  };

  const duplicateMilestone = (row: MilestoneRow) => {
    setMilestones((current) => {
      const taken = new Set(current.map((item) => item.milestone_name.trim().toLowerCase()));
      let name = `${row.milestone_name} (Copy)`;
      let suffix = 2;
      while (taken.has(name.toLowerCase())) {
        name = `${row.milestone_name} (Copy ${suffix})`;
        suffix += 1;
      }
      return reindexMilestones([
        ...current.slice().sort((left, right) => left.sort_order - right.sort_order),
        createMilestoneRow(
          { ...row, key: generateRowKey(), persisted: false, milestone_name: name },
          current.length + 1,
        ),
      ]);
    });
  };

  const handleCopyMilestonesFromTemplate = async () => {
    if (!copyFromTemplateId) {
      showError('Select a template to copy milestones from.');
      return;
    }
    setCopyingMilestones(true);
    try {
      const source = await fetchProjectTemplate(copyFromTemplateId);
      if (!source.milestones.length) {
        showError('Selected template has no milestones to copy.');
        return;
      }
      const keyMap = new Map(source.milestones.map((row) => [row.id, generateRowKey()]));
      setMilestones(
        reindexMilestones(
          rowsFromTemplate(source).map((row) => ({
            ...row,
            key: keyMap.get(row.key) ?? generateRowKey(),
            persisted: false,
            depends_on: row.depends_on
              .map((dep) => keyMap.get(dep))
              .filter((dep): dep is string => Boolean(dep)),
          })),
        ),
      );
      closeDraft();
      showSuccess(`Copied ${source.milestones.length} milestones.`);
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setCopyingMilestones(false);
    }
  };

  const moveMilestone = (index: number, direction: -1 | 1) => {
    const ordered = sortedMilestones.slice();
    const target = index + direction;
    if (target < 0 || target >= ordered.length) return;
    const [moved] = ordered.splice(index, 1);
    ordered.splice(target, 0, moved);
    setMilestones(reindexMilestones(ordered));
  };

  const handleDrop = (index: number) => {
    if (dragIndex === null || dragIndex === index) {
      setDragIndex(null);
      return;
    }
    const ordered = sortedMilestones.slice();
    const [moved] = ordered.splice(dragIndex, 1);
    ordered.splice(index, 0, moved);
    setMilestones(reindexMilestones(ordered));
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
        scheduling_mode: form.scheduling_mode,
        revision_note: form.revision_note.trim() || null,
        milestones: sortedMilestones.map(({ key, persisted, ...milestone }) => ({
          ...milestone,
          id: persisted ? key : null,
          client_key: key,
          project_stage: milestone.project_stage || null,
          assigned_role: milestone.assigned_role || null,
          default_assigned_user_id: milestone.default_assigned_user_id || null,
        })),
      };

      if (isNew) {
        const created = await createProjectTemplate(payload);
        captureBaseline(formFromTemplate(created), rowsFromTemplate(created));
        showSuccess('Template created successfully.');
        navigate(`/admin/project-templates/${created.id}`, { replace: true });
      } else if (templateId) {
        const updated = await updateProjectTemplate(templateId, payload);
        if (updated.created_new_version) {
          showSuccess(
            `Saved as version ${updated.version ?? ''}. Projects already using the previous version keep their milestones.`,
          );
          captureBaseline(formFromTemplate(updated), rowsFromTemplate(updated));
          navigate(`/admin/project-templates/${updated.id}`, { replace: true });
        } else {
          showSuccess('Template updated successfully.');
          applyTemplate(updated);
          void loadVersions();
        }
      }
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const runTemplateAction = async (action: () => Promise<void>) => {
    setActionBusy(true);
    try {
      await action();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setActionBusy(false);
    }
  };

  const handleDuplicateTemplate = () =>
    runTemplateAction(async () => {
      if (!templateId) return;
      const copy = await duplicateProjectTemplate(templateId);
      showSuccess(`Created "${copy.name}".`);
      navigate(`/admin/project-templates/${copy.id}`);
    });

  const handleToggleActive = () =>
    runTemplateAction(async () => {
      if (!templateId || !template) return;
      if (template.is_active) {
        await deactivateProjectTemplate(templateId);
        showSuccess('Template deactivated. It will no longer be offered for new projects.');
      } else {
        await reactivateProjectTemplate(templateId);
        showSuccess('This version is now active. Other versions of this template were deactivated.');
      }
      await loadTemplate();
      await loadVersions();
    });

  const handleActivateVersion = (versionId: string) =>
    runTemplateAction(async () => {
      await reactivateProjectTemplate(versionId);
      showSuccess('Version activated. Other versions of this template were deactivated.');
      if (versionId === templateId) {
        await loadTemplate();
        await loadVersions();
      } else {
        navigate(`/admin/project-templates/${versionId}`);
      }
    });

  const handleCreateRevision = () =>
    runTemplateAction(async () => {
      if (!templateId) return;
      const revision = await createProjectTemplateRevision(templateId, revisionNote.trim() || null);
      setRevisionNote('');
      showSuccess(
        `Draft version ${revision.version ?? ''} created (inactive). Edit it, then activate it when ready.`,
      );
      navigate(`/admin/project-templates/${revision.id}`);
    });

  const handlePreview = async () => {
    if (!templateId) return;
    if (!previewStart) {
      setPreviewError('Choose a start date for the preview.');
      return;
    }
    const stageHours: Record<string, number> = {};
    for (const option of PLANNED_STAGE_OPTIONS) {
      const raw = previewHours[option.value];
      if (raw === undefined || raw === '') continue;
      const value = Number(raw);
      if (!Number.isFinite(value) || value < 0) {
        setPreviewError(`${option.label} hours must be zero or more.`);
        return;
      }
      stageHours[option.value] = value;
    }
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      setPreview(
        await previewProjectTemplate(templateId, { start_date: previewStart, stage_hours: stageHours }),
      );
    } catch (error) {
      setPreview(null);
      setPreviewError(getErrorMessage(error));
    } finally {
      setPreviewLoading(false);
    }
  };

  const projectsUsing = template?.projects_using_count ?? 0;
  const dependencyCandidates = sortedMilestones.filter((row) => row.key !== milestoneDraft.key);

  if (lookupsLoading || loading) {
    return <LoadingState message="Loading template editor…" />;
  }

  if (lookupsError || loadError) {
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
          error={lookupsError ?? loadError}
          title="Unable to load template editor"
          onRetry={() => {
            if (lookupsError) void loadLookups();
            if (loadError) void loadTemplate();
          }}
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
          <Stack direction="row" spacing={1}>
            {!isNew && template ? (
              <>
                <Button
                  variant="outlined"
                  startIcon={<ContentCopyIcon />}
                  disabled={actionBusy}
                  onClick={() => void handleDuplicateTemplate()}
                >
                  Duplicate
                </Button>
                <Button
                  variant="outlined"
                  color={template.is_active ? 'warning' : 'success'}
                  disabled={actionBusy || isDirty}
                  onClick={() => void handleToggleActive()}
                >
                  {template.is_active ? 'Deactivate' : 'Activate this version'}
                </Button>
              </>
            ) : null}
            <Button
              startIcon={<ArrowBackIcon />}
              onClick={() => navigate('/admin/project-templates')}
            >
              Back
            </Button>
          </Stack>
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
            secondaryLabel={[
              projectTypes.find((type) => type.id === form.project_type_id)?.name ??
                'Milestone workflow template',
              template ? `Version ${template.version ?? 1} of ${template.version_count ?? 1}` : null,
              template ? (template.is_active ? 'Active' : 'Inactive') : null,
            ]
              .filter(Boolean)
              .join(' · ')}
            stickyTop={APP_TOP_BAR_OFFSET}
          />
        }
      >

      {!isNew && projectsUsing > 0 ? (
        <Alert severity="info" sx={{ mb: 3 }}>
          {projectsUsing} project{projectsUsing === 1 ? ' uses' : 's use'} this version. Saving
          milestone or scheduling changes creates a new version; those projects keep their existing
          milestones.
        </Alert>
      ) : null}

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
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControl fullWidth>
              <InputLabel>Scheduling</InputLabel>
              <Select
                label="Scheduling"
                value={form.scheduling_mode}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    scheduling_mode: event.target.value as TemplateSchedulingMode,
                  }))
                }
              >
                <MenuItem value="sequential">Sequential (each milestone follows the previous)</MenuItem>
                <MenuItem value="dependencies">Dependencies (milestones follow their predecessors)</MenuItem>
              </Select>
              <FormHelperText>
                Controls how forecast dates are laid out when a project is created from this template.
              </FormHelperText>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              label="Revision note (optional)"
              value={form.revision_note}
              onChange={(event) =>
                setForm((current) => ({ ...current, revision_note: event.target.value }))
              }
              helperText="Recorded on the new version if this save creates one."
              fullWidth
            />
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

      <Card id="milestones" ref={milestonesSectionRef} sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, gap: 2, flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="h6">Milestones</Typography>
            <Typography variant="body2" color="text.secondary">
              These steps are created as separate project milestones when a project uses this
              template. Editing the template later does not change existing projects.
            </Typography>
          </Box>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => openCreateMilestone(milestones.length)}
          >
            Add Milestone
          </Button>
        </Box>

        {form.project_type_id ? (
          <Box
            sx={{
              display: 'flex',
              gap: 1.5,
              alignItems: 'center',
              flexWrap: 'wrap',
              mb: 2,
            }}
          >
            <FilterSelect
              label="Copy milestones from"
              size="small"
              value={copyFromTemplateId}
              onChange={(event) => setCopyFromTemplateId(String(event.target.value))}
              sx={{ minWidth: 280, flex: 1, maxWidth: 420 }}
            >
              <MenuItem value="">Select a template…</MenuItem>
              {sourceTemplates.map((row) => (
                <MenuItem key={row.id} value={row.id}>
                  {row.name}
                  {row.customer_name ? ` (${row.customer_name})` : ' (General)'}
                  {` · ${row.milestone_count} milestones`}
                </MenuItem>
              ))}
            </FilterSelect>
            <Button
              variant="outlined"
              startIcon={<ContentCopyIcon />}
              disabled={!copyFromTemplateId || copyingMilestones}
              onClick={() => void handleCopyMilestonesFromTemplate()}
            >
              Copy
            </Button>
          </Box>
        ) : null}

        {milestones.length === 0 ? (
          <Alert severity="warning" sx={{ mb: 2 }}>
            This template has no milestones yet. Add at least one milestone before saving.
          </Alert>
        ) : null}

        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell width={40} />
              <TableCell width={60}>Order</TableCell>
              <TableCell>Milestone Name</TableCell>
              <TableCell width={150}>Stage</TableCell>
              <TableCell>Depends On</TableCell>
              <TableCell width={100}>Due Offset</TableCell>
              <TableCell width={130}>Assigned Role</TableCell>
              <TableCell width={100}>Default Hours</TableCell>
              <TableCell width={90}>Required</TableCell>
              <TableCell width={80}>Visible</TableCell>
              <TableCell width={170}>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sortedMilestones.length === 0 ? (
              <TableRow>
                <TableCell colSpan={11}>
                  <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
                    No milestones yet. Use Add Milestone to create the first step.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : null}
            {sortedMilestones.map((row, index) => (
              <TableRow
                key={row.key}
                hover
                selected={editingMilestoneKey === row.key}
                draggable
                onDragStart={() => setDragIndex(index)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => handleDrop(index)}
                sx={{ cursor: 'grab' }}
              >
                <TableCell>
                  <DragIndicatorIcon fontSize="small" color="action" />
                </TableCell>
                <TableCell>{row.sort_order}</TableCell>
                <TableCell>
                  <Typography variant="body2">{row.milestone_name}</Typography>
                  {row.description ? (
                    <Typography variant="caption" color="text.secondary">
                      {row.description}
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell>{projectStageLabel(row.project_stage)}</TableCell>
                <TableCell>
                  {row.depends_on.length
                    ? row.depends_on
                        .map((dep) => milestoneNameByKey.get(dep) ?? 'Removed milestone')
                        .join(', ')
                    : '—'}
                </TableCell>
                <TableCell>{formatCellValue(row.default_due_offset_days)}</TableCell>
                <TableCell>{formatCellValue(row.assigned_role)}</TableCell>
                <TableCell>{formatCellValue(row.estimated_hours)}</TableCell>
                <TableCell>{row.is_required ? 'Required' : 'Optional'}</TableCell>
                <TableCell>{row.is_visible !== false ? 'Yes' : 'No'}</TableCell>
                <TableCell>
                  <Tooltip title="Move up">
                    <span>
                      <IconButton size="small" disabled={index === 0} onClick={() => moveMilestone(index, -1)}>
                        <ArrowUpwardIcon fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title="Move down">
                    <span>
                      <IconButton
                        size="small"
                        disabled={index === sortedMilestones.length - 1}
                        onClick={() => moveMilestone(index, 1)}
                      >
                        <ArrowDownwardIcon fontSize="small" />
                      </IconButton>
                    </span>
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
                  <Tooltip title="Remove">
                    <IconButton size="small" onClick={() => deleteMilestone(row.key)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {draftOpen ? (
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
                  autoFocus
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
              <Grid size={{ xs: 12, md: 4 }}>
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
                    <MenuItem value="">Unstaged</MenuItem>
                    {PROJECT_STAGE_OPTIONS.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                  <FormHelperText>Stage hours are shared across milestones in the same stage.</FormHelperText>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <FormControl fullWidth>
                  <InputLabel>Depends On</InputLabel>
                  <Select
                    multiple
                    label="Depends On"
                    value={milestoneDraft.depends_on}
                    input={<OutlinedInput label="Depends On" />}
                    onChange={(event) => {
                      const value = event.target.value;
                      setMilestoneDraft((current) => ({
                        ...current,
                        depends_on: typeof value === 'string' ? value.split(',') : value,
                      }));
                    }}
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {selected.map((key) => (
                          <Chip key={key} size="small" label={milestoneNameByKey.get(key) ?? key} />
                        ))}
                      </Box>
                    )}
                  >
                    {dependencyCandidates.length === 0 ? (
                      <MenuItem disabled value="">
                        No other milestones yet
                      </MenuItem>
                    ) : null}
                    {dependencyCandidates.map((row) => (
                      <MenuItem key={row.key} value={row.key}>
                        <Checkbox size="small" checked={milestoneDraft.depends_on.includes(row.key)} />
                        <ListItemText primary={`${row.sort_order}. ${row.milestone_name}`} />
                      </MenuItem>
                    ))}
                  </Select>
                  <FormHelperText>
                    {form.scheduling_mode === 'dependencies'
                      ? 'This milestone starts after the selected milestones finish.'
                      : 'Used when the template scheduling is set to Dependencies.'}
                  </FormHelperText>
                </FormControl>
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
                <TextField
                  label="Default Hours"
                  type="number"
                  value={milestoneDraft.estimated_hours ?? ''}
                  slotProps={{ htmlInput: { min: 0, step: 0.5 } }}
                  onChange={(event) =>
                    setMilestoneDraft((current) => ({
                      ...current,
                      estimated_hours: event.target.value
                        ? Number(event.target.value)
                        : null,
                    }))
                  }
                  helperText="Used when no stage hours are entered"
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
                <Stack direction="row" spacing={1}>
                  <Button variant="contained" onClick={saveMilestoneDraft}>
                    {editingMilestoneKey ? 'Update Milestone' : 'Add Milestone'}
                  </Button>
                  <Button onClick={closeDraft}>Cancel</Button>
                </Stack>
              </Grid>
            </Grid>
          </Box>
        ) : null}
      </Card>

      {!isNew && template ? (
        <Card sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6">Schedule Preview</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Shows the milestones and provisional dates a new project would get from the saved
            version of this template. Nothing is created.
          </Typography>
          {isDirty ? (
            <Alert severity="info" sx={{ mb: 2 }}>
              Save your changes to preview them. The preview uses the saved template.
            </Alert>
          ) : null}
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid size={{ xs: 12, md: 3 }}>
              <TextField
                label="Project start date"
                type="date"
                value={previewStart}
                onChange={(event) => setPreviewStart(event.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                fullWidth
              />
            </Grid>
            {PLANNED_STAGE_OPTIONS.map((option) => (
              <Grid key={option.value} size={{ xs: 12, md: 2 }}>
                <TextField
                  label={`${option.label} hours`}
                  type="number"
                  value={previewHours[option.value] ?? ''}
                  slotProps={{ htmlInput: { min: 0, step: 0.5 } }}
                  onChange={(event) =>
                    setPreviewHours((current) => ({ ...current, [option.value]: event.target.value }))
                  }
                  fullWidth
                />
              </Grid>
            ))}
            <Grid size={{ xs: 12, md: 3 }} sx={{ display: 'flex', alignItems: 'center' }}>
              <Button
                variant="outlined"
                disabled={previewLoading || isDirty}
                onClick={() => void handlePreview()}
              >
                {previewLoading ? 'Calculating…' : 'Preview schedule'}
              </Button>
            </Grid>
          </Grid>
          {previewError ? (
            <Alert severity="error" sx={{ mb: 2 }}>
              {previewError}
            </Alert>
          ) : null}
          {preview ? (
            <>
              <Alert severity={preview.forecast_status === 'invalid' ? 'warning' : 'info'} sx={{ mb: 2 }}>
                {preview.forecast_status === 'invalid'
                  ? 'Dates could not be calculated for every milestone.'
                  : `Provisional completion: ${formatDate(preview.completion_date)}.`}{' '}
                {preview.forecast_note}
              </Alert>
              {preview.warnings.map((warning) => (
                <Alert key={warning} severity="warning" sx={{ mb: 1 }}>
                  {warning}
                </Alert>
              ))}
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell width={60}>Order</TableCell>
                    <TableCell>Milestone</TableCell>
                    <TableCell>Stage</TableCell>
                    <TableCell align="right">Planned Hours</TableCell>
                    <TableCell>Hours Source</TableCell>
                    <TableCell>Start</TableCell>
                    <TableCell>Finish</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.milestones.map((row) => (
                    <TableRow key={`${row.sort_order}-${row.name}`}>
                      <TableCell>{row.sort_order}</TableCell>
                      <TableCell>{row.name}</TableCell>
                      <TableCell>{projectStageLabel(row.project_stage)}</TableCell>
                      <TableCell align="right">{formatNumber(row.planned_hours, 1)}</TableCell>
                      <TableCell>{formatCellValue(row.estimate_basis)}</TableCell>
                      <TableCell>{formatDate(row.start_date)}</TableCell>
                      <TableCell>{formatDate(row.finish_date)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          ) : null}
        </Card>
      ) : null}

      {!isNew && template ? (
        <Card sx={{ p: 3 }}>
          <Typography variant="h6">Versions</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Only one version of a template is active for new projects. Existing projects stay on the
            version they were created from.
          </Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
            <TextField
              size="small"
              label="Revision note"
              value={revisionNote}
              onChange={(event) => setRevisionNote(event.target.value)}
              sx={{ minWidth: 320 }}
            />
            <Button
              variant="outlined"
              disabled={actionBusy || isDirty}
              onClick={() => void handleCreateRevision()}
            >
              Create draft revision
            </Button>
          </Stack>
          {versionsError ? (
            <ErrorState
              error={versionsError}
              title="Unable to load versions"
              onRetry={() => void loadVersions()}
            />
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell width={90}>Version</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Revision Note</TableCell>
                  <TableCell align="right">Milestones</TableCell>
                  <TableCell align="right">Projects Using</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Activated</TableCell>
                  <TableCell width={200}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {versions.map((version) => (
                  <TableRow key={version.id} selected={version.id === templateId}>
                    <TableCell>v{version.version}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        color={version.is_active ? 'success' : 'default'}
                        label={version.is_active ? 'Active' : 'Inactive'}
                      />
                    </TableCell>
                    <TableCell>{formatCellValue(version.revision_note)}</TableCell>
                    <TableCell align="right">{version.milestone_count}</TableCell>
                    <TableCell align="right">{version.projects_using_count}</TableCell>
                    <TableCell>{formatDateTime(version.created_at)}</TableCell>
                    <TableCell>{formatDateTime(version.activated_at)}</TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={1}>
                        {version.id !== templateId ? (
                          <Button size="small" onClick={() => navigate(`/admin/project-templates/${version.id}`)}>
                            Open
                          </Button>
                        ) : null}
                        {!version.is_active ? (
                          <Button
                            size="small"
                            disabled={actionBusy || isDirty || version.milestone_count === 0}
                            onClick={() => void handleActivateVersion(version.id)}
                          >
                            Activate
                          </Button>
                        ) : null}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      ) : null}
      </StickyFormPageLayout>
    </Box>
  );
}
