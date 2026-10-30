import { useState, type ReactNode } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Chip,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  fetchCapacityForecast,
  fetchEngineeringForecast,
  fetchFinanceForecast,
  fetchForecastCatalog,
  forecastQueryKeys,
} from '../../api/forecasting';
import type {
  FcCapacity,
  FcCapacityCell,
  FcCatalog,
  FcEngineering,
  FcFinance,
  FcGranularity,
  FcHorizonParams,
  FcMetadata,
  FcStatus,
  FcValueKind,
} from '../../types/Forecasting';
import { formatDate, formatDateTime, formatNumber } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { KpiCard, SectionTitle } from './ReportKpi';

type View = 'engineering' | 'capacity' | 'finance';

const STATUS_META: Record<FcStatus, { label: string; color: 'success' | 'warning' | 'default' }> = {
  available: { label: 'Available', color: 'success' },
  preliminary: { label: 'Preliminary', color: 'warning' },
  unavailable: { label: 'Unavailable', color: 'default' },
};

const KIND_META: Record<FcValueKind, { label: string; color: 'default' | 'info' | 'secondary' | 'primary' | 'warning' }> = {
  actual: { label: 'Actual', color: 'default' },
  approved_plan: { label: 'Plan', color: 'info' },
  forecast: { label: 'Forecast', color: 'secondary' },
  scenario: { label: 'Scenario', color: 'warning' },
  commitment: { label: 'Commitment', color: 'primary' },
};

const BILLING_DATE_LABELS = {
  ready_to_invoice: 'Ready to invoice',
  dated_by_target: 'Dated by project target',
  undated: 'No date',
} as const;

const TIMING_LABELS = { scheduled: 'Due', overdue: 'Overdue', no_due_date: 'No due date' } as const;

