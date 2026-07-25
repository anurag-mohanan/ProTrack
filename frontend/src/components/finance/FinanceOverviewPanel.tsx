import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Grid,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import AccountBalanceWalletOutlinedIcon from '@mui/icons-material/AccountBalanceWalletOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import PaymentsOutlinedIcon from '@mui/icons-material/PaymentsOutlined';
import ShowChartOutlinedIcon from '@mui/icons-material/ShowChartOutlined';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { AnalyticsBarChart, AnalyticsDonutChart } from '../analytics/AnalyticsCharts';
import { LoadingState } from '../common/LoadingState';
import { chartTheme } from '../../theme/chartTheme';
import { designTokens } from '../../theme/designTokens';
import { toFiniteNumber } from '../../utils/format';
import { teamQueryParam } from './FinanceTeamFilter';
import {
  FinanceHeroBanner,
  FinanceRenewalChip,
  FinanceSection,
  financeMoney,
} from './FinanceCockpitPrimitives';
import {
  FinanceKpiBreakdownDrawer,
  type KpiBreakdownMetric,
} from './FinanceKpiBreakdownDrawer';
import { FinanceRevenueBreakdownTable } from './FinanceRevenueBreakdownTable';
import { FinanceTeamPnlTable, type TeamPnlRow } from './FinanceTeamPnlTable';

type FinancePeriod = 'month' | 'quarter' | 'half' | 'year';

type RevenueBreakdownRow = {
  key: string;
  label: string;
  monthly_revenue_inr: number;
  quarterly_revenue_inr: number;
  quote_count: number;
  project_count: number;
};

type TeamRollup = TeamPnlRow & {
  pass_through_opex_inr?: number;
  team_commercial_fee_monthly_inr?: number;
  quote_revenue_inr?: number;
  estimated_cost_inr?: number;
  monthly_revenue_signal_inr?: number | string;
  other_operating_cost_inr?: number | string;
  half_year_revenue_signal_inr?: number | string;
  year_revenue_signal_inr?: number | string;
  quarter_salary_cost_inr?: number | string;
  half_year_salary_cost_inr?: number | string;
  year_salary_cost_inr?: number | string;
  quarter_other_operating_cost_inr?: number | string;
  half_year_other_operating_cost_inr?: number | string;
  year_other_operating_cost_inr?: number | string;
  quarter_operating_cost_inr?: number | string;
  half_year_operating_cost_inr?: number | string;
  year_operating_cost_inr?: number | string;
};

type FinanceDashboard = {
  base_currency: string;
  selected_team_name?: string | null;
  planning_fy_label?: string | null;
  planning_fy_start?: string | null;
  revenue: Record<string, number | string>;
  cost: Record<string, number | string>;
  profitability: Record<string, number | string>;
  period_context?: {
    months_month?: number;
    months_quarter?: number;
    months_half?: number;
    months_year?: number;
  };
  upcoming_renewals?: Array<{
    expense_id: string;
    name: string;
    vendor_name?: string | null;
    paid_by: string;
    next_renewal_date: string;
    days_until: number;
    amount: number;
    currency_code: string;
    team_name?: string | null;
  }>;
  pass_through_opex_inr?: number;
  salary_cost_inr?: number;
  team_commercial_fee_monthly_inr?: number;
  revenue_by_customer?: RevenueBreakdownRow[];
  revenue_by_stream?: RevenueBreakdownRow[];
  by_team?: TeamRollup[];
  overhead?: {
    overhead_pool_monthly_inr?: number | string;
    overhead_cost_per_resource_inr?: number | string;
    billable_resource_count?: number;
    allocated_overhead_for_filter_inr?: number | string;
    team_billable_resource_count?: number;
  };
};

const PERIOD_LABELS: Record<FinancePeriod, string> = {
  month: 'Month',
  quarter: 'Quarter',
  half: 'Half-year',
  year: 'Full year',
};

