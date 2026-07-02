import { useEffect, useMemo, useState } from 'react';
import { Box, Grid, Typography } from '@mui/material';
import AssignmentOutlinedIcon from '@mui/icons-material/AssignmentOutlined';
import BusinessOutlinedIcon from '@mui/icons-material/BusinessOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined';
import NotesOutlinedIcon from '@mui/icons-material/NotesOutlined';
import ViewListOutlinedIcon from '@mui/icons-material/ViewListOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchContacts, fetchCustomers, fetchStreams, fetchTeams, fetchUsers } from '../../api/lookups';
import { fetchMatchingProjectTemplates, fetchProjectTypes } from '../../api/projectTemplates';
import {
  createProject,
  invalidateProjectCalculationQueries,
  updateProject,
} from '../../services/projectService';
import type { ExecutionStatus, Project, ProjectCreate, ProjectStage, ProjectUpdate } from '../../types';
import {
  EXECUTION_STATUS_LABELS,
  PROJECT_STAGE_LABELS,
} from '../../types/common';
import { ErrorState } from '../common/ErrorState';
import {
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
} from '../ui/design-system';
import { userDisplayName } from '../../utils/format';
import { optionalString, optionalUuid, validateRequiredFields } from '../../utils/formValues';
import { useToast } from '../../context/ToastContext';

interface ProjectFormValues extends ProjectCreate {
  project_stage: ProjectStage;
  execution_status: ExecutionStatus;
}

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
  quoted_hours: 40,
  due_date: '',
  notes: '',
  priority: 'medium' as const,
  project_stage: 'preliminary',
  execution_status: 'currently_being_worked_on',
};

