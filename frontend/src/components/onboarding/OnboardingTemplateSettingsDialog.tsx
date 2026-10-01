import { useState } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ProsohmButton } from '../ui/ProsohmButton';
import { LoadingState } from '../common/LoadingState';
import { getErrorMessage } from '../../api/client';
import {
  onboardingApi,
  type OnboardingExecutionType,
  type OnboardingTemplateConfig,
  type OnboardingTemplateItem,
  type OnboardingTemplateItemConfig,
} from '../../api/onboarding';
import { useToast } from '../../context/ToastContext';
import { useTicketCatalog } from '../tickets/useTicketMeta';

const PRIORITIES = ['low', 'normal', 'high', 'urgent'] as const;

function toConfig(item: OnboardingTemplateItem): OnboardingTemplateItemConfig {
  return {
    execution_type: item.execution_type,
    responsibility: item.responsibility,
    owner_role: item.owner_role,
    priority: item.priority,
    due_offset_days: item.due_offset_days,
    evidence_required: item.evidence_required,
    confirm_by: item.confirm_by,
    reversible: item.reversible,
    mandatory: item.mandatory,
    blocks_completion: item.blocks_completion,
    ticket_category: item.ticket_category,
    ticket_subcategory: item.ticket_subcategory,
    completion_rule: item.completion_rule,
  };
}

