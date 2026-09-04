import { Box, Chip, Grid, Tooltip, Typography } from '@mui/material';
import AccountBalanceOutlinedIcon from '@mui/icons-material/AccountBalanceOutlined';
import PaymentsOutlinedIcon from '@mui/icons-material/PaymentsOutlined';
import ShowChartOutlinedIcon from '@mui/icons-material/ShowChartOutlined';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import { AnalyticsBarChart } from '../analytics/AnalyticsCharts';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { toFiniteNumber } from '../../utils/format';
import { FinanceSection, financeMoney } from './FinanceCockpitPrimitives';

export type FyTurnoverMonth = {
  index: number;
  label: string;
  short_label: string;
  turnover_inr: number | string;
  cash_collected_inr: number | string;
  is_elapsed: boolean;
  is_current_month: boolean;
  has_billing: boolean;
};

export type FyTurnoverControl = {
  fy_label?: string;
  fy_start?: string;
  fy_end?: string;
  is_current_fy?: boolean;
  elapsed_months?: number;
  months_with_billing?: number;
  zero_billing_months?: number;
  fytd_turnover_inr?: number | string;
  fytd_cash_collected_inr?: number | string;
  average_monthly_billing_inr?: number | string;
  current_month_turnover_inr?: number | string;
  previous_month_turnover_inr?: number | string;
  mom_change_percent?: number | string | null;
  outstanding_receivables_inr?: number | string;
  highest_billing_month?: { label: string; turnover_inr: number | string } | null;
  lowest_billing_month?: { label: string; turnover_inr: number | string } | null;
  months?: FyTurnoverMonth[];
  method_notes?: {
    turnover?: string;
    cash_collected?: string;
    average_monthly_billing?: string;
  };
};

function formatMom(value: number | string | null | undefined): string {
  if (value == null || value === '') return '—';
  const n = toFiniteNumber(value);
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(1)}%`;
}

export function FinanceFyTurnoverSection({
  data,
  currency,
}: {
  data: FyTurnoverControl | undefined | null;
  currency: string;
}) {
  if (!data) return null;

  const months = data.months ?? [];
  const categories = months.map((m) => m.short_label.replace(/ /g, '\n'));
  const turnoverSeries = months.map((m) => toFiniteNumber(m.turnover_inr));
  const cashSeries = months.map((m) => toFiniteNumber(m.cash_collected_inr));

  return (
    <FinanceSection
      title={`${data.fy_label ?? 'Current FY'} — Turnover & cash`}
      subtitle="Turnover uses invoice date (P&L). Cash collected uses payment date. Average monthly billing divides FYTD turnover by elapsed months, including zero-billing months."
        action={
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {data.is_current_fy ? <Chip size="small" color="primary" label="Current FY" /> : null}
            <Chip
              size="small"
              variant="outlined"
              label={`${data.elapsed_months ?? 0} months elapsed`}
            />
            <Chip
              size="small"
              variant="outlined"
              label={`${data.zero_billing_months ?? 0} zero-billing`}
            />
          </Box>
        }
    >
      <Grid container spacing={1.5} sx={{ mb: 2 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Tooltip title={data.method_notes?.turnover ?? 'Recognized by invoice date.'}>
            <Box sx={{ height: '100%' }}>
              <KpiMetricCard
                title="This month turnover"
                value={financeMoney(data.current_month_turnover_inr, currency)}
                subtitle={`Prev ${financeMoney(data.previous_month_turnover_inr, currency)} · MoM ${formatMom(data.mom_change_percent)}`}
                icon={TrendingUpOutlinedIcon}
                accent="success"
                compact
              />
            </Box>
          </Tooltip>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Tooltip title={data.method_notes?.average_monthly_billing}>
            <Box sx={{ height: '100%' }}>
              <KpiMetricCard
                title="Avg monthly billing"
                value={financeMoney(data.average_monthly_billing_inr, currency)}
                subtitle={`FYTD ${financeMoney(data.fytd_turnover_inr, currency)} ÷ ${data.elapsed_months ?? 0} months`}
                icon={ShowChartOutlinedIcon}
                accent="primary"
                compact
              />
            </Box>
          </Tooltip>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Tooltip title={data.method_notes?.cash_collected}>
            <Box sx={{ height: '100%' }}>
              <KpiMetricCard
                title="FYTD cash collected"
                value={financeMoney(data.fytd_cash_collected_inr, currency)}
                subtitle={`Receivables ${financeMoney(data.outstanding_receivables_inr, currency)}`}
                icon={PaymentsOutlinedIcon}
                accent="info"
                compact
              />
            </Box>
          </Tooltip>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Tooltip title="Outstanding = invoiced amounts not yet paid (all active quotes).">
            <Box sx={{ height: '100%' }}>
              <KpiMetricCard
                title="Outstanding receivables"
                value={financeMoney(data.outstanding_receivables_inr, currency)}
                subtitle={
                  data.highest_billing_month
                    ? `Peak ${data.highest_billing_month.label}: ${financeMoney(data.highest_billing_month.turnover_inr, currency)}`
                    : 'Invoiced − collected'
                }
                icon={AccountBalanceOutlinedIcon}
                accent="warning"
                compact
              />
            </Box>
          </Tooltip>
        </Grid>
      </Grid>

      {months.length > 0 ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
            Month-on-month billing (invoice date)
          </Typography>
          <AnalyticsBarChart
            categories={categories}
            series={[
              { label: 'Turnover', data: turnoverSeries },
              { label: 'Cash collected', data: cashSeries },
            ]}
            height={260}
          />
        </Box>
      ) : null}
    </FinanceSection>
  );
}
