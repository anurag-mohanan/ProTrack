import { Fragment, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  Link,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import KeyboardArrowDownRoundedIcon from '@mui/icons-material/KeyboardArrowDownRounded';
import KeyboardArrowUpRoundedIcon from '@mui/icons-material/KeyboardArrowUpRounded';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import { Link as RouterLink } from 'react-router-dom';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import {
  acknowledgeControlTowerFinding,
  controlTowerQueryKeys,
  convertControlTowerFinding,
  evaluateControlTower,
  fetchControlTower,
  fetchControlTowerFinding,
  triageControlTowerFinding,
} from '../../api/controlTower';
import { useToast } from '../../context/ToastContext';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import type {
  ControlTowerParams,
  ControlTowerResponse,
  CtCategory,
  CtDeferredRule,
  CtFinding,
  CtFindingEvent,
  CtFindingStatus,
  CtOption,
  CtRule,
  CtSeverity,
  CtState,
  CtTriageAction,
  CtTriageFilter,
  CtView,
} from '../../types/ControlTower';
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, ensureArray } from '../../types/pagination';
import { formatDate, formatDateTime } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { KpiCard, SectionTitle } from './ReportKpi';

const SEVERITY_META: Record<CtSeverity, { label: string; color: 'error' | 'warning' | 'info' | 'default' }> = {
  critical: { label: 'Critical', color: 'error' },
  high: { label: 'High', color: 'warning' },
  medium: { label: 'Medium', color: 'info' },
  info: { label: 'Informational', color: 'default' },
};

const CATEGORY_LABELS: Record<CtCategory, string> = {
  schedule: 'Milestone schedule',
  effort: 'Effort vs estimate',
  delivery: 'Project delivery',
  data_quality: 'Data quality',
  capability: 'Skills capability',
  resource: 'Resource capacity',
};

const TRIAGE_LABELS: Record<CtTriageFilter, string> = {
  untriaged: 'Not triaged',
  investigating: 'Investigating',
  dismissed: 'Dismissed',
};

const STATUS_LABELS: Record<CtFindingStatus, string> = {
  active: 'Active',
  not_assessable: 'Not assessable',
  resolved: 'Resolved',
};

const STATE_SEVERITY: Record<CtState, 'success' | 'info' | 'warning' | 'error'> = {
  ok: 'success',
  running: 'info',
  stale: 'warning',
  never_evaluated: 'warning',
  last_run_failed: 'error',
};

const EVENT_LABELS: Record<string, string> = {
  opened: 'Detected',
  reopened: 'Detected again (recurrence)',
  severity_changed: 'Severity changed',
  not_assessable: 'Became not assessable',
  reassessed: 'Assessable again',
  resolved: 'Resolved',
  acknowledged: 'Acknowledged',
  investigating: 'Marked as investigating',
  dismissed: 'Dismissed',
  triage_cleared: 'Triage cleared',
  converted: 'Recorded as a recommendation',
};

