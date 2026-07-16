/**
 * Budgets & Reports cockpit (Phase D) — portfolio KPIs, charts, risk insights, P&L statement.
 */
import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import AccountBalanceOutlinedIcon from '@mui/icons-material/AccountBalanceOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import SavingsOutlinedIcon from '@mui/icons-material/SavingsOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { toFiniteNumber } from '../../utils/format';
import { designTokens } from '../../theme/designTokens';
import { chartTheme } from '../../theme/chartTheme';
import { AnalyticsBarChart } from '../analytics/AnalyticsCharts';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { LoadingState } from '../common/LoadingState';
import { FinanceFxRatesPanel } from './FinanceFxRatesPanel';
import {
  FinanceHeroBanner,
  FinanceSection,
  FinanceUtilizationMeter,
  financeMoney,
} from './FinanceCockpitPrimitives';
import { teamQueryParam } from './FinanceTeamFilter';

const QUARTER_LABELS = ['Q1 Apr–Jun', 'Q2 Jul–Sep', 'Q3 Oct–Dec', 'Q4 Jan–Mar'];

type Cockpit = {
  currency_code: string;
  months_elapsed: number;
  operating_monthly_inr: number | string;
  operating_ytd_inr: number | string;
  totals: {
    budget_count: number;
    allocated: number | string;
    spent: number | string;
    forecast: number | string;
    remaining: number | string;
    utilization_percent: number | string;
    draft_count: number;
    approved_count: number;
    at_risk_count: number;
  };
  quarters: Record<string, number | string>;
  insights: Array<{ id: string; severity: string; title: string; detail: string }>;
  budgets: Array<{
    id: string;
    name: string;
    allocated: number | string;
    spent: number | string;
    forecast: number | string;
    remaining: number | string;
    variance: number | string;
    approval_status: string;
    utilization_percent: number | string;
    at_risk: boolean;
    q1_allocated?: number | string;
    q2_allocated?: number | string;
    q3_allocated?: number | string;
    q4_allocated?: number | string;
    q1_forecast?: number | string;
    q2_forecast?: number | string;
    q3_forecast?: number | string;
    q4_forecast?: number | string;
  }>;
};

type PlRow = { label: string; amount_inr: number };

const severityColor: Record<string, string> = {
  high: designTokens.health.red.main,
  medium: designTokens.health.yellow.main,
  low: designTokens.semantic.primary,
  info: designTokens.semantic.neutral,
};

export function FinanceBudgetsReportsPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const q = teamQueryParam(teamId);
  const [statusFilter, setStatusFilter] = useState<'all' | 'draft' | 'approved' | 'at_risk'>('all');
  const [createOpen, setCreateOpen] = useState(false);
  const [fxOpen, setFxOpen] = useState(false);
  const [budgetForm, setBudgetForm] = useState({
    name: '',
    scope_type: 'team',
    allocated: '',
    q1_allocated: '',
    q2_allocated: '',
    q3_allocated: '',
    q4_allocated: '',
    currency_code: 'INR',
    fiscal_year: String(
      new Date().getMonth() >= 3 ? new Date().getFullYear() : new Date().getFullYear() - 1,
    ),
  });

  const cockpitQuery = useQuery({
    queryKey: ['finance-budget-cockpit', teamId || 'all'],
    queryFn: async () => (await apiClient.get<Cockpit>(`/finance/budgets/cockpit${q}`)).data,
  });
  const plQuery = useQuery({
    queryKey: ['finance-pl', teamId || 'all'],
    queryFn: async () => (await apiClient.get<PlRow[]>('/finance/reports/profit-loss')).data,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['finance-budget-cockpit'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-budgets'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-pl'] });
  };

  const budgetMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post('/finance/budgets', {
          name: budgetForm.name,
          scope_type: budgetForm.scope_type,
          scope_id: budgetForm.scope_type === 'team' && teamId ? teamId : null,
          allocated: budgetForm.allocated || '0',
          q1_allocated: budgetForm.q1_allocated || '0',
          q2_allocated: budgetForm.q2_allocated || '0',
          q3_allocated: budgetForm.q3_allocated || '0',
          q4_allocated: budgetForm.q4_allocated || '0',
          currency_code: budgetForm.currency_code,
          fiscal_year: Number(budgetForm.fiscal_year) || null,
          spent: '0',
          forecast: '0',
        })
      ).data,
    onSuccess: () => {
      showSuccess('Budget created (forecast includes known renewals)');
      setBudgetForm((prev) => ({
        ...prev,
        name: '',
        allocated: '',
        q1_allocated: '',
        q2_allocated: '',
        q3_allocated: '',
        q4_allocated: '',
      }));
      setCreateOpen(false);
      invalidate();
    },
    onError: (error: unknown) => showError(apiErrorMessage(error, 'Could not create budget')),
  });

  const approveMutation = useMutation({
    mutationFn: async (budgetId: string) =>
      (
        await apiClient.patch(`/finance/budgets/${budgetId}/status`, {
          approval_status: 'approved',
        })
      ).data,
    onSuccess: () => {
      showSuccess('Budget approved');
      invalidate();
    },
    onError: (error: unknown) => showError(apiErrorMessage(error, 'Could not approve budget')),
  });

  const syncSpentMutation = useMutation({
    mutationFn: async (budgetId: string) =>
      (await apiClient.post(`/finance/budgets/${budgetId}/sync-spent${q}`)).data,
    onSuccess: () => {
      showSuccess('Spent synced from live operating cost');
      invalidate();
    },
    onError: (error: unknown) => showError(apiErrorMessage(error, 'Could not sync spent')),
  });

  const data = cockpitQuery.data;
  const currency = data?.currency_code ?? 'INR';

  const filteredBudgets = useMemo(() => {
    const rows = data?.budgets ?? [];
    if (statusFilter === 'all') return rows;
    if (statusFilter === 'at_risk') return rows.filter((row) => row.at_risk);
    return rows.filter((row) => row.approval_status === statusFilter);
  }, [data?.budgets, statusFilter]);

  if (cockpitQuery.isLoading || !data) {
    return <LoadingState message="Loading budgets cockpit…" />;
  }

  const totals = data.totals;

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="Budgets & reports cockpit"
        subtitle={`Portfolio envelopes, utilization, and P&L signals · ${data.months_elapsed} FY months elapsed · live OpEx YTD ${financeMoney(data.operating_ytd_inr, currency)}. Cost centres stay on expense forms only — not listed here.`}
        chips={
          <>
            <Chip size="small" label={`${totals.budget_count} budgets`} sx={{ fontWeight: 700 }} />
            <Chip
              size="small"
              color={totals.at_risk_count ? 'warning' : 'default'}
              label={`${totals.at_risk_count} at risk`}
            />
            <Chip size="small" variant="outlined" label={`${totals.draft_count} draft`} />
          </>
        }
      />

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Allocated"
            value={financeMoney(totals.allocated, currency)}
            subtitle={`${totals.approved_count} approved`}
            icon={AccountBalanceOutlinedIcon}
            accent="primary"
            compact
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Spent"
            value={financeMoney(totals.spent, currency)}
            subtitle={`Util ${toFiniteNumber(totals.utilization_percent).toFixed(0)}%`}
            icon={SavingsOutlinedIcon}
            accent="warning"
            compact
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Forecast"
            value={financeMoney(totals.forecast, currency)}
            subtitle="Incl. renewals"
            icon={TrendingUpOutlinedIcon}
            accent="success"
            compact
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Remaining"
            value={financeMoney(totals.remaining, currency)}
            subtitle={`${totals.at_risk_count} at risk`}
            icon={WarningAmberOutlinedIcon}
            accent={totals.at_risk_count ? 'error' : 'info'}
            compact
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 8 }}>
          <Stack spacing={2.5}>
            <FinanceSection
              title="Allocated vs forecast by quarter"
              subtitle="Portfolio roll-up (Apr–Mar FY)"
              action={
                <Button variant="contained" onClick={() => setCreateOpen(true)}>
                  New budget
                </Button>
              }
            >
              <AnalyticsBarChart
                categories={QUARTER_LABELS}
                height={280}
                series={[
                  {
                    label: 'Allocated',
                    data: ['q1', 'q2', 'q3', 'q4'].map((k) =>
                      toFiniteNumber(data.quarters[`${k}_allocated`]),
                    ),
                    color: designTokens.semantic.primary,
                  },
                  {
                    label: 'Forecast',
                    data: ['q1', 'q2', 'q3', 'q4'].map((k) =>
                      toFiniteNumber(data.quarters[`${k}_forecast`]),
                    ),
                    color: designTokens.semantic.warning,
                  },
                ]}
              />
            </FinanceSection>

            <FinanceSection
              title="Budget envelopes"
              subtitle="Filter, approve, and sync spent from live OpEx"
              action={
                <FormControl size="small" sx={{ minWidth: 140 }}>
                  <InputLabel>Filter</InputLabel>
                  <Select
                    label="Filter"
                    value={statusFilter}
                    onChange={(e) =>
                      setStatusFilter(e.target.value as typeof statusFilter)
                    }
                  >
                    <MenuItem value="all">All</MenuItem>
                    <MenuItem value="draft">Draft</MenuItem>
                    <MenuItem value="approved">Approved</MenuItem>
                    <MenuItem value="at_risk">At risk</MenuItem>
                  </Select>
                </FormControl>
              }
            >
              <Stack spacing={1.5}>
                {filteredBudgets.length === 0 ? (
                  <Typography color="text.secondary">No budgets in this filter.</Typography>
                ) : (
                  filteredBudgets.map((budget) => {
                    const allocated = toFiniteNumber(budget.allocated);
                    const spent = toFiniteNumber(budget.spent);
                    return (
                      <Card
                        key={budget.id}
                        elevation={0}
                        sx={{
                          border: '1px solid',
                          borderColor: budget.at_risk ? 'warning.main' : 'divider',
                          borderRadius: 2,
                          boxShadow: designTokens.elevation.card,
                        }}
                      >
                        <CardContent>
                          <Stack
                            direction={{ xs: 'column', sm: 'row' }}
                            spacing={2}
                            sx={{ justifyContent: 'space-between' }}
                          >
                            <Box sx={{ flex: 1, minWidth: 220 }}>
                              <Stack direction="row" spacing={1} sx={{ mb: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
                                <Typography sx={{ fontWeight: 700 }}>{budget.name}</Typography>
                                <Chip
                                  size="small"
                                  label={budget.approval_status}
                                  color={
                                    budget.approval_status === 'approved' ? 'success' : 'default'
                                  }
                                />
                                {budget.at_risk ? (
                                  <Chip size="small" color="warning" label="At risk" />
                                ) : null}
                              </Stack>
                              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                Forecast {financeMoney(budget.forecast, currency)} · Remaining{' '}
                                {financeMoney(budget.remaining, currency)} · Variance{' '}
                                {financeMoney(budget.variance, currency)}
                              </Typography>
                              <FinanceUtilizationMeter
                                spent={spent}
                                allocated={allocated}
                                currency={currency}
                              />
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ mt: 1, display: 'block' }}
                              >
                                Q alloc {budget.q1_allocated}/{budget.q2_allocated}/
                                {budget.q3_allocated}/{budget.q4_allocated} · forecast{' '}
                                {budget.q1_forecast}/{budget.q2_forecast}/{budget.q3_forecast}/
                                {budget.q4_forecast}
                              </Typography>
                            </Box>
                            <Stack spacing={1} sx={{ minWidth: 140 }}>
                              {budget.approval_status !== 'approved' ? (
                                <Button
                                  size="small"
                                  variant="contained"
                                  disabled={approveMutation.isPending}
                                  onClick={() => approveMutation.mutate(budget.id)}
                                >
                                  Approve
                                </Button>
                              ) : null}
                              <Button
                                size="small"
                                variant="outlined"
                                disabled={syncSpentMutation.isPending}
                                onClick={() => syncSpentMutation.mutate(budget.id)}
                              >
                                Sync spent
                              </Button>
                            </Stack>
                          </Stack>
                        </CardContent>
                      </Card>
                    );
                  })
                )}
              </Stack>
            </FinanceSection>

            <FinanceSection
              title="Profit & Loss statement"
              subtitle="Live operating signals (Overview basis)"
            >
              {(plQuery.data ?? []).length ? (
                <>
                  <Table size="small" sx={{ mb: 2 }}>
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>Line</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700 }}>
                          Amount ({currency})
                        </TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(plQuery.data ?? []).map((row) => (
                        <TableRow key={row.label} hover>
                          <TableCell>{row.label}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 600 }}>
                            {financeMoney(row.amount_inr, currency)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <AnalyticsBarChart
                    categories={(plQuery.data ?? []).map((row) => row.label)}
                    height={240}
                    series={[
                      {
                        label: currency,
                        data: (plQuery.data ?? []).map((row) => toFiniteNumber(row.amount_inr)),
                        color: designTokens.semantic.primary,
                      },
                    ]}
                  />
                </>
              ) : (
                <Typography color="text.secondary">No P&L rows yet.</Typography>
              )}
            </FinanceSection>

            <Box>
              <Button size="small" variant="text" onClick={() => setFxOpen((v) => !v)}>
                {fxOpen ? 'Hide advanced FX rates' : 'Advanced: FX rates (optional)'}
              </Button>
              <Collapse in={fxOpen}>
                <Box sx={{ mt: 1.5 }}>
                  <FinanceFxRatesPanel />
                </Box>
              </Collapse>
            </Box>
          </Stack>
        </Grid>

        <Grid size={{ xs: 12, lg: 4 }}>
          <FinanceSection title="Budget risk radar" subtitle="Data-driven portfolio insights">
            <Stack spacing={1.25}>
              {data.insights.map((insight) => (
                <Box
                  key={insight.id}
                  sx={{
                    p: 1.25,
                    borderRadius: 2,
                    border: `1px solid ${chartTheme.surface.hairline}`,
                    bgcolor: chartTheme.surface.muted,
                  }}
                >
                  <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
                    <Chip
                      size="small"
                      label={insight.severity}
                      sx={{
                        height: 22,
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        bgcolor: `${severityColor[insight.severity] ?? designTokens.semantic.neutral}22`,
                        color: severityColor[insight.severity] ?? designTokens.semantic.neutral,
                      }}
                    />
                    <Typography sx={{ fontWeight: 700, fontSize: '0.9rem' }}>
                      {insight.title}
                    </Typography>
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {insight.detail}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </FinanceSection>
        </Grid>
      </Grid>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Create budget</DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} sx={{ mt: 1 }}>
            <TextField
              size="small"
              label="Budget name"
              value={budgetForm.name}
              onChange={(e) => setBudgetForm((p) => ({ ...p, name: e.target.value }))}
              fullWidth
            />
            <FormControl size="small" fullWidth>
              <InputLabel>Scope</InputLabel>
              <Select
                label="Scope"
                value={budgetForm.scope_type}
                onChange={(e) => setBudgetForm((p) => ({ ...p, scope_type: e.target.value }))}
              >
                <MenuItem value="department">Department</MenuItem>
                <MenuItem value="customer">Customer</MenuItem>
                <MenuItem value="project">Project</MenuItem>
                <MenuItem value="team">Team</MenuItem>
                <MenuItem value="business_unit">Business Unit</MenuItem>
              </Select>
            </FormControl>
            <TextField
              size="small"
              label="FY allocated (optional)"
              value={budgetForm.allocated}
              onChange={(e) => setBudgetForm((p) => ({ ...p, allocated: e.target.value }))}
              helperText="Even-split to quarters if Q fields blank"
            />
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
              {(['q1', 'q2', 'q3', 'q4'] as const).map((quarter, idx) => (
                <TextField
                  key={quarter}
                  size="small"
                  label={`${quarter.toUpperCase()} ${['Apr–Jun', 'Jul–Sep', 'Oct–Dec', 'Jan–Mar'][idx]}`}
                  value={budgetForm[`${quarter}_allocated` as keyof typeof budgetForm]}
                  onChange={(e) =>
                    setBudgetForm((p) => ({ ...p, [`${quarter}_allocated`]: e.target.value }))
                  }
                  sx={{ width: 140 }}
                />
              ))}
            </Stack>
            <TextField
              size="small"
              label="FY start year"
              value={budgetForm.fiscal_year}
              onChange={(e) => setBudgetForm((p) => ({ ...p, fiscal_year: e.target.value }))}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              !budgetForm.name ||
              !(
                budgetForm.allocated ||
                budgetForm.q1_allocated ||
                budgetForm.q2_allocated ||
                budgetForm.q3_allocated ||
                budgetForm.q4_allocated
              ) ||
              budgetMutation.isPending
            }
            onClick={() => budgetMutation.mutate()}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
