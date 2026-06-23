import { useEffect, useState } from 'react';
import {
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
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
import type { Milestone } from '../../types';

interface MilestoneFormValues {
  name: string;
  due_date: string;
  description: string;
}

const emptyForm: MilestoneFormValues = {
  name: '',
  due_date: '',
  description: '',
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
          <Grid size={{ xs: 12 }}>
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
