import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  TextField,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchMatchingProjectTemplates } from '../../api/projectTemplates';
import { applyProjectTemplate } from '../../services/projectService';
import { ProsohmButton } from '../ui/ProsohmButton';

interface ChangeProjectTemplateDialogProps {
  open: boolean;
  projectId: string;
  customerId: string;
  projectTypeId: string;
  currentTemplateId?: string | null;
  currentTemplateName?: string | null;
  canChangeTemplate?: boolean;
  blockedReason?: string | null;
  onClose: () => void;
  onApplied: () => void;
  onError: (message: string) => void;
}

export function ChangeProjectTemplateDialog({
  open,
  projectId,
  customerId,
  projectTypeId,
  currentTemplateId,
  currentTemplateName,
  canChangeTemplate = true,
  blockedReason,
  onClose,
  onApplied,
  onError,
}: ChangeProjectTemplateDialogProps) {
  const [selectedTemplateId, setSelectedTemplateId] = useState(currentTemplateId ?? '');
  const [applying, setApplying] = useState(false);

  const templatesQuery = useQuery({
    queryKey: ['matching-project-templates', customerId, projectTypeId],
    queryFn: () =>
      fetchMatchingProjectTemplates({
        customer_id: customerId,
        project_type_id: projectTypeId,
      }),
    enabled: open && Boolean(customerId) && Boolean(projectTypeId) && canChangeTemplate,
  });

  const templateOptions = useMemo(() => templatesQuery.data ?? [], [templatesQuery.data]);

  useEffect(() => {
    if (!open) return;
    setSelectedTemplateId(currentTemplateId ?? '');
  }, [open, currentTemplateId]);

  const selectedTemplate = templateOptions.find((template) => template.id === selectedTemplateId);
  const templateChanged =
    Boolean(selectedTemplateId) && selectedTemplateId !== (currentTemplateId ?? '');

  const handleConfirm = async () => {
    if (!selectedTemplateId || !templateChanged) {
      onError('Select a different template to apply');
      return;
    }
    setApplying(true);
    try {
      await applyProjectTemplate(projectId, selectedTemplateId, projectTypeId);
      onApplied();
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Unable to change project template');
    } finally {
      setApplying(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{canChangeTemplate ? 'Change Project Template' : 'Template Locked'}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
        {!canChangeTemplate ? (
          <Alert severity="info">
            {blockedReason ??
              'The project template cannot be changed after work has started on milestones.'}
          </Alert>
        ) : (
          <>
            <Alert severity="warning" sx={{ py: 0.5 }}>
              Applying a new template replaces all current milestones. This is only allowed before
              any milestone is marked completed and before timesheet hours are logged against
              milestones.
            </Alert>

            {currentTemplateName ? (
              <Typography variant="body2" color="text.secondary">
                Current template: <strong>{currentTemplateName}</strong>
              </Typography>
            ) : null}

            <TextField
              select
              fullWidth
              size="small"
              label="New template"
              value={selectedTemplateId}
              disabled={templatesQuery.isLoading || applying}
              onChange={(event) => setSelectedTemplateId(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            >
              <MenuItem value="">Select template</MenuItem>
              {templateOptions.map((template) => (
                <MenuItem key={template.id} value={template.id}>
                  {template.name}
                  {template.is_default ? ' (Default)' : ''}
                  {template.is_customer_specific
                    ? ` (${template.customer_name ?? 'Customer'})`
                    : ''}
                </MenuItem>
              ))}
            </TextField>

            {selectedTemplate ? (
              <Typography variant="body2" color="text.secondary">
                {selectedTemplate.milestone_count} milestones will replace the current workflow.
              </Typography>
            ) : null}
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <ProsohmButton buttonVariant="outlined" onClick={onClose} disabled={applying}>
          {canChangeTemplate ? 'Cancel' : 'Close'}
        </ProsohmButton>
        {canChangeTemplate ? (
          <ProsohmButton
            buttonVariant="danger"
            onClick={() => void handleConfirm()}
            loading={applying || templatesQuery.isLoading}
            disabled={!templateChanged}
          >
            Apply Template
          </ProsohmButton>
        ) : null}
      </DialogActions>
    </Dialog>
  );
}
