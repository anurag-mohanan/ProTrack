import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Checkbox,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import AccountBalanceWalletOutlinedIcon from '@mui/icons-material/AccountBalanceWalletOutlined';
import EventRepeatOutlinedIcon from '@mui/icons-material/EventRepeatOutlined';
import PaymentsOutlinedIcon from '@mui/icons-material/PaymentsOutlined';
import StorefrontOutlinedIcon from '@mui/icons-material/StorefrontOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { fetchTeams } from '../../api/lookups';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { toFiniteNumber } from '../../utils/format';
import { designTokens } from '../../theme/designTokens';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import {
  FinanceHeroBanner,
  FinanceSection,
  financeMoney,
} from './FinanceCockpitPrimitives';

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
  team_name?: string | null;
  is_common?: boolean;
  display_group?: string | null;
  base_amount_inr?: number | string | null;
  prior_fy_excluded_from_overview?: boolean;
};

/** Matches backend corporate / overhead home names for form labels. */
const COMMON_TEAM_NAMES = new Set([
  'corporate / management',
  'corporate / shared services',
  'corporate',
  'management',
]);

function isCommonTeamName(name: string | null | undefined): boolean {
  if (!name) return false;
  return COMMON_TEAM_NAMES.has(name.trim().toLowerCase());
}

function teamSelectLabel(name: string): string {
  return isCommonTeamName(name) ? 'Common (Corporate / Management)' : name;
}

function expenseGroupLabel(row: Expense, teamNameById: Map<string, string>): string {
  if (row.display_group) return row.display_group;
  if (row.is_common) return 'Common';
  if (row.team_name) return row.team_name;
  if (row.team_id) return teamNameById.get(row.team_id) || 'Unassigned';
  return 'Unassigned';
}

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

const listRowSx = {
  p: 1.5,
  borderRadius: `${designTokens.radius.md}px`,
  border: '1px solid',
  borderColor: 'divider',
  bgcolor: 'background.paper',
  display: 'flex',
  justifyContent: 'space-between',
  gap: 2,
  flexWrap: 'wrap' as const,
  alignItems: 'flex-start',
};