/** Backend timestamps are UTC without an offset. */
function utc(value: string | null | undefined): string {
  if (!value) return '—';
  const iso = /[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`;
  return formatDateTime(iso) || '—';
}

function projectLabel(finding: CtFinding): string {
  return finding.project.code ?? finding.project.tool_number ?? '—';
}

function FindingDetailRow({
  finding,
  canAcknowledge,
  colSpan,
}: {
  finding: CtFinding;
  canAcknowledge: boolean;
  colSpan: number;
}) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [note, setNote] = useState('');
  const detailQuery = useQuery({
    queryKey: controlTowerQueryKeys.finding(finding.id),
    queryFn: () => fetchControlTowerFinding(finding.id),
  });
  const ackMutation = useMutation({
    mutationFn: () => acknowledgeControlTowerFinding(finding.id, note),
    onSuccess: () => {
      showSuccess('Finding acknowledged');
      setNote('');
      void queryClient.invalidateQueries({ queryKey: controlTowerQueryKeys.all });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });
  const [triageNote, setTriageNote] = useState('');
  const triageMutation = useMutation({
    mutationFn: (action: CtTriageAction) => triageControlTowerFinding(finding.id, action, triageNote),
    onSuccess: (_, action) => {
      showSuccess(action === 'dismiss' ? 'Finding dismissed' : action === 'investigate' ? 'Marked as investigating' : 'Triage cleared');
      setTriageNote('');
      void queryClient.invalidateQueries({ queryKey: controlTowerQueryKeys.all });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });
  const convertMutation = useMutation({
    mutationFn: () => convertControlTowerFinding(finding.id, triageNote),
    onSuccess: () => {
      showSuccess('Recorded as a recommendation for review');
      setTriageNote('');
      void queryClient.invalidateQueries({ queryKey: controlTowerQueryKeys.all });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });
  const canAck = canAcknowledge && finding.status !== 'resolved' && !finding.acknowledged_at;
  const canTriage = canAcknowledge && finding.status !== 'resolved';
  const busy = triageMutation.isPending || convertMutation.isPending;
  return (
    <TableRow>
      <TableCell colSpan={colSpan} sx={{ bgcolor: 'action.hover', py: 2 }}>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '3fr 2fr' } }}>
          <Stack spacing={1.5}>
            {finding.source === 'predictive' ? (
              <Alert severity="info" variant="outlined">
                Forecast, not an actual: based on comparable completed work. No dates, estimates or assignments have
                been changed.
              </Alert>
            ) : null}
            <Typography variant="body2">{finding.explanation}</Typography>
            {finding.not_assessable_reason ? (
              <Alert severity="warning" variant="outlined">
                Not assessable: {finding.not_assessable_reason} The condition is not known to be fixed, so the
                finding stays open.
              </Alert>
            ) : null}
            {finding.resolution_note ? (
              <Alert severity="success" variant="outlined">
                Resolved {utc(finding.resolved_at)}: {finding.resolution_note}
              </Alert>
            ) : null}
            {finding.evidence.length ? (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Evidence (as of {formatDate(finding.evaluation_date)})
                </Typography>
                <Table size="small">
                  <TableBody>
                    {finding.evidence.map((line) => (
                      <TableRow key={`${line.label}-${line.value}`}>
                        <TableCell sx={{ width: '40%', color: 'text.secondary', borderBottom: 'none', py: 0.25 }}>
                          {line.label}
                        </TableCell>
                        <TableCell sx={{ borderBottom: 'none', py: 0.25 }}>{line.value}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            ) : null}
            <Box>
              <Typography variant="caption" color="text.secondary">
                Recommended action
              </Typography>
              <Typography variant="body2">{finding.recommended_action}</Typography>
            </Box>
          </Stack>
          <Stack spacing={1.5}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Rule
              </Typography>
              <Typography variant="body2">
                {finding.rule_title} <Typography component="span" variant="caption" color="text.secondary">({finding.rule_id})</Typography>
              </Typography>
            </Box>
            {finding.acknowledged_at ? (
              <Typography variant="body2">
                Acknowledged by {finding.acknowledged_by_name ?? 'unknown user'} on {utc(finding.acknowledged_at)}
                {finding.acknowledgement_note ? ` — “${finding.acknowledgement_note}”` : ''}
              </Typography>
            ) : null}
            {canAck ? (
              <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
                <TextField
                  size="small"
                  label="Acknowledgement note (optional)"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  slotProps={{ htmlInput: { maxLength: 500 } }}
                  fullWidth
                />
                <Button variant="outlined" onClick={() => ackMutation.mutate()} disabled={ackMutation.isPending}>
                  Acknowledge
                </Button>
              </Stack>
            ) : null}
            {finding.triage_status ? (
              <Typography variant="body2">
                {TRIAGE_LABELS[finding.triage_status]} — {finding.triaged_by_name ?? 'unknown user'} on {utc(finding.triaged_at)}
                {finding.triage_note ? ` — “${finding.triage_note}”` : ''}
              </Typography>
            ) : null}
            {finding.recommendation_id ? (
              <Typography variant="body2">Recorded as a recommendation for review.</Typography>
            ) : null}
            {canTriage ? (
              <Stack spacing={1}>
                <TextField
                  size="small"
                  label="Triage note (required to dismiss)"
                  value={triageNote}
                  onChange={(event) => setTriageNote(event.target.value)}
                  slotProps={{ htmlInput: { maxLength: 500 } }}
                  fullWidth
                />
                <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                  {finding.triage_status !== 'investigating' ? (
                    <Button size="small" variant="outlined" disabled={busy} onClick={() => triageMutation.mutate('investigate')}>
                      Investigate
                    </Button>
                  ) : null}
                  {finding.triage_status !== 'dismissed' ? (
                    <Button
                      size="small"
                      variant="outlined"
                      color="warning"
                      disabled={busy || !triageNote.trim()}
                      onClick={() => triageMutation.mutate('dismiss')}
                    >
                      Dismiss
                    </Button>
                  ) : null}
                  {finding.triage_status ? (
                    <Button size="small" disabled={busy} onClick={() => triageMutation.mutate('reopen')}>
                      Clear triage
                    </Button>
                  ) : null}
                  {!finding.recommendation_id ? (
                    <Button size="small" variant="contained" disabled={busy} onClick={() => convertMutation.mutate()}>
                      Create workflow action
                    </Button>
                  ) : null}
                </Stack>
              </Stack>
            ) : null}
            <Box>
              <Typography variant="caption" color="text.secondary">
                History
              </Typography>
              {detailQuery.isLoading ? (
                <Typography variant="body2" color="text.secondary">
                  Loading history…
                </Typography>
              ) : detailQuery.isError ? (
                <Typography variant="body2" color="error">
                  History could not be loaded: {getErrorMessage(detailQuery.error)}
                </Typography>
              ) : (
                <Stack spacing={0.5}>
                  {ensureArray<CtFindingEvent>(detailQuery.data?.events).map((event, index) => (
                    <Typography key={`${event.event}-${index}`} variant="body2">
                      <strong>{EVENT_LABELS[event.event] ?? event.event}</strong> · {utc(event.occurred_at)}
                      {event.user_name ? ` · ${event.user_name}` : ''}
                      {event.detail ? ` — ${event.detail}` : ''}
                    </Typography>
                  ))}
                </Stack>
              )}
            </Box>
          </Stack>
        </Box>
      </TableCell>
    </TableRow>
  );
}

function FindingsTable({
  data,
  view,
  onPage,
  onPageSize,
}: {
  data: ControlTowerResponse;
  view: CtView;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const findings = ensureArray<CtFinding>(data.findings);
  const colSpan = 7;
  return (
    <Paper>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox" />
              <TableCell>Severity</TableCell>
              <TableCell>Finding</TableCell>
              <TableCell>Project / milestone</TableCell>
              <TableCell>Owner</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>{view === 'resolved' ? 'Resolved' : 'First detected'}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {findings.map((finding) => {
              const open = expanded === finding.id;
              const severity = SEVERITY_META[finding.severity];
              return (
                <Fragment key={finding.id}>
                  <TableRow hover sx={{ '& > td': { verticalAlign: 'top' } }}>
                    <TableCell padding="checkbox">
                      <IconButton
                        size="small"
                        aria-label={open ? 'Hide details' : 'Show details'}
                        onClick={() => setExpanded(open ? null : finding.id)}
                      >
                        {open ? <KeyboardArrowUpRoundedIcon /> : <KeyboardArrowDownRoundedIcon />}
                      </IconButton>
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={severity.label} color={severity.color} />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {finding.title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {finding.category_label} · {finding.rule_title}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Link component={RouterLink} to={`/projects/${finding.project.id}`} underline="hover" sx={{ fontWeight: 600 }}>
                        {projectLabel(finding)}
                      </Link>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        {finding.project.part_description}
                      </Typography>
                      {finding.milestone ? (
                        <Link
                          component={RouterLink}
                          to={`/projects/${finding.project.id}?tab=milestones`}
                          underline="hover"
                          variant="caption"
                        >
                          Milestone: {finding.milestone.name}
                        </Link>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{finding.owner.name ?? 'Unassigned'}</Typography>
                      {finding.owner.basis_label ? (
                        <Typography variant="caption" color="text.secondary">
                          {finding.owner.basis_label}
                        </Typography>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5} useFlexGap sx={{ flexWrap: 'wrap' }}>
                        <Chip
                          size="small"
                          variant="outlined"
                          label={STATUS_LABELS[finding.status]}
                          color={finding.status === 'not_assessable' ? 'warning' : finding.status === 'resolved' ? 'success' : 'default'}
                        />
                        {finding.source === 'predictive' ? <Chip size="small" color="secondary" variant="outlined" label="Forecast" /> : null}
                        {finding.triage_status ? (
                          <Chip size="small" variant="outlined" label={TRIAGE_LABELS[finding.triage_status]} />
                        ) : null}
                        {finding.acknowledged_at ? <Chip size="small" variant="outlined" label="Acknowledged" /> : null}
                        {finding.is_recurrence ? <Chip size="small" variant="outlined" label="Recurred" /> : null}
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {utc(view === 'resolved' ? finding.resolved_at : finding.first_detected_at)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Evaluated {utc(finding.last_evaluated_at)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                  {open ? (
                    <FindingDetailRow finding={finding} canAcknowledge={data.can_acknowledge} colSpan={colSpan} />
                  ) : null}
                </Fragment>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={data.total}
        page={Math.max(0, data.page - 1)}
        rowsPerPage={data.page_size}
        rowsPerPageOptions={[...PAGE_SIZE_OPTIONS]}
        onPageChange={(_, page) => onPage(page + 1)}
        onRowsPerPageChange={(event) => onPageSize(Number(event.target.value))}
      />
    </Paper>
  );
}

function RulesSection({ data }: { data: ControlTowerResponse }) {
  return (
    <Accordion disableGutters variant="outlined">
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
        <Typography variant="subtitle2">Rules, severity and deferred alerts</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={1.5}>
          {ensureArray<CtRule>(data.rules).map((rule) => (
            <Box key={rule.rule_id}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {rule.title}{' '}
                <Typography component="span" variant="caption" color="text.secondary">
                  {CATEGORY_LABELS[rule.category]} · {rule.rule_id}
                </Typography>
              </Typography>
              <Typography variant="body2">{rule.condition}</Typography>
              <Typography variant="caption" color="text.secondary">
                Severity: {rule.severity_rule}
              </Typography>
            </Box>
          ))}
          <Typography variant="subtitle2" sx={{ pt: 1 }}>
            Not evaluated yet
          </Typography>
          {ensureArray<CtDeferredRule>(data.deferred_rules).map((rule) => (
            <Box key={rule.rule_id}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {rule.title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {rule.reason}
              </Typography>
            </Box>
          ))}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}

export function ControlTowerPanel() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [view, setView] = useState<CtView>('risks');
  const [severity, setSeverity] = useState<CtSeverity | ''>('');
  const [category, setCategory] = useState<CtCategory | ''>('');
  const [status, setStatus] = useState<CtFindingStatus | ''>('');
  const [projectId, setProjectId] = useState('');
  const [ownerId, setOwnerId] = useState('');
  const [triage, setTriage] = useState<CtTriageFilter | ''>('');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 300);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const params: ControlTowerParams = {
    view,
    severity: severity || undefined,
    category: category || undefined,
    status: status || undefined,
    project_id: projectId || undefined,
    owner_id: ownerId || undefined,
    search: search || undefined,
    triage: view === 'resolved' ? undefined : triage || undefined,
    page,
    page_size: pageSize,
  };

  const query = useQuery({
    queryKey: controlTowerQueryKeys.list(params),
    queryFn: () => fetchControlTower(params),
    placeholderData: keepPreviousData,
  });

  const evaluateMutation = useMutation({
    mutationFn: evaluateControlTower,
    onSuccess: (run) => {
      showSuccess(
        `Evaluated ${run.projects_evaluated} open project(s): ${run.findings_opened} new, ${run.findings_resolved} resolved, ${run.findings_open} open.`,
      );
      void queryClient.invalidateQueries({ queryKey: controlTowerQueryKeys.all });
    },
    onError: (error: unknown) => {
      showError(getErrorMessage(error));
      void queryClient.invalidateQueries({ queryKey: controlTowerQueryKeys.all });
    },
  });

  const resetPage = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setPage(1);
  };

  const changeView = (_: unknown, next: CtView | null) => {
    if (!next) return;
    setView(next);
    setStatus('');
    if (next === 'resolved') setTriage('');
    setCategory(next === 'data_quality' ? '' : category === 'data_quality' ? '' : category);
    setSeverity(next === 'data_quality' ? '' : severity);
    setPage(1);
  };

  const data = query.data;
  const filtersActive = Boolean(severity || category || status || projectId || ownerId || search || triage);

  if (query.isError && !data) {
    return (
      <ErrorState
        error={query.error}
        title="Unable to load the Control Tower. Risk status is unknown — this is not a clean result."
        onRetry={() => void query.refetch()}
      />
    );
  }
  if (!data) {
    return <LoadingState message="Loading Control Tower…" />;
  }

  const summary = data.summary;
  const severityCount = (key: CtSeverity) => summary.by_severity.find((row) => row.severity === key)?.count ?? 0;
  const lastRun = data.last_successful_run;
  const evaluationUnavailable = data.state === 'never_evaluated' || (data.state === 'last_run_failed' && !lastRun);

  return (
    <Stack spacing={2.5}>
      <Paper sx={{ p: 2 }}>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={2}
          sx={{ alignItems: { md: 'center' }, justifyContent: 'space-between' }}
        >
          <SectionTitle
            title="Engineering Control Tower"
            subtitle="Deterministic risk and data-quality findings for open projects, with forecast findings kept separate. Nothing here changes estimates, dates, assignments or statuses."
          />
          {data.can_evaluate ? (
            <Button
              variant="contained"
              startIcon={<RefreshRoundedIcon />}
              onClick={() => evaluateMutation.mutate()}
              disabled={evaluateMutation.isPending || data.state === 'running'}
            >
              {evaluateMutation.isPending ? 'Evaluating…' : 'Evaluate now'}
            </Button>
          ) : null}
        </Stack>
        <Alert severity={STATE_SEVERITY[data.state]} sx={{ mt: 1 }}>
          {data.state_message}
          {lastRun ? (
            <Typography variant="caption" sx={{ display: 'block' }}>
              Last successful evaluation: {utc(lastRun.finished_at ?? lastRun.started_at)} · {lastRun.projects_evaluated}{' '}
              open project(s) · rules v{lastRun.rules_version}
            </Typography>
          ) : null}
          {data.state === 'last_run_failed' && data.latest_run?.error ? (
            <Typography variant="caption" sx={{ display: 'block' }}>
              Failure: {data.latest_run.error}
            </Typography>
          ) : null}
        </Alert>
        {query.isError ? (
          <Alert severity="error" sx={{ mt: 1 }}>
            Refreshing failed: {getErrorMessage(query.error)}. Showing the previous result.
          </Alert>
        ) : null}
      </Paper>

      {evaluationUnavailable ? null : (
        <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(8, minmax(0, 1fr))' } }}>
          {(['critical', 'high', 'medium'] as CtSeverity[]).map((key) => (
            <KpiCard
              key={key}
              label={`${SEVERITY_META[key].label} risks`}
              value={String(severityCount(key))}
              selected={view === 'risks' && severity === key}
              onClick={() => {
                setView('risks');
                setStatus('');
                setSeverity(severity === key && view === 'risks' ? '' : key);
                setPage(1);
              }}
            />
          ))}
          <KpiCard label="Projects with risks" value={String(summary.projects_with_risks)} />
          <KpiCard
            label="Forecast findings"
            value={String(summary.open_predictive)}
            caption="Not certainties"
            selected={view === 'predictive'}
            onClick={() => changeView(null, 'predictive')}
          />
          <KpiCard
            label="Data-quality items"
            value={String(summary.open_data_quality)}
            caption={`${summary.projects_with_data_quality} project(s)`}
            selected={view === 'data_quality'}
            onClick={() => changeView(null, 'data_quality')}
          />
          <KpiCard
            label="Not assessable"
            value={String(summary.not_assessable)}
            caption="Open, inputs missing"
          />
          <KpiCard
            label="Resolved (30 days)"
            value={String(summary.resolved_last_30_days)}
            selected={view === 'resolved'}
            onClick={() => changeView(null, 'resolved')}
          />
        </Box>
      )}

      <Paper sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <ToggleButtonGroup size="small" exclusive value={view} onChange={changeView} aria-label="Finding view">
            <ToggleButton value="risks">Risks ({summary.open_risks})</ToggleButton>
            <ToggleButton value="predictive">Forecasts ({summary.open_predictive})</ToggleButton>
            <ToggleButton value="data_quality">Data quality ({summary.open_data_quality})</ToggleButton>
            <ToggleButton value="resolved">Resolved</ToggleButton>
          </ToggleButtonGroup>
          {view === 'predictive' ? (
            <Alert severity="info" variant="outlined">
              Forecast findings come from the latest stored predictions (made in the last 8 days) and are never shown
              for a condition that is already true — that appears under Risks instead. Projects without enough
              comparable history get no forecast and so no finding.
            </Alert>
          ) : null}
          <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: 'repeat(7, minmax(0, 1fr))' } }}>
            <TextField
              select
              size="small"
              label="Severity"
              value={severity}
              onChange={(event) => resetPage(setSeverity)(event.target.value as CtSeverity | '')}
              disabled={view === 'data_quality'}
            >
              <MenuItem value="">All</MenuItem>
              {(['critical', 'high', 'medium', 'info'] as CtSeverity[]).map((key) => (
                <MenuItem key={key} value={key}>
                  {SEVERITY_META[key].label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label="Category"
              value={category}
              onChange={(event) => resetPage(setCategory)(event.target.value as CtCategory | '')}
              disabled={view === 'data_quality'}
            >
              <MenuItem value="">All</MenuItem>
              {(Object.keys(CATEGORY_LABELS) as CtCategory[])
                .filter((key) => view === 'resolved' || key !== 'data_quality')
                .map((key) => (
                  <MenuItem key={key} value={key}>
                    {CATEGORY_LABELS[key]}
                  </MenuItem>
                ))}
            </TextField>
            <TextField
              select
              size="small"
              label="Status"
              value={status}
              onChange={(event) => resetPage(setStatus)(event.target.value as CtFindingStatus | '')}
              disabled={view === 'resolved'}
            >
              <MenuItem value="">All open</MenuItem>
              <MenuItem value="active">Active</MenuItem>
              <MenuItem value="not_assessable">Not assessable</MenuItem>
            </TextField>
            <TextField
              select
              size="small"
              label="Triage"
              value={triage}
              onChange={(event) => resetPage(setTriage)(event.target.value as CtTriageFilter | '')}
              disabled={view === 'resolved'}
              helperText={summary.dismissed && view !== 'resolved' ? `${summary.dismissed} dismissed hidden` : undefined}
            >
              <MenuItem value="">All except dismissed</MenuItem>
              {(Object.keys(TRIAGE_LABELS) as CtTriageFilter[]).map((key) => (
                <MenuItem key={key} value={key}>
                  {TRIAGE_LABELS[key]}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label="Project"
              value={projectId}
              onChange={(event) => resetPage(setProjectId)(event.target.value)}
            >
              <MenuItem value="">All projects</MenuItem>
              {ensureArray<CtOption>(data.project_options).map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label="Owner"
              value={ownerId}
              onChange={(event) => resetPage(setOwnerId)(event.target.value)}
            >
              <MenuItem value="">All owners</MenuItem>
              {ensureArray<CtOption>(data.owner_options).map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              label="Search project or finding"
              value={searchInput}
              onChange={(event) => {
                setSearchInput(event.target.value);
                setPage(1);
              }}
            />
          </Box>
          {filtersActive ? (
            <Box>
              <Button
                size="small"
                onClick={() => {
                  setSeverity('');
                  setCategory('');
                  setStatus('');
                  setProjectId('');
                  setOwnerId('');
                  setTriage('');
                  setSearchInput('');
                  setPage(1);
                }}
              >
                Clear filters
              </Button>
            </Box>
          ) : null}
        </Stack>
      </Paper>

      {data.total === 0 ? (
        <Alert severity={evaluationUnavailable ? 'warning' : 'info'}>
          {evaluationUnavailable ? data.state_message : data.empty_message}
        </Alert>
      ) : (
        <Box sx={{ opacity: query.isPlaceholderData ? 0.6 : 1, transition: 'opacity 120ms' }}>
          <FindingsTable data={data} view={view} onPage={setPage} onPageSize={resetPage(setPageSize)} />
        </Box>
      )}

      <RulesSection data={data} />
    </Stack>
  );
}
