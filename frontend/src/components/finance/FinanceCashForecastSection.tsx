import {
  Box,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import TimelapseOutlinedIcon from '@mui/icons-material/TimelapseOutlined';
import { apiClient } from '../../api/client';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { FinanceSection, financeMoney } from './FinanceCockpitPrimitives';
import { financeQueryParam } from './FinanceTeamFilter';
import { toFiniteNumber } from '../../utils/format';

type CashForecast = {
  fy_label?: string;
  opening_cash?: number | string;
  has_manual_cash_position?: boolean;
  months?: Array<{
    index: number;
    short_label: string;
    opening_cash: number | string;
    customer_collections: number | string;
    collections_source: string;
    investment_income: number | string;
    operating_expenses: number | string;
    loan_payments_total: number | string;
    loan_principal: number | string;
    loan_interest: number | string;
    od_interest: number | string;
    net_cash_flow: number | string;
    closing_cash: number | string;
    is_future: boolean;
  }>;
  runway?: {
    available_cash?: number | string;
    average_monthly_net_burn?: number | string;
    runway_months?: number | string | null;
    status?: string;
    message?: string;
    has_manual_cash_position?: boolean;
  };
  method_notes?: Record<string, string>;
};

export function FinanceCashForecastSection({
  teamId,
  currency = 'INR',
  fyStartYear = null,
}: {
  teamId: string;
  currency?: string;
  fyStartYear?: number | null;
}) {
  const q = financeQueryParam(teamId, fyStartYear);
  const forecastQuery = useQuery({
    queryKey: ['finance-cash-forecast', teamId || 'all', fyStartYear ?? 'current'],
    queryFn: async () =>
      (await apiClient.get<CashForecast>(`/finance/treasury/cash-flow-forecast${q}`)).data,
  });

  if (forecastQuery.isLoading || !forecastQuery.data) {
    return <LoadingState message="Loading cash forecast…" />;
  }

  const data = forecastQuery.data;
  const runway = data.runway;
  const runwayValue =
    runway?.status === 'cash_generative'
      ? 'Cash +'
      : runway?.status === 'missing_cash_position'
        ? 'Set cash'
        : runway?.runway_months != null
          ? `${toFiniteNumber(runway.runway_months).toFixed(1)} mo`
          : '—';

  return (
    <Stack spacing={2}>
      <Box sx={{ maxWidth: 360 }}>
        <Tooltip title={runway?.message ?? ''}>
          <Box>
            <KpiMetricCard
              title="Cash runway"
              value={runwayValue}
              subtitle={
                runway?.status === 'burning'
                  ? `Net burn ${financeMoney(runway.average_monthly_net_burn, currency)}/mo · Cash ${financeMoney(runway.available_cash, currency)}`
                  : runway?.message
              }
              icon={TimelapseOutlinedIcon}
              accent={runway?.status === 'burning' ? 'warning' : 'success'}
              compact
            />
          </Box>
        </Tooltip>
      </Box>

      <FinanceSection
        title={`Cash-flow forecast — ${data.fy_label ?? 'Current FY'}`}
        subtitle="Payment dates drive collections. Loan principal is cash + debt reduction (not P&L). Invoice-date turnover is on the P&L, not here."
        action={
          <Chip
            size="small"
            variant="outlined"
            label={`Opening ${financeMoney(data.opening_cash, currency)}`}
          />
        }
      >
        {!data.has_manual_cash_position ? (
          <Typography color="warning.main" sx={{ mb: 1.5 }}>
            No manual cash position yet — opening cash is 0 until you set bank/cash balances above.
          </Typography>
        ) : null}
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 700 }}>Month</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                Collections
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                OpEx+salary
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                Loan cash
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                Net
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                Closing
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(data.months ?? []).map((row) => (
              <TableRow key={row.index} hover>
                <TableCell>
                  {row.short_label}
                  {row.is_future ? (
                    <Chip size="small" label="Forecast" sx={{ ml: 1 }} variant="outlined" />
                  ) : null}
                </TableCell>
                <TableCell align="right">
                  {financeMoney(row.customer_collections, currency)}
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                    {row.collections_source === 'actual_payment_lines' ? 'actual' : 'avg'}
                  </Typography>
                </TableCell>
                <TableCell align="right">{financeMoney(row.operating_expenses, currency)}</TableCell>
                <TableCell align="right">
                  {financeMoney(row.loan_payments_total, currency)}
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                    int {financeMoney(row.loan_interest, currency)} · prin{' '}
                    {financeMoney(row.loan_principal, currency)}
                  </Typography>
                </TableCell>
                <TableCell align="right">{financeMoney(row.net_cash_flow, currency)}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 700 }}>
                  {financeMoney(row.closing_cash, currency)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </FinanceSection>
    </Stack>
  );
}
