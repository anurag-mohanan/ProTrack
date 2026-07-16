import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Collapse,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import PaymentsOutlinedIcon from '@mui/icons-material/PaymentsOutlined';
import PersonOutlineOutlinedIcon from '@mui/icons-material/PersonOutlineOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { toFiniteNumber } from '../../utils/format';
import { designTokens } from '../../theme/designTokens';
import { LoadingState } from '../common/LoadingState';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { AnalyticsDonutChart } from '../analytics/AnalyticsCharts';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { teamQueryParam } from './FinanceTeamFilter';
import {
  FinanceHeroBanner,
  FinanceSection,
  financeMoney,
} from './FinanceCockpitPrimitives';

/** HQ OpEx lines Finance wants pre-shown for amount entry (maps to seeded cost centres). */
const DEFAULT_OVERHEAD_PLACEHOLDERS: Array<{
  code: string;
  label: string;
  frequency: 'monthly' | 'quarterly' | 'yearly';
  hint: string;
}> = [
  { code: 'RENT', label: 'Rent', frequency: 'monthly', hint: 'Office / facility rent' },
  { code: 'UTILITIES', label: 'Utilities', frequency: 'monthly', hint: 'Power, water, shared utilities' },
  { code: 'INTERNET', label: 'Internet', frequency: 'monthly', hint: 'Connectivity & WAN' },
  { code: 'OFFICE', label: 'Office expenses', frequency: 'monthly', hint: 'Supplies & admin OpEx' },
  { code: 'MAINTENANCE', label: 'Maintenance', frequency: 'monthly', hint: 'Facility & equipment upkeep' },
  { code: 'CLOUD', label: 'Cloud', frequency: 'monthly', hint: 'Hosting & SaaS infra' },
  { code: 'SW_LICENSES', label: 'Software licenses', frequency: 'yearly', hint: 'CAD / tools licenses' },
  { code: 'INSURANCE', label: 'Insurance', frequency: 'yearly', hint: 'Corporate policies' },
  { code: 'TRAINING', label: 'Training', frequency: 'yearly', hint: 'Learning & certifications' },
  { code: 'TRAVEL', label: 'Travel', frequency: 'yearly', hint: 'Business travel OpEx' },
];

type OverheadExpense = {
  id: string;
  cost_centre_id: string;
  name: string;
  amount: number | string;
  currency_code: string;
  nature: string;
  paid_by: string;
  vendor_name?: string | null;
  purchase_date?: string | null;
  end_date?: string | null;
  is_recurring?: boolean;
  frequency?: string;
  team_id?: string | null;
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
  };
};

type DraftMap = Record<string, string>;

