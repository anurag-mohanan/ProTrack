import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { fetchTeams } from '../../api/lookups';
import { useToast } from '../../context/ToastContext';
import { teamQueryParam } from './FinanceTeamFilter';

type CostCentre = { id: string; name: string; code?: string };
type Expense = {
  id: string;
  name: string;
  amount: number;
  currency_code: string;
  nature: string;
  frequency: string;
  paid_by: string;
  vendor_name?: string | null;
  next_renewal_date?: string | null;
  notify_before_days?: number;
  notify_enabled?: boolean;
  team_id?: string | null;
};

const emptyForm = {
  cost_centre_id: '',
  team_id: '',
  name: '',
  amount: '',
  currency_code: 'INR',
  nature: 'opex',
  frequency: 'monthly',
  paid_by: 'prosohm',
  vendor_name: '',
  is_recurring: false,
  next_renewal_date: '',
  notify_before_days: '7',
  notify_enabled: true,
};

export function FinanceExpensesPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ ...emptyForm, team_id: teamId });
  const [paidByHint, setPaidByHint] = useState('');
  const q = teamQueryParam(teamId);

  useEffect(() => {
    setForm((prev) => ({ ...prev, team_id: teamId || prev.team_id }));
  }, [teamId]);

  const costCentresQuery = useQuery({
    queryKey: ['finance-cost-centres'],
    queryFn: async () => (await apiClient.get<CostCentre[]>('/finance/cost-centres')).data,
  });
  const teamsQuery = useQuery({
    queryKey: ['lookup-teams'],
    queryFn: fetchTeams,
  });
  const expensesQuery = useQuery({
    queryKey: ['finance-expenses', teamId || 'all'],
    queryFn: async () => (await apiClient.get<Expense[]>(`/finance/expenses${q}`)).data,
  });

  const refreshPaidByDefault = async (nextTeamId: string, nextCentreId: string) => {
    if (!nextTeamId || !nextCentreId) {
      setPaidByHint('');
      return;
    }
    try {
      const { data } = await apiClient.get<{ paid_by: string; reason: string }>(
        `/finance/expenses/paid-by-default?team_id=${encodeURIComponent(nextTeamId)}&cost_centre_id=${encodeURIComponent(nextCentreId)}`,
      );
      setForm((prev) => ({ ...prev, paid_by: data.paid_by }));
      setPaidByHint(data.reason);
    } catch {
      setPaidByHint('');
    }
  };

  const mutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post('/finance/expenses', {
          cost_centre_id: form.cost_centre_id,
          team_id: form.team_id,
          name: form.name,
          amount: form.amount,
          currency_code: form.currency_code,
          nature: form.nature,
          frequency: form.frequency,
          paid_by: form.paid_by,
          vendor_name: form.vendor_name || null,
          is_recurring: form.is_recurring || form.frequency === 'recurring',
          next_renewal_date: form.next_renewal_date || null,
          notify_before_days: Number(form.notify_before_days) || 7,
          notify_enabled: form.notify_enabled,
        })
      ).data,
    onSuccess: () => {
      showSuccess('Expense saved');
      setForm((prev) => ({
        ...emptyForm,
        cost_centre_id: prev.cost_centre_id,
        team_id: prev.team_id || teamId,
        currency_code: prev.currency_code,
      }));
      void queryClient.invalidateQueries({ queryKey: ['finance-expenses'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not save expense');
    },
  });

  const teams = teamsQuery.data ?? [];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Add expense / subscription
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Team is required. Paid by defaults from Team commercial (customer pays software/hardware) for SW/HW cost
          centres — you can override.
        </Typography>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap', mb: 1 }}>
          <FormControl size="small" sx={{ minWidth: 200 }} required>
            <InputLabel>Team</InputLabel>
            <Select
              label="Team"
              value={form.team_id}
              onChange={(e) => {
                const next = e.target.value;
                setForm((p) => ({ ...p, team_id: next }));
                void refreshPaidByDefault(next, form.cost_centre_id);
              }}
            >
              {teams.map((team) => (
                <MenuItem key={team.id} value={team.id}>
                  {team.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Cost centre</InputLabel>
            <Select
              label="Cost centre"
              value={form.cost_centre_id}
              onChange={(e) => {
                const next = e.target.value;
                setForm((p) => ({ ...p, cost_centre_id: next }));
                void refreshPaidByDefault(form.team_id, next);
              }}
            >
              {(costCentresQuery.data ?? []).map((c) => (
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
            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
          />
          <TextField
            size="small"
            label="Vendor"
            value={form.vendor_name}
            onChange={(e) => setForm((p) => ({ ...p, vendor_name: e.target.value }))}
          />
          <TextField
            size="small"
            label="Amount"
            value={form.amount}
            onChange={(e) => setForm((p) => ({ ...p, amount: e.target.value }))}
          />
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Paid by</InputLabel>
            <Select
              label="Paid by"
              value={form.paid_by}
              onChange={(e) => {
                setForm((p) => ({ ...p, paid_by: e.target.value }));
                setPaidByHint('Manual override');
              }}
            >
              <MenuItem value="prosohm">Paid by Prosohm</MenuItem>
              <MenuItem value="customer">Paid by customer</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 110 }}>
            <InputLabel>Nature</InputLabel>
            <Select
              label="Nature"
              value={form.nature}
              onChange={(e) => setForm((p) => ({ ...p, nature: e.target.value }))}
            >
              <MenuItem value="opex">OPEX</MenuItem>
              <MenuItem value="capex">CAPEX</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>Frequency</InputLabel>
            <Select
              label="Frequency"
              value={form.frequency}
              onChange={(e) => setForm((p) => ({ ...p, frequency: e.target.value }))}
            >
              <MenuItem value="monthly">Monthly</MenuItem>
              <MenuItem value="quarterly">Quarterly</MenuItem>
              <MenuItem value="yearly">Yearly</MenuItem>
              <MenuItem value="one_time">One-time</MenuItem>
              <MenuItem value="recurring">Recurring</MenuItem>
            </Select>
          </FormControl>
          <TextField
            size="small"
            type="date"
            label="Next renewal"
            value={form.next_renewal_date}
            onChange={(e) => setForm((p) => ({ ...p, next_renewal_date: e.target.value }))}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            size="small"
            label="Notify days before"
            value={form.notify_before_days}
            onChange={(e) => setForm((p) => ({ ...p, notify_before_days: e.target.value }))}
            sx={{ width: 140 }}
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={form.is_recurring}
                onChange={(e) => setForm((p) => ({ ...p, is_recurring: e.target.checked }))}
              />
            }
            label="Recurring"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={form.notify_enabled}
                onChange={(e) => setForm((p) => ({ ...p, notify_enabled: e.target.checked }))}
              />
            }
            label="Notify before renewal"
          />
          <Button
            variant="contained"
            disabled={
              !form.team_id ||
              !form.cost_centre_id ||
              !form.name ||
              !form.amount ||
              mutation.isPending
            }
            onClick={() => mutation.mutate()}
          >
            Add expense
          </Button>
        </Stack>
        {paidByHint ? (
          <Typography variant="caption" color="text.secondary">
            {paidByHint}
          </Typography>
        ) : null}
      </Box>

      <Box>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Expenses
        </Typography>
        <Stack spacing={1}>
          {(expensesQuery.data ?? []).map((row) => (
            <Card key={row.id} variant="outlined">
              <CardContent>
                <Typography sx={{ fontWeight: 600 }}>{row.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {row.amount} {row.currency_code} · {row.nature} · {row.frequency} · Paid by{' '}
                  {row.paid_by}
                  {row.vendor_name ? ` · ${row.vendor_name}` : ''}
                  {row.next_renewal_date
                    ? ` · Renews ${row.next_renewal_date}${
                        row.notify_enabled
                          ? ` (notify ${row.notify_before_days ?? 7}d before)`
                          : ''
                      }`
                    : ''}
                </Typography>
              </CardContent>
            </Card>
          ))}
        </Stack>
      </Box>
    </Stack>
  );
}