export function FinanceExpensesPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ ...emptyForm, team_id: teamId });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Expense | null>(null);
  const [paidByHint, setPaidByHint] = useState('');
  const [currentFyOnly, setCurrentFyOnly] = useState(false);
  /** Advanced = group by team / Common (default on for All teams). */
  const [advancedMode, setAdvancedMode] = useState(!teamId);

  useEffect(() => {
    if (!editingId) setForm((prev) => ({ ...prev, team_id: teamId || prev.team_id }));
  }, [teamId, editingId]);

  useEffect(() => {
    if (!teamId) setAdvancedMode(true);
  }, [teamId]);

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
  const expenses = expensesQuery.data ?? [];
  const teamNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const team of teams) map.set(team.id, team.name);
    return map;
  }, [teams]);

  const baseOf = (e: Expense) => toFiniteNumber(e.base_amount_inr ?? e.amount);

  const expenseStats = useMemo(() => {
    const prosohm = expenses.filter((e) => e.paid_by === 'prosohm');
    const customer = expenses.filter((e) => e.paid_by === 'customer');
    const renewals = expenses.filter((e) => Boolean(e.next_renewal_date)).length;
    const currencies = new Set(
      expenses.map((e) => (e.currency_code || 'INR').toUpperCase()).filter(Boolean),
    );
    const commonCount = expenses.filter(
      (e) => e.is_common || e.display_group === 'Common' || isCommonTeamName(e.team_name),
    ).length;
    return {
      count: expenses.length,
      prosohmSum: prosohm.reduce((s, e) => s + baseOf(e), 0),
      customerSum: customer.reduce((s, e) => s + baseOf(e), 0),
      renewals,
      mixedFx: currencies.size > 1,
      commonCount,
    };
  }, [expenses]);

  const expenseGroups = useMemo(() => {
    const buckets = new Map<string, Expense[]>();
    for (const row of expenses) {
      const key = expenseGroupLabel(row, teamNameById);
      const list = buckets.get(key) ?? [];
      list.push(row);
      buckets.set(key, list);
    }
    const keys = [...buckets.keys()].sort((a, b) => {
      if (a === 'Common') return -1;
      if (b === 'Common') return 1;
      return a.localeCompare(b);
    });
    return keys.map((key) => {
      const rows = buckets.get(key) ?? [];
      const prosohmSum = rows
        .filter((e) => e.paid_by === 'prosohm')
        .reduce((s, e) => s + baseOf(e), 0);
      return { key, rows, prosohmSum, isCommon: key === 'Common' };
    });
  }, [expenses, teamNameById]);

  const showGrouped = advancedMode && !teamId;

  const renderExpenseRow = (row: Expense) => {
    const groupLabel = expenseGroupLabel(row, teamNameById);
    const isCommon = row.is_common || groupLabel === 'Common';
    return (
      <Box key={row.id} sx={listRowSx}>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Stack
            direction="row"
            spacing={1}
            useFlexGap
            sx={{ flexWrap: 'wrap', alignItems: 'center', mb: 0.5 }}
          >
            <Typography sx={{ fontWeight: 600 }}>{row.name}</Typography>
            <Chip
              size="small"
              label={isCommon ? 'Common' : groupLabel}
              color={isCommon ? 'secondary' : 'default'}
              variant="outlined"
            />
            <Chip
              size="small"
              label={row.paid_by === 'customer' ? 'Customer' : 'Prosohm'}
              color={row.paid_by === 'customer' ? 'info' : 'default'}
              variant="outlined"
            />
            {row.next_renewal_date ? (
              <Chip
                size="small"
                color="success"
                variant="outlined"
                label={`Renews ${row.next_renewal_date}`}
              />
            ) : null}
          </Stack>
          <Typography variant="body2" color="text.secondary">
            {financeMoney(row.amount, row.currency_code)} · {row.nature} · {row.frequency}
            {row.purchase_date ? ` · Purchased ${row.purchase_date}` : ''}
            {row.vendor_name ? ` · ${row.vendor_name}` : ''}
            {row.next_renewal_date && row.notify_enabled
              ? ` · notify ${row.notify_before_days ?? 7}d before`
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
      </Box>
    );
  };

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="Expenses & subscriptions"
        subtitle="Team OpEx vs Common (shared HQ) — Advanced mode groups spend for team P&L. Feeds Overview and Annual Plan renewals."
        chips={
          <>
            <Chip size="small" label={currentFyOnly ? 'Current FY' : 'All years'} sx={{ fontWeight: 700 }} />
            <Chip size="small" variant="outlined" label={`${expenseStats.count} lines`} />
            {expenseStats.commonCount > 0 ? (
              <Chip size="small" color="secondary" variant="outlined" label={`${expenseStats.commonCount} Common`} />
            ) : null}
            {advancedMode && !teamId ? (
              <Chip size="small" color="primary" label="Advanced · by team" />
            ) : null}
            {expenseStats.mixedFx ? (
              <Chip size="small" color="info" label="Mixed FX → base INR" />
            ) : null}
          </>
        }
      />

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="primary"
            icon={AccountBalanceWalletOutlinedIcon}
            title="Expense lines"
            value={String(expenseStats.count)}
            subtitle={currentFyOnly ? 'Current FY filter' : 'All listed'}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="warning"
            icon={PaymentsOutlinedIcon}
            title="Prosohm paid Σ"
            value={financeMoney(expenseStats.prosohmSum, 'INR')}
            subtitle="Base INR · FX at purchase"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="info"
            icon={StorefrontOutlinedIcon}
            title="Customer paid Σ"
            value={financeMoney(expenseStats.customerSum, 'INR')}
            subtitle="Base INR · pass-through"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="success"
            icon={EventRepeatOutlinedIcon}
            title="With renewals"
            value={String(expenseStats.renewals)}
            subtitle="Renewal date set"
          />
        </Grid>
      </Grid>

      <FinanceSection
        title={editingId ? 'Edit expense / subscription' : 'Add expense / subscription'}
        subtitle="Team and date of purchase are required. Use Common (Corporate / Management) for shared HQ spend — delivery teams keep direct OpEx for team P&L. Overview counts current Indian FY (Apr–Mar) only."
      >
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap', mb: 1 }}>
          <FormControl size="small" sx={{ minWidth: 240 }} required>
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
                  {teamSelectLabel(team.name)}
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
      </FinanceSection>

      <FinanceSection
        title="Expense lines"
        subtitle={
          showGrouped
            ? 'Grouped by team for P&L: Common (shared) first, then delivery teams. Prior-FY purchases stay listed but do not hit Overview.'
            : 'Edit or delete rows. Turn on Advanced (All teams) to group by team vs Common. Prior-FY purchases stay listed but do not hit Overview.'
        }
        action={
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
            {!teamId ? (
              <FormControlLabel
                control={
                  <Switch
                    checked={advancedMode}
                    onChange={(e) => setAdvancedMode(e.target.checked)}
                    size="small"
                  />
                }
                label="Advanced"
              />
            ) : null}
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
        }
      >
        <Stack spacing={1.25}>
          {expenses.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No expenses yet — add the first line above.
            </Typography>
          ) : showGrouped ? (
            expenseGroups.map((group) => (
              <Box key={group.key} sx={{ mb: 0.5 }}>
                <Stack
                  direction="row"
                  spacing={1}
                  useFlexGap
                  sx={{ flexWrap: 'wrap', alignItems: 'center', mb: 1 }}
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    {group.isCommon ? 'Common (shared HQ)' : group.key}
                  </Typography>
                  <Chip size="small" variant="outlined" label={`${group.rows.length} lines`} />
                  <Chip
                    size="small"
                    color={group.isCommon ? 'secondary' : 'default'}
                    variant="outlined"
                    label={`Prosohm Σ ${financeMoney(group.prosohmSum, 'INR')}`}
                  />
                </Stack>
                <Stack spacing={1.25}>{group.rows.map((row) => renderExpenseRow(row))}</Stack>
              </Box>
            ))
          ) : (
            expenses.map((row) => renderExpenseRow(row))
          )}
        </Stack>
      </FinanceSection>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete expense?"
        message="This removes the expense from Financial Planning lists and Overview totals (soft-delete)."
        recordName={
          deleteTarget
            ? `${deleteTarget.name} · ${
                deleteTarget.is_common || deleteTarget.display_group === 'Common'
                  ? 'Common'
                  : deleteTarget.display_group ||
                    deleteTarget.team_name ||
                    (deleteTarget.team_id
                      ? teamNameById.get(deleteTarget.team_id) || 'Team'
                      : 'Team')
              } · ${deleteTarget.amount} ${deleteTarget.currency_code} · Paid by ${deleteTarget.paid_by}`
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