function TemplateItemEditor({
  templateId,
  config,
  item,
  onClose,
}: {
  templateId: string;
  config: OnboardingTemplateConfig;
  item: OnboardingTemplateItem;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { showSuccess } = useToast();
  const catalog = useTicketCatalog();
  const [form, setForm] = useState<OnboardingTemplateItemConfig>(() => toConfig(item));
  const set = <K extends keyof OnboardingTemplateItemConfig>(key: K, value: OnboardingTemplateItemConfig[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  const save = useMutation({
    mutationFn: () => onboardingApi.updateTemplateItem(templateId, item.section_index, item.item_index, form),
    onSuccess: (data) => {
      queryClient.setQueryData(['onboarding', 'template-config', templateId], data);
      showSuccess('Task settings saved. They apply to onboarding checklists started from now on.');
      onClose();
    },
  });

  const isTicket = form.execution_type === 'TICKET_REQUIRED';
  const isOptional = form.execution_type === 'OPTIONAL';
  const ticketCategories = Object.keys(config.ticket_subcategories);
  const subcategories = form.ticket_category ? config.ticket_subcategories[form.ticket_category] ?? {} : {};

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle sx={{ pb: 0.5 }}>Task settings</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {item.text}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
          {item.section}
        </Typography>
        <Stack spacing={1.5}>
          <TextField
            select
            size="small"
            label="Execution type"
            value={form.execution_type}
            onChange={(event) => {
              const next = event.target.value as OnboardingExecutionType;
              setForm((current) => ({
                ...current,
                execution_type: next,
                ...(next === 'OPTIONAL' ? { mandatory: false, blocks_completion: false } : {}),
              }));
            }}
          >
            {Object.entries(config.execution_types).map(([value, label]) => (
              <MenuItem key={value} value={value} disabled={value === 'AUTOMATED' && !item.validation}>
                {label}
                {value === 'AUTOMATED' && !item.validation ? ' (needs a system check)' : ''}
              </MenuItem>
            ))}
          </TextField>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField
              select
              fullWidth
              size="small"
              label="Responsible team"
              value={form.responsibility}
              onChange={(event) => set('responsibility', event.target.value)}
            >
              {Object.entries(config.responsibilities).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              fullWidth
              size="small"
              label="Confirmed by"
              value={form.confirm_by}
              onChange={(event) => set('confirm_by', event.target.value)}
            >
              {Object.entries(config.confirm_by).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          {isTicket ? (
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <TextField
                select
                fullWidth
                size="small"
                label="Ticket category"
                value={form.ticket_category ?? ''}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    ticket_category: event.target.value || null,
                    ticket_subcategory: null,
                  }))
                }
                helperText="Leave blank to use the responsible team's queue"
              >
                <MenuItem value="">Team default</MenuItem>
                {ticketCategories.map((value) => (
                  <MenuItem key={value} value={value}>
                    {catalog.data?.categories[value] ?? value}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                fullWidth
                size="small"
                label="Subcategory"
                value={form.ticket_subcategory ?? ''}
                disabled={!form.ticket_category}
                onChange={(event) => set('ticket_subcategory', event.target.value || null)}
              >
                <MenuItem value="">None</MenuItem>
                {Object.entries(subcategories).map(([value, label]) => (
                  <MenuItem key={value} value={value}>
                    {label}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
          ) : null}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField
              select
              fullWidth
              size="small"
              label="Ticket priority"
              value={form.priority ?? ''}
              disabled={!isTicket}
              onChange={(event) =>
                set('priority', (event.target.value || null) as OnboardingTemplateItemConfig['priority'])
              }
            >
              <MenuItem value="">Default</MenuItem>
              {PRIORITIES.map((value) => (
                <MenuItem key={value} value={value}>
                  {catalog.data?.priorities[value] ?? value}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              fullWidth
              size="small"
              type="number"
              label="Due (days from joining)"
              value={form.due_offset_days ?? ''}
              onChange={(event) =>
                set('due_offset_days', event.target.value === '' ? null : Number(event.target.value))
              }
              helperText="Blank uses the team default"
            />
            {isTicket ? (
              <TextField
                select
                fullWidth
                size="small"
                label="Task completes when"
                value={form.completion_rule}
                onChange={(event) => set('completion_rule', event.target.value as 'resolved' | 'closed')}
              >
                {Object.entries(config.completion_rules).map(([value, label]) => (
                  <MenuItem key={value} value={value}>
                    {label}
                  </MenuItem>
                ))}
              </TextField>
            ) : null}
          </Stack>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', columnGap: 2 }}>
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={form.mandatory}
                  disabled={isOptional}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      mandatory: event.target.checked,
                      blocks_completion: event.target.checked ? current.blocks_completion : false,
                    }))
                  }
                />
              }
              label={<Typography variant="body2">Mandatory</Typography>}
            />
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={form.blocks_completion}
                  disabled={isOptional || !form.mandatory}
                  onChange={(event) => set('blocks_completion', event.target.checked)}
                />
              }
              label={<Typography variant="body2">Blocks onboarding completion</Typography>}
            />
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={form.evidence_required}
                  onChange={(event) => set('evidence_required', event.target.checked)}
                />
              }
              label={<Typography variant="body2">Evidence required</Typography>}
            />
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={form.reversible}
                  onChange={(event) => set('reversible', event.target.checked)}
                />
              }
              label={<Typography variant="body2">Can be reopened by the owner</Typography>}
            />
          </Box>
          <Typography variant="caption" color="text.secondary">
            Changes apply to checklists started after saving. Tasks already in progress keep the
            settings they started with.
          </Typography>
          {save.isError ? <Alert severity="error">{getErrorMessage(save.error)}</Alert> : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="secondary" onClick={onClose} disabled={save.isPending}>
          Cancel
        </ProsohmButton>
        <ProsohmButton buttonVariant="primary" onClick={() => save.mutate()} disabled={save.isPending}>
          Save
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}

export function OnboardingTemplateSettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const templatesQuery = useQuery({
    queryKey: ['onboarding', 'templates'],
    queryFn: onboardingApi.templates,
    enabled: open,
  });
  const [chosenId, setChosenId] = useState<string | null>(null);
  const templateId = chosenId ?? templatesQuery.data?.[0]?.id ?? null;
  const configQuery = useQuery({
    queryKey: ['onboarding', 'template-config', templateId],
    queryFn: () => onboardingApi.templateConfig(templateId!),
    enabled: open && Boolean(templateId),
  });
  const [editing, setEditing] = useState<OnboardingTemplateItem | null>(null);
  const catalog = useTicketCatalog();
  const config = configQuery.data;

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="lg">
      <DialogTitle sx={{ pb: 0.5 }}>Onboarding task settings</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Decide how each checklist task is carried out: completed on the checklist, through a
          ticket, by approval, by an external party, or automatically by a system check.
        </Typography>
        {(templatesQuery.data?.length ?? 0) > 1 ? (
          <TextField
            select
            size="small"
            label="Template"
            value={templateId ?? ''}
            onChange={(event) => setChosenId(event.target.value)}
            sx={{ mb: 1.5, minWidth: 260 }}
          >
            {(templatesQuery.data ?? []).map((row) => (
              <MenuItem key={row.id} value={row.id}>
                {row.name} (v{row.version})
              </MenuItem>
            ))}
          </TextField>
        ) : null}
        {templatesQuery.isError || configQuery.isError ? (
          <Alert severity="error">{getErrorMessage(templatesQuery.error ?? configQuery.error)}</Alert>
        ) : !config ? (
          <LoadingState message="Loading task settings…" />
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Task</TableCell>
                <TableCell>Execution</TableCell>
                <TableCell>Team</TableCell>
                <TableCell>Ticket</TableCell>
                <TableCell>Rules</TableCell>
                <TableCell align="right" />
              </TableRow>
            </TableHead>
            <TableBody>
              {config.items.map((item, index) => (
                <TableRow key={`${item.section_index}-${item.item_index}`} hover>
                  <TableCell sx={{ maxWidth: 340 }}>
                    {index === 0 || config.items[index - 1].section !== item.section ? (
                      <Typography variant="overline" color="text.secondary" sx={{ display: 'block', lineHeight: 1.6 }}>
                        {item.section}
                      </Typography>
                    ) : null}
                    <Typography variant="body2">{item.text}</Typography>
                  </TableCell>
                  <TableCell>
                    <Chip size="small" variant="outlined" label={item.execution_type_label} />
                  </TableCell>
                  <TableCell>{item.responsibility_label}</TableCell>
                  <TableCell>
                    {item.execution_type === 'TICKET_REQUIRED'
                      ? [
                          item.ticket_category
                            ? catalog.data?.categories[item.ticket_category] ?? item.ticket_category
                            : null,
                          item.ticket_subcategory
                            ? config.ticket_subcategories[item.ticket_category ?? '']?.[item.ticket_subcategory]
                            : null,
                        ]
                          .filter(Boolean)
                          .join(' · ') || 'Team queue'
                      : '—'}
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {[
                        item.mandatory ? 'Mandatory' : 'Optional',
                        item.blocks_completion ? 'blocks completion' : null,
                        item.evidence_required ? 'evidence' : null,
                        `confirmed by ${(config.confirm_by[item.confirm_by] ?? item.confirm_by).toLowerCase()}`,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <IconButton size="small" aria-label={`Edit settings for ${item.text}`} onClick={() => setEditing(item)}>
                      <EditOutlinedIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="secondary" onClick={onClose}>
          Close
        </ProsohmButton>
      </DialogActions>
      {editing && config && templateId ? (
        <TemplateItemEditor templateId={templateId} config={config} item={editing} onClose={() => setEditing(null)} />
      ) : null}
    </Dialog>
  );
}