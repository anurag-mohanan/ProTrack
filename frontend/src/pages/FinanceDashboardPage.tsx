import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { AnnualPlanPanel } from '../components/finance/AnnualPlanPanel';
import { FinanceExpensesPanel } from '../components/finance/FinanceExpensesPanel';
import { FinanceFxRatesPanel } from '../components/finance/FinanceFxRatesPanel';
import { FinanceOverheadsPanel } from '../components/finance/FinanceOverheadsPanel';
import { FinanceOverviewPanel } from '../components/finance/FinanceOverviewPanel';
import { FinancePeopleCostsPanel } from '../components/finance/FinancePeopleCostsPanel';
import { FinanceQuotesPanel } from '../components/finance/FinanceQuotesPanel';
import { FinanceTeamCommercialPanel } from '../components/finance/FinanceTeamCommercialPanel';
import {
  FinanceHeroBanner,
  FinanceSection,
  FinanceUtilizationMeter,
  financeMoney,
} from '../components/finance/FinanceCockpitPrimitives';
import {
  FinanceTeamFilter,
  readStoredFinanceTeamId,
  teamQueryParam,
} from '../components/finance/FinanceTeamFilter';
import { AnalyticsBarChart } from '../components/analytics/AnalyticsCharts';
import { useToast } from '../context/ToastContext';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { apiErrorMessage } from '../utils/apiErrorMessage';
import { designTokens } from '../theme/designTokens';
import { toFiniteNumber } from '../utils/format';

type FinanceDashboard = {
  base_currency: string;
  ai_placeholders: Array<{ id: string; kind: string; title: string; description?: string }>;
  budget?: {
    budget_allocated?: number;
    budget_consumed?: number;
    budget_variance?: number;
  };
  cost?: {
    monthly_operating_cost?: number;
  };
};

