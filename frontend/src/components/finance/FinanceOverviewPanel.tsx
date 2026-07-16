import { useEffect, useState } from 'react';
import { Box, Chip, Grid, Stack, Typography } from '@mui/material';
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
import { FinanceTeamPnlTable } from './FinanceTeamPnlTable';

type RevenueBreakdownRow = {
  key: string;
  label: string;
  monthly_revenue_inr: number;
  quarterly_revenue_inr: number;
  quote_count: number;
  project_count: number;
};

type FinanceDashboard = {
  base_currency: string;
  selected_team_name?: string | null;
  planning_fy_label?: string | null;
  planning_fy_start?: string | null;
  revenue: Record<string, number | string>;
  cost: Record<string, number | string>;
  profitability: Record<string, number | string>;
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
  by_team?: Array<{
    team_id: string;
    team_name: string;
    is_overhead_home?: boolean;
    monthly_operating_cost_inr: number;
    pass_through_opex_inr: number;
    team_commercial_fee_monthly_inr: number;
    planning_revenue_signal_inr: number;
    quote_revenue_inr?: number;
    estimated_cost_inr?: number;
    gross_profit_inr?: number;
    net_profit_inr?: number;
    gross_margin_percent?: number;
    net_margin_percent?: number;
    quarterly_revenue_signal_inr?: number;
  }>;
  overhead?: {
    overhead_pool_monthly_inr?: number | string;
    overhead_cost_per_resource_inr?: number | string;
    billable_resource_count?: number;
    allocated_overhead_for_filter_inr?: number | string;
    team_billable_resource_count?: number;
  };
};

export function FinanceOverviewPanel({ teamId }: { teamId: string }) {
  const { showSuccess } = useToast();
  const queryClient = useQueryClient();
  const q = teamQueryParam(teamId);
  const [breakdownMetric, setBreakdownMetric] = useState<KpiBreakdownMetric | null>(null);

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard', teamId || 'all'],
    queryFn: async () => (await apiClient.get<FinanceDashboard>(`/finance/dashboard${q}`)).data,
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
  const teamOpex = teamRows.map((row) => toFiniteNumber(row.monthly_operating_cost_inr));
  const teamFees = teamRows.map((row) => toFiniteNumber(row.team_commercial_fee_monthly_inr));

  const scopeLabel = data.selected_team_name ? data.selected_team_name : 'All teams';

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
            subtitle="Click for quotes + fees mix"
            icon={TrendingUpOutlinedIcon}
            accent="success"
            compact
            onClick={() => setBreakdownMetric('revenue_quarter')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <KpiMetricCard
            title="Gross profit signal"
            value={financeMoney(grossProfit, currency)}
            subtitle={`Net margin ${netMargin.toFixed(1)}%`}
            icon={ShowChartOutlinedIcon}
            accent={netMargin >= 0 ? 'success' : 'error'}
            compact
            trend={{
              value: `${netMargin.toFixed(1)}%`,
              direction: netMargin > 0 ? 'up' : netMargin < 0 ? 'down' : 'flat',
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

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 5 }}>
          <FinanceSection
            title="Cost composition"
            subtitle="Where monthly spend sits (Abacum / Mosaic style mix)"
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
            title="Team operating cost vs fees"
            subtitle={!teamId ? 'Delivery teams at a glance' : 'Filtered team context'}
          >
            {!teamId && teamCategories.length ? (
              <AnalyticsBarChart
                categories={teamCategories}
                height={280}
                series={[
                  {
                    label: 'OpEx / mo',
                    data: teamOpex,
                    color: designTokens.semantic.warning,
                  },
                  {
                    label: 'Fees / mo',
                    data: teamFees,
                    color: designTokens.semantic.success,
                  },
                ]}
              />
            ) : (
              <Stack spacing={1.5}>
                <Typography variant="body2" color="text.secondary">
                  {teamId
                    ? 'Switch to All teams to compare OpEx vs commercial fees across delivery teams.'
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
                    OpEx {financeMoney(operating, currency)} · Fees {financeMoney(fees, currency)} ·
                    Pass-through {financeMoney(passThrough, currency)}
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
          subtitle="Monthly planning signals per delivery team — revenue (quotes + fees) vs operating cost. Sort by net margin to compare performance."
        >
          <FinanceTeamPnlTable rows={data.by_team ?? []} currency={currency} />
        </FinanceSection>
      ) : null}

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 6 }}>
          <FinanceSection
            title="Revenue by customer"
            subtitle="Awarded quote revenue signal grouped by customer for the current scope."
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
            subtitle="Awarded quote revenue signal grouped by project stream."
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
