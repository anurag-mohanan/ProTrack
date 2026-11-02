import { useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { EmptyState } from '../../components/common/EmptyState';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import {
  fetchAutomationExecutions,
  fetchAutomationRules,
  retryAutomationExecution,
  reviewAutomationExecution,
  runAutomationSweeps,
  setAutomationRuleEnabled,
  type AutomationExecution,
  type AutomationRule,
} from '../../api/automation';

const STATUS_COLORS: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  succeeded: 'success',
  skipped: 'default',
  failed: 'error',
  pending_review: 'warning',
  dismissed: 'default',
};

const KIND_LABELS: Record<string, string> = {
  event: 'On event',
  sweep: 'Scheduled sweep',
  external: 'Runs in its module',
};

function label(value: string | null | undefined): string {
  return value ? value.replace(/_/g, ' ') : '—';
}

function when(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : '—';
}

function RulesTab() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<AutomationRule | null>(null);
  const [details, setDetails] = useState<AutomationRule | null>(null);
  const [reason, setReason] = useState('');

  const rulesQuery = useQuery({ queryKey: ['automation', 'rules'], queryFn: fetchAutomationRules });

  const toggle = useMutation({
    mutationFn: (rule: AutomationRule) => setAutomationRuleEnabled(rule.key, !rule.is_enabled, reason.trim()),
    onSuccess: (rule) => {
      showSuccess(`${rule.name} ${rule.is_enabled ? 'enabled' : 'disabled'}`);
      setPending(null);
      setReason('');
      void queryClient.invalidateQueries({ queryKey: ['automation'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const sweeps = useMutation({
    mutationFn: () => runAutomationSweeps(),
    onSuccess: (summary) => {
      const keys = Object.keys(summary);
      if (!keys.length) {
        showSuccess('No scheduled rules are enabled.');
      } else {
        const created = keys.reduce((n, k) => n + summary[k].new, 0);
        const deduped = keys.reduce((n, k) => n + summary[k].deduplicated, 0);
        const failed = keys.reduce((n, k) => n + summary[k].failed, 0);
        showSuccess(`Sweeps ran: ${created} new, ${deduped} already handled, ${failed} failed.`);
      }
      void queryClient.invalidateQueries({ queryKey: ['automation'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  if (rulesQuery.isLoading) return <LoadingState message="Loading automation rules…" />;
  if (rulesQuery.isError) return <Alert severity="error">{getErrorMessage(rulesQuery.error)}</Alert>;
  const rules = rulesQuery.data ?? [];

  return (
    <ContentCard
      title="Rules"
      subtitle="Every rule is off until an administrator turns it on. Rules notify or recommend; they never approve, pay, assign or complete work."
      action={
        <ProsohmButton buttonVariant="outlined" loading={sweeps.isPending} onClick={() => sweeps.mutate()}>
          Run scheduled rules now
        </ProsohmButton>
      }
    >
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Rule</TableCell>
            <TableCell>Module</TableCell>
            <TableCell>Trigger</TableCell>
            <TableCell>Last run</TableCell>
            <TableCell>Failed</TableCell>
            <TableCell>Awaiting review</TableCell>
            <TableCell align="right">On</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rules.map((rule) => (
            <TableRow key={rule.key} hover>
              <TableCell sx={{ cursor: 'pointer' }} onClick={() => setDetails(rule)}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {rule.name}
                  {rule.consequential ? (
                    <Chip size="small" color="warning" variant="outlined" label="Recommendation" sx={{ ml: 1 }} />
                  ) : null}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {rule.description}
                </Typography>
              </TableCell>
              <TableCell>{rule.module}</TableCell>
              <TableCell>
                <Typography variant="body2">{KIND_LABELS[rule.kind]}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {rule.trigger}
                </Typography>
              </TableCell>
              <TableCell>
                {rule.executable ? (
                  <>
                    <Typography variant="body2">{when(rule.last_run_at)}</Typography>
                    {rule.last_status ? (
                      <Chip size="small" label={label(rule.last_status)} color={STATUS_COLORS[rule.last_status] ?? 'default'} />
                    ) : null}
                  </>
                ) : (
                  '—'
                )}
              </TableCell>
              <TableCell>{rule.executable ? rule.failed_count : '—'}</TableCell>
              <TableCell>{rule.executable ? rule.pending_review_count : '—'}</TableCell>
              <TableCell align="right">
                {rule.executable ? (
                  <Switch checked={rule.is_enabled} onChange={() => setPending(rule)} />
                ) : (
                  <Tooltip title={`Managed in ${rule.managed_by ?? 'its module'}`}>
                    <Chip size="small" variant="outlined" label="External" />
                  </Tooltip>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={Boolean(pending)} onClose={() => setPending(null)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {pending?.is_enabled ? 'Turn off' : 'Turn on'} “{pending?.name}”?
        </DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: 1 }}>
          <Typography variant="body2">{pending?.conditions}</Typography>
          <Typography variant="body2" color="text.secondary">
            {pending?.authorization}
          </Typography>
          <TextField
            size="small"
            label="Reason (recorded in the decision audit)"
            value={reason}
            onChange={(e) => setReason(e.target.value.slice(0, 500))}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setPending(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={toggle.isPending}
            onClick={() => pending && toggle.mutate(pending)}
          >
            {pending?.is_enabled ? 'Turn off' : 'Turn on'}
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(details)} onClose={() => setDetails(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{details?.name}</DialogTitle>
        <DialogContent>
          {details ? (
            <Stack spacing={1}>
              {(
                [
                  ['What it does', details.description],
                  ['Trigger', `${KIND_LABELS[details.kind]} · ${details.trigger}`],
                  ['Conditions', details.conditions],
                  ['Action', details.action],
                  ['Recipients', details.recipients],
                  ['Authorisation', details.authorization],
                  ['Managed in', details.managed_by ?? 'This automation engine'],
                  ['Last error', details.last_error ?? '—'],
                ] as const
              ).map(([title, value]) => (
                <Box key={title}>
                  <Typography variant="caption" color="text.secondary">
                    {title}
                  </Typography>
                  <Typography variant="body2">{value}</Typography>
                </Box>
              ))}
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setDetails(null)}>
            Close
          </ProsohmButton>
        </DialogActions>
      </Dialog>
    </ContentCard>
  );
}

function ExecutionsTab({ rules }: { rules: AutomationRule[] }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [ruleKey, setRuleKey] = useState('');
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<AutomationExecution | null>(null);
  const [reviewing, setReviewing] = useState<{ row: AutomationExecution; decision: 'acknowledge' | 'dismiss' } | null>(null);
  const [note, setNote] = useState('');

  const filters = { rule_key: ruleKey, status, search: search.trim(), page: page + 1, page_size: pageSize };
  const query = useQuery({
    queryKey: ['automation', 'executions', filters],
    queryFn: () => fetchAutomationExecutions(filters),
    placeholderData: keepPreviousData,
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['automation'] });
  const retry = useMutation({
    mutationFn: (id: string) => retryAutomationExecution(id),
    onSuccess: (row) => {
      if (row.status === 'failed') showError(`Retry failed: ${row.error_message ?? 'unknown error'}`);
      else showSuccess(`Retry ${label(row.status)}`);
      refresh();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });
  const review = useMutation({
    mutationFn: (args: { id: string; decision: 'acknowledge' | 'dismiss'; note: string }) =>
      reviewAutomationExecution(args.id, args.decision, args.note),
    onSuccess: () => {
      showSuccess('Review recorded');
      setReviewing(null);
      setNote('');
      refresh();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const rows = query.data?.items ?? [];

  return (
    <ContentCard title="Execution history" subtitle="One row per rule and target; repeated events and sweeps never act twice.">
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} sx={{ mb: 2 }}>
        <TextField select size="small" label="Rule" value={ruleKey} sx={{ minWidth: 220 }}
          onChange={(e) => { setRuleKey(e.target.value); setPage(0); }}>
          <MenuItem value="">All rules</MenuItem>
          {rules.filter((r) => r.executable).map((r) => (
            <MenuItem key={r.key} value={r.key}>{r.name}</MenuItem>
          ))}
        </TextField>
        <TextField select size="small" label="Status" value={status} sx={{ minWidth: 180 }}
          onChange={(e) => { setStatus(e.target.value); setPage(0); }}>
          <MenuItem value="">All</MenuItem>
          {Object.keys(STATUS_COLORS).map((s) => (
            <MenuItem key={s} value={s}>{label(s)}</MenuItem>
          ))}
        </TextField>
        <TextField size="small" label="Search" value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }} />
      </Stack>
      {query.isError ? <Alert severity="error">{getErrorMessage(query.error)}</Alert> : null}
      {!query.isLoading && rows.length === 0 ? (
        <EmptyState title="No executions" description="Enabled rules record their runs here." />
      ) : (
        <>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Started</TableCell>
                <TableCell>Rule</TableCell>
                <TableCell>Project</TableCell>
                <TableCell>Outcome</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Attempts</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id} hover>
                  <TableCell>{when(row.started_at)}</TableCell>
                  <TableCell sx={{ cursor: 'pointer' }} onClick={() => setSelected(row)}>
                    <Typography variant="body2">{row.rule_name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.trigger_event} · {row.actor_type === 'user' ? row.actor_name ?? 'user' : 'system'}
                    </Typography>
                  </TableCell>
                  <TableCell>{row.project_label ?? '—'}</TableCell>
                  <TableCell>
                    <Typography variant="body2">{row.summary ?? '—'}</Typography>
                    {row.error_message ? (
                      <Typography variant="caption" color="error">{row.error_message}</Typography>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={label(row.status)} color={STATUS_COLORS[row.status] ?? 'default'} />
                  </TableCell>
                  <TableCell>{row.attempts}</TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
                      {row.status === 'failed' ? (
                        <ProsohmButton size="small" buttonVariant="outlined"
                          loading={retry.isPending && retry.variables === row.id}
                          onClick={() => retry.mutate(row.id)}>
                          Retry
                        </ProsohmButton>
                      ) : null}
                      {row.status === 'pending_review' ? (
                        <>
                          <ProsohmButton size="small" buttonVariant="primary"
                            onClick={() => setReviewing({ row, decision: 'acknowledge' })}>
                            Acknowledge
                          </ProsohmButton>
                          <ProsohmButton size="small" buttonVariant="outlined"
                            onClick={() => setReviewing({ row, decision: 'dismiss' })}>
                            Dismiss
                          </ProsohmButton>
                        </>
                      ) : null}
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={query.data?.total ?? 0}
            page={page}
            rowsPerPage={pageSize}
            rowsPerPageOptions={[25, 50, 100]}
            onPageChange={(_e, next) => setPage(next)}
            onRowsPerPageChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}
          />
        </>
      )}

      <Dialog open={Boolean(reviewing)} onClose={() => setReviewing(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{reviewing?.decision === 'acknowledge' ? 'Acknowledge recommendation' : 'Dismiss recommendation'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: 1 }}>
          <Typography variant="body2">{reviewing?.row.summary}</Typography>
          <Typography variant="caption" color="text.secondary">
            Recording a review does not change the project. Act on the recommendation from the project itself.
          </Typography>
          <TextField size="small" multiline minRows={2} label="Note" value={note}
            onChange={(e) => setNote(e.target.value.slice(0, 1000))} />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setReviewing(null)}>Cancel</ProsohmButton>
          <ProsohmButton buttonVariant="primary" loading={review.isPending}
            onClick={() => reviewing && review.mutate({ id: reviewing.row.id, decision: reviewing.decision, note })}>
            Save
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{selected?.rule_name}</DialogTitle>
        <DialogContent>
          {selected ? (
            <Stack spacing={1}>
              <Typography variant="body2">{selected.summary}</Typography>
              <Typography variant="caption" color="text.secondary">
                Target: {selected.target_type} {selected.target_id ?? ''} · Started {when(selected.started_at)} · Finished{' '}
                {when(selected.finished_at)}
              </Typography>
              {selected.reviewed_at ? (
                <Typography variant="caption">
                  Reviewed by {selected.reviewed_by_name} on {when(selected.reviewed_at)}
                  {selected.review_note ? `: ${selected.review_note}` : ''}
                </Typography>
              ) : null}
              {selected.result ? (
                <Box component="pre" sx={{ m: 0, p: 1, bgcolor: 'action.hover', borderRadius: 1, fontSize: 12, overflow: 'auto' }}>
                  {JSON.stringify(selected.result, null, 2)}
                </Box>
              ) : null}
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setSelected(null)}>Close</ProsohmButton>
        </DialogActions>
      </Dialog>
    </ContentCard>
  );
}

export default function AutomationPage() {
  const [tab, setTab] = useState<'rules' | 'executions'>('rules');
  const rulesQuery = useQuery({ queryKey: ['automation', 'rules'], queryFn: fetchAutomationRules });
  return (
    <Box>
      <PageHeader
        title="Workflow Automation"
        subtitle="Rules, their on/off switches, execution history, failures and recommendations awaiting review"
      />
      <Tabs value={tab} onChange={(_e, value: 'rules' | 'executions') => setTab(value)} sx={{ mb: 2 }}>
        <Tab value="rules" label="Rules" />
        <Tab value="executions" label="History & review" />
      </Tabs>
      {tab === 'rules' ? <RulesTab /> : <ExecutionsTab rules={rulesQuery.data ?? []} />}
    </Box>
  );
}