function projectToForm(project: Project): ProjectFormValues {
  return {
    tool_number: project.tool_number,
    part_description: project.part_description,
    customer_id: project.customer_id,
    customer_contact_id: project.customer_contact_id,
    design_leader_id: project.design_leader_id,
    designer_id: project.designer_id ?? '',
    surfacer_id: project.surfacer_id ?? '',
    stream_id: project.stream_id,
    project_type_id: project.project_type_id ?? '',
    project_template_id: project.project_template_id ?? '',
    team_id: project.team_id ?? '',
    code: project.code,
    quoted_hours: project.quoted_hours,
    due_date: project.due_date,
    notes: project.notes ?? '',
    priority: project.priority ?? 'medium',
    project_stage: project.project_stage,
    execution_status: project.execution_status,
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
      return;
    }
    if (project) {
      setForm(projectToForm(project));
    }
  }, [open, project]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        ...form,
        designer_id: optionalUuid(form.designer_id),
        surfacer_id: optionalUuid(form.surfacer_id),
        project_template_id: optionalUuid(form.project_template_id),
        notes: optionalString(form.notes),
      };

      if (isEdit && project) {
        const updatePayload: ProjectUpdate = {
          tool_number: payload.tool_number,
          code: payload.code,
          customer_id: payload.customer_id,
          customer_contact_id: payload.customer_contact_id,
          design_leader_id: payload.design_leader_id,
          designer_id: payload.designer_id,
          surfacer_id: payload.surfacer_id,
          stream_id: payload.stream_id,
          team_id: optionalUuid(form.team_id),
          quoted_hours: payload.quoted_hours,
          due_date: payload.due_date,
          notes: payload.notes,
          project_stage: payload.project_stage,
          execution_status: payload.execution_status,
          priority: payload.priority,
        };
        return updateProject(project.id, updatePayload);
      }

      return createProject({
        ...payload,
        team_id: optionalUuid(form.team_id),
      });
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
    if (!form.customer_id || !form.project_type_id || matchingTemplates.length === 0) {
      if (form.project_template_id) {
        setForm((current) => ({ ...current, project_template_id: '' }));
      }
      return;
    }

    const preferred =
      matchingTemplates.find((template) => template.is_customer_specific) ??
      matchingTemplates.find((template) => template.is_default) ??
      matchingTemplates[0];

    if (preferred && preferred.id !== form.project_template_id) {
      setForm((current) => ({ ...current, project_template_id: preferred.id }));
    }
  }, [
    form.customer_id,
    form.project_template_id,
    form.project_type_id,
    isEdit,
    matchingTemplates,
    open,
  ]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    const validationError = isEdit
      ? validateRequiredFields(
          {
            tool_number: form.tool_number,
            code: form.code,
            customer_id: form.customer_id,
            customer_contact_id: form.customer_contact_id,
            design_leader_id: form.design_leader_id,
            stream_id: form.stream_id,
            due_date: form.due_date,
          },
          [
            { key: 'tool_number', label: 'Tool number' },
            { key: 'code', label: 'Project code' },
            { key: 'customer_id', label: 'Customer' },
            { key: 'customer_contact_id', label: 'Customer contact' },
            { key: 'design_leader_id', label: 'Design leader' },
            { key: 'stream_id', label: 'Stream' },
            { key: 'due_date', label: 'Due date' },
          ],
        )
      : validateRequiredFields(
          {
            tool_number: form.tool_number,
            code: form.code,
            part_description: form.part_description,
            customer_id: form.customer_id,
            customer_contact_id: form.customer_contact_id,
            project_type_id: form.project_type_id,
            design_leader_id: form.design_leader_id,
            stream_id: form.stream_id,
            due_date: form.due_date,
          },
          [
            { key: 'tool_number', label: 'Tool number' },
            { key: 'code', label: 'Project code' },
            { key: 'part_description', label: 'Part description' },
            { key: 'customer_id', label: 'Customer' },
            { key: 'customer_contact_id', label: 'Customer contact' },
            { key: 'project_type_id', label: 'Project type' },
            { key: 'design_leader_id', label: 'Design leader' },
            { key: 'stream_id', label: 'Stream' },
            { key: 'due_date', label: 'Due date' },
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
          ? project.customer_contact_id
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

  return (
    <FormDrawer
      open={open}
      onClose={onClose}
      title={isEdit ? 'Edit Project' : 'Create Project'}
      subtitle={
        isEdit
          ? 'Update project details, team assignments, and execution status.'
          : 'Set up a new engineering project with customer, team, and template.'
      }
      icon={AssignmentOutlinedIcon}
      formId="project-form"
      width={640}
      submitLabel={isEdit ? 'Save Changes' : 'Create Project'}
      loading={saveMutation.isPending}
    >
      <Box
        component="form"
        id="project-form"
        onSubmit={handleSubmit}
        sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
      >
        <FormSection
          title="General Information"
          subtitle="Tool identification and description"
          icon={AssignmentOutlinedIcon}
        >
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Tool Number"
              required
              value={form.tool_number}
              onChange={(event) =>
                setForm({ ...form, tool_number: event.target.value })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Project Code"
              required
              value={form.code}
              onChange={(event) => setForm({ ...form, code: event.target.value })}
            />
          </Grid>
          {!isEdit ? (
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
          ) : null}
        </FormSection>

        <FormSection title="Customer" subtitle="Customer and primary contact" icon={BusinessOutlinedIcon}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormSelect
              label="Customer"
              required
              searchable
              value={form.customer_id}
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
              required
              searchable
              disabled={!form.customer_id}
              value={form.customer_contact_id}
              options={(contactsQuery.data ?? []).map((contact) => ({
                value: contact.id,
                label: userDisplayName(contact),
              }))}
              onChange={(event) =>
                setForm({ ...form, customer_contact_id: String(event.target.value) })
              }
            />
          </Grid>
        </FormSection>

        {!isEdit ? (
          <>
            <FormSection title="Project Type" icon={ViewListOutlinedIcon}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormSelect
                  label="Project Type"
                  required
                  value={form.project_type_id}
                  options={(projectTypesQuery.data ?? []).map((projectType) => ({
                    value: projectType.id,
                    label: projectType.name,
                  }))}
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
                  options={(teamsQuery.data ?? []).map((team) => ({
                    value: team.id,
                    label: team.name,
                  }))}
                  onChange={(event) =>
                    setForm({ ...form, team_id: String(event.target.value) })
                  }
                />
              </Grid>
            </FormSection>

            <FormSection
              title="Project Template"
              subtitle="Milestone template applied at creation"
              icon={ViewListOutlinedIcon}
            >
              <Grid size={{ xs: 12 }}>
                <FormSelect
                  label="Template"
                  disabled={!form.customer_id || !form.project_type_id}
                  value={form.project_template_id ?? ''}
                  options={matchingTemplates.map((template) => ({
                    value: template.id,
                    label: `${template.name}${template.is_customer_specific ? ' (Customer)' : ''}${template.is_default ? ' (Default)' : ''}`,
                  }))}
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
            </FormSection>
          </>
        ) : null}

        <FormSection title="Team" subtitle="Design leadership and assignments" icon={GroupsOutlinedIcon}>
          <Grid size={{ xs: 12, sm: 4 }}>
            <FormSelect
              label="Design Leader"
              required
              searchable
              value={form.design_leader_id}
              options={userOptions}
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
              label="Stream"
              required
              value={form.stream_id}
              options={activeStreams.map((stream) => ({
                value: stream.id,
                label: stream.name,
              }))}
              onChange={(event) =>
                setForm({ ...form, stream_id: String(event.target.value) })
              }
            />
          </Grid>
        </FormSection>

        <FormSection title="Schedule & Hours" subtitle="Due date and quoted effort" icon={ScheduleOutlinedIcon}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Due Date"
              type="date"
              required
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
              required
              slotProps={{ htmlInput: { min: 0.25, step: 0.25 } }}
              value={form.quoted_hours}
              onChange={(event) =>
                setForm({ ...form, quoted_hours: Number(event.target.value) })
              }
            />
          </Grid>
        </FormSection>

        {isEdit ? (
          <FormSection
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
          </FormSection>
        ) : (
          <FormSection title="Priority" icon={FlagOutlinedIcon}>
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
          </FormSection>
        )}

        <FormSection title="Notes" subtitle="Additional project context" icon={NotesOutlinedIcon}>
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
        </FormSection>

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
