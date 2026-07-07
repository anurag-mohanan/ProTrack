import { useEffect, useMemo, useRef, useState } from 'react';
import { Box, Grid, Typography } from '@mui/material';
import AssignmentOutlinedIcon from '@mui/icons-material/AssignmentOutlined';
import BusinessOutlinedIcon from '@mui/icons-material/BusinessOutlined';
import FolderOpenOutlinedIcon from '@mui/icons-material/FolderOpenOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined';
import NotesOutlinedIcon from '@mui/icons-material/NotesOutlined';
import ViewListOutlinedIcon from '@mui/icons-material/ViewListOutlined';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchContacts, fetchCustomers, fetchStreams, fetchTeams, fetchUsers } from '../../api/lookups';
import { fetchMatchingProjectTemplates, fetchProjectTypes } from '../../api/projectTemplates';
import {
  createProject,
  invalidateProjectCalculationQueries,
  updateProject,
} from '../../services/projectService';
import type { ExecutionStatus, Project, ProjectCreate, ProjectHealth, ProjectStage, ProjectUpdate } from '../../types';
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
import { useToast } from '../../context/ToastContext';

interface ProjectFormValues {
  tool_number: string;
  part_description: string;
  customer_id: string;
  customer_contact_id: string;
  design_leader_id: string;
  designer_id: string;
  surfacer_id: string;
  stream_id: string;
  project_type_id: string;
  project_template_id: string;
  team_id: string;
  code: string;
  quoted_hours: number | '';
  due_date: string;
  notes: string;
  priority: ProjectCreate['priority'];
  project_stage: ProjectStage;
  execution_status: ExecutionStatus;
  health: ProjectHealth;
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
  project_type_id: '',
  project_template_id: '',
  team_id: '',
  code: '',
  quoted_hours: '',
  due_date: '',
  notes: '',
  priority: 'medium',
  project_stage: 'preliminary',
  execution_status: 'planning',
  health: 'green',
};

