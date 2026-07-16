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
import { ConfirmDialog } from '../common/ConfirmDialog';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { FinanceHeroBanner } from './FinanceCockpitPrimitives';

type CostCentre = { id: string; name: string; code?: string };
type Expense = {
  id: string;
  cost_centre_id: string;
  name: string;
  amount: number;
  currency_code: string;
  nature: string;
  frequency: string;
  paid_by: string;
  vendor_name?: string | null;
  purchase_date?: string | null;
  next_renewal_date?: string | null;
  notify_before_days?: number;
  notify_enabled?: boolean;
  is_recurring?: boolean;
  team_id?: string | null;
  prior_fy_excluded_from_overview?: boolean;
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
  purchase_date: new Date().toISOString().slice(0, 10),
  is_recurring: false,
  next_renewal_date: '',
  notify_before_days: '7',
  notify_enabled: true,
};

export function FinanceExpensesPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ ...emptyForm, team_id: teamId });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Expense | null>(null);
  const [paidByHint, setPaidByHint] = useState('');
  const [currentFyOnly, setCurrentFyOnly] = useState(false);

  useEffect(() => {
    if (!editingId) setForm((prev) => ({ ...prev, team_id: teamId || prev.team_id }));
  }, [teamId, editingId]);

  const costCentresQuery = useQuery({
    queryKey: ['finance-cost-centres'],
    queryFn: async () => (await apiClient.get<CostCentre[]>('/finance/cost-centres')).data,
  });
  const currenciesQuery = useQuery({
    queryKey: ['finance-currencies'],
    queryFn: async () =>
      (await apiClient.get<Array<{ code: string; name: string }>>('/finance/currencies')).data,
  });
  const teamsQuery = useQuery({
    queryKey: ['lookup-teams'],
    queryFn: fetchTeams,
  });
  const expensesQuery = useQuery({
    queryKey: ['finance-expenses', teamId || 'all', currentFyOnly ? 'fy' : 'all'],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (teamId) params.set('team_id', teamId);
      if (currentFyOnly) params.set('current_fy_only', 'true');
      const suffix = params.toString() ? `?${params.toString()}` : '';
      return (await apiClient.get<Expense[]>(`/finance/expenses${suffix}`)).data;
    },
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

  const payloadBody = () => ({
    cost_centre_id: form.cost_centre_id,
    team_id: form.team_id,
    name: form.name,
    amount: form.amount,
    currency_code: form.currency_code,
    nature: form.nature,
    frequency: form.frequency,
    paid_by: form.paid_by,
    vendor_name: form.vendor_name || null,
    purchase_date: form.purchase_date,
    is_recurring: form.is_recurring || form.frequency === 'recurring',
    next_renewal_date: form.next_renewal_date || null,
    notify_before_days: Number(form.notify_before_days) || 7,
    notify_enabled: form.notify_enabled,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (editingId) {
        return (await apiClient.patch(`/finance/expenses/${editingId}`, payloadBody())).data;
      }
      return (await apiClient.post('/finance/expenses', payloadBody())).data;
    },
    onSuccess: () => {
      showSuccess(editingId ? 'Expense updated' : 'Expense saved');
      setEditingId(null);
      setForm((prev) => ({
        ...emptyForm,
        cost_centre_id: prev.cost_centre_id,
        team_id: prev.team_id || teamId,
        currency_code: prev.currency_code,
      }));
      setPaidByHint('');
      void queryClient.invalidateQueries({ queryKey: ['finance-expenses'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not save expense'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/finance/expenses/${id}`);
    },
    onSuccess: () => {
      showSuccess('Expense deleted');
      setDeleteTarget(null);
      if (editingId && deleteTarget?.id === editingId) {
        setEditingId(null);
        setForm({ ...emptyForm, team_id: teamId });
      }
      void queryClient.invalidateQueries({ queryKey: ['finance-expenses'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not delete expense'));
    },
  });

  const startEdit = (row: Expense) => {
    setEditingId(row.id);
    setForm({
      cost_centre_id: row.cost_centre_id,
      team_id: row.team_id || teamId || '',
      name: row.name,
      amount: String(row.amount),
      currency_code: row.currency_code || 'INR',
      nature: row.nature,
      frequency: row.frequency,
      paid_by: row.paid_by,
      vendor_name: row.vendor_name || '',
      purchase_date: row.purchase_date || new Date().toISOString().slice(0, 10),
      is_recurring: Boolean(row.is_recurring),
      next_renewal_date: row.next_renewal_date || '',
      notify_before_days: String(row.notify_before_days ?? 7),
      notify_enabled: row.notify_enabled !== false,
    });
    setPaidByHint('');
  };

  const teams = teamsQuery.data ?? [];

  return (
    <Stack spacing={3}>
      <FinanceHeroBanner
        title="Expenses & subscriptions"
        subtitle="Capture Prosohm vs customer-paid spend with purchase dates and renewal radar — feeds Overview and Annual Plan renewals sync."
      />
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {editingId ? 'Edit expense / subscription' : 'Add expense / subscription'}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Team and date of purchase are required. Overview only counts purchases in the current
          Indian FY (Apr–Mar). Paid by defaults from Team commercial for SW/HW — you can override.
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
          <TextField
            size="small"
            type="date"
            label="Date of purchase"
            value={form.purchase_date}
            onChange={(e) => setForm((p) => ({ ...p, purchase_date: e.target.value }))}
            required
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <FormControl size="small" sx={{ minWidth: 110 }}>
            <InputLabel>Currency</InputLabel>
            <Select
              label="Currency"
              value={form.currency_code}
              onChange={(e) => setForm((p) => ({ ...p, currency_code: e.target.value }))}
            >
              {(currenciesQuery.data ?? [{ code: 'INR' }, { code: 'USD' }, { code: 'EUR' }]).map(
                (c) => (
                  <MenuItem key={c.code} value={c.code}>
                    {c.code}
                  </MenuItem>
                ),
              )}
            </Select>
          </FormControl>
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
              !form.purchase_date ||
              saveMutation.isPending
            }
            onClick={() => saveMutation.mutate()}
          >
            {editingId ? 'Save changes' : 'Add expense'}
          </Button>
          {editingId ? (
            <Button
              variant="outlined"
              onClick={() => {
                setEditingId(null);
                setForm({ ...emptyForm, team_id: teamId });
                setPaidByHint('');
              }}
            >
              Cancel
            </Button>
          ) : null}
        </Stack>
        {paidByHint ? (
          <Typography variant="caption" color="text.secondary">
            {paidByHint}
          </Typography>
        ) : null}
      </Box>

      <Box>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          sx={{ mb: 1, alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
        >
          <Typography variant="subtitle2">Expenses</Typography>
          <FormControlLabel
            control={
              <Checkbox
                checked={currentFyOnly}
                onChange={(e) => setCurrentFyOnly(e.target.checked)}
              />
            }
            label="Current FY only"
          />
        </Stack>
        <Stack spacing={1}>
          {(expensesQuery.data ?? []).map((row) => (
            <Card key={row.id} variant="outlined">
              <CardContent
                sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}
              >
                <Box>
                  <Typography sx={{ fontWeight: 600 }}>{row.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {row.amount} {row.currency_code} · {row.nature} · {row.frequency} · Paid by{' '}
                    {row.paid_by}
                    {row.purchase_date ? ` · Purchased ${row.purchase_date}` : ''}
                    {row.vendor_name ? ` · ${row.vendor_name}` : ''}
                    {row.next_renewal_date
                      ? ` · Renews ${row.next_renewal_date}${
                          row.notify_enabled
                            ? ` (notify ${row.notify_before_days ?? 7}d before)`
                            : ''
                        }`
                      : ''}
                  </Typography>
                  {row.prior_fy_excluded_from_overview ? (
                    <Typography variant="caption" color="warning.main">
                      Prior FY — not in Overview
                    </Typography>
                  ) : null}
                </Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                  <Button size="small" variant="contained" onClick={() => startEdit(row)}>
                    Edit
                  </Button>
                  <Button size="small" color="error" variant="outlined" onClick={() => setDeleteTarget(row)}>
                    Delete
                  </Button>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Stack>
      </Box>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete expense?"
        message="This removes the expense from Financial Planning lists and Overview totals (soft-delete)."
        recordName={
          deleteTarget
            ? `${deleteTarget.name} · ${deleteTarget.amount} ${deleteTarget.currency_code} · Paid by ${deleteTarget.paid_by}`
            : undefined
        }
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
      />
    </Stack>
  );
}
