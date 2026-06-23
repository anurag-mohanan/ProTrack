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
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchContacts, fetchCustomers, fetchStreams, fetchUsers } from '../../api/lookups';
import {
  createProject,
  invalidateProjectDetail,
  projectQueryKeys,
  updateProject,
} from '../../services/projectService';
import type { Project, ProjectCreate, ProjectStatus, ProjectUpdate } from '../../types';
import { ErrorState } from '../common/ErrorState';
import { userDisplayName } from '../../utils/format';

const statusOptions: Array<{ value: ProjectStatus; label: string }> = [
  { value: 'not_started', label: 'Not Started' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'waiting_for_customer', label: 'On Hold' },
  { value: 'completed', label: 'Completed' },
];

const emptyForm: ProjectCreate = {
  tool_number: '',
  part_description: '',
  customer_id: '',
  customer_contact_id: '',
  design_leader_id: '',
  designer_id: '',
  surfacer_id: '',
  stream_id: '',
  code: '',
  quoted_hours: 40,
  due_date: '',
  status: 'not_started',
  notes: '',
};

function projectToForm(project: Project): ProjectCreate {
  return {
    tool_number: project.tool_number,
    part_description: project.part_description,
    customer_id: project.customer_id,
    customer_contact_id: project.customer_contact_id,
    design_leader_id: project.design_leader_id,
    designer_id: project.designer_id ?? '',
    surfacer_id: project.surfacer_id ?? '',
    stream_id: project.stream_id,
    code: project.code,
    quoted_hours: project.quoted_hours,
    due_date: project.due_date,
    status: project.status,
    notes: project.notes ?? '',
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
  const [form, setForm] = useState<ProjectCreate>(emptyForm);

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
          status: payload.status,
          notes: payload.notes,
        };
        return updateProject(project.id, updatePayload);
      }

      return createProject(payload);
    },
    onSuccess: (savedProject) => {
      void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      if (isEdit) {
        invalidateProjectDetail(queryClient, savedProject.id);
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
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                label="Status"
                value={form.status ?? 'not_started'}
                onChange={(event) =>
                  setForm({
                    ...form,
                    status: event.target.value as ProjectStatus,
                  })
                }
              >
                {statusOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
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
