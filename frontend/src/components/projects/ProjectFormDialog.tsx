import { useEffect, useMemo, useRef, useState } from 'react';
import { Box, FormControlLabel, Grid, Switch, Typography, Alert } from '@mui/material';
import AssignmentOutlinedIcon from '@mui/icons-material/AssignmentOutlined';
import BusinessOutlinedIcon from '@mui/icons-material/BusinessOutlined';
import FolderOpenOutlinedIcon from '@mui/icons-material/FolderOpenOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined';
import NotesOutlinedIcon from '@mui/icons-material/NotesOutlined';
import PrecisionManufacturingOutlinedIcon from '@mui/icons-material/PrecisionManufacturingOutlined';
import ViewListOutlinedIcon from '@mui/icons-material/ViewListOutlined';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchContacts, fetchCustomers, fetchProjectSmallTaskTypes, fetchStreams, fetchTeams, fetchUsers, fetchWorkingModels } from '../../api/lookups';
import { fetchMatchingProjectTemplates, fetchProjectTemplate, fetchProjectTypes } from '../../api/projectTemplates';
import type { ExecutionStatus, Project, ProjectClassification, ProjectCreate, ProjectHealth, ProjectStage, ProjectUpdate, Workstream } from '../../types';
import { workstreamsApi } from '../../api/resources';
import {
  createProject,
  invalidateProjectCalculationQueries,
  replaceProjectWorkstreams,
  updateProject,
} from '../../services/projectService';
import {
  EXECUTION_STATUS_LABELS,
  PROJECT_STAGE_LABELS,
} from '../../types/common';
import { ErrorState } from '../common/ErrorState';
import {
  CollapsibleFormSection,
  FormDrawer,
  FormField,
  FormSelect,
  StickyRecordHeader,
} from '../ui/design-system';
import { userDisplayName } from '../../utils/format';
import { optionalString, optionalUuid, optionalNumber, validateRequiredFields, isBlankDisplayValue } from '../../utils/formValues';
import { ChangeProjectTemplateDialog } from './ChangeProjectTemplateDialog';
import { ProjectDocumentsPanel } from './ProjectDocumentsPanel';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { ProsohmButton } from '../ui/ProsohmButton';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { fetchAssignmentSkillFit } from '../../api/assignmentSkillFit';
import { getErrorMessage } from '../../api/client';
import {
  isMoldStreamName,
  projectReferenceLabel,
  projectReferenceTooltip,
} from '../../utils/projectStreamScope';

interface ProjectFormValues {
  tool_number: string;
  part_description: string;
  customer_id: string;
  customer_contact_id: string;
  design_leader_id: string;
  designer_id: string;
  surfacer_id: string;
  stream_id: string;
  project_classification: ProjectClassification | '';
  small_task_type_id: string;
  project_type_id: string;
  project_template_id: string;
  working_model_id: string;
  team_id: string;
  workstream_ids: string[];
  code: string;
  quoted_hours: number | '';
  due_date: string;
  notes: string;
  work_order_number: string;
  press_tonnage: string;
  plastic_material: string;
  cavity_count: string;
  tool_type: string;
  customer_specs: string;
  priority: ProjectCreate['priority'];
  complexity: NonNullable<ProjectCreate['complexity']>;
  project_stage: ProjectStage;
  execution_status: ExecutionStatus;
  health: ProjectHealth;
  qa_gate_enabled: boolean;
}

const PROJECT_SECTION_STORAGE_KEY = 'protrack:sections:project-form';

const emptyForm: ProjectFormValues = {
  tool_number: '',
  part_description: '',
  customer_id: '',
  customer_contact_id: '',
  design_leader_id: '',
  designer_id: '',
  surfacer_id: '',
  stream_id: '',
  project_classification: '',
  small_task_type_id: '',
  project_type_id: '',
  project_template_id: '',
  working_model_id: '',
  team_id: '',
  workstream_ids: [],
  code: '',
  quoted_hours: '',
  due_date: '',
  notes: '',
  work_order_number: '',
  press_tonnage: '',
  plastic_material: '',
  cavity_count: '',
  tool_type: '',
  customer_specs: '',
  priority: 'medium',
  complexity: 'medium',
  project_stage: 'preliminary',
  execution_status: 'planning',
  health: 'green',
  qa_gate_enabled: false,
};

function projectToForm(project: Project): ProjectFormValues {
  const id = (value: string | null | undefined) => (value == null || value === '' ? '' : String(value));
  return {
    tool_number: project.tool_number ?? '',
    part_description: project.part_description ?? '',
    customer_id: id(project.customer_id),
    customer_contact_id: id(project.customer_contact_id),
    design_leader_id: id(project.design_leader_id),
    designer_id: id(project.designer_id),
    surfacer_id: id(project.surfacer_id),
    stream_id: id(project.stream_id),
    project_classification: project.project_classification ?? '',
    small_task_type_id: id(project.small_task_type_id),
    project_type_id: id(project.project_type_id),
    project_template_id: id(project.project_template_id),
    working_model_id: id(project.working_model_id),
    team_id: id(project.team_id),
    workstream_ids: (project.workstreams ?? []).map((ws) => ws.workstream_id),
    code: project.code ?? '',
    quoted_hours: project.quoted_hours,
    due_date: project.due_date ?? '',
    notes: project.notes ?? '',
    work_order_number: project.work_order_number ?? '',
    press_tonnage: project.press_tonnage ?? '',
    plastic_material: project.plastic_material ?? '',
    cavity_count:
      project.cavity_count === null || project.cavity_count === undefined
        ? ''
        : String(project.cavity_count),
    tool_type: project.tool_type ?? '',
    customer_specs: project.customer_specs ?? '',
    priority: project.priority ?? 'medium',
    complexity: project.complexity ?? 'medium',
    project_stage: project.project_stage,
    execution_status: project.execution_status,
    health: project.health,
    qa_gate_enabled: Boolean(project.qa_gate_enabled),
  };
}

