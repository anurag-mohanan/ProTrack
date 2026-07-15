import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
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
import { FinanceOverviewPanel } from '../components/finance/FinanceOverviewPanel';
import { FinancePeopleCostsPanel } from '../components/finance/FinancePeopleCostsPanel';
import { FinanceQuotesPanel } from '../components/finance/FinanceQuotesPanel';
import { FinanceTeamCommercialPanel } from '../components/finance/FinanceTeamCommercialPanel';
import {
  FinanceTeamFilter,
  readStoredFinanceTeamId,
  teamQueryParam,
} from '../components/finance/FinanceTeamFilter';
import { useToast } from '../context/ToastContext';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { apiErrorMessage } from '../utils/apiErrorMessage';

type FinanceDashboard = {
  base_currency: string;
  ai_placeholders: Array<{ id: string; kind: string; title: string; description?: string }>;
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
    enabled: tab === 6,
  });
  const costCentresQuery = useQuery({
    queryKey: ['finance-cost-centres'],
    queryFn: async () => (await apiClient.get('/finance/cost-centres')).data,
    enabled: tab === 6,
  });
  const plQuery = useQuery({
    queryKey: ['finance-pl'],
    queryFn: async () => (await apiClient.get('/finance/reports/profit-loss')).data,
    enabled: tab === 6,
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
        subtitle={`Industry-standard cost & commercial planning (base ${
          dashboardQuery.data?.base_currency ?? 'INR'
        }). Grant the Financial Planning module in Admin → Users.`}
      />

      <FinanceTeamFilter value={teamId} onChange={setTeamId} />

      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 2 }} variant="scrollable">
        <Tab label="Overview" />
        <Tab label="People costs" />
        <Tab label="Expenses & subscriptions" />
        <Tab label="Team commercial" />
        <Tab label="Annual Plan" />
        <Tab label="Revenue / quotes" />
        <Tab label="Budgets & reports" />
      </Tabs>

      {tab === 0 && <FinanceOverviewPanel teamId={teamId} />}
      {tab === 1 && <FinancePeopleCostsPanel teamId={teamId} />}
      {tab === 2 && <FinanceExpensesPanel teamId={teamId} />}
      {tab === 3 && <FinanceTeamCommercialPanel teamId={teamId} />}
      {tab === 4 && <AnnualPlanPanel />}
      {tab === 5 && <FinanceQuotesPanel teamId={teamId} />}

      {tab === 6 && (
        <Stack spacing={3}>
          <FinanceFxRatesPanel />

          <Box>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Budgets
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Enter FY total or Q1–Q4 amounts (Apr–Mar). Forecast auto-adds known software renewals in each
              quarter.
            </Typography>
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
            <Stack spacing={1}>
              {(budgetsQuery.data ?? []).map(
                (budget: {
                  id: string;
                  name: string;
                  allocated: number;
                  remaining: number;
                  forecast?: number;
                  approval_status: string;
                  q1_allocated?: number;
                  q2_allocated?: number;
                  q3_allocated?: number;
                  q4_allocated?: number;
                  q1_forecast?: number;
                  q2_forecast?: number;
                  q3_forecast?: number;
                  q4_forecast?: number;
                }) => (
                  <Card key={budget.id} variant="outlined">
                    <CardContent
                      sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}
                    >
                      <Box>
                        <Typography sx={{ fontWeight: 600 }}>{budget.name}</Typography>
                        <Typography variant="body2">
                          Allocated {budget.allocated} · Forecast {budget.forecast ?? '—'} · Remaining{' '}
                          {budget.remaining} · {budget.approval_status}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Q1–Q4 alloc {budget.q1_allocated ?? 0}/{budget.q2_allocated ?? 0}/
                          {budget.q3_allocated ?? 0}/{budget.q4_allocated ?? 0} · forecast{' '}
                          {budget.q1_forecast ?? 0}/{budget.q2_forecast ?? 0}/{budget.q3_forecast ?? 0}/
                          {budget.q4_forecast ?? 0}
                        </Typography>
                      </Box>
                      {budget.approval_status !== 'approved' ? (
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={approveMutation.isPending}
                          onClick={() => approveMutation.mutate(budget.id)}
                        >
                          Approve
                        </Button>
                      ) : null}
                    </CardContent>
                  </Card>
                ),
              )}
            </Stack>
          </Box>

          <Box>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Profit &amp; Loss
            </Typography>
            <Stack spacing={1}>
              {(plQuery.data ?? []).map((row: { label: string; amount_inr: number }) => (
                <Card key={row.label} variant="outlined">
                  <CardContent>
                    <Typography sx={{ fontWeight: 600 }}>{row.label}</Typography>
                    <Typography>
                      {Number(row.amount_inr).toLocaleString()}{' '}
                      {dashboardQuery.data?.base_currency ?? 'INR'}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Stack>
          </Box>

          <Box>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Cost centres
            </Typography>
            <Grid container spacing={1.5}>
              {(costCentresQuery.data ?? []).map(
                (centre: { id: string; code: string; name: string; nature: string }) => (
                  <Grid key={centre.id} size={{ xs: 12, sm: 6, md: 4 }}>
                    <Card variant="outlined">
                      <CardContent>
                        <Typography sx={{ fontWeight: 600 }}>{centre.name}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {centre.code} · {centre.nature}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ),
              )}
            </Grid>
          </Box>

          <Box>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Future AI forecasts (placeholders)
            </Typography>
            <Grid container spacing={1.5}>
              {(dashboardQuery.data?.ai_placeholders ?? []).map((item) => (
                <Grid key={item.id} size={{ xs: 12, sm: 6, md: 4 }}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography sx={{ fontWeight: 600 }}>{item.title}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {item.description}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>
        </Stack>
      )}
    </Box>
  );
}

export default FinanceDashboardPage;
