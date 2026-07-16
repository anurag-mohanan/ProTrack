import { useMemo, useState } from 'react';
import {
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import CompareArrowsOutlinedIcon from '@mui/icons-material/CompareArrowsOutlined';
import SavingsOutlinedIcon from '@mui/icons-material/SavingsOutlined';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { formatIndianNumber, toFiniteNumber } from '../../utils/format';
import { LoadingState } from '../common/LoadingState';
import { AnalyticsBarChart } from '../analytics/AnalyticsCharts';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { designTokens } from '../../theme/designTokens';
import {
  FinanceHeroBanner,
  FinanceSection,
  financeMoney,
} from './FinanceCockpitPrimitives';

const QUARTER_KEYS = ['q1', 'q2', 'q3', 'q4'] as const;
const QUARTER_LABELS = ['Q1 Apr–Jun', 'Q2 Jul–Sep', 'Q3 Oct–Dec', 'Q4 Jan–Mar'];

/** Indian FY starts in April — return the calendar year of the current FY's April. */
export function currentFyStartYear(now = new Date()): number {
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  return month >= 4 ? year : year - 1;
}

function fyLabelFromStartYear(startYear: number): string {
  return `${startYear}-${String(startYear + 1).slice(-2)}`;
}

type PlanListItem = {
  id: string;
  name: string;
  fiscal_year_label: string;
  currency_code: string;
  tax_percent: number;
  provision_percent: number;
  status: string;
};

type PlanLine = {
  id: string;
  section: 'sales' | 'expenses' | 'resources' | 'capex';
  code: string;
  label: string;
  q1: number;
  q2: number;
  q3: number;
  q4: number;
  month_01?: number;
  month_02?: number;
  month_03?: number;
  month_04?: number;
  month_05?: number;
  month_06?: number;
  month_07?: number;
  month_08?: number;
  month_09?: number;
  month_10?: number;
  month_11?: number;
  month_12?: number;
};

type PlanDetail = PlanListItem & {
  lines: PlanLine[];
  summary: {
    sales_fy: string;
    expenses_fy: string;
    gain_loss: string;
    after_tax: string;
    provision_amount: string;
    gain_loss_after_provision: string;
    tax_percent: string;
    provision_percent: string;
    sales_by_quarter?: Record<string, string>;
    expenses_by_quarter?: Record<string, string>;
  };
  line_totals: Record<string, string>;
};

function lineTotal(line: PlanLine): number {
  return QUARTER_KEYS.reduce((sum, key) => sum + Number(line[key] || 0), 0);
}

function PlanSectionGrid({
  title,
  lines,
  onCellBlur,
}: {
  title: string;
  lines: PlanLine[];
  onCellBlur: (lineId: string, field: (typeof QUARTER_KEYS)[number], value: string) => void;
}) {
  return (
    <FinanceSection title={title} subtitle="Edit quarterly amounts — stored as even monthly split">
        <TableContainer sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ minWidth: 140, fontWeight: 700 }}>Line</TableCell>
                {QUARTER_LABELS.map((label) => (
                  <TableCell key={label} align="right" sx={{ minWidth: 120, fontWeight: 700 }}>
                    {label}
                  </TableCell>
                ))}
                <TableCell align="right" sx={{ minWidth: 100, fontWeight: 700 }}>
                  Total
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {lines.map((line) => (
                <TableRow key={line.id} hover>
                  <TableCell sx={{ fontWeight: 600 }}>{line.label}</TableCell>
                  {QUARTER_KEYS.map((key) => (
                    <TableCell key={key} align="right" sx={{ p: 0.5 }}>
                      <TextField
                        size="small"
                        defaultValue={Number(line[key] || 0)}
                        key={`${line.id}-${key}-${Number(line[key] || 0)}`}
                        slotProps={{
                          htmlInput: { style: { textAlign: 'right' } },
                        }}
                        onBlur={(event) => onCellBlur(line.id, key, event.target.value)}
                      />
                    </TableCell>
                  ))}
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {formatIndianNumber(lineTotal(line))}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
    </FinanceSection>
  );
}

export function AnnualPlanPanel() {
  const { showError, showSuccess } = useToast();
  const queryClient = useQueryClient();
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [createOpen, setCreateOpen] = useState(false);
  const defaultFyStart = currentFyStartYear();
  const [newName, setNewName] = useState(`FY ${fyLabelFromStartYear(defaultFyStart)}`);
  const [newYear, setNewYear] = useState(defaultFyStart);
  const [taxPercent, setTaxPercent] = useState('30');
  const [provisionPercent, setProvisionPercent] = useState('20');

  const plansQuery = useQuery({
    queryKey: ['finance-plans'],
    queryFn: async () => (await apiClient.get<PlanListItem[]>('/finance/plans')).data,
  });

  const activePlanId = selectedPlanId || plansQuery.data?.[0]?.id || '';

  const detailQuery = useQuery({
    queryKey: ['finance-plan', activePlanId],
    enabled: Boolean(activePlanId),
    queryFn: async () => (await apiClient.get<PlanDetail>(`/finance/plans/${activePlanId}`)).data,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['finance-plans'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-plan', activePlanId] });
    void queryClient.invalidateQueries({ queryKey: ['finance-plan-vs-actual', activePlanId] });
  };

  const createMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post<PlanDetail>('/finance/plans', {
          name: newName,
          fiscal_year_start_year: newYear,
          fy_start_month: 4,
          tax_percent: Number(taxPercent),
          provision_percent: Number(provisionPercent),
        })
      ).data,
    onSuccess: (plan) => {
      showSuccess(`Created plan FY ${plan.fiscal_year_label}`);
      setSelectedPlanId(plan.id);
      setCreateOpen(false);
      invalidate();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not create plan');
    },
  });

  const settingsMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.patch(`/finance/plans/${activePlanId}`, {
          tax_percent: Number(taxPercent),
          provision_percent: Number(provisionPercent),
        })
      ).data,
    onSuccess: () => {
      showSuccess('Plan settings saved');
      invalidate();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not save settings');
    },
  });

  const cellMutation = useMutation({
    mutationFn: async (payload: {
      lineId: string;
      field: (typeof QUARTER_KEYS)[number];
      value: number;
    }) =>
      apiClient.put(`/finance/plans/${activePlanId}/lines/${payload.lineId}`, {
        [payload.field]: payload.value,
      }),
    onSuccess: () => invalidate(),
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not update cell');
    },
  });

  const syncRenewalsMutation = useMutation({
    mutationFn: async () =>
      (await apiClient.post(`/finance/plans/${activePlanId}/sync-renewals`)).data,
    onSuccess: () => {
      showSuccess('Renewals synced into expense quarters');
      invalidate();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not sync renewals');
    },
  });

  const seedLiveMutation = useMutation({
    mutationFn: async () =>
      (await apiClient.post(`/finance/plans/${activePlanId}/seed-from-live`)).data,
    onSuccess: () => {
      showSuccess('Wages and Overhead seeded from live costs');
      invalidate();
      void queryClient.invalidateQueries({ queryKey: ['finance-plan-vs-actual', activePlanId] });
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not seed from live costs');
    },
  });

  const cloneMutation = useMutation({
    mutationFn: async (scenarioName: string) =>
      (
        await apiClient.post(`/finance/plans/${activePlanId}/clone`, {
          scenario_name: scenarioName,
        })
      ).data,
    onSuccess: (plan: PlanDetail) => {
      showSuccess(`Scenario created: ${plan.name}`);
      setSelectedPlanId(plan.id);
      invalidate();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not clone plan');
    },
  });

  const varianceQuery = useQuery({
    queryKey: ['finance-plan-vs-actual', activePlanId],
    enabled: Boolean(activePlanId),
    queryFn: async () =>
      (await apiClient.get(`/finance/plans/${activePlanId}/plan-vs-actual`)).data as {
        months_elapsed: number;
        months_remaining: number;
        plan_sales_ytd: string;
        actual_sales_ytd: string;
        sales_variance_ytd: string;
        plan_expenses_ytd: string;
        actual_expenses_ytd: string;
        expenses_variance_ytd: string;
        plan_gain_loss_ytd: string;
        actual_gain_loss_ytd: string;
        gain_loss_variance_ytd: string;
        rolling_forecast_sales_fy: string;
        rolling_forecast_expenses_fy: string;
        rolling_forecast_gain_loss_fy: string;
        methodology: string;
      },
  });

  const salesLines = useMemo(
    () => (detailQuery.data?.lines ?? []).filter((line: PlanLine) => line.section === 'sales'),
    [detailQuery.data],
  );
  const expenseLines = useMemo(
    () => (detailQuery.data?.lines ?? []).filter((line: PlanLine) => line.section === 'expenses'),
    [detailQuery.data],
  );

  if (plansQuery.isLoading) return <LoadingState message="Loading annual plans…" />;

  const currency = detailQuery.data?.currency_code ?? 'INR';
  const pva = varianceQuery.data;

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="Annual plan workbook"
        subtitle="Quarterly Sales & Expenses (Apr–Mar). Charts show Adaptive-style Plan vs Actual; grids stay the source of truth for edits."
      />
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        sx={{ alignItems: { sm: 'center' }, flexWrap: 'wrap' }}
      >
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel id="plan-select">Fiscal year plan</InputLabel>
          <Select
            labelId="plan-select"
            label="Fiscal year plan"
            value={activePlanId}
            onChange={(event) => {
              setSelectedPlanId(event.target.value);
              const plan = plansQuery.data?.find((row: PlanListItem) => row.id === event.target.value);
              if (plan) {
                setTaxPercent(String(plan.tax_percent));
                setProvisionPercent(String(plan.provision_percent));
              }
            }}
          >
            {(plansQuery.data ?? []).map((plan: PlanListItem) => (
              <MenuItem key={plan.id} value={plan.id}>
                FY {plan.fiscal_year_label} — {plan.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button
          variant="contained"
          onClick={() => {
            const fy = currentFyStartYear();
            setNewYear(fy);
            setNewName(`FY ${fyLabelFromStartYear(fy)}`);
            setCreateOpen(true);
          }}
        >
          Create Plan
        </Button>
        {activePlanId ? (
          <>
            <Button
              variant="outlined"
              disabled={syncRenewalsMutation.isPending}
              onClick={() => syncRenewalsMutation.mutate()}
            >
              Sync software renewals
            </Button>
            <Button
              variant="outlined"
              disabled={seedLiveMutation.isPending}
              onClick={() => seedLiveMutation.mutate()}
            >
              Seed wages & overhead
            </Button>
            <Button
              variant="outlined"
              disabled={cloneMutation.isPending}
              onClick={() => {
                const name = window.prompt('Scenario name (e.g. Stretch, Downside)', 'Stretch');
                if (name?.trim()) cloneMutation.mutate(name.trim());
              }}
            >
              Clone scenario
            </Button>
          </>
        ) : null}
      </Stack>

      {!activePlanId ? (
        <Typography color="text.secondary">
          No plan yet for this year. Click <strong>Create Plan</strong> for FY{' '}
          {fyLabelFromStartYear(currentFyStartYear())} (April {currentFyStartYear()} – March{' '}
          {currentFyStartYear() + 1}), then type quarterly Sales and Expenses.
        </Typography>
      ) : detailQuery.isLoading ? (
        <LoadingState message="Loading plan…" />
      ) : detailQuery.data ? (
        <>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" sx={{ mb: 1.5, fontWeight: 600 }}>
                Settings (FY {detailQuery.data.fiscal_year_label})
              </Typography>
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                spacing={1.5}
                sx={{ alignItems: { sm: 'center' } }}
              >
                <TextField
                  size="small"
                  label="Tax %"
                  value={taxPercent}
                  onChange={(event) => setTaxPercent(event.target.value)}
                  sx={{ width: 120 }}
                />
                <TextField
                  size="small"
                  label="Provision %"
                  value={provisionPercent}
                  onChange={(event) => setProvisionPercent(event.target.value)}
                  sx={{ width: 140 }}
                />
                <Button
                  variant="outlined"
                  onClick={() => settingsMutation.mutate()}
                  disabled={settingsMutation.isPending}
                >
                  Save settings
                </Button>
              </Stack>
            </CardContent>
          </Card>

          <PlanSectionGrid
            title="Sales"
            lines={salesLines}
            onCellBlur={(lineId, field, value) => {
              const numeric = Number(String(value).replace(/,/g, ''));
              if (Number.isNaN(numeric)) {
                showError('Enter a valid number');
                return;
              }
              cellMutation.mutate({ lineId, field, value: numeric });
            }}
          />
          <PlanSectionGrid
            title="Expenses"
            lines={expenseLines}
            onCellBlur={(lineId, field, value) => {
              const numeric = Number(String(value).replace(/,/g, ''));
              if (Number.isNaN(numeric)) {
                showError('Enter a valid number');
                return;
              }
              cellMutation.mutate({ lineId, field, value: numeric });
            }}
          />

          {varianceQuery.data ? (
            <FinanceSection
              title="Plan vs Actual (YTD)"
              subtitle={`${pva?.months_elapsed ?? 0} months elapsed · ${pva?.months_remaining ?? 0} remaining · rolling forecast = actual YTD + remaining plan`}
            >
              <Grid container spacing={1.5} sx={{ mb: 2 }}>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <KpiMetricCard
                    title="Sales variance YTD"
                    value={financeMoney(pva?.sales_variance_ytd, currency)}
                    subtitle={`Plan ${financeMoney(pva?.plan_sales_ytd, currency)}`}
                    icon={TrendingUpOutlinedIcon}
                    accent="success"
                    compact
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <KpiMetricCard
                    title="Expense variance YTD"
                    value={financeMoney(pva?.expenses_variance_ytd, currency)}
                    subtitle="Positive = under plan"
                    icon={SavingsOutlinedIcon}
                    accent="warning"
                    compact
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <KpiMetricCard
                    title="Rolling GAIN/LOSS FY"
                    value={financeMoney(pva?.rolling_forecast_gain_loss_fy, currency)}
                    subtitle={`Actual YTD ${financeMoney(pva?.actual_gain_loss_ytd, currency)}`}
                    icon={CompareArrowsOutlinedIcon}
                    accent="primary"
                    compact
                  />
                </Grid>
              </Grid>
              <AnalyticsBarChart
                categories={['Sales', 'Expenses', 'GAIN/LOSS']}
                height={280}
                series={[
                  {
                    label: 'Plan YTD',
                    data: [
                      toFiniteNumber(pva?.plan_sales_ytd),
                      toFiniteNumber(pva?.plan_expenses_ytd),
                      toFiniteNumber(pva?.plan_gain_loss_ytd),
                    ],
                    color: designTokens.semantic.primary,
                  },
                  {
                    label: 'Actual YTD',
                    data: [
                      toFiniteNumber(pva?.actual_sales_ytd),
                      toFiniteNumber(pva?.actual_expenses_ytd),
                      toFiniteNumber(pva?.actual_gain_loss_ytd),
                    ],
                    color: designTokens.semantic.success,
                  },
                  {
                    label: 'Rolling FY forecast',
                    data: [
                      toFiniteNumber(pva?.rolling_forecast_sales_fy),
                      toFiniteNumber(pva?.rolling_forecast_expenses_fy),
                      toFiniteNumber(pva?.rolling_forecast_gain_loss_fy),
                    ],
                    color: '#0ea5e9',
                  },
                ]}
              />
            </FinanceSection>
          ) : null}

          <FinanceSection title="Summary (computed)" subtitle="Tax and provision applied to FY gain/loss">
              <Grid container spacing={1.5}>
                {[
                  ['Sales (FY)', detailQuery.data.summary.sales_fy],
                  ['Expenses (FY)', detailQuery.data.summary.expenses_fy],
                  ['GAIN/LOSS', detailQuery.data.summary.gain_loss],
                  [`After ${detailQuery.data.summary.tax_percent}% tax`, detailQuery.data.summary.after_tax],
                  [
                    `${detailQuery.data.summary.provision_percent}% provision`,
                    detailQuery.data.summary.provision_amount,
                  ],
                  ['GAIN/LOSS after provision', detailQuery.data.summary.gain_loss_after_provision],
                ].map(([label, value]) => (
                  <Grid key={label} size={{ xs: 12, sm: 6, md: 4 }}>
                    <Typography variant="body2" color="text.secondary">
                      {label}
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
                      {formatIndianNumber(value)}
                    </Typography>
                  </Grid>
                ))}
              </Grid>
          </FinanceSection>
        </>
      ) : null}

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Create annual plan</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Name"
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              fullWidth
            />
            <TextField
              label="FY start year (April)"
              type="number"
              value={newYear}
              onChange={(event) => {
                const year = Number(event.target.value);
                setNewYear(year);
                setNewName(`FY ${fyLabelFromStartYear(year)}`);
              }}
              helperText={`Creates FY ${fyLabelFromStartYear(newYear)} — quarters Apr–Jun through Jan–Mar.`}
              fullWidth
            />
            <TextField
              label="Tax %"
              value={taxPercent}
              onChange={(event) => setTaxPercent(event.target.value)}
            />
            <TextField
              label="Provision %"
              value={provisionPercent}
              onChange={(event) => setProvisionPercent(event.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
