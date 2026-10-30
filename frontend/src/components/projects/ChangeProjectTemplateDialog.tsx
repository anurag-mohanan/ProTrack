import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchMatchingProjectTemplates } from '../../api/projectTemplates';
import { ApiError, getErrorMessage } from '../../api/client';
import {
  applyTemplateReconciliation,
  fetchTemplateReconciliations,
  previewTemplateReconciliation,
  type ExistingDecision,
  type TemplateDecision,
  type TemplateReconciliationApplyResult,
  type TemplateReconciliationPreviewRequest,
} from '../../services/templateReconciliationService';
import { ProsohmButton } from '../ui/ProsohmButton';
import { TemplateReconciliationPreviewView } from './TemplateReconciliationPreviewView';

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
  onApplied: (result: TemplateReconciliationApplyResult) => void;
  onError: (message: string) => void;
}

type Step = 'select' | 'preview' | 'confirm';

function newRequestKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID().replace(/-/g, '');
  }
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 14)}`;
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
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<'change' | 'history'>('change');
  const [step, setStep] = useState<Step>('select');
  const [selectedTemplateId, setSelectedTemplateId] = useState(currentTemplateId ?? '');
  const [templateDecisions, setTemplateDecisions] = useState<Record<string, TemplateDecision>>({});
  const [existingDecisions, setExistingDecisions] = useState<Record<string, ExistingDecision>>({});
  const [applyTemplateHours, setApplyTemplateHours] = useState(false);
  const [scheduleNew, setScheduleNew] = useState(true);
  const [reviewed, setReviewed] = useState(false);
  const [ackEstimate, setAckEstimate] = useState(false);
  const [reason, setReason] = useState('');
  const [requestKey, setRequestKey] = useState('');
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);

  const [openedFor, setOpenedFor] = useState<string | null>(null);
  const openKey = open ? `${projectId}:${currentTemplateId ?? ''}` : null;
  if (openKey !== openedFor) {
    setOpenedFor(openKey);
    if (openKey) {
      setTab('change');
      setStep('select');
      setSelectedTemplateId(currentTemplateId ?? '');
      setTemplateDecisions({});
      setExistingDecisions({});
      setApplyTemplateHours(false);
      setScheduleNew(true);
      setReviewed(false);
      setAckEstimate(false);
      setReason('');
      setApplyError(null);
    }
  }

  const templatesQuery = useQuery({
    queryKey: ['matching-project-templates', customerId, projectTypeId],
    queryFn: () =>
      fetchMatchingProjectTemplates({ customer_id: customerId, project_type_id: projectTypeId }),
    enabled: open && Boolean(customerId) && Boolean(projectTypeId) && canChangeTemplate,
  });
  const templateOptions = useMemo(() => templatesQuery.data ?? [], [templatesQuery.data]);

  const request: TemplateReconciliationPreviewRequest = useMemo(
    () => ({
      template_id: selectedTemplateId,
      template_decisions: Object.values(templateDecisions),
      existing_decisions: Object.values(existingDecisions),
      apply_template_hours: applyTemplateHours,
      schedule_new: scheduleNew,
    }),
    [selectedTemplateId, templateDecisions, existingDecisions, applyTemplateHours, scheduleNew],
  );

  const previewQuery = useQuery({
    queryKey: ['template-reconciliation-preview', projectId, request],
    queryFn: () => previewTemplateReconciliation(projectId, request),
    enabled: open && canChangeTemplate && step !== 'select' && Boolean(selectedTemplateId),
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: false,
    retry: false,
  });
  const preview = previewQuery.data;

  const historyQuery = useQuery({
    queryKey: ['template-reconciliations', projectId],
    queryFn: () => fetchTemplateReconciliations(projectId),
    enabled: open && tab === 'history',
  });

  const resetDecisions = () => {
    setTemplateDecisions({});
    setExistingDecisions({});
    setReviewed(false);
    setAckEstimate(false);
  };

  const goToConfirm = () => {
    setRequestKey(newRequestKey());
    setReviewed(false);
    setAckEstimate(false);
    setApplyError(null);
    setStep('confirm');
  };

  const handleApply = async () => {
    if (!preview) return;
    setApplying(true);
    setApplyError(null);
    try {
      const result = await applyTemplateReconciliation(projectId, {
        ...request,
        preview_fingerprint: preview.fingerprint,
        plan_version: preview.plan_version,
        request_key: requestKey,
        confirm: true,
        acknowledge_estimate_change: ackEstimate,
        reason: reason.trim() || null,
      });
      void queryClient.invalidateQueries({ queryKey: ['template-reconciliations', projectId] });
      onApplied(result);
    } catch (error) {
      const message = getErrorMessage(error);
      setApplyError(message);
      if (error instanceof ApiError && error.status === 409) {
        setStep('preview');
        void queryClient.invalidateQueries({ queryKey: ['template-reconciliation-preview', projectId] });
      } else if (!(error instanceof ApiError) || error.status >= 500) {
        onError(message);
      }
    } finally {
      setApplying(false);
    }
  };

  const blocked = Boolean(preview?.blockers.length);
  const busy = applying || previewQuery.isFetching;
  const confirmReady =
    reviewed && (!preview?.requires_estimate_acknowledgement || ackEstimate) && !blocked && !busy;

  const renderSelect = () => (
    <>
      <Alert severity="info" sx={{ py: 0.5 }}>
        Changing the template reconciles the project's milestones with the new template. Completed and in-progress
        work, completion dates, hours, owners, comments and history are kept. You see every change before anything
        is saved.
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
        disabled={templatesQuery.isLoading}
        onChange={(event) => {
          setSelectedTemplateId(event.target.value);
          resetDecisions();
        }}
        slotProps={{ inputLabel: { shrink: true } }}
      >
        <MenuItem value="">Select template</MenuItem>
        {templateOptions.map((template) => (
          <MenuItem key={template.id} value={template.id}>
            {template.name}
            {template.is_default ? ' (Default)' : ''}
            {template.is_customer_specific ? ` (${template.customer_name ?? 'Customer'})` : ''}
            {template.id === currentTemplateId ? ' (current)' : ''}
          </MenuItem>
        ))}
      </TextField>
    </>
  );

  const renderPreview = () => {
    if (previewQuery.isError && !preview) {
      return <Alert severity="error">{getErrorMessage(previewQuery.error)}</Alert>;
    }
    if (!preview) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress size={28} />
        </Box>
      );
    }
    return (
      <>
        {previewQuery.isError ? <Alert severity="error">{getErrorMessage(previewQuery.error)}</Alert> : null}
        <Typography variant="body2" color="text.secondary">
          {preview.previous_template
            ? `${preview.previous_template.name} v${preview.previous_template.version}`
            : 'No template'}{' '}
          → <strong>{preview.new_template.name}</strong> v{preview.new_template.version}
          {previewQuery.isFetching ? ' · updating…' : ''}
        </Typography>
        <TemplateReconciliationPreviewView
          preview={preview}
          disabled={busy}
          applyTemplateHours={applyTemplateHours}
          scheduleNew={scheduleNew}
          onTemplateDecision={(d) => setTemplateDecisions((prev) => ({ ...prev, [d.template_milestone_id]: d }))}
          onExistingDecision={(d) => setExistingDecisions((prev) => ({ ...prev, [d.milestone_id]: d }))}
          onApplyTemplateHours={setApplyTemplateHours}
          onScheduleNew={setScheduleNew}
        />
      </>
    );
  };

  const renderConfirm = () => {
    if (!preview) return null;
    const c = preview.counts;
    const lines = [
      `${c.add} new milestone(s) will be added and linked to ${preview.new_template.name}.`,
      `${c.match} existing milestone(s) will be linked to their template milestone.`,
      `${c.retain} existing milestone(s) stay active as they are.`,
    ];
    if (c.merge) lines.push(`${c.merge} milestone(s) will be merged into a surviving milestone.`);
    if (c.supersede) lines.push(`${c.supersede} milestone(s) will be marked superseded.`);
    if (c.archive) lines.push(`${c.archive} milestone(s) will be archived.`);
    lines.push('Nothing is deleted. Completion records, hours and history are not rewritten.');
    return (
      <>
        <List dense disablePadding>
          {lines.map((line) => (
            <ListItem key={line} disableGutters sx={{ py: 0 }}>
              <ListItemText primary={line} slotProps={{ primary: { variant: 'body2' } }} />
            </ListItem>
          ))}
        </List>
        {preview.warnings.map((w) => (
          <Alert key={w} severity="warning" sx={{ py: 0.25 }}>
            {w}
          </Alert>
        ))}
        <TextField
          size="small"
          fullWidth
          multiline
          minRows={2}
          label="Reason for the change (recorded in the audit history)"
          value={reason}
          onChange={(e) => setReason(e.target.value.slice(0, 1000))}
        />
        {preview.requires_estimate_acknowledgement ? (
          <FormControlLabel
            control={<Checkbox size="small" checked={ackEstimate} onChange={(e) => setAckEstimate(e.target.checked)} />}
            label={
              <Typography variant="body2">
                I accept that planned hours change from {Number(preview.planned_hours.before).toFixed(1)} h to{' '}
                {Number(preview.planned_hours.after).toFixed(1)} h.
              </Typography>
            }
          />
        ) : null}
        <FormControlLabel
          control={<Checkbox size="small" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} />}
          label={<Typography variant="body2">I have reviewed this preview and want to apply it.</Typography>}
        />
      </>
    );
  };

  const renderHistory = () => {
    if (historyQuery.isLoading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress size={28} />
        </Box>
      );
    }
    if (historyQuery.isError) return <Alert severity="error">{getErrorMessage(historyQuery.error)}</Alert>;
    const rows = historyQuery.data ?? [];
    if (!rows.length) {
      return (
        <Typography variant="body2" color="text.secondary">
          No template changes have been recorded for this project.
        </Typography>
      );
    }
    return (
      <Stack spacing={1}>
        {rows.map((r) => (
          <Box key={r.id} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.25 }}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
              <Typography variant="body2" sx={{ flex: 1, fontWeight: 600 }}>
                {r.previous_template ? `${r.previous_template.name} v${r.previous_template.version}` : 'No template'} →{' '}
                {r.new_template.name} v{r.new_template.version}
              </Typography>
              <Chip size="small" color={r.status === 'applied' ? 'success' : 'error'} label={r.status} />
            </Stack>
            <Typography variant="caption" color="text.secondary" component="div">
              {new Date(r.confirmed_at).toLocaleString()} · {r.confirmed_by_name ?? 'Unknown user'} · {r.counts.add} added,{' '}
              {r.counts.match} matched, {r.counts.retain} kept, {r.counts.merge} merged, {r.counts.supersede} superseded,{' '}
              {r.counts.archive} archived
            </Typography>
            {r.reason ? (
              <Typography variant="caption" component="div">
                Reason: {r.reason}
              </Typography>
            ) : null}
            {r.error_message ? (
              <Typography variant="caption" color="error" component="div">
                Not applied: {r.error_message}
              </Typography>
            ) : null}
          </Box>
        ))}
      </Stack>
    );
  };

  const title = !canChangeTemplate
    ? 'Template Locked'
    : step === 'confirm'
      ? 'Confirm Template Change'
      : 'Change Project Template';

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="md" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <Tabs value={tab} onChange={(_e, value: 'change' | 'history') => setTab(value)} sx={{ px: 3 }}>
        <Tab value="change" label="Change template" />
        <Tab value="history" label="History" />
      </Tabs>
      <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {tab === 'history' ? (
          renderHistory()
        ) : !canChangeTemplate ? (
          <Alert severity="info">{blockedReason ?? 'The template cannot be changed on this project.'}</Alert>
        ) : (
          <>
            {applyError ? <Alert severity="error">{applyError}</Alert> : null}
            {step === 'select' ? renderSelect() : step === 'preview' ? renderPreview() : renderConfirm()}
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <ProsohmButton buttonVariant="outlined" onClick={onClose} disabled={applying}>
          {canChangeTemplate && tab === 'change' ? 'Cancel' : 'Close'}
        </ProsohmButton>
        {canChangeTemplate && tab === 'change' && step !== 'select' ? (
          <ProsohmButton
            buttonVariant="secondary"
            disabled={applying}
            onClick={() => setStep(step === 'confirm' ? 'preview' : 'select')}
          >
            Back
          </ProsohmButton>
        ) : null}
        {canChangeTemplate && tab === 'change' && step === 'select' ? (
          <ProsohmButton
            buttonVariant="primary"
            disabled={!selectedTemplateId}
            loading={templatesQuery.isLoading}
            onClick={() => {
              setApplyError(null);
              setStep('preview');
            }}
          >
            Preview changes
          </ProsohmButton>
        ) : null}
        {canChangeTemplate && tab === 'change' && step === 'preview' ? (
          <ProsohmButton buttonVariant="primary" disabled={!preview || blocked || busy} onClick={goToConfirm}>
            Continue
          </ProsohmButton>
        ) : null}
        {canChangeTemplate && tab === 'change' && step === 'confirm' ? (
          <ProsohmButton
            buttonVariant={preview?.consequential ? 'danger' : 'primary'}
            disabled={!confirmReady}
            loading={applying}
            onClick={() => void handleApply()}
          >
            Apply changes
          </ProsohmButton>
        ) : null}
      </DialogActions>
    </Dialog>
  );
}
