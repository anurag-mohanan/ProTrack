import { Chip, Grid, Stack } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import AccountBalanceWalletOutlinedIcon from '@mui/icons-material/AccountBalanceWalletOutlined';
import AccountBalanceOutlinedIcon from '@mui/icons-material/AccountBalanceOutlined';
import SavingsOutlinedIcon from '@mui/icons-material/SavingsOutlined';
import CreditCardOutlinedIcon from '@mui/icons-material/CreditCardOutlined';
import { apiClient } from '../../api/client';
import { toFiniteNumber } from '../../utils/format';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { FinanceSection, financeMoney } from './FinanceCockpitPrimitives';
import { teamQueryParam } from './FinanceTeamFilter';

type TreasurySummary = {
  cash?: {
    available_cash?: number | string;
    has_manual_position?: boolean;
    as_of_date?: string | null;
  };
  debt?: {
    loan_outstanding_principal?: number | string;
    od_utilized?: number | string;
    od_available?: number | string;
    od_utilization_percent?: number | string;
    od_sanctioned_limit?: number | string;
  };
  investments?: {
    current_value?: number | string;
    count?: number;
  };
};

export function FinanceBusinessPositionStrip({
  teamId,
  currency = 'INR',
}: {
  teamId: string;
  currency?: string;
}) {
  const summaryQuery = useQuery({
    queryKey: ['finance-treasury-summary', teamId || 'all'],
    queryFn: async () =>
      (await apiClient.get<TreasurySummary>(`/finance/treasury/summary${teamQueryParam(teamId)}`))
        .data,
  });

  if (summaryQuery.isLoading || !summaryQuery.data) {
    return <LoadingState message="Loading business position…" />;
  }

  const data = summaryQuery.data;
  const cash = toFiniteNumber(data.cash?.available_cash);
  const loans = toFiniteNumber(data.debt?.loan_outstanding_principal);
  const odUsed = toFiniteNumber(data.debt?.od_utilized);
  const odAvail = toFiniteNumber(data.debt?.od_available);
  const odPct = toFiniteNumber(data.debt?.od_utilization_percent);
  const invest = toFiniteNumber(data.investments?.current_value);

  return (
    <FinanceSection
      title="Business position"
      subtitle="Live treasury snapshot — loan/OD principal is financing position (not P&L). Investments are assets, not automatic OpEx."
    >
      <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap', gap: 1 }}>
        {data.cash?.has_manual_position ? (
          <Chip
            size="small"
            color="success"
            label={
              data.cash.as_of_date ? `Cash as of ${data.cash.as_of_date}` : 'Cash position set'
            }
          />
        ) : (
          <Chip size="small" color="warning" label="Set cash in Treasury" />
        )}
      </Stack>
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="success"
            icon={AccountBalanceWalletOutlinedIcon}
            title="Bank / cash"
            value={financeMoney(cash, currency)}
            subtitle="Latest manual cash position"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="warning"
            icon={AccountBalanceOutlinedIcon}
            title="Loans outstanding"
            value={financeMoney(loans, currency)}
            subtitle="Principal liability (not expense)"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent={odPct >= 85 ? 'error' : odPct >= 60 ? 'warning' : 'info'}
            icon={CreditCardOutlinedIcon}
            title="OD used / available"
            value={`${financeMoney(odUsed, currency)} / ${financeMoney(odAvail, currency)}`}
            subtitle={`Utilization ${odPct.toFixed(1)}%`}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="primary"
            icon={SavingsOutlinedIcon}
            title="Investments"
            value={financeMoney(invest, currency)}
            subtitle={`${data.investments?.count ?? 0} holdings · asset value`}
          />
        </Grid>
      </Grid>
    </FinanceSection>
  );
}