export function FinanceDashboardPage() {
  const [tab, setTab] = useState(0);
  const [teamId, setTeamId] = useState(readStoredFinanceTeamId);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [budgetForm, setBudgetForm] = useState({
    name: '',
    scope_type: 'team',
    allocated: '',
    q1_allocated: '',
    q2_allocated: '',
    q3_allocated: '',
    q4_allocated: '',
    currency_code: 'INR',
    fiscal_year: String(new Date().getMonth() >= 3 ? new Date().getFullYear() : new Date().getFullYear() - 1),
  });

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard', teamId || 'all'],
    queryFn: async () =>
      (await apiClient.get<FinanceDashboard>(`/finance/dashboard${teamQueryParam(teamId)}`)).data,
  });
  const budgetsQuery = useQuery({
    queryKey: ['finance-budgets', teamId || 'all'],
    queryFn: async () =>
      (await apiClient.get(`/finance/budgets${teamQueryParam(teamId)}`)).data,
    enabled: tab === 7,
  });
  const costCentresQuery = useQuery({
    queryKey: ['finance-cost-centres'],
    queryFn: async () => (await apiClient.get('/finance/cost-centres')).data,
    enabled: tab === 7,
  });
  const plQuery = useQuery({
    queryKey: ['finance-pl'],
    queryFn: async () => (await apiClient.get('/finance/reports/profit-loss')).data,
    enabled: tab === 7,
  });

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
      void queryClient.invalidateQueries({ queryKey: ['finance-budgets'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not create budget'));
    },
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
      void queryClient.invalidateQueries({ queryKey: ['finance-budgets'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not approve budget'));
    },
  });

  if (dashboardQuery.isLoading && tab === 0) {
    return <LoadingState message="Loading financial dashboard…" />;
  }

  return (
    <Box>
      <PageHeader
        title="Financial Planning"
        subtitle={`Modern FP&A cockpit (base ${
          dashboardQuery.data?.base_currency ?? 'INR'
        }) — chart-led Overview, Annual Plan variance, budgets. Grant Financial Planning in Admin → Users.`}
      />

      <FinanceTeamFilter value={teamId} onChange={setTeamId} />

      <Tabs
        value={tab}
        onChange={(_, value) => setTab(value)}
        sx={{
          mb: 2.5,
          minHeight: 44,
          '& .MuiTab-root': { textTransform: 'none', fontWeight: 600, minHeight: 44 },
        }}
        variant="scrollable"
      >
        <Tab label="Overview" />
        <Tab label="People costs" />
        <Tab label="Expenses & subscriptions" />
        <Tab label="Overheads" />
        <Tab label="Team commercial" />
        <Tab label="Annual Plan" />
        <Tab label="Revenue / quotes" />
        <Tab label="Budgets & reports" />
      </Tabs>

      {tab === 0 && <FinanceOverviewPanel teamId={teamId} />}
      {tab === 1 && <FinancePeopleCostsPanel teamId={teamId} />}
      {tab === 2 && <FinanceExpensesPanel teamId={teamId} />}
      {tab === 3 && <FinanceOverheadsPanel teamId={teamId} />}
      {tab === 4 && <FinanceTeamCommercialPanel teamId={teamId} />}
      {tab === 5 && <AnnualPlanPanel />}
      {tab === 6 && <FinanceQuotesPanel teamId={teamId} />}

      {tab === 7 && (
        <Stack spacing={2.5}>
          <FinanceHeroBanner
            title="Budgets & reports"
            subtitle="QBO/Xero-style remaining meters, P&L signals, and cost centres — renewals auto-feed quarterly forecasts."
          />
          <FinanceFxRatesPanel />

          <FinanceSection
            title="Budgets"
            subtitle="Enter FY total or Q1–Q4 amounts (Apr–Mar). Forecast auto-adds known software renewals."
          >
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ mb: 2, flexWrap: 'wrap' }}>
              <TextField
                size="small"
                label="Budget name"
                value={budgetForm.name}
                onChange={(e) => setBudgetForm((p) => ({ ...p, name: e.target.value }))}
              />
              <FormControl size="small" sx={{ minWidth: 140 }}>
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
                helperText="Even-split if quarters blank"
              />
              {(['q1', 'q2', 'q3', 'q4'] as const).map((q, idx) => (
                <TextField
                  key={q}
                  size="small"
                  label={`${q.toUpperCase()} ${['Apr–Jun', 'Jul–Sep', 'Oct–Dec', 'Jan–Mar'][idx]}`}
                  value={budgetForm[`${q}_allocated` as keyof typeof budgetForm]}
                  onChange={(e) =>
                    setBudgetForm((p) => ({ ...p, [`${q}_allocated`]: e.target.value }))
                  }
                  sx={{ width: 120 }}
                />
              ))}
              <TextField
                size="small"
                label="FY start year"
                value={budgetForm.fiscal_year}
                onChange={(e) => setBudgetForm((p) => ({ ...p, fiscal_year: e.target.value }))}
              />
              <Button
                variant="contained"
                disabled={
                  !budgetForm.name ||
                  (!(budgetForm.allocated || budgetForm.q1_allocated || budgetForm.q2_allocated || budgetForm.q3_allocated || budgetForm.q4_allocated)) ||
                  budgetMutation.isPending
                }
                onClick={() => budgetMutation.mutate()}
              >
                Create
              </Button>
            </Stack>
            <Stack spacing={1.5}>
              {(budgetsQuery.data ?? []).map(
                (budget: {
                  id: string;
                  name: string;
                  allocated: number;
                  remaining: number;
                  spent?: number;
                  forecast?: number;
                  variance?: number;
                  approval_status: string;
                  q1_allocated?: number;
                  q2_allocated?: number;
                  q3_allocated?: number;
                  q4_allocated?: number;
                  q1_forecast?: number;
                  q2_forecast?: number;
                  q3_forecast?: number;
                  q4_forecast?: number;
                }) => {
                  const allocated = Number(budget.allocated || 0);
                  const spent = Number(budget.spent ?? 0);
                  const variance = Number(budget.variance ?? allocated - spent);
                  const currency = dashboardQuery.data?.base_currency ?? 'INR';
                  return (
                    <Card
                      key={budget.id}
                      elevation={0}
                      sx={{
                        border: '1px solid',
                        borderColor: 'divider',
                        borderRadius: 2,
                        boxShadow: designTokens.elevation.card,
                      }}
                    >
                      <CardContent
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          gap: 2,
                          flexWrap: 'wrap',
                        }}
                      >
                        <Box sx={{ flex: 1, minWidth: 240 }}>
                          <Stack direction="row" spacing={1} sx={{ mb: 0.5, alignItems: 'center' }}>
                            <Typography sx={{ fontWeight: 700 }}>{budget.name}</Typography>
                            <Chip
                              size="small"
                              label={budget.approval_status}
                              color={budget.approval_status === 'approved' ? 'success' : 'default'}
                            />
                          </Stack>
                          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                            Forecast {budget.forecast ?? '—'} · Remaining {budget.remaining} ·
                            Variance {variance}
                          </Typography>
                          <FinanceUtilizationMeter
                            spent={spent}
                            allocated={allocated}
                            currency={currency}
                          />
                          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                            Q1–Q4 alloc {budget.q1_allocated ?? 0}/{budget.q2_allocated ?? 0}/
                            {budget.q3_allocated ?? 0}/{budget.q4_allocated ?? 0} · forecast{' '}
                            {budget.q1_forecast ?? 0}/{budget.q2_forecast ?? 0}/
                            {budget.q3_forecast ?? 0}/{budget.q4_forecast ?? 0}
                          </Typography>
                        </Box>
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
                      </CardContent>
                    </Card>
                  );
                },
              )}
            </Stack>
          </FinanceSection>

          <FinanceSection
            title="Profit & Loss signals"
            subtitle="Live operating signals (Overview basis). Open Annual Plan for Plan vs Actual charts."
          >
            {(plQuery.data ?? []).length ? (
              <AnalyticsBarChart
                categories={(plQuery.data ?? []).map((row: { label: string }) => row.label)}
                height={280}
                series={[
                  {
                    label: dashboardQuery.data?.base_currency ?? 'INR',
                    data: (plQuery.data ?? []).map((row: { amount_inr: number }) =>
                      toFiniteNumber(row.amount_inr),
                    ),
                    color: designTokens.semantic.primary,
                  },
                ]}
              />
            ) : (
              <Typography color="text.secondary">No P&L rows yet.</Typography>
            )}
            {dashboardQuery.data ? (
              <Grid container spacing={1.5} sx={{ mt: 1 }}>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Typography variant="body2" color="text.secondary">
                    Budget allocated
                  </Typography>
                  <Typography sx={{ fontWeight: 700 }}>
                    {financeMoney(
                      dashboardQuery.data.budget?.budget_allocated ?? 0,
                      dashboardQuery.data.base_currency,
                    )}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Typography variant="body2" color="text.secondary">
                    Budget spent
                  </Typography>
                  <Typography sx={{ fontWeight: 700 }}>
                    {financeMoney(
                      dashboardQuery.data.budget?.budget_consumed ?? 0,
                      dashboardQuery.data.base_currency,
                    )}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Typography variant="body2" color="text.secondary">
                    Variance / monthly opex
                  </Typography>
                  <Typography sx={{ fontWeight: 700 }}>
                    {financeMoney(
                      dashboardQuery.data.budget?.budget_variance ?? 0,
                      dashboardQuery.data.base_currency,
                    )}{' '}
                    /{' '}
                    {financeMoney(
                      dashboardQuery.data.cost?.monthly_operating_cost ?? 0,
                      dashboardQuery.data.base_currency,
                    )}
                  </Typography>
                </Grid>
              </Grid>
            ) : null}
          </FinanceSection>

          <FinanceSection title="Cost centres" subtitle="Chart of accounts style centres for expense posting">
            <Grid container spacing={1.5}>
              {(costCentresQuery.data ?? []).map(
                (centre: { id: string; code: string; name: string; nature: string }) => (
                  <Grid key={centre.id} size={{ xs: 12, sm: 6, md: 4 }}>
                    <Card
                      elevation={0}
                      sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2 }}
                    >
                      <CardContent>
                        <Typography sx={{ fontWeight: 700 }}>{centre.name}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {centre.code} · {centre.nature}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ),
              )}
            </Grid>
          </FinanceSection>

          <FinanceSection title="Future AI forecasts" subtitle="Placeholders only — no live AI this release">
            <Grid container spacing={1.5}>
              {(dashboardQuery.data?.ai_placeholders ?? []).map((item) => (
                <Grid key={item.id} size={{ xs: 12, sm: 6, md: 4 }}>
                  <Card
                    elevation={0}
                    sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2 }}
                  >
                    <CardContent>
                      <Typography sx={{ fontWeight: 700 }}>{item.title}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {item.description}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </FinanceSection>
        </Stack>
      )}
    </Box>
  );
}

export default FinanceDashboardPage;