function teamPeriodSeries(row: TeamRollup, period: FinancePeriod) {
  if (period === 'month') {
    const salary = toFiniteNumber(row.salary_cost_inr);
    const other =
      toFiniteNumber(row.other_operating_cost_inr) ||
      toFiniteNumber(row.prosohm_opex_inr) + toFiniteNumber(row.prosohm_capex_inr);
    return {
      salary,
      other,
      operating: toFiniteNumber(row.monthly_operating_cost_inr),
      // Calendar-month awards + this month's retainer (not open quote pipeline).
      revenue:
        toFiniteNumber(row.monthly_revenue_signal_inr) ||
        toFiniteNumber(row.planning_revenue_signal_inr),
    };
  }
  if (period === 'quarter') {
    return {
      salary: toFiniteNumber(row.quarter_salary_cost_inr ?? row.salary_cost_inr),
      other: toFiniteNumber(row.quarter_other_operating_cost_inr),
      operating: toFiniteNumber(row.quarter_operating_cost_inr ?? row.monthly_operating_cost_inr),
      revenue: toFiniteNumber(row.quarterly_revenue_signal_inr),
    };
  }
  if (period === 'half') {
    return {
      salary: toFiniteNumber(row.half_year_salary_cost_inr ?? row.salary_cost_inr),
      other: toFiniteNumber(row.half_year_other_operating_cost_inr),
      operating: toFiniteNumber(row.half_year_operating_cost_inr ?? row.monthly_operating_cost_inr),
      revenue: toFiniteNumber(row.half_year_revenue_signal_inr),
    };
  }
  return {
    salary: toFiniteNumber(row.year_salary_cost_inr ?? row.salary_cost_inr),
    other: toFiniteNumber(row.year_other_operating_cost_inr),
    operating: toFiniteNumber(row.year_operating_cost_inr ?? row.monthly_operating_cost_inr),
    revenue: toFiniteNumber(row.year_revenue_signal_inr),
  };
}

function companyPeriodTotals(data: FinanceDashboard, period: FinancePeriod) {
  const salary = toFiniteNumber(data.salary_cost_inr ?? data.cost.salary_cost);
  const operating = toFiniteNumber(data.cost.monthly_operating_cost);
  const other = Math.max(0, operating - salary);
  const ctx = data.period_context ?? {};
  if (period === 'month') {
    return {
      salary,
      other,
      operating,
      revenue: toFiniteNumber(data.revenue.monthly_revenue),
      label: '/ mo',
    };
  }
  if (period === 'quarter') {
    const m = toFiniteNumber(ctx.months_quarter) || 3;
    return {
      salary: salary * m,
      other: other * m,
      operating: toFiniteNumber(data.cost.quarterly_operating_cost) || operating * m,
      revenue: toFiniteNumber(data.revenue.quarterly_revenue),
      label: '/ qtr',
    };
  }
  if (period === 'half') {
    const m = toFiniteNumber(ctx.months_half) || 6;
    return {
      salary: salary * m,
      other: other * m,
      operating: toFiniteNumber(data.cost.half_year_operating_cost) || operating * m,
      revenue: toFiniteNumber(data.revenue.half_year_revenue),
      label: '/ half',
    };
  }
  const m = toFiniteNumber(ctx.months_year) || 12;
  return {
    salary: salary * m,
    other: other * m,
    operating: toFiniteNumber(data.cost.annual_operating_cost) || operating * m,
    revenue: toFiniteNumber(data.revenue.yearly_revenue),
    label: '/ FY',
  };
}