export function FinanceOverheadsPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const dashQ = teamQueryParam(teamId);
  const [drafts, setDrafts] = useState<DraftMap>({});
  const [showCustom, setShowCustom] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<OverheadExpense | null>(null);
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

  const centres = costCentresQuery.data ?? [];
  const centreByCode = useMemo(() => {
    const map = new Map<string, CostCentre>();
    for (const row of centres) {
      if (row.code) map.set(row.code.toUpperCase(), row);
    }
    return map;
  }, [centres]);

  const expenses = useMemo(
    () =>
      (expensesQuery.data ?? []).filter(
        (row) => row.paid_by === 'prosohm' && row.nature === 'opex',
      ),
    [expensesQuery.data],
  );

  const expensesByCentreId = useMemo(() => {
    const map = new Map<string, OverheadExpense>();
    for (const row of expenses) {
      const prev = map.get(row.cost_centre_id);
      if (!prev || toFiniteNumber(row.amount) >= toFiniteNumber(prev.amount)) {
        map.set(row.cost_centre_id, row);
      }
    }
    return map;
  }, [expenses]);

  useEffect(() => {
    const next: DraftMap = {};
    for (const ph of DEFAULT_OVERHEAD_PLACEHOLDERS) {
      const centre = centreByCode.get(ph.code);
      if (!centre) continue;
      const existing = expensesByCentreId.get(centre.id);
      next[ph.code] = existing
        ? String(existing.amount ?? '')
        : (drafts[ph.code] ?? '');
    }
    setDrafts((prev) => {
      const merged = { ...next };
      for (const ph of DEFAULT_OVERHEAD_PLACEHOLDERS) {
        if (prev[ph.code] !== undefined && !expensesByCentreId.get(centreByCode.get(ph.code)?.id ?? '')) {
          // keep in-progress typing for empty placeholders
          if (prev[ph.code] !== '' && next[ph.code] === '') merged[ph.code] = prev[ph.code];
        }
      }
      return merged;
    });
    // Intentionally sync when expenses / centres change — not on every drafts keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [centreByCode, expensesByCentreId]);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['finance-overhead-expenses'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-expenses'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
  };

  const savePlaceholderMutation = useMutation({
    mutationFn: async (code: string) => {
      const ph = DEFAULT_OVERHEAD_PLACEHOLDERS.find((row) => row.code === code);
      const centre = centreByCode.get(code);
      if (!ph || !centre) throw new Error(`Cost centre ${code} is not seeded.`);
      const team = corporateId || managementId;
      if (!team) throw new Error('Management / Corporate team not ready.');
      const amountRaw = (drafts[code] ?? '').trim().replace(/,/g, '');
      if (!amountRaw) throw new Error('Enter an amount for this overhead line.');
      const amount = Number(amountRaw);
      if (!Number.isFinite(amount) || amount < 0) throw new Error('Amount must be a valid number.');

      const existing = expensesByCentreId.get(centre.id);
      const purchase = new Date().toISOString().slice(0, 10);
      if (existing) {
        return (
          await apiClient.patch(`/finance/expenses/${existing.id}`, {
            amount,
            name: existing.name || ph.label,
            frequency: existing.frequency || ph.frequency,
            is_recurring: true,
            paid_by: 'prosohm',
            nature: 'opex',
          })
        ).data;
      }
      return (
        await apiClient.post('/finance/expenses', {
          team_id: team,
          cost_centre_id: centre.id,
          name: ph.label,
          amount,
          currency_code: 'INR',
          nature: 'opex',
          frequency: ph.frequency,
          paid_by: 'prosohm',
          purchase_date: purchase,
          start_date: purchase,
          is_recurring: true,
          notify_enabled: false,
        })
      ).data;
    },
    onSuccess: () => {
      showSuccess('Overhead line saved');
      invalidate();
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not save overhead line'));
    },
  });

  const createCustomMutation = useMutation({
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
      showSuccess('Custom recurring overhead saved');
      setForm((prev) => ({ ...prev, name: '', amount: '', end_date: '' }));
      invalidate();
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not save overhead cost'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/finance/expenses/${id}`);
    },
    onSuccess: () => {
      showSuccess('Overhead line removed');
      setDeleteTarget(null);
      invalidate();
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not delete overhead line'));
    },
  });

  const currency = dashboardQuery.data?.base_currency ?? 'INR';
  const placeholderCodes = new Set(DEFAULT_OVERHEAD_PLACEHOLDERS.map((p) => p.code));
  const otherExpenses = expenses.filter((row) => {
    const centre = centres.find((c) => c.id === row.cost_centre_id);
    const code = (centre?.code || '').toUpperCase();
    return !code || !placeholderCodes.has(code);
  });

  const salaryInr =
    toFiniteNumber(overhead?.overhead_management_salary_inr) ||
    toFiniteNumber(overhead?.overhead_salary_inr);
  const opexInr = toFiniteNumber(overhead?.overhead_opex_inr);
  const poolInr = toFiniteNumber(overhead?.overhead_pool_monthly_inr);
  const cprInr = toFiniteNumber(overhead?.overhead_cost_per_resource_inr);
  const billableN = overhead?.billable_resource_count ?? 0;

  if (dashboardQuery.isLoading) {
    return <LoadingState message="Loading overheads…" />;
  }

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="Overheads cockpit"
        subtitle="HQ burden rate: Management + Corporate salaries and Prosohm OpEx ÷ delivery billable FTE. Enter default lines below — CPR updates live for bids and P&L."
        chips={
          <>
            {dashboardQuery.data?.planning_fy_label ? (
              <Chip size="small" label={`FY ${dashboardQuery.data.planning_fy_label}`} sx={{ fontWeight: 700 }} />
            ) : null}
            <Chip
              size="small"
              color="info"
              label={`${billableN} delivery billable FTE`}
              sx={{ fontWeight: 700 }}
            />
            <Chip
              size="small"
              variant="outlined"
              label={`${overhead?.management_team_name ?? 'Management'} + ${overhead?.corporate_team_name ?? 'Corporate'}`}
            />
          </>
        }
      />

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="info"
            icon={GroupsOutlinedIcon}
            title="Management salaries"
            value={financeMoney(salaryInr, currency)}
            subtitle="Leaders on Management team"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="warning"
            icon={ApartmentOutlinedIcon}
            title="Overhead OpEx"
            value={financeMoney(opexInr, currency)}
            subtitle="Prosohm · current FY"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="primary"
            icon={PaymentsOutlinedIcon}
            title="Pool / month"
            value={financeMoney(poolInr, currency)}
            subtitle="Salaries + OpEx"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="success"
            icon={PersonOutlineOutlinedIcon}
            title="Cost per resource"
            value={financeMoney(cprInr, currency)}
            subtitle={`÷ ${billableN} billable FTE`}
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <FinanceSection
            title="Pool mix"
            subtitle="What drives the monthly overhead pool"
          >
            {salaryInr > 0 || opexInr > 0 ? (
              <AnalyticsDonutChart
                height={220}
                data={[
                  {
                    id: 'salary',
                    label: 'Management salaries',
                    value: salaryInr,
                    color: designTokens.semantic.primary,
                  },
                  {
                    id: 'opex',
                    label: 'HQ OpEx',
                    value: opexInr,
                    color: designTokens.semantic.warning,
                  },
                ]}
              />
            ) : (
              <Typography variant="body2" color="text.secondary">
                No pool yet — add salaries on People costs or amounts on default lines.
              </Typography>
            )}
          </FinanceSection>
        </Grid>
        <Grid size={{ xs: 12, md: 8 }}>
          <FinanceSection
            title="Default overhead lines"
            subtitle="Placeholders from the cost-centre catalogue — enter amounts to book Prosohm OpEx on Corporate (or Management if Corporate is missing)."
          >
            <Grid container spacing={1.5}>
              {DEFAULT_OVERHEAD_PLACEHOLDERS.map((ph) => {
                const centre = centreByCode.get(ph.code);
                const existing = centre ? expensesByCentreId.get(centre.id) : undefined;
                const missingCentre = !centre;
                return (
                  <Grid key={ph.code} size={{ xs: 12, sm: 6 }}>
                    <Box
                      sx={{
                        p: 1.5,
                        borderRadius: `${designTokens.radius.md}px`,
                        border: '1px solid',
                        borderColor: existing ? 'primary.light' : 'divider',
                        bgcolor: existing ? 'action.hover' : 'background.paper',
                        height: '100%',
                      }}
                    >
                      <Stack spacing={1}>
                        <Stack
                          direction="row"
                          sx={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 1 }}
                        >
                          <Box>
                            <Typography sx={{ fontWeight: 700 }}>{ph.label}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              {ph.hint} · {ph.frequency}
                            </Typography>
                          </Box>
                          <Chip size="small" label={ph.code} variant="outlined" />
                        </Stack>
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                          <TextField
                            size="small"
                            label="Amount"
                            placeholder="0"
                            value={drafts[ph.code] ?? ''}
                            disabled={missingCentre || savePlaceholderMutation.isPending}
                            onChange={(e) =>
                              setDrafts((prev) => ({ ...prev, [ph.code]: e.target.value }))
                            }
                            sx={{ flex: 1 }}
                          />
                          <Button
                            size="small"
                            variant="contained"
                            disabled={missingCentre || savePlaceholderMutation.isPending}
                            onClick={() => savePlaceholderMutation.mutate(ph.code)}
                          >
                            {existing ? 'Update' : 'Save'}
                          </Button>
                          {existing ? (
                            <Button
                              size="small"
                              color="error"
                              variant="outlined"
                              onClick={() => setDeleteTarget(existing)}
                            >
                              Delete
                            </Button>
                          ) : null}
                        </Stack>
                        {existing ? (
                          <Typography variant="caption" color="text.secondary">
                            Booked {existing.currency_code} ·{' '}
                            {existing.is_recurring ? 'Recurring' : 'One-time'}
                            {existing.purchase_date ? ` · from ${existing.purchase_date}` : ''}
                          </Typography>
                        ) : missingCentre ? (
                          <Typography variant="caption" color="warning.main">
                            Cost centre {ph.code} not seeded
                          </Typography>
                        ) : (
                          <Typography variant="caption" color="text.secondary">
                            Not booked yet — enter amount and Save
                          </Typography>
                        )}
                      </Stack>
                    </Box>
                  </Grid>
                );
              })}
            </Grid>
          </FinanceSection>
        </Grid>
      </Grid>

      {otherExpenses.length > 0 ? (
        <FinanceSection
          title="Other overhead OpEx"
          subtitle="Custom or non-catalogue lines on Management / Corporate this FY"
        >
          <Stack spacing={1}>
            {otherExpenses.map((row) => (
              <Box
                key={row.id}
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 2,
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  p: 1.25,
                  borderRadius: `${designTokens.radius.md}px`,
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Box>
                  <Typography sx={{ fontWeight: 600 }}>{row.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {financeMoney(row.amount, row.currency_code)} · {row.frequency ?? '—'}
                    {row.purchase_date ? ` · from ${row.purchase_date}` : ''}
                    {row.end_date ? ` · until ${row.end_date}` : ''}
                  </Typography>
                </Box>
                <Button size="small" color="error" variant="outlined" onClick={() => setDeleteTarget(row)}>
                  Delete
                </Button>
              </Box>
            ))}
          </Stack>
        </FinanceSection>
      ) : null}

      <FinanceSection
        title="Custom recurring overhead"
        subtitle="Escape hatch for lines outside the default catalogue"
        action={
          <Button size="small" onClick={() => setShowCustom((v) => !v)}>
            {showCustom ? 'Hide' : 'Show form'}
          </Button>
        }
      >
        <Collapse in={showCustom}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ flexWrap: 'wrap' }}>
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
              disabled={createCustomMutation.isPending}
              onClick={() => createCustomMutation.mutate()}
            >
              Save recurring
            </Button>
          </Stack>
        </Collapse>
        {!showCustom ? (
          <Typography variant="body2" color="text.secondary">
            Prefer the default lines above. Open this form only for one-off or non-catalogue OpEx.
          </Typography>
        ) : null}
      </FinanceSection>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Remove overhead line?"
        message="This soft-deletes the expense from Management / Corporate OpEx and refreshes the overhead pool."
        recordName={
          deleteTarget
            ? `${deleteTarget.name} · ${deleteTarget.currency_code} ${deleteTarget.amount}`
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