function projectToForm(project: Project): ProjectFormValues {
  return {
    tool_number: project.tool_number,
    part_description: project.part_description,
    customer_id: project.customer_id,
    customer_contact_id: project.customer_contact_id ?? '',
    design_leader_id: project.design_leader_id ?? '',
    designer_id: project.designer_id ?? '',
    surfacer_id: project.surfacer_id ?? '',
    stream_id: project.stream_id ?? '',
    project_type_id: project.project_type_id ?? '',
    project_template_id: project.project_template_id ?? '',
    team_id: project.team_id ?? '',
    code: project.code ?? '',
    quoted_hours: project.quoted_hours,
    due_date: project.due_date ?? '',
    notes: project.notes ?? '',
    priority: project.priority ?? 'medium',
    project_stage: project.project_stage,
    execution_status: project.execution_status,
    health: project.health,
  };
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
  const { showError } = useToast();
  const [form, setForm] = useState<ProjectFormValues>(emptyForm);
  const baselineRef = useRef('');

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

  const teamsQuery = useQuery({
    queryKey: ['teams'],
    queryFn: fetchTeams,
    enabled: open,
  });

  const projectTypesQuery = useQuery({
    queryKey: ['project-types'],
    queryFn: fetchProjectTypes,
    enabled: open && !isEdit,
  });

  const matchingTemplatesQuery = useQuery({
    queryKey: ['project-templates', form.customer_id, form.project_type_id],
    queryFn: () =>
      fetchMatchingProjectTemplates({
        customer_id: form.customer_id,
        project_type_id: form.project_type_id,
      }),
    enabled: open && !isEdit && Boolean(form.customer_id) && Boolean(form.project_type_id),
  });

  useEffect(() => {
    if (!open) {
      setForm(emptyForm);
      baselineRef.current = serializeForm(emptyForm);
      return;
    }
    const initial = project ? projectToForm(project) : emptyForm;
    setForm(initial);
    baselineRef.current = serializeForm(initial);
  }, [open, project]);

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

  useEffect(() => {
    if (!open || isEdit) return;
    if (form.code.trim()) return;
    const suggested = form.tool_number
      .trim()
      .replace(/\s+/g, '-')
      .replace(/[^a-zA-Z0-9-_]/g, '')
      .toUpperCase();
    if (!suggested) return;
    setForm((current) => ({ ...current, code: suggested }));
  }, [form.tool_number, form.code, open, isEdit]);

  const saveMutation = useMutation({
    mutationFn: async () => {
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
          quoted_hours: form.quoted_hours === '' ? null : Number(form.quoted_hours),
          due_date: optionalString(form.due_date),
          notes: optionalString(form.notes),
          project_stage: form.project_stage,
          execution_status: form.execution_status,
          priority: form.priority,
          health: form.health,
        };
        return updateProject(project.id, updatePayload);
      }

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
        code: optionalString(form.code),
        quoted_hours: optionalNumber(form.quoted_hours),
        due_date: optionalString(form.due_date),
        priority: form.priority,
        notes: optionalString(form.notes),
      };
      return createProject(createPayload);
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

  const activeStreams = useMemo(
    () => (streamsQuery.data ?? []).filter((stream) => stream.is_active),
    [streamsQuery.data],
  );

  const activeCustomers = useMemo(
    () => (customersQuery.data ?? []).filter((customer) => customer.is_active),
    [customersQuery.data],
  );

  const matchingTemplates = useMemo(
    () => matchingTemplatesQuery.data ?? [],
    [matchingTemplatesQuery.data],
  );

  const selectedTemplate = useMemo(
    () => matchingTemplates.find((template) => template.id === form.project_template_id),
    [form.project_template_id, matchingTemplates],
  );

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
      !isBlankDisplayValue(form.customer_id),
    [form.tool_number, form.part_description, form.customer_id],
  );

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    const validationError = validateRequiredFields(
      {
        tool_number: form.tool_number,
        part_description: form.part_description,
        customer_id: form.customer_id,
      },
      [
        { key: 'tool_number', label: 'Tool number' },
        { key: 'part_description', label: 'Part description' },
        { key: 'customer_id', label: 'Customer' },
      ],
    );

    if (validationError) {
      showError(validationError);
      return;
    }

    saveMutation.mutate();
  };

  const handleCustomerChange = (customerId: string) => {
    const customer = activeCustomers.find((item) => item.id === customerId);
    setForm((current) => ({
      ...current,
      customer_id: customerId,
      customer_contact_id:
        project && customerId === project.customer_id
          ? (project.customer_contact_id ?? '')
          : '',
      project_type_id: customer?.default_project_type_id ?? current.project_type_id,
      team_id: customer?.default_team_id ?? current.team_id,
      project_template_id: customer?.default_project_template_id ?? '',
    }));
  };

  const userOptions = (usersQuery.data ?? []).map((user) => ({
    value: user.id,
    label: userDisplayName(user),
  }));

  const selectedCustomerName = useMemo(() => {
    if (project?.customer_name && form.customer_id === project.customer_id) {
      return project.customer_name;
    }
    return activeCustomers.find((customer) => customer.id === form.customer_id)?.name ?? null;
  }, [activeCustomers, form.customer_id, project]);

  return (
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
      loading={saveMutation.isPending}
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
          subtitle="Tool identification and description"
          icon={AssignmentOutlinedIcon}
        >
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Tool Number"
              required
              value={form.tool_number}
              tooltip="Customer tool or mold number used to uniquely identify the project."
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
              helper="Suggested automatically from Tool Number. You can edit if needed."
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
              searchable
              value={form.customer_id}
              helper="Select the customer first to filter contacts and templates."
              options={activeCustomers.map((customer) => ({
                value: customer.id,
                label: customer.name,
              }))}
              onChange={(event) => handleCustomerChange(String(event.target.value))}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormSelect
              label="Customer Contact"
              searchable
              disabled={!form.customer_id}
              value={form.customer_contact_id}
              helper="Defaults to the primary contact when available."
              options={[
                { value: '', label: 'None' },
                ...(contactsQuery.data ?? []).map((contact) => ({
                  value: contact.id,
                  label: userDisplayName(contact),
                })),
              ]}
              onChange={(event) =>
                setForm({ ...form, customer_contact_id: String(event.target.value) })
              }
            />
          </Grid>
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
                  label="Team"
                  searchable
                  value={form.team_id ?? ''}
                  options={[
                    { value: '', label: 'None' },
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
                    ...matchingTemplates.map((template) => ({
                      value: template.id,
                      label: `${template.name}${template.is_customer_specific ? ' (Customer)' : ''}${template.is_default ? ' (Default)' : ''}`,
                    })),
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
                <Typography variant="body2" color="text.secondary">
                  {selectedTemplate.milestone_count} milestones will be created from this
                  template.
                </Typography>
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
              searchable
              value={form.design_leader_id}
              options={[{ value: '', label: 'None' }, ...userOptions]}
              onChange={(event) =>
                setForm({ ...form, design_leader_id: String(event.target.value) })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <FormSelect
              label="Designer"
              searchable
              value={form.designer_id ?? ''}
              options={[{ value: '', label: 'None' }, ...userOptions]}
              onChange={(event) => {
                const designerId = String(event.target.value);
                const designer = (usersQuery.data ?? []).find((user) => user.id === designerId);
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
              searchable
              value={form.surfacer_id ?? ''}
              options={[{ value: '', label: 'None' }, ...userOptions]}
              onChange={(event) =>
                setForm({ ...form, surfacer_id: String(event.target.value) })
              }
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <FormSelect
              label="Team"
              searchable
              value={form.team_id ?? ''}
              options={[
                { value: '', label: 'None' },
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
          <Grid size={{ xs: 12 }}>
            <FormSelect
              label="Stream"
              value={form.stream_id}
              options={[
                { value: '', label: 'None' },
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
          </CollapsibleFormSection>
        ) : (
          <CollapsibleFormSection
            sectionId="priority"
            storageKey={PROJECT_SECTION_STORAGE_KEY}
            title="Priority"
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
          </CollapsibleFormSection>
        )}

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
              <Typography variant="body2" color="text.secondary">
                Folder paths and engineering files are managed from the project command center.
                Open the project detail page to edit folder locations and released documents.
              </Typography>
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
  );
}