function utc(value: string): string {
  const iso = /[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`;
  return formatDateTime(iso) || '—';
}

function hours(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return `${formatNumber(value, 1)} h`;
}

function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return formatNumber(value, 2);
}

function date(value: string | null | undefined): string {
  return value ? formatDate(value) : '—';
}

function StatusChip({ status }: { status: FcStatus }) {
  const meta = STATUS_META[status];
  return <Chip size="small" label={meta.label} color={meta.color} variant={status === 'unavailable' ? 'outlined' : 'filled'} />;
}

function KindHeader({ kind, children }: { kind: FcValueKind; children: ReactNode }) {
  const meta = KIND_META[kind];
  return (
    <Stack spacing={0.5} sx={{ alignItems: 'flex-end' }}>
      <Chip size="small" label={meta.label} color={meta.color} variant="outlined" sx={{ height: 18, fontSize: 11 }} />
      <span>{children}</span>
    </Stack>
  );
}

function MetadataPanel({ metadata, title }: { metadata: FcMetadata; title: string }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ alignItems: { md: 'center' }, justifyContent: 'space-between' }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            {title}
          </Typography>
          <StatusChip status={metadata.status} />
          <Chip size="small" variant="outlined" label={`Method ${metadata.method_version}`} />
        </Stack>
        <Typography variant="caption" color="text.secondary">
          As of {date(metadata.as_of)}
          {metadata.period_start ? ` · ${date(metadata.period_start)} – ${date(metadata.period_end)}` : ''} · generated{' '}
          {utc(metadata.generated_at)}
        </Typography>
      </Stack>
      {metadata.status_reason ? (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {metadata.status_reason}
        </Typography>
      ) : null}
      <Accordion disableGutters elevation={0} sx={{ mt: 1, '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />} sx={{ px: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            Sources, assumptions and limitations
          </Typography>
        </AccordionSummary>
        <AccordionDetails sx={{ px: 0 }}>
          {(
            [
              ['Sources', metadata.sources],
              ['Assumptions', metadata.assumptions],
              ['Limitations', metadata.limitations],
            ] as const
          ).map(([label, items]) => (
            <Box key={label} sx={{ mb: 1 }}>
              <Typography variant="caption" sx={{ fontWeight: 700 }}>
                {label}
              </Typography>
              <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                {items.map((item) => (
                  <li key={item}>
                    <Typography variant="body2">{item}</Typography>
                  </li>
                ))}
              </Box>
            </Box>
          ))}
          <Typography variant="caption" color="text.secondary">
            {metadata.confidence_note}
          </Typography>
        </AccordionDetails>
      </Accordion>
    </Paper>
  );
}

function HorizonControls({ value, onChange }: { value: FcHorizonParams; onChange: (next: FcHorizonParams) => void }) {
  return (
    <Stack direction="row" spacing={1.5} sx={{ mb: 2, alignItems: 'center' }}>
      <ToggleButtonGroup
        size="small"
        exclusive
        value={value.granularity}
        onChange={(_, next: FcGranularity | null) => next && onChange({ ...value, granularity: next })}
      >
        <ToggleButton value="week">Weekly</ToggleButton>
        <ToggleButton value="month">Monthly</ToggleButton>
      </ToggleButtonGroup>
      <TextField
        select
        size="small"
        label="Periods"
        value={value.periods}
        onChange={(event) => onChange({ ...value, periods: Number(event.target.value) })}
        sx={{ width: 110 }}
      >
        {[4, 6, 8, 12, 26].map((n) => (
          <MenuItem key={n} value={n}>
            {n}
          </MenuItem>
        ))}
      </TextField>
    </Stack>
  );
}

function EngineeringSection({ data }: { data: FcEngineering }) {
  const { summary, history, backtest } = data;
  return (
    <Stack spacing={2}>
      <MetadataPanel metadata={data.metadata} title="Remaining effort" />
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' } }}>
        <KpiCard label="Open projects in scope" value={String(summary.projects)} />
        <KpiCard
          label="Forecastable"
          value={`${summary.available + summary.preliminary}`}
          caption={`${summary.available} available · ${summary.preliminary} preliminary · ${summary.unavailable} unavailable`}
        />
        <KpiCard
          label="Approved remaining (plan)"
          value={hours(summary.approved_remaining_hours)}
          caption="Per project, overruns count as zero"
        />
        <KpiCard
          label="Forecast remaining"
          value={summary.forecast_remaining_hours === null ? 'Unavailable' : hours(summary.forecast_remaining_hours)}
          caption={summary.forecast_remaining_note}
        />
      </Box>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <SectionTitle title="History and backtest" subtitle={history.basis} />
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={3}>
          <Box>
            <Typography variant="body2">
              Sample: <strong>{history.sample_size}</strong> of {history.minimum_sample} needed · factor{' '}
              <strong>{history.factor ?? '—'}</strong> <StatusChip status={history.factor_status} />
            </Typography>
            {history.factor_reason ? (
              <Typography variant="caption" color="text.secondary">
                {history.factor_reason}
              </Typography>
            ) : null}
          </Box>
          <Box>
            {backtest.status === 'evaluated' ? (
              <Typography variant="body2">
                Backtest on {backtest.evaluated_count} of {backtest.candidate_count} projects: mean absolute error{' '}
                <strong>{hours(backtest.mean_absolute_error_hours)}</strong> ({backtest.mean_absolute_percentage_error}%), bias{' '}
                {hours(backtest.mean_signed_error_hours)}; plan-as-is baseline {hours(backtest.naive_mean_absolute_error_hours)} (
                {backtest.naive_mean_absolute_percentage_error}%).
              </Typography>
            ) : (
              <Typography variant="body2">Backtest not possible: {backtest.reason}</Typography>
            )}
            <Typography variant="caption" color="text.secondary">
              {backtest.method}
            </Typography>
          </Box>
        </Stack>
      </Paper>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Project</TableCell>
              <TableCell>Forecast status</TableCell>
              <TableCell align="right">Quoted</TableCell>
              <TableCell align="right"><KindHeader kind="approved_plan">Approved estimate</KindHeader></TableCell>
              <TableCell align="right"><KindHeader kind="actual">Actual</KindHeader></TableCell>
              <TableCell align="right"><KindHeader kind="approved_plan">Approved remaining</KindHeader></TableCell>
              <TableCell align="right"><KindHeader kind="forecast">Remaining</KindHeader></TableCell>
              <TableCell align="right"><KindHeader kind="forecast">At completion</KindHeader></TableCell>
              <TableCell><KindHeader kind="commitment">Original / current target</KindHeader></TableCell>
              <TableCell>Completion forecast</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.projects.length === 0 ? (
              <TableRow>
                <TableCell colSpan={10}>No open projects in your scope.</TableCell>
              </TableRow>
            ) : null}
            {data.projects.map((row) => (
              <TableRow key={row.project_id} hover>
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {row.code ?? row.tool_number ?? '—'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {row.tool_number} · {row.execution_status.replaceAll('_', ' ')}
                  </Typography>
                </TableCell>
                <TableCell sx={{ maxWidth: 260 }}>
                  <StatusChip status={row.forecast_status} />
                  {row.forecast_reason ? (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      {row.forecast_reason}
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell align="right">{hours(row.quoted_hours)}</TableCell>
                <TableCell align="right">{hours(row.approved_current_estimate_hours)}</TableCell>
                <TableCell align="right">
                  <Tooltip
                    title={`Includes ${formatNumber(row.actual_unapproved_hours, 1)} h unapproved and ${formatNumber(row.actual_rejected_hours, 1)} h rejected`}
                  >
                    <span>{row.actual_status === 'missing' ? 'Missing' : hours(row.actual_hours)}</span>
                  </Tooltip>
                </TableCell>
                <TableCell align="right">{hours(row.approved_remaining_hours)}</TableCell>
                <TableCell align="right">{hours(row.forecast_remaining_hours)}</TableCell>
                <TableCell align="right">{hours(row.forecast_at_completion_hours)}</TableCell>
                <TableCell>
                  <Typography variant="body2">
                    {row.original_commitment_date ? date(row.original_commitment_date) : 'No baseline'} / {date(row.current_target_date)}
                  </Typography>
                  {row.provisional_schedule_date ? (
                    <Typography variant="caption" color="text.secondary">
                      Provisional schedule (capacity-unaware): {date(row.provisional_schedule_date)}
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell>
                  <Tooltip title={row.completion_forecast_reason}>
                    <span>
                      <StatusChip status={row.completion_forecast_status} />
                    </span>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}

function CapacityRow({ label, cells, total }: { label: ReactNode; cells: FcCapacityCell[]; total: FcCapacityCell }) {
  return (
    <TableRow hover>
      <TableCell>{label}</TableCell>
      {cells.map((cell) => (
        <TableCell key={cell.period_key} align="right">
          <Tooltip
            title={`Scheduled ${hours(cell.scheduled_hours)} − holidays ${hours(cell.holiday_hours)} − outside employment ${hours(cell.outside_employment_hours)} − unavailable status ${hours(cell.status_unavailable_hours)}; allocatable ${hours(cell.allocatable_hours)}`}
          >
            <span>{formatNumber(cell.available_hours, 0)}</span>
          </Tooltip>
        </TableCell>
      ))}
      <TableCell align="right" sx={{ fontWeight: 700 }}>
        {formatNumber(total.available_hours, 0)}
      </TableCell>
    </TableRow>
  );
}

function CapacitySection({ data }: { data: FcCapacity }) {
  return (
    <Stack spacing={2}>
      <MetadataPanel metadata={data.metadata} title="Capacity supply" />
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' } }}>
        <KpiCard label="People" value={String(data.people.length)} />
        <KpiCard label="Scheduled hours" value={hours(data.grand_total.scheduled_hours)} />
        <KpiCard label="Available hours (forecast)" value={hours(data.grand_total.available_hours)} caption="Before planned leave and non-project work" />
        <KpiCard label="Allocatable hours (forecast)" value={hours(data.grand_total.allocatable_hours)} caption="Available × max allocation %" />
      </Box>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Available hours by team</TableCell>
              {data.periods.map((p) => (
                <TableCell key={p.key} align="right">
                  {p.label}
                </TableCell>
              ))}
              <TableCell align="right">Total</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.teams.map((team) => (
              <CapacityRow key={team.team_id ?? 'none'} label={`${team.team_name} (${team.headcount})`} cells={team.periods} total={team.total} />
            ))}
            <CapacityRow label={<strong>All teams</strong>} cells={data.totals} total={data.grand_total} />
          </TableBody>
        </Table>
      </TableContainer>
      <Accordion disableGutters variant="outlined">
        <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            Per person ({data.people.length})
          </Typography>
        </AccordionSummary>
        <AccordionDetails sx={{ p: 0 }}>
          <Table size="small">
            <TableBody>
              {data.people.map((person) => (
                <CapacityRow
                  key={person.user_id}
                  label={
                    <>
                      <Typography variant="body2">{person.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {person.team_name ?? 'No team'} · {person.hours_source} hours · {person.max_allocation_percent}% ·{' '}
                        {person.availability_status.replaceAll('_', ' ')}
                      </Typography>
                    </>
                  }
                  cells={person.periods}
                  total={person.total}
                />
              ))}
            </TableBody>
          </Table>
        </AccordionDetails>
      </Accordion>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <SectionTitle
          title="Known demand (approved plan, unphased)"
          subtitle={data.demand.phasing_reason}
        />
        <Typography variant="body2">
          <strong>{hours(data.demand.approved_remaining_hours)}</strong> approved remaining across{' '}
          {data.demand.projects_with_approved_estimate} project(s); {data.demand.projects_without_approved_estimate} open project(s)
          have no approved estimate and are not counted
          {data.demand.projects_without_designer ? `; ${data.demand.projects_without_designer} have no designer` : ''}.
        </Typography>
        {data.demand.by_designer.length ? (
          <Box component="ul" sx={{ m: 0, mt: 1, pl: 2.5 }}>
            {data.demand.by_designer.map((d) => (
              <li key={d.user_id}>
                <Typography variant="body2">
                  {d.name}: {hours(d.approved_remaining_hours)} over {d.projects} project(s)
                </Typography>
              </li>
            ))}
          </Box>
        ) : null}
      </Paper>
      <Alert severity="info">Capacity gaps: {data.gap_analysis_reason}</Alert>
      <Alert severity="info">Skill demand: {data.skill_demand_reason}</Alert>
    </Stack>
  );
}

function FinanceSection({ data }: { data: FcFinance }) {
  return (
    <Stack spacing={2}>
      <MetadataPanel metadata={data.metadata} title="Billing and collections" />
      {data.warnings.map((warning) => (
        <Alert key={warning} severity="warning">
          {warning}
        </Alert>
      ))}
      {!data.reconciliation.outstanding_matches_ledger || !data.reconciliation.billing_matches_remaining ? (
        <Alert severity="error">The forecast does not reconcile with the Finance ledger. Do not rely on these totals.</Alert>
      ) : null}
      {data.totals.length === 0 ? <Alert severity="info">No active quotes in scope.</Alert> : null}
      {data.totals.map((t) => (
        <Paper key={t.currency} variant="outlined" sx={{ p: 2 }}>
          <SectionTitle title={`${t.currency} · ${t.quotes} quote(s)`} subtitle="Amounts in quote currency; currencies are never added together." />
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, mb: 2 }}>
            <KpiCard label="Invoiced (actual)" value={money(t.invoiced)} caption={`Collected ${money(t.collected)}`} />
            <KpiCard
              label="Outstanding (actual)"
              value={money(t.outstanding)}
              caption={`Due ${money(t.outstanding_scheduled)} · overdue ${money(t.outstanding_overdue)} · no due date ${money(t.outstanding_no_due_date)}`}
            />
            <KpiCard
              label="Remaining to invoice"
              value={money(t.remaining_to_invoice)}
              caption={`Ready ${money(t.billing_ready)} · dated ${money(t.billing_dated)} · no date ${money(t.billing_undated)} · excluded ${money(t.excluded_remaining_to_invoice)}`}
            />
            <KpiCard label="Awarded value" value={money(t.awarded_value)} caption="Active quote value; award status is not recorded" />
          </Box>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell />
                  {data.periods.map((p) => (
                    <TableCell key={p.key} align="right">
                      {p.label}
                    </TableCell>
                  ))}
                  <TableCell align="right">Later</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell><KindHeader kind="forecast">Collections by due date</KindHeader></TableCell>
                  {[...data.periods.map((p) => p.key), 'later'].map((key) => (
                    <TableCell key={key} align="right">
                      {money(t.collections_by_period[key] ?? 0)}
                    </TableCell>
                  ))}
                </TableRow>
                <TableRow>
                  <TableCell><KindHeader kind="forecast">Billing dated by project target</KindHeader></TableCell>
                  {[...data.periods.map((p) => p.key), 'later'].map((key) => (
                    <TableCell key={key} align="right">
                      {money(t.billing_by_period[key] ?? 0)}
                    </TableCell>
                  ))}
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      ))}
      {data.collections.length ? (
        <Accordion disableGutters variant="outlined">
          <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              Outstanding invoices ({data.collections.length})
            </Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ p: 0 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Quote</TableCell>
                  <TableCell>Invoice</TableCell>
                  <TableCell>Due date</TableCell>
                  <TableCell>Timing</TableCell>
                  <TableCell align="right">Outstanding</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.collections.map((c) => (
                  <TableRow key={c.invoice_line_id}>
                    <TableCell>
                      {c.tool_number}
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        {c.customer_name ?? '—'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {c.invoice_number ?? '—'} · {date(c.invoice_date)}
                    </TableCell>
                    <TableCell>{date(c.due_date)}</TableCell>
                    <TableCell>
                      {TIMING_LABELS[c.timing]}
                      {c.days_overdue ? ` (${c.days_overdue} d)` : ''}
                    </TableCell>
                    <TableCell align="right">
                      {money(c.outstanding)} {c.currency}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AccordionDetails>
        </Accordion>
      ) : null}
      {data.billing.length || data.excluded.length ? (
        <Accordion disableGutters variant="outlined">
          <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              Remaining to invoice ({data.billing.length} item(s), {data.excluded.length} excluded quote(s))
            </Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ p: 0 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Quote / project</TableCell>
                  <TableCell>Item</TableCell>
                  <TableCell>Expected invoice</TableCell>
                  <TableCell align="right">Amount</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.billing.map((b, index) => (
                  <TableRow key={`${b.quote_id}-${index}`}>
                    <TableCell>
                      {b.tool_number}
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        {b.project_code ?? '—'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {b.kind === 'milestone' ? `${b.milestone_name} (${b.trigger_type})` : 'Not covered by a billing milestone'}
                    </TableCell>
                    <TableCell sx={{ maxWidth: 320 }}>
                      {BILLING_DATE_LABELS[b.date_status]}
                      {b.expected_invoice_date ? `: ${date(b.expected_invoice_date)}` : ''}
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        {b.reason}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      {money(b.amount)} {b.currency}
                    </TableCell>
                  </TableRow>
                ))}
                {data.excluded.map((e) => (
                  <TableRow key={e.quote_id} sx={{ opacity: 0.7 }}>
                    <TableCell>{e.tool_number}</TableCell>
                    <TableCell>Excluded</TableCell>
                    <TableCell>{e.reason}</TableCell>
                    <TableCell align="right">
                      {money(e.remaining_to_invoice)} {e.currency}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AccordionDetails>
        </Accordion>
      ) : null}
    </Stack>
  );
}

function viewOptions(catalog: FcCatalog): { value: View; label: string }[] {
  const options: { value: View; label: string }[] = [];
  if (catalog.can_view_engineering) options.push({ value: 'engineering', label: 'Engineering effort' });
  if (catalog.can_view_capacity) options.push({ value: 'capacity', label: 'Capacity' });
  if (catalog.can_view_finance) options.push({ value: 'finance', label: 'Billing & collections' });
  return options;
}

export function ForecastsPanel() {
  const [selected, setSelected] = useState<View | null>(null);
  const [capacityHorizon, setCapacityHorizon] = useState<FcHorizonParams>({ granularity: 'week', periods: 8 });
  const [financeHorizon, setFinanceHorizon] = useState<FcHorizonParams>({ granularity: 'month', periods: 6 });
  const catalogQuery = useQuery({ queryKey: forecastQueryKeys.catalog, queryFn: fetchForecastCatalog });
  const options = catalogQuery.data ? viewOptions(catalogQuery.data) : [];
  const view: View | null = selected && options.some((o) => o.value === selected) ? selected : options[0]?.value ?? null;

  const engineeringQuery = useQuery({
    queryKey: forecastQueryKeys.engineering,
    queryFn: fetchEngineeringForecast,
    enabled: view === 'engineering',
  });
  const capacityQuery = useQuery({
    queryKey: forecastQueryKeys.capacity(capacityHorizon),
    queryFn: () => fetchCapacityForecast(capacityHorizon),
    enabled: view === 'capacity',
    placeholderData: keepPreviousData,
  });
  const financeQuery = useQuery({
    queryKey: forecastQueryKeys.finance(financeHorizon),
    queryFn: () => fetchFinanceForecast(financeHorizon),
    enabled: view === 'finance',
    placeholderData: keepPreviousData,
  });

  if (catalogQuery.isLoading) return <LoadingState message="Loading forecasts…" />;
  if (catalogQuery.isError || !catalogQuery.data) {
    return <ErrorState error={catalogQuery.error} title="Could not load forecasts" onRetry={() => void catalogQuery.refetch()} />;
  }
  const deferred = catalogQuery.data.definitions.filter((d) => d.deferred);

  return (
    <Stack spacing={2}>
      <Alert severity="info">
        Forecasts are calculated on demand and never change project, timesheet or Finance records. Actual, plan, forecast and
        commitment values are labelled separately. A forecast marked unavailable has no number on purpose.
      </Alert>
      {options.length === 0 ? (
        <Alert severity="warning">You do not have access to any forecast.</Alert>
      ) : (
        <ToggleButtonGroup size="small" exclusive value={view} onChange={(_, next: View | null) => next && setSelected(next)}>
          {options.map((o) => (
            <ToggleButton key={o.value} value={o.value}>
              {o.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      )}

      {view === 'engineering' ? (
        engineeringQuery.isLoading ? (
          <LoadingState message="Calculating remaining effort…" />
        ) : engineeringQuery.isError || !engineeringQuery.data ? (
          <ErrorState
            error={engineeringQuery.error}
            title="Could not load the engineering forecast"
            onRetry={() => void engineeringQuery.refetch()}
          />
        ) : (
          <EngineeringSection data={engineeringQuery.data} />
        )
      ) : null}

      {view === 'capacity' ? (
        <Box>
          <HorizonControls value={capacityHorizon} onChange={setCapacityHorizon} />
          {capacityQuery.isLoading ? (
            <LoadingState message="Calculating capacity…" />
          ) : capacityQuery.isError || !capacityQuery.data ? (
            <ErrorState
              error={capacityQuery.error}
              title="Could not load the capacity forecast"
              onRetry={() => void capacityQuery.refetch()}
            />
          ) : (
            <CapacitySection data={capacityQuery.data} />
          )}
        </Box>
      ) : null}

      {view === 'finance' ? (
        <Box>
          <HorizonControls value={financeHorizon} onChange={setFinanceHorizon} />
          {financeQuery.isLoading ? (
            <LoadingState message="Calculating billing and collections…" />
          ) : financeQuery.isError || !financeQuery.data ? (
            <ErrorState
              error={financeQuery.error}
              title="Could not load the billing and collection forecast"
              onRetry={() => void financeQuery.refetch()}
            />
          ) : (
            <FinanceSection data={financeQuery.data} />
          )}
        </Box>
      ) : null}

      {deferred.length ? (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <SectionTitle title="Not forecast yet" />
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {deferred.map((d) => (
              <li key={d.key}>
                <Typography variant="body2">
                  <strong>{d.label}:</strong> {d.deferred_reason}
                </Typography>
              </li>
            ))}
          </Box>
        </Paper>
      ) : null}
    </Stack>
  );
}
