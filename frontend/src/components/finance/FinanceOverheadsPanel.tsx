import { useMemo, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
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
import AddOutlinedIcon from '@mui/icons-material/AddOutlined';
import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
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
import {
  FinanceKpiBreakdownDrawer,
  type KpiBreakdownMetric,
} from './FinanceKpiBreakdownDrawer';

/** Catalogue categories — each holds many named expense lines. */
const OVERHEAD_CATEGORIES: Array<{
  code: string;
  label: string;
  frequency: 'monthly' | 'quarterly' | 'yearly';
  hint: string;
  namePlaceholder: string;
}> = [
  {
    code: 'RENT',
    label: 'Rent',
    frequency: 'monthly',
    hint: 'Facilities & leases',
    namePlaceholder: 'e.g. HQ lease, annex, parking',
  },
  {
    code: 'UTILITIES',
    label: 'Utilities',
    frequency: 'monthly',
    hint: 'Power, water, genset',
    namePlaceholder: 'e.g. Electricity, water, diesel',
  },
  {
    code: 'INTERNET',
    label: 'Internet',
    frequency: 'monthly',
    hint: 'Connectivity',
    namePlaceholder: 'e.g. Primary ISP, backup link',
  },
  {
    code: 'OFFICE',
    label: 'Office expenses',
    frequency: 'monthly',
    hint: 'Supplies & admin',
    namePlaceholder: 'e.g. Stationery, pantry',
  },
  {
    code: 'MAINTENANCE',
    label: 'Maintenance',
    frequency: 'monthly',
    hint: 'Facility & equipment',
    namePlaceholder: 'e.g. AMC, HVAC service',
  },
  {
    code: 'CLOUD',
    label: 'Cloud',
    frequency: 'monthly',
    hint: 'Hosting & SaaS infra',
    namePlaceholder: 'e.g. AWS, Azure, Google Workspace',
  },
  {
    code: 'SW_LICENSES',
    label: 'Software licenses',
    frequency: 'yearly',
    hint: 'CAD / engineering tools',
    namePlaceholder: 'e.g. NX Mach 3, AutoCAD, SolidWorks',
  },
  {
    code: 'SW_RENEWALS',
    label: 'Software renewals',
    frequency: 'yearly',
    hint: 'Renewal cycles',
    namePlaceholder: 'e.g. NX renewal FY26',
  },
  {
    code: 'INSURANCE',
    label: 'Insurance',
    frequency: 'yearly',
    hint: 'Corporate policies',
    namePlaceholder: 'e.g. Property, liability',
  },
  {
    code: 'TRAINING',
    label: 'Training',
    frequency: 'yearly',
    hint: 'Learning',
    namePlaceholder: 'e.g. Certification cohort',
  },
  {
    code: 'TRAVEL',
    label: 'Travel',
    frequency: 'yearly',
    hint: 'Business travel',
    namePlaceholder: 'e.g. Client visit Q2',
  },
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

type LineDraft = {
  name: string;
  amount: string;
  frequency: string;
  vendor_name: string;
};

type AddDraft = {
  name: string;
  amount: string;
  vendor_name: string;
};

const emptyAdd = (): AddDraft => ({ name: '', amount: '', vendor_name: '' });

function lineDraftFromExpense(row: OverheadExpense): LineDraft {
  return {
    name: row.name ?? '',
    amount: row.amount === null || row.amount === undefined ? '' : String(row.amount),
    frequency: row.frequency || 'monthly',
    vendor_name: row.vendor_name ?? '',
  };
}

export function FinanceOverheadsPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const dashQ = teamQueryParam(teamId);
  const [expanded, setExpanded] = useState<string | false>('SW_LICENSES');
  const [lineDrafts, setLineDrafts] = useState<Record<string, LineDraft>>({});
  const [addDrafts, setAddDrafts] = useState<Record<string, AddDraft>>({});
  const [showCustom, setShowCustom] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<OverheadExpense | null>(null);
  const [breakdownMetric, setBreakdownMetric] = useState<KpiBreakdownMetric | null>(null);
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
    const map = new Map<string, OverheadExpense[]>();
    for (const row of expenses) {
      const list = map.get(row.cost_centre_id) ?? [];
      list.push(row);
      map.set(row.cost_centre_id, list);
    }
    for (const list of map.values()) {
      list.sort((a, b) => a.name.localeCompare(b.name));
    }
    return map;
  }, [expenses]);

  const categoryCodes = new Set(OVERHEAD_CATEGORIES.map((c) => c.code));
  const otherExpenses = expenses.filter((row) => {
    const centre = centres.find((c) => c.id === row.cost_centre_id);
    const code = (centre?.code || '').toUpperCase();
    return !code || !categoryCodes.has(code);
  });

  const draftFor = (row: OverheadExpense): LineDraft =>
    lineDrafts[row.id] ?? lineDraftFromExpense(row);

  const addFor = (code: string): AddDraft => addDrafts[code] ?? emptyAdd();

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['finance-overhead-expenses'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-expenses'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
  };

  const defaultTeamId = corporateId || managementId || '';

  const createLineMutation = useMutation({
    mutationFn: async (payload: {
      code: string;
      name: string;
      amount: number;
      vendor_name?: string;
      frequency: string;
    }) => {
      const centre = centreByCode.get(payload.code);
      if (!centre) throw new Error(`Cost centre ${payload.code} is not seeded.`);
      if (!defaultTeamId) throw new Error('Management / Corporate team not ready.');
      const purchase = new Date().toISOString().slice(0, 10);
      return (
        await apiClient.post('/finance/expenses', {
          team_id: defaultTeamId,
          cost_centre_id: centre.id,
          name: payload.name,
          amount: payload.amount,
          currency_code: 'INR',
          nature: 'opex',
          frequency: payload.frequency,
          paid_by: 'prosohm',
          vendor_name: payload.vendor_name || null,
          purchase_date: purchase,
          start_date: purchase,
          is_recurring: true,
          notify_enabled: false,
        })
      ).data;
    },
    onSuccess: (_data, vars) => {
      showSuccess(`Added line under ${vars.code}`);
      setAddDrafts((prev) => ({ ...prev, [vars.code]: emptyAdd() }));
      invalidate();
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not add overhead line'));
    },
  });

  const updateLineMutation = useMutation({
    mutationFn: async (payload: { id: string; draft: LineDraft }) => {
      const amount = Number(String(payload.draft.amount).replace(/,/g, ''));
      if (!payload.draft.name.trim()) throw new Error('Name is required.');
      if (!Number.isFinite(amount) || amount < 0) throw new Error('Amount must be a valid number.');
      return (
        await apiClient.patch(`/finance/expenses/${payload.id}`, {
          name: payload.draft.name.trim(),
          amount,
          frequency: payload.draft.frequency,
          vendor_name: payload.draft.vendor_name.trim() || null,
          is_recurring: true,
          paid_by: 'prosohm',
          nature: 'opex',
        })
      ).data;
    },
    onSuccess: (_data, vars) => {
      showSuccess('Overhead line updated');
      setLineDrafts((prev) => {
        const next = { ...prev };
        delete next[vars.id];
        return next;
      });
      invalidate();
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not update overhead line'));
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

  const submitAdd = (code: string, defaultFrequency: string) => {
    const draft = addFor(code);
    const name = draft.name.trim();
    const amount = Number(String(draft.amount).replace(/,/g, ''));
    if (!name) {
      showError('Enter a line name (e.g. NX Mach 3).');
      return;
    }
    if (!Number.isFinite(amount) || amount < 0) {
      showError('Enter a valid amount.');
      return;
    }
    createLineMutation.mutate({
      code,
      name,
      amount,
      vendor_name: draft.vendor_name.trim() || undefined,
      frequency: defaultFrequency,
    });
  };

  const currency = dashboardQuery.data?.base_currency ?? 'INR';
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
        subtitle="Each category holds many named lines (licenses, rents, utilities…). Click a KPI card to see what accumulates into that number. Pool = Management + Corporate salaries + Prosohm OpEx ÷ delivery billable FTE."
        chips={
          <>
            {dashboardQuery.data?.planning_fy_label ? (
              <Chip
                size="small"
                label={`FY ${dashboardQuery.data.planning_fy_label}`}
                sx={{ fontWeight: 700 }}
              />
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
            subtitle="Click for people breakdown"
            onClick={() => setBreakdownMetric('overhead_salaries')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="warning"
            icon={ApartmentOutlinedIcon}
            title="Overhead OpEx"
            value={financeMoney(opexInr, currency)}
            subtitle="Click for ranked spend"
            onClick={() => setBreakdownMetric('overhead_opex')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="primary"
            icon={PaymentsOutlinedIcon}
            title="Pool / month"
            value={financeMoney(poolInr, currency)}
            subtitle="Click for pool mix"
            onClick={() => setBreakdownMetric('overhead_pool')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="success"
            icon={PersonOutlineOutlinedIcon}
            title="Cost per resource"
            value={financeMoney(cprInr, currency)}
            subtitle="Click for CPR build-up"
            onClick={() => setBreakdownMetric('overhead_cpr')}
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <FinanceSection title="Pool mix" subtitle="What drives the monthly overhead pool">
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
                No pool yet — add category lines below or salaries on People costs.
              </Typography>
            )}
          </FinanceSection>
        </Grid>

        <Grid size={{ xs: 12, md: 8 }}>
          <FinanceSection
            title="Overhead categories"
            subtitle="Expand a category to manage multiple lines — e.g. several software licenses under one centre."
          >
            <Stack spacing={1}>
              {OVERHEAD_CATEGORIES.map((cat) => {
                const centre = centreByCode.get(cat.code);
                const lines = centre ? (expensesByCentreId.get(centre.id) ?? []) : [];
                const total = lines.reduce((sum, row) => sum + toFiniteNumber(row.amount), 0);
                const missingCentre = !centre;
                return (
                  <Accordion
                    key={cat.code}
                    disableGutters
                    elevation={0}
                    expanded={expanded === cat.code}
                    onChange={(_e, isExpanded) => setExpanded(isExpanded ? cat.code : false)}
                    sx={{
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: `${designTokens.radius.md}px !important`,
                      '&:before': { display: 'none' },
                      overflow: 'hidden',
                    }}
                  >
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Stack
                        direction="row"
                        spacing={1}
                        sx={{
                          alignItems: 'center',
                          flexWrap: 'wrap',
                          width: '100%',
                          pr: 1,
                          gap: 1,
                        }}
                      >
                        <Typography sx={{ fontWeight: 700, flex: 1, minWidth: 140 }}>
                          {cat.label}
                        </Typography>
                        <Chip size="small" label={cat.code} variant="outlined" />
                        <Chip
                          size="small"
                          color={lines.length ? 'primary' : 'default'}
                          label={`${lines.length} line${lines.length === 1 ? '' : 's'}`}
                        />
                        <Typography variant="body2" sx={{ fontWeight: 600, minWidth: 100 }}>
                          {financeMoney(total, currency)}
                        </Typography>
                      </Stack>
                    </AccordionSummary>
                    <AccordionDetails sx={{ pt: 0 }}>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
                        {cat.hint} · default {cat.frequency}
                        {missingCentre ? ' · cost centre not seeded' : ''}
                      </Typography>

                      <Stack spacing={1.25} sx={{ mb: 2 }}>
                        {lines.length === 0 ? (
                          <Typography variant="body2" color="text.secondary">
                            No lines yet — add the first one below.
                          </Typography>
                        ) : (
                          lines.map((row) => {
                            const draft = draftFor(row);
                            return (
                              <Box
                                key={row.id}
                                sx={{
                                  p: 1.25,
                                  borderRadius: `${designTokens.radius.md}px`,
                                  border: '1px solid',
                                  borderColor: 'divider',
                                  bgcolor: 'background.paper',
                                }}
                              >
                                <Stack
                                  direction={{ xs: 'column', sm: 'row' }}
                                  spacing={1}
                                  sx={{ flexWrap: 'wrap', alignItems: { sm: 'center' } }}
                                >
                                  <TextField
                                    size="small"
                                    label="Line name"
                                    value={draft.name}
                                    onChange={(e) =>
                                      setLineDrafts((prev) => ({
                                        ...prev,
                                        [row.id]: { ...draft, name: e.target.value },
                                      }))
                                    }
                                    sx={{ flex: 2, minWidth: 160 }}
                                  />
                                  <TextField
                                    size="small"
                                    label="Amount"
                                    value={draft.amount}
                                    onChange={(e) =>
                                      setLineDrafts((prev) => ({
                                        ...prev,
                                        [row.id]: { ...draft, amount: e.target.value },
                                      }))
                                    }
                                    sx={{ width: 120 }}
                                  />
                                  <FormControl size="small" sx={{ minWidth: 110 }}>
                                    <InputLabel>Freq</InputLabel>
                                    <Select
                                      label="Freq"
                                      value={draft.frequency}
                                      onChange={(e) =>
                                        setLineDrafts((prev) => ({
                                          ...prev,
                                          [row.id]: { ...draft, frequency: e.target.value },
                                        }))
                                      }
                                    >
                                      <MenuItem value="monthly">Monthly</MenuItem>
                                      <MenuItem value="quarterly">Quarterly</MenuItem>
                                      <MenuItem value="yearly">Yearly</MenuItem>
                                    </Select>
                                  </FormControl>
                                  <TextField
                                    size="small"
                                    label="Vendor"
                                    value={draft.vendor_name}
                                    onChange={(e) =>
                                      setLineDrafts((prev) => ({
                                        ...prev,
                                        [row.id]: { ...draft, vendor_name: e.target.value },
                                      }))
                                    }
                                    sx={{ flex: 1, minWidth: 120 }}
                                  />
                                  <Button
                                    size="small"
                                    variant="contained"
                                    disabled={updateLineMutation.isPending}
                                    onClick={() =>
                                      updateLineMutation.mutate({ id: row.id, draft })
                                    }
                                  >
                                    Update
                                  </Button>
                                  <Button
                                    size="small"
                                    color="error"
                                    variant="outlined"
                                    onClick={() => setDeleteTarget(row)}
                                  >
                                    Delete
                                  </Button>
                                </Stack>
                              </Box>
                            );
                          })
                        )}
                      </Stack>

                      <Box
                        sx={{
                          p: 1.5,
                          borderRadius: `${designTokens.radius.md}px`,
                          border: '1px dashed',
                          borderColor: 'primary.light',
                          bgcolor: 'action.hover',
                        }}
                      >
                        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
                          Add line
                        </Typography>
                        <Stack
                          direction={{ xs: 'column', sm: 'row' }}
                          spacing={1}
                          sx={{ flexWrap: 'wrap', alignItems: { sm: 'center' } }}
                        >
                          <TextField
                            size="small"
                            label="Name"
                            placeholder={cat.namePlaceholder}
                            value={addFor(cat.code).name}
                            disabled={missingCentre || createLineMutation.isPending}
                            onChange={(e) =>
                              setAddDrafts((prev) => ({
                                ...prev,
                                [cat.code]: { ...addFor(cat.code), name: e.target.value },
                              }))
                            }
                            sx={{ flex: 2, minWidth: 180 }}
                          />
                          <TextField
                            size="small"
                            label="Amount"
                            value={addFor(cat.code).amount}
                            disabled={missingCentre || createLineMutation.isPending}
                            onChange={(e) =>
                              setAddDrafts((prev) => ({
                                ...prev,
                                [cat.code]: { ...addFor(cat.code), amount: e.target.value },
                              }))
                            }
                            sx={{ width: 120 }}
                          />
                          <TextField
                            size="small"
                            label="Vendor (optional)"
                            value={addFor(cat.code).vendor_name}
                            disabled={missingCentre || createLineMutation.isPending}
                            onChange={(e) =>
                              setAddDrafts((prev) => ({
                                ...prev,
                                [cat.code]: {
                                  ...addFor(cat.code),
                                  vendor_name: e.target.value,
                                },
                              }))
                            }
                            sx={{ flex: 1, minWidth: 140 }}
                          />
                          <Button
                            size="small"
                            variant="contained"
                            startIcon={<AddOutlinedIcon />}
                            disabled={missingCentre || createLineMutation.isPending}
                            onClick={() => submitAdd(cat.code, cat.frequency)}
                          >
                            Add
                          </Button>
                        </Stack>
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                );
              })}
            </Stack>
          </FinanceSection>
        </Grid>
      </Grid>

      {otherExpenses.length > 0 ? (
        <FinanceSection
          title="Other overhead OpEx"
          subtitle="Lines on Management / Corporate whose cost centre is outside the catalogue above"
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
                    {row.vendor_name ? ` · ${row.vendor_name}` : ''}
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
        subtitle="Escape hatch for centres not listed above"
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
            Prefer category accordions above for multi-line OpEx (licenses, rents, utilities).
          </Typography>
        ) : null}
      </FinanceSection>

      <FinanceKpiBreakdownDrawer
        open={Boolean(breakdownMetric)}
        metric={breakdownMetric}
        teamId={teamId}
        onClose={() => setBreakdownMetric(null)}
      />

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