export function FinanceOverviewPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const q = teamQueryParam(teamId);
  const [breakdownMetric, setBreakdownMetric] = useState<KpiBreakdownMetric | null>(null);
  const [period, setPeriod] = useState<FinancePeriod>('month');
  const [taxDraft, setTaxDraft] = useState('30');

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard', teamId || 'all'],
    queryFn: async () => (await apiClient.get<FinanceDashboard>(`/finance/dashboard${q}`)).data,
  });

  const taxPercent = toFiniteNumber(dashboardQuery.data?.profitability?.corporate_tax_percent) || 30;

  useEffect(() => {
    if (dashboardQuery.data?.profitability?.corporate_tax_percent != null) {
      setTaxDraft(String(toFiniteNumber(dashboardQuery.data.profitability.corporate_tax_percent)));
    }
  }, [dashboardQuery.data?.profitability?.corporate_tax_percent]);

  const taxMutation = useMutation({
    mutationFn: async (corporate_tax_percent: number) =>
      (await apiClient.patch('/finance/settings', { corporate_tax_percent })).data,
    onSuccess: () => {
      showSuccess('Corporate tax rate saved');
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: () => {
      showError('Could not save corporate tax rate');
    },
  });

  const notifyMutation = useMutation({
    mutationFn: async () => (await apiClient.post(`/finance/renewals/notify${q}`)).data,
    onSuccess: (data: { notified_count: number }) => {
      if (data.notified_count > 0) {
        showSuccess(`Sent ${data.notified_count} renewal notification(s)`);
      }
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: () => {},
  });

  useEffect(() => {
    notifyMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teamId]);

  const data = dashboardQuery.data;
  const currency = data?.base_currency ?? 'INR';

  if (dashboardQuery.isLoading || !data) {
    return <LoadingState message="Loading executive finance cockpit…" />;
  }

  const salary = toFiniteNumber(data.salary_cost_inr ?? data.cost.salary_cost);
  const prosohmOpex = toFiniteNumber(data.cost.prosohm_opex ?? data.cost.recurring_costs);
  const passThrough = toFiniteNumber(data.pass_through_opex_inr ?? data.cost.pass_through_opex);
  const overheadPool = toFiniteNumber(
    data.overhead?.overhead_pool_monthly_inr ?? data.cost.overhead_pool_monthly_inr,
  );
  const operating = toFiniteNumber(data.cost.monthly_operating_cost);
  const revenueQ = toFiniteNumber(data.revenue.quarterly_revenue ?? data.revenue.monthly_revenue);
  const fees = toFiniteNumber(
    data.team_commercial_fee_monthly_inr ?? data.revenue.team_commercial_fee_monthly,
  );
  const grossProfit = toFiniteNumber(data.profitability.gross_profit);
  const netMargin = toFiniteNumber(data.profitability.net_margin);
  const preTaxNet = toFiniteNumber(data.profitability.profit_forecast);
  const afterTaxNet = toFiniteNumber(data.profitability.after_tax_net_profit);
  const afterTaxMargin = toFiniteNumber(data.profitability.after_tax_net_margin_percent);
  const cpr = toFiniteNumber(
    data.overhead?.overhead_cost_per_resource_inr ?? data.cost.overhead_cost_per_resource_inr,
  );
  const renewalsFy = toFiniteNumber(data.cost.known_renewals_fy_inr);

  const costMix = [
    { id: 'salary', label: 'Salaries', value: salary, color: designTokens.semantic.primary },
    { id: 'opex', label: 'Prosohm OpEx', value: prosohmOpex, color: designTokens.semantic.warning },
    { id: 'overhead', label: 'Overhead pool', value: overheadPool, color: '#0ea5e9' },
    { id: 'passthrough', label: 'Pass-through', value: passThrough, color: designTokens.semantic.neutral },
  ].filter((row) => row.value > 0);

  const teamRows = data.by_team ?? [];
  const teamCategories = teamRows.map((row) => row.team_name);
  const teamPeriod = teamRows.map((row) => teamPeriodSeries(row, period));
  const teamSalaries = teamPeriod.map((row) => row.salary);
  const teamOtherCost = teamPeriod.map((row) => row.other);
  const teamRevenue = teamPeriod.map((row) => row.revenue);
  const companyPeriod = companyPeriodTotals(data, period);
  const periodShort = PERIOD_LABELS[period];
  const periodHint =
    period === 'month'
      ? 'Month: salaries + OpEx/CapEx vs quotes awarded this calendar month + this month’s retainer. Pipeline projections are in Annual Plan.'
      : `${periodShort}: salaries + OpEx/CapEx × months elapsed vs quote awards in period + retainer accrued.`;

  const scopeLabel = data.selected_team_name ? data.selected_team_name : 'All teams';

  const periodToggle = (
    <ToggleButtonGroup
      exclusive
      size="small"
      value={period}
      onChange={(_, next: FinancePeriod | null) => {
        if (next) setPeriod(next);
      }}
      aria-label="Finance period"
      sx={{ flexWrap: 'wrap' }}
    >
      {(Object.keys(PERIOD_LABELS) as FinancePeriod[]).map((key) => (
        <ToggleButton key={key} value={key} sx={{ px: 1.25, textTransform: 'none', fontWeight: 600 }}>
          {PERIOD_LABELS[key]}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="Financial planning cockpit"
        subtitle={`Live cost, revenue, and overhead signals for ${scopeLabel}${
          data.planning_fy_label ? ` · ${data.planning_fy_label}` : ''
        }. Click any KPI card to see what accumulates into that number.`}
        chips={
          <>
            <Chip size="small" label={currency} sx={{ fontWeight: 700 }} />
            {data.planning_fy_label ? (
              <Chip size="small" variant="outlined" label={data.planning_fy_label} />
            ) : null}
            <Chip
              size="small"
              variant="outlined"
              label={`${data.overhead?.billable_resource_count ?? 0} billable FTE`}
            />
          </>
        }
      />

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <KpiMetricCard
            title="Operating cost / mo"
            value={financeMoney(operating, currency)}
            subtitle="Click for salary + OpEx drivers"
            icon={AccountBalanceWalletOutlinedIcon}
            accent="warning"
            compact
            onClick={() => setBreakdownMetric('operating_cost')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <KpiMetricCard
            title="Revenue / quarter"
            value={financeMoney(revenueQ, currency)}
            subtitle="Actual awards this FY quarter (not ×3)"
            icon={TrendingUpOutlinedIcon}
            accent="success"
            compact
            onClick={() => setBreakdownMetric('revenue_quarter')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <KpiMetricCard
            title="Gross profit this month"
            value={financeMoney(grossProfit, currency)}
            subtitle={`Pre-tax net ${financeMoney(preTaxNet, currency)} (${netMargin.toFixed(1)}%) · After-tax ${financeMoney(afterTaxNet, currency)} (${afterTaxMargin.toFixed(1)}% @ ${taxPercent}%) · awards + retainer this month`}
            icon={ShowChartOutlinedIcon}
            accent={netMargin >= 0 ? 'success' : 'error'}
            compact
            trend={{
              value: `${afterTaxMargin.toFixed(1)}%`,
              direction: afterTaxMargin > 0 ? 'up' : afterTaxMargin < 0 ? 'down' : 'flat',
            }}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <KpiMetricCard
            title="Team fees / mo"
            value={financeMoney(fees, currency)}
            subtitle="Click for fee composition"
            icon={PaymentsOutlinedIcon}
            accent="primary"
            compact
            onClick={() => setBreakdownMetric('team_fees')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <KpiMetricCard
            title="Overhead / resource"
            value={financeMoney(cpr, currency)}
            subtitle="Click for pool ÷ FTE detail"
            icon={GroupsOutlinedIcon}
            accent="info"
            compact
            onClick={() => setBreakdownMetric('overhead_cpr')}
          />
        </Grid>
      </Grid>

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        sx={{ alignItems: { xs: 'stretch', sm: 'center' }, justifyContent: 'space-between' }}
      >
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 640 }}>
          {periodHint}
        </Typography>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField
            size="small"
            label="Corporate tax %"
            value={taxDraft}
            onChange={(event) => setTaxDraft(event.target.value)}
            sx={{ width: 130 }}
            slotProps={{ htmlInput: { inputMode: 'decimal' } }}
          />
          <Button
            size="small"
            variant="outlined"
            disabled={taxMutation.isPending}
            onClick={() => {
              const next = Number(String(taxDraft).replace(/,/g, ''));
              if (!Number.isFinite(next) || next < 0 || next > 100) {
                showError('Corporate tax must be between 0 and 100');
                return;
              }
              taxMutation.mutate(next);
            }}
          >
            Save tax
          </Button>
          {periodToggle}
        </Stack>
      </Stack>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 5 }}>
          <FinanceSection
            title="Cost composition"
            subtitle={`Where ${periodShort.toLowerCase()} spend sits (salaries included)`}
          >
            {costMix.length ? (
              <AnalyticsDonutChart data={costMix} height={280} />
            ) : (
              <Typography color="text.secondary">No cost signals yet for this scope.</Typography>
            )}
          </FinanceSection>
        </Grid>
        <Grid size={{ xs: 12, md: 7 }}>
          <FinanceSection
            title={`Team cost vs revenue · ${periodShort}`}
            subtitle={
              !teamId
                ? 'Salaries stacked with OpEx/CapEx; revenue = awards in period + retainer'
                : 'Filtered team context'
            }
          >
            {!teamId && teamCategories.length ? (
              <AnalyticsBarChart
                categories={teamCategories}
                height={280}
                series={[
                  {
                    label: `Salaries`,
                    data: teamSalaries,
                    color: designTokens.semantic.primary,
                    stack: 'cost',
                  },
                  {
                    label: `OpEx + CapEx`,
                    data: teamOtherCost,
                    color: designTokens.semantic.warning,
                    stack: 'cost',
                  },
                  {
                    label: `Revenue`,
                    data: teamRevenue,
                    color: designTokens.semantic.success,
                  },
                ]}
              />
            ) : (
              <Stack spacing={1.5}>
                <Typography variant="body2" color="text.secondary">
                  {teamId
                    ? 'Switch to All teams to compare cost vs revenue across delivery teams.'
                    : 'No team rollups available yet.'}
                </Typography>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    bgcolor: chartTheme.surface.muted,
                    border: `1px solid ${chartTheme.surface.hairline}`,
                  }}
                >
                  <Typography sx={{ fontWeight: 700 }}>{scopeLabel}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Salaries {financeMoney(companyPeriod.salary, currency)} · OpEx/CapEx{' '}
                    {financeMoney(companyPeriod.other, currency)} · Revenue{' '}
                    {financeMoney(companyPeriod.revenue, currency)}
                  </Typography>
                </Box>
              </Stack>
            )}
          </FinanceSection>
        </Grid>
      </Grid>

      {!teamId && (data.by_team ?? []).length > 0 ? (
        <FinanceSection
          title="Team P&L performance"
          subtitle={`${periodShort} actuals — awards in period + retainer vs fully loaded cost (salary + software OpEx + hardware CapEx). After-tax uses ${taxPercent}% corporate tax. Pipeline projections are in Annual Plan.`}
        >
          <FinanceTeamPnlTable
            rows={data.by_team ?? []}
            currency={currency}
            period={period}
            corporateTaxPercent={taxPercent}
          />
        </FinanceSection>
      ) : null}

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 6 }}>
          <FinanceSection
            title="Revenue by customer"
            subtitle="Actual awarded quotes by quoted date — this month and this FY quarter (project/quote model). Not a 3× monthly projection."
          >
            <FinanceRevenueBreakdownTable
              rows={data.revenue_by_customer ?? []}
              currency={currency}
            />
          </FinanceSection>
        </Grid>
        <Grid size={{ xs: 12, lg: 6 }}>
          <FinanceSection
            title="Revenue by stream"
            subtitle="Actual awarded quotes by quoted date — this month and this FY quarter. Retainer fees are on the Revenue / quarter KPI, not in this stream split."
          >
            <FinanceRevenueBreakdownTable
              rows={data.revenue_by_stream ?? []}
              currency={currency}
            />
          </FinanceSection>
        </Grid>
      </Grid>

      <FinanceSection
        title="Renewals radar"
        subtitle={`Known software renewals in notify window · FY renewals signal ${financeMoney(
          renewalsFy,
          currency,
        )}`}
        action={
          (data.upcoming_renewals ?? []).length > 0 ? (
            <Chip
              size="small"
              icon={<WarningAmberOutlinedIcon />}
              color="warning"
              label={`${data.upcoming_renewals?.length} upcoming`}
            />
          ) : null
        }
      >
        {(data.upcoming_renewals ?? []).length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No renewals in the notification window for this scope.
          </Typography>
        ) : (
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
            {(data.upcoming_renewals ?? []).map((row) => (
              <FinanceRenewalChip
                key={row.expense_id}
                name={`${row.name}${row.team_name ? ` (${row.team_name})` : ''}`}
                daysUntil={row.days_until}
                amountLabel={`${row.amount} ${row.currency_code}`}
              />
            ))}
          </Stack>
        )}
      </FinanceSection>

      <FinanceKpiBreakdownDrawer
        open={Boolean(breakdownMetric)}
        metric={breakdownMetric}
        teamId={teamId}
        onClose={() => setBreakdownMetric(null)}
      />
    </Stack>
  );
}
