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
import {
  IMPORT_ACCEPT_WITH_CSV,
  IMPORT_FORMAT_LABEL_WITH_CSV,
} from '../config/importFormats';
import { AnnualPlanPanel } from '../components/finance/AnnualPlanPanel';
import { FinanceExpensesPanel } from '../components/finance/FinanceExpensesPanel';
import { FinanceOverviewPanel } from '../components/finance/FinanceOverviewPanel';
import { FinancePeopleCostsPanel } from '../components/finance/FinancePeopleCostsPanel';
import { FinanceTeamCommercialPanel } from '../components/finance/FinanceTeamCommercialPanel';
import {
  FinanceTeamFilter,
  readStoredFinanceTeamId,
  teamQueryParam,
} from '../components/finance/FinanceTeamFilter';
import { useToast } from '../context/ToastContext';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';

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
    currency_code: 'INR',
    fiscal_year: String(new Date().getFullYear()),
  });

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard', teamId || 'all'],
    queryFn: async () =>
      (await apiClient.get<FinanceDashboard>(`/finance/dashboard${teamQueryParam(teamId)}`)).data,
  });
  const quotesQuery = useQuery({
    queryKey: ['finance-quotes'],
    queryFn: async () => (await apiClient.get('/finance/quotes')).data,
    enabled: tab === 5,
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

  const importMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return (await apiClient.post('/finance/quotes/import', form)).data;
    },
    onSuccess: (data) => {
      showSuccess(`Imported ${data.imported_count} quote(s)`);
      void queryClient.invalidateQueries({ queryKey: ['finance-quotes'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Quote import failed');
    },
  });

  const budgetMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post('/finance/budgets', {
          name: budgetForm.name,
          scope_type: budgetForm.scope_type,
          scope_id: budgetForm.scope_type === 'team' && teamId ? teamId : null,
          allocated: budgetForm.allocated,
          currency_code: budgetForm.currency_code,
          fiscal_year: Number(budgetForm.fiscal_year) || null,
          spent: '0',
          forecast: budgetForm.allocated,
        })
      ).data,
    onSuccess: () => {
      showSuccess('Budget created');
      setBudgetForm((prev) => ({ ...prev, name: '', allocated: '' }));
      void queryClient.invalidateQueries({ queryKey: ['finance-budgets'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not create budget');
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
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not approve budget');
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

      {tab === 5 && (
        <Stack spacing={2}>
          <Typography>
            Import quotes with customer, tool number, quoted hours, estimated cost, quoted revenue,
            margin, business model, dates, version and revision.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Default formats: {IMPORT_FORMAT_LABEL_WITH_CSV}. PDF must be a text table with a header
            row (same columns as Excel/CSV). Legacy .xls is not supported — save as .xlsx.
          </Typography>
          <Button variant="contained" component="label" disabled={importMutation.isPending}>
            Upload Quote File
            <input
              hidden
              type="file"
              accept={IMPORT_ACCEPT_WITH_CSV}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) importMutation.mutate(file);
              }}
            />
          </Button>
          <Typography variant="subtitle2">Imported quotes</Typography>
          <Stack spacing={1}>
            {(quotesQuery.data ?? []).map(
              (quote: {
                id: string;
                tool_number: string;
                currency_code: string;
                current_revision: string;
              }) => (
                <Card key={quote.id} variant="outlined">
                  <CardContent>
                    <Typography sx={{ fontWeight: 600 }}>{quote.tool_number}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {quote.currency_code} · rev {quote.current_revision}
                    </Typography>
                  </CardContent>
                </Card>
              ),
            )}
          </Stack>
        </Stack>
      )}

      {tab === 6 && (
        <Stack spacing={3}>
          <Box>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Budgets
            </Typography>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
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
                label="Allocated"
                value={budgetForm.allocated}
                onChange={(e) => setBudgetForm((p) => ({ ...p, allocated: e.target.value }))}
              />
              <TextField
                size="small"
                label="Fiscal year"
                value={budgetForm.fiscal_year}
                onChange={(e) => setBudgetForm((p) => ({ ...p, fiscal_year: e.target.value }))}
              />
              <Button
                variant="contained"
                disabled={!budgetForm.name || !budgetForm.allocated || budgetMutation.isPending}
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
                  approval_status: string;
                }) => (
                  <Card key={budget.id} variant="outlined">
                    <CardContent
                      sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}
                    >
                      <Box>
                        <Typography sx={{ fontWeight: 600 }}>{budget.name}</Typography>
                        <Typography variant="body2">
                          Allocated {budget.allocated} · Remaining {budget.remaining} ·{' '}
                          {budget.approval_status}
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
