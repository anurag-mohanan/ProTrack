import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
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

  const activeProjectTypes = useMemo(
    () => projectTypesQuery.data ?? [],
    [projectTypesQuery.data],
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

  const handleProjectTypeChange = (projectTypeId: string) => {
    setForm((current) => ({
      ...current,
      project_type_id: projectTypeId,
      project_template_id: '',
    }));
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{isEdit ? 'Edit Project' : 'Create Project'}</DialogTitle>
      <DialogContent>
        <Grid
          container
          spacing={2}
          component="form"
          id="project-form"
          onSubmit={handleSubmit}
          sx={{ mt: 0.5 }}
        >
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Tool Number"
              required
              fullWidth
              value={form.tool_number}
              onChange={(event) =>
                setForm({ ...form, tool_number: event.target.value })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Project Code"
              required
              fullWidth
              value={form.code}
              onChange={(event) => setForm({ ...form, code: event.target.value })}
            />
          </Grid>
          {!isEdit ? (
            <Grid size={{ xs: 12 }}>
              <TextField
                label="Part Description"
                required
                fullWidth
                value={form.part_description}
                onChange={(event) =>
                  setForm({ ...form, part_description: event.target.value })
                }
              />
            </Grid>
          ) : null}
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControl fullWidth required>
              <InputLabel>Customer</InputLabel>
              <Select
                label="Customer"
                value={form.customer_id}
                onChange={(event) => handleCustomerChange(event.target.value)}
              >
                {activeCustomers.map((customer) => (
                  <MenuItem key={customer.id} value={customer.id}>
                    {customer.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControl fullWidth required disabled={!form.customer_id}>
              <InputLabel>Customer Contact</InputLabel>
              <Select
                label="Customer Contact"
                value={form.customer_contact_id}
                onChange={(event) =>
                  setForm({ ...form, customer_contact_id: event.target.value })
                }
              >
                {(contactsQuery.data ?? []).map((contact) => (
                  <MenuItem key={contact.id} value={contact.id}>
                    {userDisplayName(contact)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          {!isEdit ? (
            <>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControl fullWidth required>
                  <InputLabel>Project Type</InputLabel>
                  <Select
                    label="Project Type"
                    value={form.project_type_id}
                    onChange={(event) => handleProjectTypeChange(event.target.value)}
                  >
                    {activeProjectTypes.map((projectType) => (
                      <MenuItem key={projectType.id} value={projectType.id}>
                        {projectType.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControl
                  fullWidth
                  required
                  disabled={!form.customer_id || !form.project_type_id}
                >
                  <InputLabel>Project Template</InputLabel>
                  <Select
                    label="Project Template"
                    value={form.project_template_id}
                    onChange={(event) =>
                      setForm({ ...form, project_template_id: event.target.value })
                    }
                  >
                    {matchingTemplates.map((template) => (
                      <MenuItem key={template.id} value={template.id}>
                        {template.name}
                        {template.is_customer_specific ? ' (Customer)' : ''}
                        {template.is_default ? ' (Default)' : ''}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              {selectedTemplate ? (
                <Grid size={{ xs: 12 }}>
                  <Typography variant="body2" color="text.secondary">
                    {selectedTemplate.milestone_count} milestones will be created from this
                    template.
                  </Typography>
                </Grid>
              ) : null}
            </>
          ) : null}
          <Grid size={{ xs: 12, sm: 4 }}>
            <FormControl fullWidth required>
              <InputLabel>Design Leader</InputLabel>
              <Select
                label="Design Leader"
                value={form.design_leader_id}
                onChange={(event) =>
                  setForm({ ...form, design_leader_id: event.target.value })
                }
              >
                {(usersQuery.data ?? []).map((user) => (
                  <MenuItem key={user.id} value={user.id}>
                    {userDisplayName(user)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <FormControl fullWidth>
              <InputLabel>Designer</InputLabel>
              <Select
                label="Designer"
                value={form.designer_id ?? ''}
                onChange={(event) =>
                  setForm({ ...form, designer_id: event.target.value })
                }
              >
                <MenuItem value="">None</MenuItem>
                {(usersQuery.data ?? []).map((user) => (
                  <MenuItem key={user.id} value={user.id}>
                    {userDisplayName(user)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <FormControl fullWidth>
              <InputLabel>Surfacer</InputLabel>
              <Select
                label="Surfacer"
                value={form.surfacer_id ?? ''}
                onChange={(event) =>
                  setForm({ ...form, surfacer_id: event.target.value })
                }
              >
                <MenuItem value="">None</MenuItem>
                {(usersQuery.data ?? []).map((user) => (
                  <MenuItem key={user.id} value={user.id}>
                    {userDisplayName(user)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControl fullWidth required>
              <InputLabel>Stream</InputLabel>
              <Select
                label="Stream"
                value={form.stream_id}
                onChange={(event) =>
                  setForm({ ...form, stream_id: event.target.value })
                }
              >
                {activeStreams.map((stream) => (
                  <MenuItem key={stream.id} value={stream.id}>
                    {stream.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <TextField
              label="Quoted Hours"
              type="number"
              required
              fullWidth
              slotProps={{ htmlInput: { min: 0.25, step: 0.25 } }}
              value={form.quoted_hours}
              onChange={(event) =>
                setForm({ ...form, quoted_hours: Number(event.target.value) })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <TextField
              label="Due Date"
              type="date"
              required
              fullWidth
              slotProps={{ inputLabel: { shrink: true } }}
              value={form.due_date}
              onChange={(event) =>
                setForm({ ...form, due_date: event.target.value })
              }
            />
          </Grid>
          {isEdit ? (
            <>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControl fullWidth required>
                  <InputLabel>Project Stage</InputLabel>
                  <Select
                    label="Project Stage"
                    value={form.project_stage}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        project_stage: event.target.value as ProjectStage,
                      })
                    }
                  >
                    {(
                      Object.entries(PROJECT_STAGE_LABELS) as Array<
                        [ProjectStage, string]
                      >
                    ).map(([value, label]) => (
                      <MenuItem key={value} value={value}>
                        {label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControl fullWidth required>
                  <InputLabel>Execution Status</InputLabel>
                  <Select
                    label="Execution Status"
                    value={form.execution_status}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        execution_status: event.target.value as ExecutionStatus,
                      })
                    }
                  >
                    {(
                      Object.entries(EXECUTION_STATUS_LABELS) as Array<
                        [ExecutionStatus, string]
                      >
                    ).map(([value, label]) => (
                      <MenuItem key={value} value={value}>
                        {label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </>
          ) : null}
          <Grid size={{ xs: 12 }}>
            <TextField
              label="Notes"
              fullWidth
              multiline
              rows={2}
              value={form.notes ?? ''}
              onChange={(event) => setForm({ ...form, notes: event.target.value })}
            />
          </Grid>
        </Grid>

        {saveMutation.error ? (
          <ErrorState
            error={saveMutation.error}
            title={isEdit ? 'Update failed' : 'Create failed'}
          />
        ) : null}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          type="submit"
          form="project-form"
          variant="contained"
          disabled={saveMutation.isPending}
        >
          {saveMutation.isPending
            ? isEdit
              ? 'Saving…'
              : 'Creating…'
            : isEdit
              ? 'Save Changes'
              : 'Create Project'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
