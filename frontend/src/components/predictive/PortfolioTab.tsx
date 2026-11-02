import { useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { useQuery } from '@tanstack/react-query';
import { fetchPredictionPatterns, predictiveQueryKeys } from '../../api/predictive';
import type { PatternReport, Prediction, PredictionCoverage, PredictionOverview } from '../../types/Predictive';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { KpiCard, SectionTitle } from '../reports/ReportKpi';
import {
  amountText,
  dataString,
  dateText,
  daysVariance,
  hoursText,
  hoursVariance,
  percentOver,
  rangeText,
} from './predictiveFormat';

function emptyMessage(coverage: PredictionCoverage, none: string): string {
  if (!coverage.predicted && coverage.insufficient) {
    return `None of the ${coverage.insufficient} item(s) in scope could be forecast; see the reasons below.`;
  }
  if (!coverage.predicted) return 'Nothing in scope has been forecast yet.';
  return none;
}

function LikelyLateTable({ rows, coverage, onOpen }: { rows: Prediction[]; coverage: PredictionCoverage; onOpen: (id: string) => void }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, minWidth: 0 }}>
      <SectionTitle title="Likely to finish after the target date" subtitle="Forecast completion against the current target date." />
      {rows.length ? (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Project</TableCell>
                <TableCell>Target (recorded)</TableCell>
                <TableCell>Forecast completion</TableCell>
                <TableCell>Variance</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id} hover sx={{ cursor: r.project_id ? 'pointer' : undefined }} onClick={() => r.project_id && onOpen(r.project_id)}>
                  <TableCell>{r.subject_label}</TableCell>
                  <TableCell>{dateText(r.baseline_date)}</TableCell>
                  <TableCell>
                    {dateText(r.predicted_date)}
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {rangeText(r) ?? 'No range: fewer than 10 comparable outcomes'}
                    </Typography>
                  </TableCell>
                  <TableCell>{daysVariance(r.variance_value)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Typography variant="body2" color="text.secondary">
          {emptyMessage(coverage, 'No forecast project is expected to finish after its target date.')}
        </Typography>
      )}
    </Paper>
  );
}

function LikelyOverrunTable({ rows, coverage, onOpen }: { rows: Prediction[]; coverage: PredictionCoverage; onOpen: (id: string) => void }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, minWidth: 0 }}>
      <SectionTitle title="Likely to exceed the approved estimate" subtitle="Forecast final hours against the current approved estimate." />
      {rows.length ? (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Project</TableCell>
                <TableCell align="right">Approved (recorded)</TableCell>
                <TableCell align="right">Forecast final</TableCell>
                <TableCell align="right">Variance</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id} hover sx={{ cursor: r.project_id ? 'pointer' : undefined }} onClick={() => r.project_id && onOpen(r.project_id)}>
                  <TableCell>{r.subject_label}</TableCell>
                  <TableCell align="right">{hoursText(r.baseline_value)}</TableCell>
                  <TableCell align="right">
                    {hoursText(r.predicted_value)}
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {rangeText(r, 'hours') ?? 'No range'}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    {hoursVariance(r.variance_value)}
                    {percentOver(r.variance_value, r.baseline_value) ? ` (${percentOver(r.variance_value, r.baseline_value)})` : ''}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Typography variant="body2" color="text.secondary">
          {emptyMessage(coverage, 'No forecast project is expected to exceed its approved estimate.')}
        </Typography>
      )}
    </Paper>
  );
}

