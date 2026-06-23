import { useEffect, useState } from 'react';
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
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  createMilestone,
  milestoneQueryKeys,
  updateMilestone,
} from '../../services/milestoneService';
import {
  invalidateProjectDetail,
  projectQueryKeys,
} from '../../services/projectService';
import type { Milestone, MilestoneCreate, MilestoneStatus } from '../../types';
import { ErrorState } from '../common/ErrorState';

const statusOptions: Array<{ value: MilestoneStatus; label: string }> = [
  { value: 'not_started', label: 'Not Started' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'not_applicable', label: 'Not Applicable' },
];

const emptyForm: Omit<MilestoneCreate, 'project_id'> = {
  name: '',
  description: '',
  status: 'not_started',
  due_date: '',
  sort_order: 0,
};

interface MilestoneFormDialogProps {
  open: boolean;
  onClose: () => void;
  projectId: string;
  milestone?: Milestone | null;
}

export function MilestoneFormDialog({
  open,
  onClose,
  projectId,
  milestone,
}: MilestoneFormDialogProps) {
  const isEdit = Boolean(milestone);
  const queryClient = useQueryClient();
  const [form, setForm] = useState(emptyForm);

  useEffect(() => {
    if (!open) {
      setForm(emptyForm);
      return;
    }
    if (milestone) {
      setForm({
        name: milestone.name,
        description: milestone.description ?? '',
        status: milestone.status,
        due_date: milestone.due_date ?? '',
        sort_order: milestone.sort_order,
      });
    }
  }, [open, milestone]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name,
        description: form.description || null,
        status: form.status,
        due_date: form.due_date || null,
        sort_order: form.sort_order,
      };

      if (isEdit && milestone) {
        return updateMilestone(milestone.id, payload);
      }

      return createMilestone({
        project_id: projectId,
        ...payload,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: milestoneQueryKeys.byProject(projectId),
      });
      invalidateProjectDetail(queryClient, projectId);
      void queryClient.invalidateQueries({ queryKey: projectQueryKeys.detail(projectId) });
      onClose();
    },
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    saveMutation.mutate();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? 'Edit Milestone' : 'Create Milestone'}</DialogTitle>
      <DialogContent>
        <Grid
          container
          spacing={2}
          component="form"
          id="milestone-form"
          onSubmit={handleSubmit}
          sx={{ mt: 0.5 }}
        >
          <Grid size={{ xs: 12 }}>
            <TextField
              label="Milestone Name"
              required
              fullWidth
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <TextField
              label="Description"
              fullWidth
              multiline
              rows={2}
              value={form.description ?? ''}
              onChange={(event) =>
                setForm({ ...form, description: event.target.value })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Due Date"
              type="date"
              fullWidth
              slotProps={{ inputLabel: { shrink: true } }}
              value={form.due_date ?? ''}
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
                    status: event.target.value as MilestoneStatus,
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
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Sort Order"
              type="number"
              fullWidth
              value={form.sort_order ?? 0}
              onChange={(event) =>
                setForm({ ...form, sort_order: Number(event.target.value) })
              }
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
          form="milestone-form"
          variant="contained"
          disabled={saveMutation.isPending}
        >
          {saveMutation.isPending ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Milestone'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
