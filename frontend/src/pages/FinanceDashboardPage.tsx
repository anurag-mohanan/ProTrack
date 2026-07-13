import { useMemo, useState } from 'react';
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
import { api } from '../api/client';
import { useToast } from '../context/ToastContext';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';

type FinanceDashboard = {
  base_currency: string;
  revenue: Record<string, number | string>;
  cost: Record<string, number | string>;
  profitability: Record<string, number | string>;
  budget: Record<string, number | string>;
  productivity: Record<string, number | string>;
  ai_placeholders: Array<{ id: string; kind: string; title: string; description?: string }>;
};

function MetricCard({ title, value, suffix }: { title: string; value: string | number; suffix?: string }) {
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="caption" color="text.secondary">
          {title}
        </Typography>
        <Typography variant="h6" sx={{ mt: 0.5 }}>
          {value}
          {suffix ? ` ${suffix}` : ''}
        </Typography>
      </CardContent>
    </Card>
  );
}

export function FinanceDashboardPage() {
  const [tab, setTab] = useState(0);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [expenseForm, setExpenseForm] = useState({
    cost_centre_id: '',
    name: '',
    amount: '',
    currency_code: 'INR',
    nature: 'opex',
    frequency: 'monthly',
  });
  const [budgetForm, setBudgetForm] = useState({
    name: '',
    scope_type: 'team',
    allocated: '',
    currency_code: 'INR',
    fiscal_year: String(new Date().getFullYear()),
  });
  const [salaryForm, setSalaryForm] = useState({
    user_id: '',
    monthly_salary: '',
    hourly_cost: '',
    currency_code: 'INR',
    effective_from: new Date().toISOString().slice(0, 10),
  });

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard'],
    queryFn: async () => (await api.get<FinanceDashboard>('/finance/dashboard')).data,
  });
  const quotesQuery = useQuery({
    queryKey: ['finance-quotes'],
    queryFn: async () => (await api.get('/finance/quotes')).data,
  });
  const budgetsQuery = useQuery({
    queryKey: ['finance-budgets'],
    queryFn: async () => (await api.get('/finance/budgets')).data,
  });
  const costCentresQuery = useQuery({
    queryKey: ['finance-cost-centres'],
    queryFn: async () => (await api.get('/finance/cost-centres')).data,
  });
  const expensesQuery = useQuery({
    queryKey: ['finance-expenses'],
    queryFn: async () => (await api.get('/finance/expenses')).data,
  });
  const employeeCostsQuery = useQuery({
    queryKey: ['finance-employee-costs'],
    queryFn: async () => (await api.get('/finance/employee-costs')).data,
  });
  const usersQuery = useQuery({
    queryKey: ['lookup-users'],
    queryFn: async () => (await api.get('/lookups/users')).data,
  });
  const currenciesQuery = useQuery({
    queryKey: ['finance-currencies'],
    queryFn: async () => (await api.get('/finance/currencies')).data,
  });
  const plQuery = useQuery({
    queryKey: ['finance-pl'],
    queryFn: async () => (await api.get('/finance/reports/profit-loss')).data,
    enabled: tab === 5,
  });

  const invalidateFinance = () => {
    queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    queryClient.invalidateQueries({ queryKey: ['finance-quotes'] });
    queryClient.invalidateQueries({ queryKey: ['finance-budgets'] });
    queryClient.invalidateQueries({ queryKey: ['finance-expenses'] });
    queryClient.invalidateQueries({ queryKey: ['finance-employee-costs'] });
  };

  const importMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return (await api.post('/finance/quotes/import', form)).data;
    },
    onSuccess: (data) => {
      showSuccess(`Imported ${data.imported_count} quote(s)`);
      invalidateFinance();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Quote import failed');
    },
  });

  const expenseMutation = useMutation({
    mutationFn: async () =>
      (
        await api.post('/finance/expenses', {
          cost_centre_id: expenseForm.cost_centre_id,
          name: expenseForm.name,
          amount: expenseForm.amount,
          currency_code: expenseForm.currency_code,
          nature: expenseForm.nature,
          frequency: expenseForm.frequency,
          is_recurring: expenseForm.frequency !== 'one_time',
        })
      ).data,
    onSuccess: () => {
      showSuccess('Expense saved');
      setExpenseForm((prev) => ({ ...prev, name: '', amount: '' }));
      invalidateFinance();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not save expense');
    },
  });

  const budgetMutation = useMutation({
    mutationFn: async () =>
      (
        await api.post('/finance/budgets', {
          name: budgetForm.name,
          scope_type: budgetForm.scope_type,
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
      invalidateFinance();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not create budget');
    },
  });

  const salaryMutation = useMutation({
    mutationFn: async () =>
      (
        await api.post('/finance/employee-costs', {
          user_id: salaryForm.user_id,
          monthly_salary: salaryForm.monthly_salary,
          hourly_cost: salaryForm.hourly_cost,
          currency_code: salaryForm.currency_code,
          effective_from: salaryForm.effective_from,
        })
      ).data,
    onSuccess: () => {
      showSuccess('Employee cost profile saved');
      invalidateFinance();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not save employee cost');
    },
  });

  const sections = useMemo(() => {
    const data = dashboardQuery.data;
    if (!data) return [];
    return [
      { key: 'revenue', title: 'Revenue', rows: data.revenue },
      { key: 'cost', title: 'Cost', rows: data.cost },
      { key: 'profitability', title: 'Profitability', rows: data.profitability },
      { key: 'budget', title: 'Budget', rows: data.budget },
      { key: 'productivity', title: 'Productivity', rows: data.productivity },
    ];
  }, [dashboardQuery.data]);

  if (dashboardQuery.isLoading) return <LoadingState message="Loading financial dashboard…" />;

  const currencies = currenciesQuery.data ?? [{ code: 'INR' }, { code: 'USD' }];

  return (
    <Box>
      <PageHeader
        title="Financial Planning"
        subtitle={`Multi-currency planning (base ${dashboardQuery.data?.base_currency ?? 'INR'}). Visible to Engineering Managers by default; grant the Financial Planning module to any other user in Admin → Users.`}
      />

      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 2 }} variant="scrollable">
        <Tab label="Dashboard" />
        <Tab label="Import Quote" />
        <Tab label="Costs & Salaries" />
        <Tab label="Cost Centres" />
        <Tab label="Budgets" />
        <Tab label="Reports" />
        <Tab label="AI Placeholders" />
      </Tabs>

      {tab === 0 && (
        <Stack spacing={3}>
          {sections.map((section) => (
            <Box key={section.key}>
              <Typography variant="h6" sx={{ mb: 1 }}>
                {section.title}
              </Typography>
              <Grid container spacing={1.5}>
                {Object.entries(section.rows).map(([key, value]) => (
                  <Grid key={key} size={{ xs: 12, sm: 6, md: 3 }}>
                    <MetricCard
                      title={key.replaceAll('_', ' ')}
                      value={typeof value === 'number' ? value.toLocaleString() : String(value)}
                      suffix={
                        key.includes('percent') || key.includes('rate') || key.includes('margin')
                          ? '%'
                          : dashboardQuery.data?.base_currency
                      }
                    />
                  </Grid>
                ))}
              </Grid>
            </Box>
          ))}
        </Stack>
      )}

      {tab === 1 && (
        <Stack spacing={2}>
          <Typography>
            Import quotes (Excel/CSV) with customer, tool number, quoted hours, estimated cost, quoted
            revenue, margin, business model, dates, version and revision. Used for productivity and
            profitability. PDF import is planned later.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            CSV headers example: Customer, Tool Number, Quoted Hours, Estimated Cost, Quoted Revenue,
            Currency, Version, Revision
          </Typography>
          <Button variant="contained" component="label" disabled={importMutation.isPending}>
            Upload Quote File
            <input
              hidden
              type="file"
              accept=".csv,.xlsx,.xls"
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
                    <Typography fontWeight={600}>{quote.tool_number}</Typography>
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

      {tab === 2 && (
        <Stack spacing={3}>
          <Box>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Employee salary / hourly cost (usually INR)
            </Typography>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
              <FormControl size="small" sx={{ minWidth: 220 }}>
                <InputLabel>Employee</InputLabel>
                <Select
                  label="Employee"
                  value={salaryForm.user_id}
                  onChange={(e) => setSalaryForm((p) => ({ ...p, user_id: e.target.value }))}
                >
                  {(usersQuery.data ?? []).map((user: { id: string; first_name: string; last_name: string }) => (
                    <MenuItem key={user.id} value={user.id}>
                      {user.first_name} {user.last_name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                size="small"
                label="Monthly salary"
                value={salaryForm.monthly_salary}
                onChange={(e) => setSalaryForm((p) => ({ ...p, monthly_salary: e.target.value }))}
              />
              <TextField
                size="small"
                label="Hourly cost"
                value={salaryForm.hourly_cost}
                onChange={(e) => setSalaryForm((p) => ({ ...p, hourly_cost: e.target.value }))}
              />
              <FormControl size="small" sx={{ minWidth: 100 }}>
                <InputLabel>Currency</InputLabel>
                <Select
                  label="Currency"
                  value={salaryForm.currency_code}
                  onChange={(e) => setSalaryForm((p) => ({ ...p, currency_code: e.target.value }))}
                >
                  {currencies.map((c: { code: string }) => (
                    <MenuItem key={c.code} value={c.code}>
                      {c.code}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Button
                variant="contained"
                disabled={!salaryForm.user_id || salaryMutation.isPending}
                onClick={() => salaryMutation.mutate()}
              >
                Save
              </Button>
            </Stack>
            <Stack spacing={1}>
              {(employeeCostsQuery.data ?? []).map(
                (row: {
                  id: string;
                  user_id: string;
                  monthly_salary: number;
                  hourly_cost: number;
                  currency_code: string;
                }) => (
                  <Card key={row.id} variant="outlined">
                    <CardContent>
                      <Typography variant="body2">
                        User {row.user_id.slice(0, 8)}… · Salary {row.monthly_salary} {row.currency_code} ·
                        Hourly {row.hourly_cost}
                      </Typography>
                    </CardContent>
                  </Card>
                ),
              )}
            </Stack>
          </Box>

          <Box>
            <Typography variant="h6" sx={{ mb: 1 }}>
              CAPEX / OPEX / software / overhead expenses
            </Typography>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ mb: 2 }} flexWrap="wrap">
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel>Cost centre</InputLabel>
                <Select
                  label="Cost centre"
                  value={expenseForm.cost_centre_id}
                  onChange={(e) => setExpenseForm((p) => ({ ...p, cost_centre_id: e.target.value }))}
                >
                  {(costCentresQuery.data ?? []).map((c: { id: string; name: string }) => (
                    <MenuItem key={c.id} value={c.id}>
                      {c.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                size="small"
                label="Name"
                value={expenseForm.name}
                onChange={(e) => setExpenseForm((p) => ({ ...p, name: e.target.value }))}
              />
              <TextField
                size="small"
                label="Amount"
                value={expenseForm.amount}
                onChange={(e) => setExpenseForm((p) => ({ ...p, amount: e.target.value }))}
              />
              <FormControl size="small" sx={{ minWidth: 100 }}>
                <InputLabel>Nature</InputLabel>
                <Select
                  label="Nature"
                  value={expenseForm.nature}
                  onChange={(e) => setExpenseForm((p) => ({ ...p, nature: e.target.value }))}
                >
                  <MenuItem value="opex">OPEX</MenuItem>
                  <MenuItem value="capex">CAPEX</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>Frequency</InputLabel>
                <Select
                  label="Frequency"
                  value={expenseForm.frequency}
                  onChange={(e) => setExpenseForm((p) => ({ ...p, frequency: e.target.value }))}
                >
                  <MenuItem value="monthly">Monthly</MenuItem>
                  <MenuItem value="quarterly">Quarterly</MenuItem>
                  <MenuItem value="yearly">Yearly</MenuItem>
                  <MenuItem value="one_time">One-time</MenuItem>
                  <MenuItem value="recurring">Recurring</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained"
                disabled={
                  !expenseForm.cost_centre_id || !expenseForm.name || expenseMutation.isPending
                }
                onClick={() => expenseMutation.mutate()}
              >
                Add expense
              </Button>
            </Stack>
            <Stack spacing={1}>
              {(expensesQuery.data ?? []).map(
                (row: {
                  id: string;
                  name: string;
                  amount: number;
                  currency_code: string;
                  nature: string;
                  frequency: string;
                }) => (
                  <Card key={row.id} variant="outlined">
                    <CardContent>
                      <Typography fontWeight={600}>{row.name}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {row.amount} {row.currency_code} · {row.nature} · {row.frequency}
                      </Typography>
                    </CardContent>
                  </Card>
                ),
              )}
            </Stack>
          </Box>
        </Stack>
      )}

      {tab === 3 && (
        <Grid container spacing={1.5}>
          {(costCentresQuery.data ?? []).map(
            (centre: { id: string; code: string; name: string; nature: string }) => (
              <Grid key={centre.id} size={{ xs: 12, sm: 6, md: 4 }}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography fontWeight={600}>{centre.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {centre.code} · {centre.nature}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ),
          )}
        </Grid>
      )}

      {tab === 4 && (
        <Stack spacing={2}>
          <Typography variant="h6">Create budget allotment</Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
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
                  <CardContent>
                    <Typography fontWeight={600}>{budget.name}</Typography>
                    <Typography variant="body2">
                      Allocated {budget.allocated} · Remaining {budget.remaining} ·{' '}
                      {budget.approval_status}
                    </Typography>
                  </CardContent>
                </Card>
              ),
            )}
          </Stack>
        </Stack>
      )}

      {tab === 5 && (
        <Stack spacing={2}>
          <Typography>
            Profit &amp; Loss and profitability (base currency). Export requires Financial Planning
            export permission.
          </Typography>
          <Stack spacing={1}>
            {(plQuery.data ?? []).map((row: { label: string; amount_inr: number }) => (
              <Card key={row.label} variant="outlined">
                <CardContent>
                  <Typography fontWeight={600}>{row.label}</Typography>
                  <Typography>
                    {Number(row.amount_inr).toLocaleString()}{' '}
                    {dashboardQuery.data?.base_currency ?? 'INR'}
                  </Typography>
                </CardContent>
              </Card>
            ))}
          </Stack>
        </Stack>
      )}

      {tab === 6 && (
        <Grid container spacing={1.5}>
          {(dashboardQuery.data?.ai_placeholders ?? []).map((item) => (
            <Grid key={item.id} size={{ xs: 12, sm: 6, md: 4 }}>
              <Card variant="outlined">
                <CardContent>
                  <Typography fontWeight={600}>{item.title}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {item.description}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
}

export default FinanceDashboardPage;