/** Ensure the currently saved ID stays in the select even if lookups omit it. */
function withCurrentOption(
  options: { value: string; label: string }[],
  currentId: string | null | undefined,
  currentLabel: string | null | undefined,
): { value: string; label: string }[] {
  const id = currentId == null || currentId === '' ? '' : String(currentId);
  if (!id) return options;
  if (options.some((option) => String(option.value) === id)) return options;
  return [{ value: id, label: currentLabel?.trim() || id }, ...options];
}

interface ProjectFormDialogProps {
  open: boolean;
  onClose: () => void;
  project?: Project | null;
  onCreated?: (projectId: string) => void;
  onUpdated?: (projectId: string) => void;
}

export function ProjectFormDialog({
  open,
  onClose,
  project,
  onCreated,
  onUpdated,
}: ProjectFormDialogProps) {
  const isEdit = Boolean(project);
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { showError, showSuccess } = useToast();
  const [form, setForm] = useState<ProjectFormValues>(emptyForm);
  const [skillFitWarning, setSkillFitWarning] = useState<string | null>(null);
  const [skillFitChecking, setSkillFitChecking] = useState(false);
  const [changeTemplateOpen, setChangeTemplateOpen] = useState(false);
  const baselineRef = useRef('');
  const hydratedForRef = useRef<string | null>(null);
  const autoTemplateKeyRef = useRef<string | null>(null);

  const serializeForm = (values: ProjectFormValues) => JSON.stringify(values);

  const customersQuery = useQuery({
    queryKey: ['customers'],
    queryFn: fetchCustomers,
    enabled: open,
  });

  const contactsQuery = useQuery({
    queryKey: ['contacts', form.customer_id],
    queryFn: () => fetchContacts({ customer_id: form.customer_id }),
    enabled: open && Boolean(form.customer_id),
  });

  const usersQuery = useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers,
    enabled: open,
  });

  const streamsQuery = useQuery({
    queryKey: ['streams'],
    queryFn: fetchStreams,
    enabled: open,
  });

  const smallTaskTypesQuery = useQuery({
    queryKey: ['lookups', 'project-small-task-types'],
    queryFn: fetchProjectSmallTaskTypes,
    enabled: open,
  });

  const workstreamsQuery = useQuery({
    queryKey: ['workstreams', 'active'],
    queryFn: () => workstreamsApi.list({ limit: 500, is_active: true }),
    enabled: open,
  });

  const teamsQuery = useQuery({
    queryKey: ['teams'],
    queryFn: fetchTeams,
    enabled: open,
  });

  const projectTypesQuery = useQuery({
    queryKey: ['project-types'],
    queryFn: fetchProjectTypes,
    enabled: open,
  });

  const workingModelsQuery = useQuery({
    queryKey: ['working-models'],
    queryFn: fetchWorkingModels,
    enabled: open,
  });

  const matchingTemplatesQuery = useQuery({
    queryKey: ['project-templates', form.customer_id, form.project_type_id],
    queryFn: () =>
      fetchMatchingProjectTemplates({
        customer_id: form.customer_id,
        project_type_id: form.project_type_id,
      }),
    enabled:
      open &&
      Boolean(form.customer_id) &&
      Boolean(form.project_type_id) &&
      (!isEdit || Boolean(project?.can_change_template !== false)),
  });

  useEffect(() => {
    if (!open) {
      hydratedForRef.current = null;
      autoTemplateKeyRef.current = null;
      setForm(emptyForm);
      baselineRef.current = serializeForm(emptyForm);
      return;
    }
    // Hydrate once per open (or when switching to a different project). Avoids
    // command-center refetch while the drawer is open wiping Customer/Team selects.
    const hydrateKey = project?.id ?? 'create';
    if (hydratedForRef.current === hydrateKey) return;
    const initial = project ? projectToForm(project) : emptyForm;
    setForm(initial);
    baselineRef.current = serializeForm(initial);
    hydratedForRef.current = hydrateKey;
  }, [open, project]);

  // If the open project payload arrives asynchronously (id already hydrated as
  // empty), re-hydrate when IDs become available without clearing edits mid-type.
  useEffect(() => {
    if (!open || !project?.id) return;
    if (hydratedForRef.current !== project.id) return;
    if (form.customer_id || !project.customer_id) return;
    const initial = projectToForm(project);
    setForm(initial);
    baselineRef.current = serializeForm(initial);
  }, [open, project, form.customer_id]);

  const isDirty = useMemo(
    () => serializeForm(form) !== baselineRef.current,
    [form],
  );
  const trimmedToolNumber = form.tool_number.trim();
  const quotedHoursNumber = form.quoted_hours === '' ? null : Number(form.quoted_hours);
  const toolNumberValidationState =
    trimmedToolNumber.length >= 3 ? ('success' as const) : ('warning' as const);
  const toolNumberValidationMessage =
    trimmedToolNumber.length >= 3
      ? 'Looks good'
      : 'Use at least 3 characters for easy searchability';
  const quotedHoursValidationState =
    quotedHoursNumber === null || quotedHoursNumber <= 24
      ? ('success' as const)
      : ('warning' as const);
  const quotedHoursValidationMessage =
    quotedHoursNumber === null || quotedHoursNumber <= 24
      ? 'Quoted effort for planning and delivery tracking'
      : 'Hours cannot exceed 24 per day equivalent entry';

  const handleDiscard = () => {
    setForm(JSON.parse(baselineRef.current) as ProjectFormValues);
  };

  const activeStreams = useMemo(
    () => (streamsQuery.data ?? []).filter((stream) => stream.is_active !== false),
    [streamsQuery.data],
  );

  const selectedStream = useMemo(
    () => activeStreams.find((stream) => stream.id === form.stream_id) ?? null,
    [activeStreams, form.stream_id],
  );

  const referenceLabel = projectReferenceLabel(selectedStream?.name);
  const referenceTooltip = projectReferenceTooltip(selectedStream?.name);
  const showMoldToolingFields = isMoldStreamName(selectedStream?.name) || !selectedStream;

  const streamManagesCodes = Boolean(
    selectedStream?.use_project_numbering || selectedStream?.use_project_prefix,
  );

  useEffect(() => {
    if (!open || isEdit) return;
    if (form.stream_id) return;
    const preferred =
      user?.stream_id && activeStreams.some((stream) => stream.id === user.stream_id)
        ? user.stream_id
        : activeStreams.find((stream) => isMoldStreamName(stream.name))?.id ??
          activeStreams[0]?.id ??
          '';
    if (!preferred) return;
    setForm((current) => ({ ...current, stream_id: preferred }));
  }, [open, isEdit, form.stream_id, activeStreams, user?.stream_id]);

  useEffect(() => {
    if (!open || isEdit) return;
    if (streamManagesCodes) return;
    if (form.code.trim()) return;
    const suggested = form.tool_number
      .trim()
      .replace(/\s+/g, '-')
      .replace(/[^a-zA-Z0-9-_]/g, '')
      .toUpperCase();
    if (!suggested) return;
    setForm((current) => ({ ...current, code: suggested }));
  }, [form.tool_number, form.code, open, isEdit, streamManagesCodes]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      let saved: Project;
      if (isEdit && project) {
        const updatePayload: ProjectUpdate = {
          tool_number: form.tool_number.trim(),
          part_description: form.part_description.trim(),
          code: optionalString(form.code),
          customer_id: form.customer_id,
          customer_contact_id: optionalUuid(form.customer_contact_id),
          design_leader_id: optionalUuid(form.design_leader_id),
          designer_id: optionalUuid(form.designer_id),
          surfacer_id: optionalUuid(form.surfacer_id),
          stream_id: optionalUuid(form.stream_id),
          team_id: optionalUuid(form.team_id),
          project_type_id: optionalUuid(form.project_type_id),
          quoted_hours: form.quoted_hours === '' ? null : Number(form.quoted_hours),
          due_date: optionalString(form.due_date),
          notes: optionalString(form.notes),
          work_order_number: optionalString(form.work_order_number),
          press_tonnage: optionalString(form.press_tonnage),
          plastic_material: optionalString(form.plastic_material),
          cavity_count: optionalNumber(form.cavity_count),
          tool_type: optionalString(form.tool_type),
          customer_specs: optionalString(form.customer_specs),
          project_stage: form.project_stage,
          execution_status: form.execution_status,
          priority: form.priority,
          complexity: form.complexity,
          health: form.health,
          working_model_id: optionalUuid(form.working_model_id),
          qa_gate_enabled: form.qa_gate_enabled,
          project_classification:
            form.project_classification === '' ? undefined : form.project_classification,
          small_task_type_id:
            form.project_classification === 'small_task'
              ? optionalUuid(form.small_task_type_id)
              : null,
        };
        saved = await updateProject(project.id, updatePayload);
      } else {
        const createPayload: ProjectCreate = {
          tool_number: form.tool_number.trim(),
          part_description: form.part_description.trim(),
          customer_id: form.customer_id,
          customer_contact_id: optionalUuid(form.customer_contact_id),
          design_leader_id: optionalUuid(form.design_leader_id),
          designer_id: optionalUuid(form.designer_id),
          surfacer_id: optionalUuid(form.surfacer_id),
          stream_id: optionalUuid(form.stream_id),
          team_id: optionalUuid(form.team_id),
          project_type_id: optionalUuid(form.project_type_id),
          project_template_id: optionalUuid(form.project_template_id),
          working_model_id: optionalUuid(form.working_model_id),
          code: optionalString(form.code),
          quoted_hours: optionalNumber(form.quoted_hours),
          due_date: optionalString(form.due_date),
          priority: form.priority,
          complexity: form.complexity,
          project_classification: form.project_classification as ProjectClassification,
          small_task_type_id:
            form.project_classification === 'small_task'
              ? optionalUuid(form.small_task_type_id)
              : null,
          notes: optionalString(form.notes),
          work_order_number: optionalString(form.work_order_number),
          press_tonnage: optionalString(form.press_tonnage),
          plastic_material: optionalString(form.plastic_material),
          cavity_count: optionalNumber(form.cavity_count),
          tool_type: optionalString(form.tool_type),
          customer_specs: optionalString(form.customer_specs),
        };
        saved = await createProject(createPayload);
      }
      await replaceProjectWorkstreams(
        saved.id,
        form.workstream_ids.map((workstream_id) => ({ workstream_id })),
      );
      return saved;
    },
    onSuccess: (savedProject) => {
      invalidateProjectCalculationQueries(queryClient, savedProject.id);
      if (isEdit) {
        onUpdated?.(savedProject.id);
      } else {
        onCreated?.(savedProject.id);
      }
      onClose();
    },
  });

  const activeCustomers = useMemo(
    () => (customersQuery.data ?? []).filter((customer) => customer.is_active !== false),
    [customersQuery.data],
  );

  const matchingTemplates = useMemo(
    () => matchingTemplatesQuery.data ?? [],
    [matchingTemplatesQuery.data],
  );

  const currentTemplateName = useMemo(() => {
    const match = matchingTemplates.find((template) => template.id === project?.project_template_id);
    return match?.name ?? null;
  }, [matchingTemplates, project?.project_template_id]);

  const selectedTemplate = useMemo(
    () => matchingTemplates.find((template) => template.id === form.project_template_id),
    [form.project_template_id, matchingTemplates],
  );

  const templatePreviewQuery = useQuery({
    queryKey: ['project-template-preview', form.project_template_id],
    queryFn: () => fetchProjectTemplate(form.project_template_id),
    enabled: open && !isEdit && Boolean(form.project_template_id),
  });

  const previewMilestones = useMemo(
    () =>
      (templatePreviewQuery.data?.milestones ?? [])
        .filter((row) => row.is_visible !== false)
        .slice()
        .sort((left, right) => left.sort_order - right.sort_order),
    [templatePreviewQuery.data?.milestones],
  );

  useEffect(() => {
    if (isEdit || !open || !form.customer_id || !form.project_type_id) return;
    if (matchingTemplatesQuery.isFetching) return;

    const key = `${form.customer_id}:${form.project_type_id}`;
    if (autoTemplateKeyRef.current === key) return;

    if (
      form.project_template_id &&
      matchingTemplates.some((template) => template.id === form.project_template_id)
    ) {
      autoTemplateKeyRef.current = key;
      return;
    }

    const customer = activeCustomers.find((item) => item.id === form.customer_id);
    const withMilestones = matchingTemplates.filter(
      (template) => (template.milestone_count ?? 0) > 0,
    );
    const preferred =
      withMilestones.find((template) => template.id === customer?.default_project_template_id) ||
      withMilestones.find((template) => template.is_customer_specific) ||
      withMilestones.find((template) => template.is_default) ||
      withMilestones[0] ||
      matchingTemplates[0];

    autoTemplateKeyRef.current = key;
    if (!preferred) return;
    setForm((current) => ({
      ...current,
      project_template_id: preferred.id,
      team_id: current.team_id || preferred.default_team_id || current.team_id,
    }));
  }, [
    activeCustomers,
    form.customer_id,
    form.project_template_id,
    form.project_type_id,
    isEdit,
    matchingTemplates,
    matchingTemplatesQuery.isFetching,
    open,
  ]);

  useEffect(() => {
    if (isEdit || !open) return;
    if (!form.customer_id || !form.project_type_id) {
      if (form.project_template_id) {
        setForm((current) => ({ ...current, project_template_id: '' }));
      }
    }
  }, [form.customer_id, form.project_type_id, form.project_template_id, isEdit, open]);

  const canSubmit = useMemo(
    () =>
      !isBlankDisplayValue(form.tool_number) &&
      !isBlankDisplayValue(form.part_description) &&
      !isBlankDisplayValue(form.customer_id) &&
      (isEdit || !isBlankDisplayValue(form.stream_id)) &&
      (isEdit || !isBlankDisplayValue(form.project_classification)) &&
      (isEdit ||
        form.project_classification !== 'small_task' ||
        !isBlankDisplayValue(form.small_task_type_id)),
    [
      form.tool_number,
      form.part_description,
      form.customer_id,
      form.stream_id,
      form.project_classification,
      form.small_task_type_id,
      isEdit,
    ],
  );

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    const validationError = validateRequiredFields(
      {
        tool_number: form.tool_number,
        part_description: form.part_description,
        customer_id: form.customer_id,
        ...(isEdit ? {} : { team_id: form.team_id, stream_id: form.stream_id }),
      },
      [
        { key: 'tool_number', label: referenceLabel },
        { key: 'part_description', label: 'Part description' },
        { key: 'customer_id', label: 'Customer' },
        ...(isEdit
          ? []
          : [
              { key: 'team_id', label: 'Team' },
              { key: 'stream_id', label: 'Engineering stream' },
              { key: 'project_classification', label: 'Project classification' },
            ]),
      ],
    );

    if (validationError) {
      showError(validationError);
      return;
    }

    if (
      !isEdit &&
      form.project_classification === 'small_task' &&
      isBlankDisplayValue(form.small_task_type_id)
    ) {
      showError('Task type is required for Small Task projects.');
      return;
    }

    if (
      isEdit &&
      form.project_classification === 'small_task' &&
      isBlankDisplayValue(form.small_task_type_id)
    ) {
      showError('Task type is required for Small Task projects.');
      return;
    }

    const runSave = () => {
      setSkillFitWarning(null);
      saveMutation.mutate();
    };

    const hasAssignees = Boolean(form.designer_id || form.surfacer_id || form.design_leader_id);
    if (!hasAssignees) {
      runSave();
      return;
    }

    setSkillFitChecking(true);
    void fetchAssignmentSkillFit({
      complexity: form.complexity,
      designer_id: form.designer_id || null,
      surfacer_id: form.surfacer_id || null,
      design_leader_id: form.design_leader_id || null,
    })
      .then((fit) => {
        if (fit.requires_confirmation) {
          setSkillFitWarning(fit.message);
          return;
        }
        runSave();
      })
      .catch((error: unknown) => {
        showError(getErrorMessage(error));
      })
      .finally(() => setSkillFitChecking(false));
  };

  const handleCustomerChange = (customerId: string) => {
    const customer = activeCustomers.find((item) => String(item.id) === customerId);
    setForm((current) => ({
      ...current,
      customer_id: customerId,
      customer_contact_id:
        project && customerId === String(project.customer_id ?? '')
          ? String(project.customer_contact_id ?? '')
          : '',
      project_type_id: customer?.default_project_type_id ?? current.project_type_id,
      working_model_id: customer?.default_working_model_id ?? current.working_model_id,
      team_id: customer?.default_team_id ?? current.team_id,
      // Clear so the match effect can pick a type-compatible template with milestones.
      project_template_id: isEdit ? current.project_template_id : '',
    }));
  };

  const userOptions = useMemo(() => {
    const base = (usersQuery.data ?? []).map((user) => ({
      value: String(user.id),
      label: userDisplayName(user),
    }));
    return withCurrentOption(
      withCurrentOption(
        withCurrentOption(base, form.design_leader_id, project?.design_leader_name),
        form.designer_id,
        project?.designer_name,
      ),
      form.surfacer_id,
      project?.surfacer_name,
    );
  }, [
    form.design_leader_id,
    form.designer_id,
    form.surfacer_id,
    project?.design_leader_name,
    project?.designer_name,
    project?.surfacer_name,
    usersQuery.data,
  ]);

  const customerOptions = useMemo(
    () =>
      withCurrentOption(
        activeCustomers.map((customer) => ({
          value: String(customer.id),
          label: customer.name,
        })),
        form.customer_id,
        project?.customer_name,
      ),
    [activeCustomers, form.customer_id, project?.customer_name],
  );

  const teamOptions = useMemo(
    () =>
      withCurrentOption(
        (teamsQuery.data ?? []).map((team) => ({
          value: String(team.id),
          label: team.name,
        })),
        form.team_id,
        project?.team_name,
      ),
    [form.team_id, project?.team_name, teamsQuery.data],
  );

  const contactOptions = useMemo(() => {
    const base = [
      { value: '', label: 'None' },
      ...(contactsQuery.data ?? []).map((contact) => ({
        value: String(contact.id),
        label: userDisplayName(contact),
      })),
    ];
    return withCurrentOption(base, form.customer_contact_id, null);
  }, [contactsQuery.data, form.customer_contact_id]);

  const selectedCustomerName = useMemo(() => {
    if (project?.customer_name && form.customer_id === String(project.customer_id ?? '')) {
      return project.customer_name;
    }
    return activeCustomers.find((customer) => String(customer.id) === form.customer_id)?.name ?? null;
  }, [activeCustomers, form.customer_id, project]);

  return (
    <>
    <FormDrawer
      open={open}
      onClose={onClose}
      title={isEdit ? 'Edit Project' : 'Create Project'}
      subtitle={
        isEdit
          ? 'Update project details, team assignments, and execution status.'
          : 'Create a placeholder project with tool number, customer, and description.'
      }
      icon={AssignmentOutlinedIcon}
      formId="project-form"
      width={640}
      submitLabel={isEdit ? 'Save Changes' : 'Create Project'}
      loading={saveMutation.isPending || skillFitChecking}
      submitDisabled={!canSubmit}
      dirty={isDirty}
      onDiscard={handleDiscard}
    >
      <Box
        component="form"
        id="project-form"
        onSubmit={handleSubmit}
        sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
      >
        <StickyRecordHeader
          compact
          mode={isEdit ? 'full' : 'draft'}
          toolNumber={form.tool_number}
          partDescription={form.part_description}
          customerName={selectedCustomerName}
          executionStatus={isEdit ? form.execution_status : null}
          dueDate={form.due_date}
          health={isEdit ? project?.health ?? null : null}
          stickyTop={0}
        />

        <CollapsibleFormSection
          sectionId="general-information"
          storageKey={PROJECT_SECTION_STORAGE_KEY}
          title="General Information"
          subtitle={`${referenceLabel} and description`}
          icon={AssignmentOutlinedIcon}
        >
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label={referenceLabel}
              required
              value={form.tool_number}
              tooltip={referenceTooltip}
              validationState={toolNumberValidationState}
              validationMessage={toolNumberValidationMessage}
              onChange={(event) =>
                setForm({ ...form, tool_number: event.target.value })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Project Code"
              value={form.code}
              helper={
                streamManagesCodes
                  ? 'Optional. Leave blank to auto-assign from the stream prefix/numbering, or enter a customer project number.'
                  : 'Suggested automatically from Tool Number. You can edit if needed.'
              }
              onChange={(event) => setForm({ ...form, code: event.target.value })}
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <FormField
              label="Part Description"
              required
              value={form.part_description}
              maxLength={255}
              onChange={(event) =>
                setForm({ ...form, part_description: event.target.value })
              }
            />
          </Grid>
        </CollapsibleFormSection>

        <CollapsibleFormSection
          sectionId="customer"
          storageKey={PROJECT_SECTION_STORAGE_KEY}
          title="Customer"
          subtitle="Customer and primary contact"
          icon={BusinessOutlinedIcon}
        >
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormSelect
              label="Customer"
              required
              value={form.customer_id}
              selectedLabel={project?.customer_name}
              helper="Select the customer first to filter contacts and templates."
              options={customerOptions}
              onChange={(event) => handleCustomerChange(String(event.target.value))}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormSelect
              label="Customer Contact"
              disabled={!form.customer_id}
              value={form.customer_contact_id}
              helper="Defaults to the primary contact when available."
              options={contactOptions}
              onChange={(event) =>
                setForm({ ...form, customer_contact_id: String(event.target.value) })
              }
            />
          </Grid>
        </CollapsibleFormSection>

        <CollapsibleFormSection
          sectionId="classification"
          storageKey={PROJECT_SECTION_STORAGE_KEY}
          title="Project classification"
          subtitle="Engineering stream, full design vs small task"
          icon={PrecisionManufacturingOutlinedIcon}
          defaultExpanded
        >
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormSelect
              label="Engineering stream"
              required={!isEdit}
              value={form.stream_id}
              options={[
                ...(isEdit
                  ? [{ value: '', label: 'None' }]
                  : [{ value: '', label: 'Select stream' }]),
                ...activeStreams.map((stream) => ({
                  value: stream.id,
                  label: stream.name,
                })),
              ]}
              onChange={(event) =>
                setForm({ ...form, stream_id: String(event.target.value) })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormSelect
              label="Project classification"
              required={!isEdit}
              value={form.project_classification}
              options={[
                ...(isEdit
                  ? [{ value: '', label: 'Unclassified' }]
                  : [{ value: '', label: 'Select classification' }]),
                { value: 'full_design', label: 'Full Design' },
                { value: 'small_task', label: 'Small Task' },
              ]}
              onChange={(event) => {
                const next = String(event.target.value) as ProjectClassification | '';
                setForm({
                  ...form,
                  project_classification: next,
                  small_task_type_id: next === 'small_task' ? form.small_task_type_id : '',
                });
              }}
            />
          </Grid>
          {form.project_classification === 'small_task' ? (
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Task type"
                required
                value={form.small_task_type_id}
                selectedLabel={project?.small_task_type_name}
                options={[
                  { value: '', label: 'Select task type' },
                  ...(smallTaskTypesQuery.data ?? []).map((taskType) => ({
                    value: taskType.id,
                    label: taskType.name,
                  })),
                ]}
                onChange={(event) =>
                  setForm({ ...form, small_task_type_id: String(event.target.value) })
                }
              />
            </Grid>
          ) : null}
        </CollapsibleFormSection>

        {!isEdit ? (
          <>
            <CollapsibleFormSection
              sectionId="project-type"
              storageKey={PROJECT_SECTION_STORAGE_KEY}
              title="Project Type"
              subtitle="Classification and default team"
              icon={ViewListOutlinedIcon}
            >
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormSelect
                  label="Project Type"
                  value={form.project_type_id}
                  options={[
                    { value: '', label: 'None' },
                    ...(projectTypesQuery.data ?? []).map((projectType) => ({
                      value: projectType.id,
                      label: projectType.name,
                    })),
                  ]}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      project_type_id: String(event.target.value),
                      project_template_id: '',
                    })
                  }
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormSelect
                  label="Working Model"
                  value={form.working_model_id}
                  helper="Inherited from the customer default. Override here if needed."
                  options={[
                    { value: '', label: 'Inherit from customer' },
                    ...(workingModelsQuery.data ?? []).map((model) => ({
                      value: model.id,
                      label: model.name,
                    })),
                  ]}
                  onChange={(event) =>
                    setForm({ ...form, working_model_id: String(event.target.value) })
                  }
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormSelect
                  label="Team"
                  required={!isEdit}
                  value={form.team_id ?? ''}
                  options={[
                    ...(isEdit ? [{ value: '', label: 'None' }] : [{ value: '', label: 'Select team' }]),
                    ...(teamsQuery.data ?? []).map((team) => ({
                      value: team.id,
                      label: team.name,
                    })),
                  ]}
                  onChange={(event) =>
                    setForm({ ...form, team_id: String(event.target.value) })
                  }
                />
              </Grid>
            </CollapsibleFormSection>

            <CollapsibleFormSection
              sectionId="milestones"
              storageKey={PROJECT_SECTION_STORAGE_KEY}
              title="Milestones"
              subtitle="Template applied at creation"
              icon={TimelineOutlinedIcon}
            >
              <Grid size={{ xs: 12 }}>
                <FormSelect
                  label="Template"
                  disabled={!form.customer_id || !form.project_type_id}
                  value={form.project_template_id ?? ''}
                  helper="Defines the default milestones created for the project."
                  options={[
                    { value: '', label: 'None' },
                    ...matchingTemplates.map((template) => {
                      const scopeLabel = template.is_customer_specific
                        ? template.customer_name ?? 'Customer'
                        : 'General';
                      const milestoneLabel =
                        (template.milestone_count ?? 0) === 0
                          ? ' · no milestones'
                          : ` · ${template.milestone_count} milestones`;
                      return {
                        value: template.id,
                        label: `${template.name}${template.is_default ? ' (Default)' : ''} (${scopeLabel})${milestoneLabel}`,
                      };
                    }),
                  ]}
                  onChange={(event) => {
                    const templateId = String(event.target.value);
                    const template = matchingTemplates.find((item) => item.id === templateId);
                    setForm({
                      ...form,
                      project_template_id: templateId,
                      team_id:
                        form.team_id ||
                        template?.default_team_id ||
                        form.team_id,
                    });
                  }}
                />
              </Grid>
            {selectedTemplate ? (
              <Grid size={{ xs: 12 }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  {previewMilestones.length || selectedTemplate.milestone_count} milestones will be
                  created from this template.
                </Typography>
                {previewMilestones.length ? (
                  <Box
                    component="ol"
                    sx={{
                      m: 0,
                      pl: 2.5,
                      color: 'text.secondary',
                      fontSize: '0.875rem',
                      maxHeight: 180,
                      overflow: 'auto',
                    }}
                  >
                    {previewMilestones.map((milestone) => (
                      <Box component="li" key={`${milestone.sort_order}-${milestone.milestone_name}`}>
                        {milestone.sort_order}. {milestone.milestone_name}
                        {milestone.assigned_role ? ` — ${milestone.assigned_role}` : ''}
                      </Box>
                    ))}
                  </Box>
                ) : null}
              </Grid>
            ) : null}
            </CollapsibleFormSection>
          </>
        ) : null}

        <CollapsibleFormSection
          sectionId="team"
          storageKey={PROJECT_SECTION_STORAGE_KEY}
          title="Team"
          subtitle="Design leadership and assignments"
          icon={GroupsOutlinedIcon}
        >
          <Grid size={{ xs: 12, sm: 4 }}>
            <FormSelect
              label="Design Leader"
              value={form.design_leader_id}
              selectedLabel={project?.design_leader_name}
              options={[{ value: '', label: 'None' }, ...userOptions]}
              onChange={(event) =>
                setForm({ ...form, design_leader_id: String(event.target.value) })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <FormSelect
              label="Designer"
              value={form.designer_id ?? ''}
              selectedLabel={project?.designer_name}
              options={[{ value: '', label: 'None' }, ...userOptions]}
              onChange={(event) => {
                const designerId = String(event.target.value);
                const designer = (usersQuery.data ?? []).find((user) => String(user.id) === designerId);
                setForm({
                  ...form,
                  designer_id: designerId,
                  team_id: designer?.team_id ?? form.team_id,
                });
              }}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <FormSelect
              label="Surfacer"
              value={form.surfacer_id ?? ''}
              selectedLabel={project?.surfacer_name}
              options={[{ value: '', label: 'None' }, ...userOptions]}
              onChange={(event) =>
                setForm({ ...form, surfacer_id: String(event.target.value) })
              }
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <FormSelect
              label="Team"
              required={!isEdit}
              value={form.team_id ?? ''}
              selectedLabel={project?.team_name}
              options={[
                ...(isEdit ? [{ value: '', label: 'None' }] : [{ value: '', label: 'Select team' }]),
                ...teamOptions,
              ]}
              onChange={(event) =>
                setForm({ ...form, team_id: String(event.target.value) })
              }
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <FormSelect
              label="Stream"
              required={!isEdit}
              value={form.stream_id}
              options={[
                ...(isEdit
                  ? [{ value: '', label: 'None' }]
                  : [{ value: '', label: 'Select stream' }]),
                ...activeStreams.map((stream) => ({
                  value: stream.id,
                  label: stream.name,
                })),
              ]}
              onChange={(event) =>
                setForm({ ...form, stream_id: String(event.target.value) })
              }
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              Workstreams (optional — projects can have zero or many)
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {(workstreamsQuery.data ?? []).map((ws: Workstream) => {
                const checked = form.workstream_ids.includes(ws.id);
                return (
                  <FormControlLabel
                    key={ws.id}
                    control={
                      <Switch
                        size="small"
                        checked={checked}
                        onChange={() => {
                          setForm((current) => ({
                            ...current,
                            workstream_ids: checked
                              ? current.workstream_ids.filter((id) => id !== ws.id)
                              : [...current.workstream_ids, ws.id],
                          }));
                        }}
                      />
                    }
                    label={ws.name}
                  />
                );
              })}
            </Box>
          </Grid>
        </CollapsibleFormSection>

        <CollapsibleFormSection
          sectionId="schedule"
          storageKey={PROJECT_SECTION_STORAGE_KEY}
          title="Schedule"
          subtitle="Due date and quoted effort"
          icon={ScheduleOutlinedIcon}
        >
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Due Date"
              type="date"
              helper="Suggested by project template and can be adjusted."
              slotProps={{ inputLabel: { shrink: true } }}
              value={form.due_date}
              onChange={(event) =>
                setForm({ ...form, due_date: event.target.value })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Quoted Hours"
              type="number"
              tooltip="Estimated engineering effort quoted to the customer."
              validationState={quotedHoursValidationState}
              validationMessage={quotedHoursValidationMessage}
              slotProps={{ htmlInput: { min: 0, step: 0.25 } }}
              value={form.quoted_hours}
              onChange={(event) =>
                setForm({
                  ...form,
                  quoted_hours:
                    event.target.value === '' ? '' : Number(event.target.value),
                })
              }
            />
          </Grid>
        </CollapsibleFormSection>

        {isEdit ? (
          <CollapsibleFormSection
            sectionId="project-status"
            storageKey={PROJECT_SECTION_STORAGE_KEY}
            title="Project Status"
            subtitle="Engineering stage and execution status"
            icon={FlagOutlinedIcon}
          >
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Project Stage"
                required
                value={form.project_stage}
                options={(
                  Object.entries(PROJECT_STAGE_LABELS) as Array<[ProjectStage, string]>
                ).map(([value, label]) => ({ value, label }))}
                onChange={(event) =>
                  setForm({
                    ...form,
                    project_stage: event.target.value as ProjectStage,
                  })
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Execution Status"
                required
                value={form.execution_status}
                options={(
                  Object.entries(EXECUTION_STATUS_LABELS) as Array<
                    [ExecutionStatus, string]
                  >
                ).map(([value, label]) => ({ value, label }))}
                onChange={(event) =>
                  setForm({
                    ...form,
                    execution_status: event.target.value as ExecutionStatus,
                  })
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Health"
                value={form.health}
                options={[
                  { value: 'green', label: 'Green' },
                  { value: 'yellow', label: 'Yellow' },
                  { value: 'red', label: 'Red' },
                ]}
                onChange={(event) =>
                  setForm({
                    ...form,
                    health: event.target.value as ProjectHealth,
                  })
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Project Type"
                value={form.project_type_id}
                helper="Required to choose a project template and generate milestones."
                options={[
                  { value: '', label: 'None' },
                  ...(projectTypesQuery.data ?? []).map((projectType) => ({
                    value: projectType.id,
                    label: projectType.name,
                  })),
                ]}
                onChange={(event) =>
                  setForm({
                    ...form,
                    project_type_id: String(event.target.value),
                    project_template_id: '',
                  })
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Working Model"
                value={form.working_model_id}
                options={[
                  { value: '', label: 'None' },
                  ...(workingModelsQuery.data ?? []).map((model) => ({
                    value: model.id,
                    label: model.name,
                  })),
                ]}
                onChange={(event) =>
                  setForm({ ...form, working_model_id: String(event.target.value) })
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Priority"
                required
                value={form.priority ?? 'medium'}
                options={[
                  { value: 'critical', label: 'Critical' },
                  { value: 'high', label: 'High' },
                  { value: 'medium', label: 'Medium' },
                  { value: 'low', label: 'Low' },
                ]}
                onChange={(event) =>
                  setForm({
                    ...form,
                    priority: event.target.value as ProjectFormValues['priority'],
                  })
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Complexity"
                required
                value={form.complexity ?? 'medium'}
                options={[
                  { value: 'low', label: 'Low' },
                  { value: 'medium', label: 'Medium' },
                  { value: 'high', label: 'High' },
                  { value: 'expert', label: 'Expert' },
                ]}
                onChange={(event) =>
                  setForm({
                    ...form,
                    complexity: event.target.value as ProjectFormValues['complexity'],
                  })
                }
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={form.qa_gate_enabled}
                    onChange={(event) =>
                      setForm({ ...form, qa_gate_enabled: event.target.checked })
                    }
                  />
                }
                label="Require QA acknowledgement before completing milestones"
              />
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                When enabled, Completing a milestone asks for an explicit QA confirm.
              </Typography>
            </Grid>
          </CollapsibleFormSection>
        ) : (
          <CollapsibleFormSection
            sectionId="priority"
            storageKey={PROJECT_SECTION_STORAGE_KEY}
            title="Priority & complexity"
            icon={FlagOutlinedIcon}
          >
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Priority"
                value={form.priority ?? 'medium'}
                options={[
                  { value: 'critical', label: 'Critical' },
                  { value: 'high', label: 'High' },
                  { value: 'medium', label: 'Medium' },
                  { value: 'low', label: 'Low' },
                ]}
                onChange={(event) =>
                  setForm({
                    ...form,
                    priority: event.target.value as ProjectFormValues['priority'],
                  })
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Complexity"
                value={form.complexity ?? 'medium'}
                options={[
                  { value: 'low', label: 'Low' },
                  { value: 'medium', label: 'Medium' },
                  { value: 'high', label: 'High' },
                  { value: 'expert', label: 'Expert' },
                ]}
                onChange={(event) =>
                  setForm({
                    ...form,
                    complexity: event.target.value as ProjectFormValues['complexity'],
                  })
                }
              />
            </Grid>
          </CollapsibleFormSection>
        )}

        {isEdit && project ? (
          <CollapsibleFormSection
            sectionId="template-change"
            storageKey={PROJECT_SECTION_STORAGE_KEY}
            title="Project Template"
            subtitle="Apply or change workflow before milestones are completed"
            icon={TimelineOutlinedIcon}
          >
            <Grid size={{ xs: 12 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                Current template:{' '}
                <strong>{currentTemplateName ?? 'Not set'}</strong>
              </Typography>
              {!form.project_type_id ? (
                <Alert severity="info" sx={{ mb: 1.5 }}>
                  Select a Project Type above, then apply a template to generate milestones.
                </Alert>
              ) : null}
              {project.can_change_template === false ? (
                <Alert severity="info" sx={{ mb: 1.5 }}>
                  {project.template_change_blocked_reason ??
                    'Template cannot be changed after milestone work has started.'}
                </Alert>
              ) : null}
              <ProsohmButton
                buttonVariant="outlined"
                disabled={!form.project_type_id || project.can_change_template === false}
                onClick={() => setChangeTemplateOpen(true)}
              >
                {project.project_template_id ? 'Change Template' : 'Apply Template'}
              </ProsohmButton>
            </Grid>
          </CollapsibleFormSection>
        ) : null}

        <CollapsibleFormSection
          sectionId="workorder"
          storageKey={PROJECT_SECTION_STORAGE_KEY}
          title={showMoldToolingFields ? 'Workorder / tooling' : 'Workorder'}
          subtitle={
            showMoldToolingFields
              ? 'Searchable attributes from customer workorders'
              : 'Optional workorder reference'
          }
          icon={PrecisionManufacturingOutlinedIcon}
        >
          <Grid size={{ xs: 12, md: 6 }}>
            <FormField
              label="Work order number"
              value={form.work_order_number ?? ''}
              onChange={(event) => setForm({ ...form, work_order_number: event.target.value })}
              maxLength={100}
            />
          </Grid>
          {showMoldToolingFields ? (
            <>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormField
              label="Press tonnage"
              value={form.press_tonnage ?? ''}
              onChange={(event) => setForm({ ...form, press_tonnage: event.target.value })}
              maxLength={50}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormField
              label="Plastic material"
              value={form.plastic_material ?? ''}
              onChange={(event) => setForm({ ...form, plastic_material: event.target.value })}
              maxLength={150}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <FormField
              label="Cavity count"
              type="number"
              value={form.cavity_count ?? ''}
              onChange={(event) => setForm({ ...form, cavity_count: event.target.value })}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 3 }}>
            <FormField
              label="Tool type"
              value={form.tool_type ?? ''}
              onChange={(event) => setForm({ ...form, tool_type: event.target.value })}
              maxLength={100}
            />
          </Grid>
            </>
          ) : null}
          <Grid size={{ xs: 12 }}>
            <FormField
              label="Customer specs / other details"
              multiline
              rows={3}
              maxLength={4000}
              value={form.customer_specs ?? ''}
              onChange={(event) => setForm({ ...form, customer_specs: event.target.value })}
            />
          </Grid>
        </CollapsibleFormSection>

        <CollapsibleFormSection
          sectionId="notes"
          storageKey={PROJECT_SECTION_STORAGE_KEY}
          title="Notes"
          subtitle="Additional project context"
          icon={NotesOutlinedIcon}
        >
          <Grid size={{ xs: 12 }}>
            <FormField
              label="Notes"
              multiline
              rows={4}
              maxLength={2000}
              value={form.notes ?? ''}
              onChange={(event) => setForm({ ...form, notes: event.target.value })}
            />
          </Grid>
        </CollapsibleFormSection>

        {isEdit && project ? (
          <CollapsibleFormSection
            sectionId="files"
            storageKey={PROJECT_SECTION_STORAGE_KEY}
            title="Files"
            subtitle="Project folders and released documents"
            icon={FolderOpenOutlinedIcon}
            defaultExpanded={false}
          >
            <Grid size={{ xs: 12 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                Folder paths and engineering files are managed from the project command center.
                Document metadata uploads below use the R4 DMS foundation.
              </Typography>
              <ProjectDocumentsPanel projectId={project.id} />
            </Grid>
          </CollapsibleFormSection>
        ) : null}

        {saveMutation.error ? (
          <ErrorState
            error={saveMutation.error}
            title={isEdit ? 'Update failed' : 'Create failed'}
          />
        ) : null}
      </Box>
    </FormDrawer>

    {isEdit && project && form.project_type_id ? (
      <ChangeProjectTemplateDialog
        open={changeTemplateOpen}
        projectId={project.id}
        customerId={form.customer_id || project.customer_id}
        projectTypeId={form.project_type_id}
        currentTemplateId={project.project_template_id}
        currentTemplateName={currentTemplateName}
        canChangeTemplate={project.can_change_template ?? true}
        blockedReason={project.template_change_blocked_reason}
        onClose={() => setChangeTemplateOpen(false)}
        onApplied={() => {
          showSuccess('Project template changed. Milestones were regenerated.');
          setChangeTemplateOpen(false);
          void queryClient.invalidateQueries({ queryKey: ['projects'] });
          onUpdated?.(project.id);
        }}
        onError={(message) => showError(message)}
      />
    ) : null}

    <ConfirmDialog
      open={Boolean(skillFitWarning)}
      title="Skill fit warning"
      message={skillFitWarning ?? ''}
      confirmLabel="Assign anyway"
      danger
      loading={saveMutation.isPending}
      onClose={() => setSkillFitWarning(null)}
      onConfirm={() => {
        setSkillFitWarning(null);
        saveMutation.mutate();
      }}
    />
    </>
  );
}
