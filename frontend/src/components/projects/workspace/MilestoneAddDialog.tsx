import { useState } from 'react';
import { Stack } from '@mui/material';
import { FormDrawer, FormField, FormSelect } from '../../ui/design-system';
import { useToast } from '../../../context/ToastContext';
import { createMilestone } from '../../../services/milestoneService';
import type { MilestoneStatus } from '../../../types';
import { MILESTONE_STATUS_LABELS } from '../../../types/common';

const FORM_ID = 'milestone-add-form';

interface MilestoneAddDialogProps {
  open: boolean;
  projectId: string;
  nextSortOrder: number;
  userOptions: Array<{ value: string; label: string }>;
  onClose: () => void;
  onCreated: () => void;
}

const STATUS_OPTIONS = Object.keys(MILESTONE_STATUS_LABELS) as MilestoneStatus[];

export function MilestoneAddDialog({
  open,
  projectId,
  nextSortOrder,
  userOptions,
  onClose,
  onCreated,
}: MilestoneAddDialogProps) {
  const { showSuccess, showError } = useToast();
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState('');
  const [plannedHours, setPlannedHours] = useState('8');
  const [assignedUserId, setAssignedUserId] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [status, setStatus] = useState<MilestoneStatus>('not_started');
  const [insertPosition, setInsertPosition] = useState(String(nextSortOrder));

  const reset = () => {
    setName('');
    setPlannedHours('8');
    setAssignedUserId('');
    setDueDate('');
    setStatus('not_started');
    setInsertPosition(String(nextSortOrder));
  };

  const handleSave = async () => {
    if (!name.trim()) {
      showError('Milestone name is required');
      return;
    }
    setSaving(true);
    try {
      await createMilestone({
        project_id: projectId,
        name: name.trim(),
        planned_hours: Number(plannedHours) || 0,
        assigned_user_id: assignedUserId || null,
        due_date: dueDate || null,
        status,
        sort_order: Number(insertPosition) || nextSortOrder,
      });
      showSuccess('Milestone added');
      reset();
      onCreated();
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Unable to add milestone');
    } finally {
      setSaving(false);
    }
  };

  return (
    <FormDrawer
      formId={FORM_ID}
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="Add milestone"
      subtitle="Insert a custom milestone into the execution plan"
      onSubmit={handleSave}
      submitLabel="Add Milestone"
      loading={saving}
    >
      <Stack spacing={2} component="form" id={FORM_ID} onSubmit={(e) => e.preventDefault()}>
        <FormField label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
        <FormField
          label="Planned hours"
          type="number"
          value={plannedHours}
          onChange={(e) => setPlannedHours(e.target.value)}
        />
        <FormSelect
          label="Assigned user"
          searchable
          value={assignedUserId}
          options={[{ value: '', label: 'Unassigned' }, ...userOptions]}
          onChange={(e) => setAssignedUserId(String(e.target.value))}
        />
        <FormField
          label="Target date"
          type="date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
        />
        <FormSelect
          label="Status"
          value={status}
          options={STATUS_OPTIONS.map((option) => ({
            value: option,
            label: MILESTONE_STATUS_LABELS[option],
          }))}
          onChange={(e) => setStatus(e.target.value as MilestoneStatus)}
        />
        <FormField
          label="Insert position"
          type="number"
          value={insertPosition}
          onChange={(e) => setInsertPosition(e.target.value)}
          helper={`Order in the milestone list (1–${nextSortOrder})`}
        />
      </Stack>
    </FormDrawer>
  );
}
