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
import { fetchContacts, fetchCustomers, fetchStreams, fetchUsers } from '../../api/lookups';
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
  code: '',
  quoted_hours: 40,
  due_date: '',
  notes: '',
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
    code: project.code,
    quoted_hours: project.quoted_hours,
    due_date: project.due_date,
    notes: project.notes ?? '',
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
        designer_id: form.designer_id || null,
        surfacer_id: form.surfacer_id || null,
        project_template_id: form.project_template_id || null,
        notes: form.notes || null,
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
          quoted_hours: payload.quoted_hours,
          due_date: payload.due_date,
          notes: payload.notes,
          project_stage: payload.project_stage,
          execution_status: payload.execution_status,
        };
        return updateProject(project.id, updatePayload);
      }

      return createProject(payload);
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
    saveMutation.mutate();
  };

  const handleCustomerChange = (customerId: string) => {
    setForm((current) => ({
      ...current,
      customer_id: customerId,
      customer_contact_id:
        project && customerId === project.customer_id
          ? project.customer_contact_id
          : '',
      project_template_id: '',
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
          <FormSection
            title="Project Template"
            subtitle="Milestone template applied at creation"
            icon={ViewListOutlinedIcon}
          >
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
                label="Template"
                required
                disabled={!form.customer_id || !form.project_type_id}
                value={form.project_template_id ?? ''}
                options={matchingTemplates.map((template) => ({
                  value: template.id,
                  label: `${template.name}${template.is_customer_specific ? ' (Customer)' : ''}${template.is_default ? ' (Default)' : ''}`,
                }))}
                onChange={(event) =>
                  setForm({ ...form, project_template_id: String(event.target.value) })
                }
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
              onChange={(event) =>
                setForm({ ...form, designer_id: String(event.target.value) })
              }
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
          </FormSection>
        ) : null}

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
