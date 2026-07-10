import { useEffect, useState } from 'react';
import { Box, Grid } from '@mui/material';
import NotesOutlinedIcon from '@mui/icons-material/NotesOutlined';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { useToast } from '../../context/ToastContext';
import {
  createMilestone,
  deleteMilestone,
  updateMilestone,
} from '../../services/milestoneService';
import { invalidateMilestoneRelatedQueries } from '../../utils/queryInvalidation';
import type { Milestone, MilestoneStatus } from '../../types';
import { formatDateTime } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import { ProsohmButton } from '../ui/ProsohmButton';
import {
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
} from '../ui/design-system';

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

const milestoneStatusOptions = [
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
  onSaved?: () => void;
}

export function MilestoneFormDialog({
  open,
  onClose,
  projectId,
  milestone,
  onSaved,
}: MilestoneFormDialogProps) {
  const isEdit = Boolean(milestone);
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [form, setForm] = useState<MilestoneFormValues>(emptyForm);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

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
        description: optionalString(form.description),
        due_date: optionalString(form.due_date),
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
      onSaved?.();
      onClose();
    },
    onError: (error) => {
      showError(getErrorMessage(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteMilestone(milestone!.id),
    onSuccess: () => {
      invalidateMilestoneRelatedQueries(queryClient, projectId);
      showSuccess('Milestone deleted');
      onSaved?.();
      onClose();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const validationError = validateRequiredFields(form, [{ key: 'name', label: 'Milestone name' }]);
    if (validationError) {
      showError(validationError);
      return;
    }
    saveMutation.mutate();
  };

  return (
    <>
    <FormDrawer
      open={open}
      onClose={onClose}
      title={isEdit ? 'Edit Milestone' : 'Add Milestone'}
      subtitle="Milestones inherit the project's team assignment. Set the team on the project first."
      icon={TimelineOutlinedIcon}
      formId="milestone-form"
      width={520}
      submitLabel={isEdit ? 'Save Changes' : 'Add Milestone'}
      loading={saveMutation.isPending || deleteMutation.isPending}
      destructiveAction={
        isEdit ? (
          <ProsohmButton
            buttonVariant="danger"
            onClick={() => setDeleteConfirmOpen(true)}
            loading={deleteMutation.isPending}
            disabled={saveMutation.isPending}
          >
            Delete
          </ProsohmButton>
        ) : undefined
      }
    >
      <Box
        component="form"
        id="milestone-form"
        onSubmit={handleSubmit}
        sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
      >
        <FormSection title="Milestone Details" icon={TimelineOutlinedIcon}>
          <Grid size={{ xs: 12 }}>
            <FormField
              label="Milestone Name"
              required
              maxLength={200}
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Due Date"
              type="date"
              slotProps={{ inputLabel: { shrink: true } }}
              value={form.due_date}
              onChange={(event) =>
                setForm({ ...form, due_date: event.target.value })
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormSelect
              label="Status"
              value={form.status}
              options={milestoneStatusOptions}
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
            />
          </Grid>
          {form.status === 'completed' ? (
            <Grid size={{ xs: 12 }}>
              <FormField
                label="Completed Date"
                type="datetime-local"
                slotProps={{ inputLabel: { shrink: true } }}
                value={form.completed_at}
                helper={
                  milestone?.completed_at
                    ? `Previous: ${formatDateTime(milestone.completed_at)}`
                    : undefined
                }
                onChange={(event) =>
                  setForm({ ...form, completed_at: event.target.value })
                }
              />
            </Grid>
          ) : null}
        </FormSection>

        <FormSection title="Description" icon={NotesOutlinedIcon}>
          <Grid size={{ xs: 12 }}>
            <FormField
              label="Description"
              multiline
              rows={4}
              maxLength={1000}
              value={form.description}
              onChange={(event) =>
                setForm({ ...form, description: event.target.value })
              }
            />
          </Grid>
        </FormSection>
      </Box>
    </FormDrawer>

    <ConfirmDialog
      open={deleteConfirmOpen}
      title="Delete Milestone"
      message={`Are you sure you want to delete "${milestone?.name ?? 'this milestone'}"? This action cannot be undone.`}
      confirmLabel="Delete"
      danger
      loading={deleteMutation.isPending}
      onClose={() => setDeleteConfirmOpen(false)}
      onConfirm={() => deleteMutation.mutate()}
    />
  </>
  );
}
