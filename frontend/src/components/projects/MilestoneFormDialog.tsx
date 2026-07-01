import { useEffect, useState } from 'react';
import {
  Button,
  CircularProgress,
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
import { getErrorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import {
  createMilestone,
  updateMilestone,
} from '../../services/milestoneService';
import { invalidateMilestoneRelatedQueries } from '../../utils/queryInvalidation';
import type { Milestone, MilestoneStatus } from '../../types';
import { formatDateTime } from '../../utils/format';

interface MilestoneFormValues {
  name: string;
  due_date: string;
  description: string;
  status: MilestoneStatus;
  completed_at: string;
}

const emptyForm: MilestoneFormValues = {
  name: '',
  due_date: '',
  description: '',
  status: 'not_started',
  completed_at: '',
};

const milestoneStatusOptions: Array<{ value: MilestoneStatus; label: string }> = [
  { value: 'not_started', label: 'Not Started' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'not_applicable', label: 'Not Applicable' },
];

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
  const { showSuccess, showError } = useToast();
  const [form, setForm] = useState<MilestoneFormValues>(emptyForm);

  useEffect(() => {
    if (!open) {
      setForm(emptyForm);
      return;
    }
    if (milestone) {
      setForm({
        name: milestone.name,
        description: milestone.description ?? '',
        due_date: milestone.due_date ?? '',
        status: milestone.status,
        completed_at: milestone.completed_at
          ? milestone.completed_at.slice(0, 16)
          : '',
      });
    } else {
      setForm(emptyForm);
    }
  }, [open, milestone]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim() || null,
        due_date: form.due_date || null,
        status: form.status,
        completed_at:
          form.status === 'completed' && form.completed_at
            ? new Date(form.completed_at).toISOString()
            : form.status === 'completed'
              ? null
              : null,
      };

      if (isEdit && milestone) {
        return updateMilestone(milestone.id, payload);
      }

      return createMilestone({
        project_id: projectId,
        name: payload.name,
        description: payload.description,
        due_date: payload.due_date,
        status: payload.status,
      });
    },
    onSuccess: () => {
      invalidateMilestoneRelatedQueries(queryClient, projectId);
      showSuccess(isEdit ? 'Milestone updated successfully' : 'Milestone added successfully');
      onClose();
    },
    onError: (error) => {
      showError(getErrorMessage(error));
    },
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    saveMutation.mutate();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? 'Edit Milestone' : 'Add Milestone'}</DialogTitle>
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
              label="Name"
              required
              fullWidth
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Due Date"
              type="date"
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
                value={form.status}
                onChange={(event) => {
                  const status = event.target.value as MilestoneStatus;
                  setForm({
                    ...form,
                    status,
                    completed_at:
                      status === 'completed' && !form.completed_at
                        ? new Date().toISOString().slice(0, 16)
                        : status === 'completed'
                          ? form.completed_at
                          : '',
                  });
                }}
              >
                {milestoneStatusOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          {form.status === 'completed' ? (
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                label="Completion Date"
                type="datetime-local"
                fullWidth
                slotProps={{ inputLabel: { shrink: true } }}
                value={form.completed_at}
                onChange={(event) =>
                  setForm({ ...form, completed_at: event.target.value })
                }
                helperText={
                  milestone?.completed_at
                    ? `Current: ${formatDateTime(milestone.completed_at)}`
                    : undefined
                }
              />
            </Grid>
          ) : null}
          <Grid size={{ xs: 12 }}>
            <TextField
              label="Description"
              fullWidth
              multiline
              rows={3}
              value={form.description}
              onChange={(event) =>
                setForm({ ...form, description: event.target.value })
              }
            />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saveMutation.isPending}>
          Cancel
        </Button>
        <Button
          type="submit"
          form="milestone-form"
          variant="contained"
          disabled={saveMutation.isPending || !form.name.trim()}
          startIcon={
            saveMutation.isPending ? (
              <CircularProgress size={16} color="inherit" />
            ) : undefined
          }
        >
          {saveMutation.isPending
            ? 'Saving…'
            : isEdit
              ? 'Save Changes'
              : 'Add Milestone'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