function CoverageReasons({ overview }: { overview: PredictionOverview }) {
  const sections = [
    ['Completion date', overview.coverage.project_delivery],
    ['Final hours', overview.coverage.project_final_hours],
    ['Milestones', overview.coverage.milestone_delay],
  ] as const;
  if (sections.every(([, c]) => !c.insufficient)) return null;
  return (
    <Accordion disableGutters variant="outlined" sx={{ '&:before': { display: 'none' } }}>
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          Why some items cannot be forecast
        </Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={1.5}>
          {sections
            .filter(([, c]) => c.insufficient)
            .map(([label, c]) => (
              <Box key={label}>
                <Typography variant="caption" sx={{ fontWeight: 700 }}>
                  {label}: {c.predicted} forecast, {c.insufficient} not forecast
                </Typography>
                <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                  {c.top_reasons.map((r) => (
                    <li key={r.reason}>
                      <Typography variant="body2">
                        {r.reason} <Typography component="span" variant="caption" color="text.secondary">({r.count})</Typography>
                      </Typography>
                    </li>
                  ))}
                </Box>
              </Box>
            ))}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}

function CompletionTrend({ trend }: { trend: PredictionOverview['completion_trend'] }) {
  if (!trend.length) return null;
  const max = Math.max(...trend.map((t) => t.projects));
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <SectionTitle title="Forecast completions by month" subtitle="Open projects by forecast completion month (forecast projects only)." />
      <Stack spacing={0.75}>
        {trend.map((t) => (
          <Stack key={t.month} direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
            <Typography variant="body2" sx={{ width: 72, flexShrink: 0 }}>
              {t.month}
            </Typography>
            <LinearProgress variant="determinate" value={(t.projects / max) * 100} sx={{ flex: 1, height: 8, borderRadius: 1 }} />
            <Typography variant="body2" sx={{ width: 32, textAlign: 'right' }}>
              {t.projects}
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Paper>
  );
}

function FinanceSummary({ finance }: { finance: NonNullable<PredictionOverview['finance']> }) {
  const currencies = [...new Set([...finance.billing, ...finance.collections].map((r) => r.currency ?? ''))].sort();
  if (!currencies.length) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <SectionTitle title="Billing and collections forecast" />
        <Typography variant="body2" color="text.secondary">
          No finance forecast has been produced yet.
        </Typography>
      </Paper>
    );
  }
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <SectionTitle
        title="Billing and collections forecast"
        subtitle="Forecast amounts per month next to the Phase 3 contractual dating. Ledger figures are recorded amounts, not forecasts."
      />
      <Stack spacing={2}>
        {currencies.map((currency) => {
          const billing = finance.billing.filter((r) => (r.currency ?? '') === currency);
          const collections = finance.collections.filter((r) => (r.currency ?? '') === currency);
          const ledger = (billing[0] ?? collections[0])?.data_used.ledger_totals as Record<string, string> | undefined;
          const periods = [...new Set([...billing, ...collections].map((r) => r.subject_label))];
          const byLabel = (rows: Prediction[], label: string) => rows.find((r) => r.subject_label === label);
          const billingReason = billing.find((r) => r.status === 'insufficient_data')?.reason;
          const collectionReason = collections.find((r) => r.status === 'insufficient_data')?.reason;
          return (
            <Box key={currency}>
              {ledger ? (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                  Ledger ({currency}, recorded): awarded {amountText(ledger.awarded_value)} · invoiced {amountText(ledger.invoiced)} ·
                  collected {amountText(ledger.collected)} · outstanding {amountText(ledger.outstanding)} · remaining to invoice{' '}
                  {amountText(ledger.remaining_to_invoice)}
                </Typography>
              ) : null}
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Month</TableCell>
                      <TableCell align="right">Billing forecast</TableCell>
                      <TableCell align="right">Billing (contractual dating)</TableCell>
                      <TableCell align="right">Collections forecast</TableCell>
                      <TableCell align="right">Collections (due dates)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {periods.map((label) => {
                      const b = byLabel(billing, label);
                      const c = byLabel(collections, label);
                      return (
                        <TableRow key={label}>
                          <TableCell>{label}</TableCell>
                          <TableCell align="right">{b?.status === 'predicted' ? amountText(b.predicted_value) : 'Not forecast'}</TableCell>
                          <TableCell align="right">{amountText(b?.baseline_value)}</TableCell>
                          <TableCell align="right">{c?.status === 'predicted' ? amountText(c.predicted_value) : 'Not forecast'}</TableCell>
                          <TableCell align="right">{amountText(c?.baseline_value)}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
              {billingReason ? (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                  Billing not forecast: {billingReason}
                </Typography>
              ) : null}
              {collectionReason ? (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  Collections not forecast: {collectionReason}
                </Typography>
              ) : null}
            </Box>
          );
        })}
      </Stack>
    </Paper>
  );
}

function PatternTable({ data }: { data: PatternReport }) {
  return (
    <Stack spacing={1.5}>
      {data.patterns.length ? (
        <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
          {data.patterns.map((p) => (
            <li key={`${p.metric}-${p.dimension}-${p.group_label}-${p.stratum ?? ''}`}>
              <Typography variant="body2">
                <strong>{p.metric_label}</strong> by {p.dimension}: {p.finding}
                {p.period_start ? ` Period ${p.period_start} – ${p.period_end}.` : ''}
              </Typography>
            </li>
          ))}
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary">
          No statistically reliable difference was found. {data.no_reliable_difference.length} group(s) were compared;{' '}
          {data.too_small.length} group(s) were too small to compare and are not labelled.
        </Typography>
      )}
      {data.metrics ? (
        <Typography variant="caption" color="text.secondary">
          {data.metrics.map((m) => `${m.label}: ${m.projects} completed project(s) (${m.rule})`).join(' ')}
        </Typography>
      ) : null}
      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
        {data.limitations.map((l) => (
          <li key={l}>
            <Typography variant="caption">{l}</Typography>
          </li>
        ))}
      </Box>
    </Stack>
  );
}

function PatternsPanel({ finance }: { finance: boolean }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<'project' | 'payment'>('project');
  const query = useQuery({
    queryKey: predictiveQueryKeys.patterns(kind),
    queryFn: () => fetchPredictionPatterns(kind),
    enabled: open,
  });
  return (
    <Accordion disableGutters variant="outlined" expanded={open} onChange={(_, next) => setOpen(next)} sx={{ '&:before': { display: 'none' } }}>
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          Portfolio patterns in completed work
        </Typography>
      </AccordionSummary>
      <AccordionDetails>
        {finance ? (
          <ToggleButtonGroup size="small" exclusive value={kind} onChange={(_, next) => next && setKind(next)} sx={{ mb: 1.5 }}>
            <ToggleButton value="project">Effort and delivery</ToggleButton>
            <ToggleButton value="payment">Invoicing and payment</ToggleButton>
          </ToggleButtonGroup>
        ) : null}
        {query.isLoading ? <LoadingState message="Comparing completed work…" /> : null}
        {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
        {query.data ? <PatternTable data={query.data} /> : null}
      </AccordionDetails>
    </Accordion>
  );
}

export function PortfolioTab({
  overview,
  onOpenProject,
  onOpenResources,
}: {
  overview: PredictionOverview;
  onOpenProject: (projectId: string) => void;
  onOpenResources: () => void;
}) {
  const { coverage, bottlenecks } = overview;
  const bottleneckCount = bottlenecks ? bottlenecks.people.length + bottlenecks.teams.length + bottlenecks.skills.length : 0;
  return (
    <Stack spacing={2}>
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' } }}>
        <KpiCard
          label="Likely late"
          value={String(overview.likely_late.length)}
          caption={`${coverage.project_delivery.predicted} forecast · ${coverage.project_delivery.insufficient} cannot be forecast`}
          definition="Open projects whose forecast completion is after their current target date. Top 10 shown."
        />
        <KpiCard
          label="Likely over estimate"
          value={String(overview.likely_overrun.length)}
          caption={`${coverage.project_final_hours.predicted} forecast · ${coverage.project_final_hours.insufficient} cannot be forecast`}
          definition="Open projects whose forecast final hours exceed the current approved estimate. Top 10 shown."
        />
        <KpiCard
          label="Milestones likely late"
          value={String(overview.late_milestones.length)}
          caption={`${coverage.milestone_delay.predicted} forecast · ${coverage.milestone_delay.insufficient} cannot be forecast`}
        />
        {bottlenecks ? (
          <KpiCard
            label="Capacity shortages (4 weeks)"
            value={String(bottleneckCount)}
            caption={`${bottlenecks.people.length} people · ${bottlenecks.teams.length} teams · ${bottlenecks.skills.length} skills`}
            onClick={onOpenResources}
          />
        ) : (
          <KpiCard label="Capacity shortages" value="—" caption="Requires Resource Planning access" />
        )}
      </Box>

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' } }}>
        <LikelyLateTable rows={overview.likely_late} coverage={coverage.project_delivery} onOpen={onOpenProject} />
        <LikelyOverrunTable rows={overview.likely_overrun} coverage={coverage.project_final_hours} onOpen={onOpenProject} />
      </Box>

      {overview.late_milestones.length ? (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <SectionTitle title="Milestones likely to finish after their target" />
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Milestone</TableCell>
                  <TableCell>Target (recorded)</TableCell>
                  <TableCell>Forecast finish</TableCell>
                  <TableCell>Variance</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {overview.late_milestones.map((r) => (
                  <TableRow key={r.id} hover sx={{ cursor: r.project_id ? 'pointer' : undefined }} onClick={() => r.project_id && onOpenProject(r.project_id)}>
                    <TableCell>{r.subject_label}</TableCell>
                    <TableCell>{dateText(r.baseline_date)}</TableCell>
                    <TableCell>{dateText(r.predicted_date)}</TableCell>
                    <TableCell>{daysVariance(r.variance_value)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      ) : null}

      <CompletionTrend trend={overview.completion_trend} />
      <CoverageReasons overview={overview} />

      {bottlenecks && bottleneckCount ? (
        <Alert severity="info" action={<Typography variant="body2" sx={{ cursor: 'pointer', fontWeight: 600 }} onClick={onOpenResources}>View</Typography>}>
          {[...bottlenecks.teams, ...bottlenecks.skills]
            .slice(0, 3)
            .map((r) => `${r.subject_label}: ${dataString(r.data_used, 'utilisation_percent') ?? '—'}% of capacity`)
            .join(' · ') || `${bottlenecks.people.length} people are forecast above capacity in the next 4 weeks.`}
        </Alert>
      ) : null}

      {overview.finance ? <FinanceSummary finance={overview.finance} /> : null}
      {overview.can.patterns ? <PatternsPanel finance={overview.can.finance} /> : null}
    </Stack>
  );
}
