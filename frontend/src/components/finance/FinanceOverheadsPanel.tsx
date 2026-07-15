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
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { teamQueryParam } from './FinanceTeamFilter';

type OverheadExpense = {
  id: string;
  name: string;
  amount: number;
  currency_code: string;
  nature: string;
  paid_by: string;
  vendor_name?: string | null;
  purchase_date?: string | null;
  end_date?: string | null;
  is_recurring?: boolean;
  frequency?: string;
};

type CostCentre = { id: string; name: string; code?: string };

type OverheadDash = {
  base_currency: string;
  planning_fy_label?: string | null;
  overhead?: {
    corporate_team_id?: string;
    corporate_team_name?: string;
    management_team_id?: string;
    management_team_name?: string;
    overhead_salary_inr?: number | string;
    overhead_management_salary_inr?: number | string;
    overhead_opex_inr?: number | string;
    overhead_pool_monthly_inr?: number | string;
    billable_resource_count?: number;
    overhead_cost_per_resource_inr?: number | string;
    team_billable_resource_count?: number;
    allocated_overhead_for_filter_inr?: number | string;
  };
};

function fmt(value: number | string | undefined) {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n.toLocaleString() : String(value ?? '—');
}

function MetricCard({
  title,
  value,
  suffix,
  hint,
}: {
  title: string;
  value: string | number;
  suffix?: string;
  hint?: string;
}) {
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
        {hint ? (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            {hint}
          </Typography>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function FinanceOverheadsPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const dashQ = teamQueryParam(teamId);
  const [form, setForm] = useState({
    team_id: '',
    cost_centre_id: '',
    name: '',
    amount: '',
    currency_code: 'INR',
    purchase_date: new Date().toISOString().slice(0, 10),
    end_date: '',
    frequency: 'monthly',
  });

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard', teamId || 'all'],
    queryFn: async () => (await apiClient.get<OverheadDash>(`/finance/dashboard${dashQ}`)).data,
  });

  const costCentresQuery = useQuery({
    queryKey: ['finance-cost-centres'],
    queryFn: async () => (await apiClient.get<CostCentre[]>('/finance/cost-centres')).data,
  });

  const overhead = dashboardQuery.data?.overhead;
  const corporateId = overhead?.corporate_team_id;
  const managementId = overhead?.management_team_id;

  const teamIds = useMemo(
    () => [managementId, corporateId].filter(Boolean) as string[],
    [managementId, corporateId],
  );

  const expensesQuery = useQuery({
    queryKey: ['finance-overhead-expenses', teamIds.join(',')],
    queryFn: async () => {
      const rows: OverheadExpense[] = [];
      for (const id of teamIds) {
        const params = new URLSearchParams();
        params.set('team_id', id);
        params.set('current_fy_only', 'true');
        const { data } = await apiClient.get<OverheadExpense[]>(
          `/finance/expenses?${params.toString()}`,
        );
        rows.push(...data);
      }
      return rows;
    },
    enabled: teamIds.length > 0,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const team = form.team_id || managementId || corporateId;
      if (!team) throw new Error('Select Management or Corporate team.');
      if (!form.cost_centre_id) throw new Error('Select a cost centre.');
      if (!form.name.trim()) throw new Error('Name is required.');
      return (
        await apiClient.post('/finance/expenses', {
          team_id: team,
          cost_centre_id: form.cost_centre_id,
          name: form.name.trim(),
          amount: form.amount || '0',
          currency_code: form.currency_code || 'INR',
          nature: 'opex',
          frequency: form.frequency,
          paid_by: 'prosohm',
          purchase_date: form.purchase_date,
          start_date: form.purchase_date,
          end_date: form.end_date || null,
          is_recurring: true,
          notify_enabled: Boolean(form.end_date),
        })
      ).data;
    },
    onSuccess: () => {
      showSuccess('Recurring overhead cost saved');
      setForm((prev) => ({ ...prev, name: '', amount: '', end_date: '' }));
      void queryClient.invalidateQueries({ queryKey: ['finance-overhead-expenses'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-expenses'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not save overhead cost'));
    },
  });

  const currency = dashboardQuery.data?.base_currency ?? 'INR';
  const expenses = (expensesQuery.data ?? []).filter(
    (row) => row.paid_by === 'prosohm' && row.nature === 'opex',
  );
  const centres = costCentresQuery.data ?? [];

  if (dashboardQuery.isLoading) {
    return <Typography color="text.secondary">Loading overheads…</Typography>;
  }

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Overheads
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Pool = <strong>{overhead?.management_team_name ?? 'Management'}</strong> salaries +{' '}
          <strong>{overhead?.corporate_team_name ?? 'Corporate'}</strong> / Management Prosohm OpEx ÷
          delivery billable resources. Leaders (Design/Engineering/OA) belong on Management. Set last
          working day on People costs so salaries stop after that date.
        </Typography>

        <Grid container spacing={1.5} sx={{ mb: 2 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Management salaries"
              value={fmt(overhead?.overhead_management_salary_inr)}
              suffix={currency}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Overhead OpEx (Prosohm)"
              value={fmt(overhead?.overhead_opex_inr)}
              suffix={currency}
              hint="Management + Corporate current FY"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Overhead pool / mo"
              value={fmt(overhead?.overhead_pool_monthly_inr)}
              suffix={currency}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Cost per billable resource"
              value={fmt(overhead?.overhead_cost_per_resource_inr)}
              suffix={currency}
              hint={`÷ ${overhead?.billable_resource_count ?? 0} delivery billable FTE`}
            />
          </Grid>
        </Grid>
      </Box>

      <Box>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Add recurring overhead cost
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ flexWrap: 'wrap', mb: 1 }}>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Team</InputLabel>
            <Select
              label="Team"
              value={form.team_id || managementId || ''}
              onChange={(e) => setForm({ ...form, team_id: e.target.value })}
            >
              {managementId ? (
                <MenuItem value={managementId}>
                  {overhead?.management_team_name ?? 'Management'}
                </MenuItem>
              ) : null}
              {corporateId ? (
                <MenuItem value={corporateId}>
                  {overhead?.corporate_team_name ?? 'Corporate'}
                </MenuItem>
              ) : null}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Cost centre</InputLabel>
            <Select
              label="Cost centre"
              value={form.cost_centre_id}
              onChange={(e) => setForm({ ...form, cost_centre_id: e.target.value })}
            >
              {centres.map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {c.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            size="small"
            label="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            sx={{ minWidth: 180 }}
          />
          <TextField
            size="small"
            label="Amount / period"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            sx={{ width: 130 }}
          />
          <TextField
            size="small"
            label="Currency"
            value={form.currency_code}
            onChange={(e) => setForm({ ...form, currency_code: e.target.value.toUpperCase() })}
            sx={{ width: 90 }}
          />
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Frequency</InputLabel>
            <Select
              label="Frequency"
              value={form.frequency}
              onChange={(e) => setForm({ ...form, frequency: e.target.value })}
            >
              <MenuItem value="monthly">Monthly</MenuItem>
              <MenuItem value="quarterly">Quarterly</MenuItem>
              <MenuItem value="yearly">Yearly</MenuItem>
            </Select>
          </FormControl>
          <TextField
            size="small"
            type="date"
            label="Start / purchase"
            value={form.purchase_date}
            onChange={(e) => setForm({ ...form, purchase_date: e.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            size="small"
            type="date"
            label="End date"
            value={form.end_date}
            onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            slotProps={{ inputLabel: { shrink: true } }}
            helperText="Stops OpEx after this date"
          />
          <Button
            variant="contained"
            disabled={createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            Save recurring
          </Button>
        </Stack>
      </Box>

      <Typography variant="subtitle2">Overhead expenses (current FY)</Typography>
      <Stack spacing={1}>
        {expenses.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No Management/Corporate Prosohm OpEx in the current FY yet.
          </Typography>
        ) : (
          expenses.map((row) => (
            <Card key={row.id} variant="outlined">
              <CardContent>
                <Typography sx={{ fontWeight: 600 }}>{row.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {row.amount} {row.currency_code} · {row.frequency ?? '—'}
                  {row.is_recurring ? ' · Recurring' : ''}
                  {row.purchase_date ? ` · From ${row.purchase_date}` : ''}
                  {row.end_date ? ` · Until ${row.end_date}` : ''}
                  {row.vendor_name ? ` · ${row.vendor_name}` : ''}
                </Typography>
              </CardContent>
            </Card>
          ))
        )}
      </Stack>
    </Stack>
  );
}
