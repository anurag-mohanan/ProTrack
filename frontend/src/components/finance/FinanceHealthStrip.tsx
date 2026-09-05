import { Chip, Grid, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import AccountBalanceOutlinedIcon from '@mui/icons-material/AccountBalanceOutlined';
import PaymentsOutlinedIcon from '@mui/icons-material/PaymentsOutlined';
import TimelapseOutlinedIcon from '@mui/icons-material/TimelapseOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import WaterDropOutlinedIcon from '@mui/icons-material/WaterDropOutlined';
import { apiClient } from '../../api/client';
import { toFiniteNumber } from '../../utils/format';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { FinanceSection, financeMoney } from './FinanceCockpitPrimitives';
import { teamQueryParam } from './FinanceTeamFilter';

type HealthIndicator = {
  key: string;
  label: string;
  status: 'healthy' | 'watch' | 'critical' | string;
  value: string;
  detail: string;
  accounting_note?: string | null;
};

export type FinancialHealth = {
  as_of?: string;
  overall_status?: string;
  overall_message?: string;
  indicators?: HealthIndicator[];
  accounting_notes?: string[];
  what_if_seed?: {
    opening_cash?: number;
    extra_loan_emi_monthly?: number;
    collections_realization_percent?: number;
  };
  treasury_snapshot?: {
    available_cash?: number | string;
    active_loan_emi_monthly?: number | string;
  };
};

const STATUS_ACCENT: Record<string, 'success' | 'warning' | 'error' | 'info'> = {
  healthy: 'success',
  watch: 'warning',
  critical: 'error',
};

const ICONS: Record<string, typeof TimelapseOutlinedIcon> = {
  cash_runway: TimelapseOutlinedIcon,
  collections_vs_turnover: PaymentsOutlinedIcon,
  receivables: WarningAmberOutlinedIcon,
  debt_od: AccountBalanceOutlinedIcon,
  liquidity_buffer: WaterDropOutlinedIcon,
};

function formatIndicatorValue(ind: HealthIndicator, currency: string): string {
  if (ind.key === 'receivables' || (ind.key === 'debt_od' && ind.value.startsWith('Loans '))) {
    const raw = ind.value.replace(/^Loans\s+/, '');
    const n = toFiniteNumber(raw);
    if (Number.isFinite(n) && /^-?\d/.test(raw.trim())) {
      return ind.key === 'debt_od' ? `Loans ${financeMoney(n, currency)}` : financeMoney(n, currency);
    }
  }
  if (ind.key === 'liquidity_buffer' && /^-?\d/.test(ind.value.trim()) && !ind.value.includes('mo')) {
    return financeMoney(toFiniteNumber(ind.value), currency);
  }
  return ind.value;
}

export function FinanceHealthStrip({
  teamId,
  currency = 'INR',
  compact = false,
}: {
  teamId: string;
  currency?: string;
  compact?: boolean;
}) {
  const q = teamQueryParam(teamId);
  const healthQuery = useQuery({
    queryKey: ['finance-health', teamId || 'all'],
    queryFn: async () => (await apiClient.get<FinancialHealth>(`/finance/health${q}`)).data,
  });

  if (healthQuery.isLoading || !healthQuery.data) {
    return <LoadingState message="Loading financial health…" />;
  }

  const data = healthQuery.data;
  const overall = data.overall_status || 'watch';
  const indicators = data.indicators || [];

  return (
    <FinanceSection
      title="Financial health"
      subtitle={
        data.overall_message ||
        'Live runway, collections vs turnover, debt/OD, and liquidity — P&L and cash kept separate.'
      }
    >
      <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap', gap: 1 }}>
        <Chip
          size="small"
          color={overall === 'healthy' ? 'success' : overall === 'critical' ? 'error' : 'warning'}
          label={`Overall: ${overall}`}
          sx={{ fontWeight: 700, textTransform: 'capitalize' }}
        />
        {data.as_of ? (
          <Chip size="small" variant="outlined" label={`As of ${data.as_of}`} />
        ) : null}
      </Stack>

      <Grid container spacing={1.5}>
        {indicators.map((ind) => {
          const Icon = ICONS[ind.key] || TimelapseOutlinedIcon;
          return (
            <Grid key={ind.key} size={{ xs: 12, sm: 6, md: compact ? 4 : 4, lg: compact ? 4 : 2.4 }}>
              <KpiMetricCard
                compact
                accent={STATUS_ACCENT[ind.status] || 'info'}
                icon={Icon}
                title={ind.label}
                value={formatIndicatorValue(ind, currency)}
                subtitle={ind.detail}
              />
            </Grid>
          );
        })}
      </Grid>

      {!compact && data.accounting_notes && data.accounting_notes.length > 0 ? (
        <Stack spacing={0.5} sx={{ mt: 1.5 }}>
          {data.accounting_notes.map((note) => (
            <Typography key={note} variant="caption" color="text.secondary">
              {note}
            </Typography>
          ))}
        </Stack>
      ) : null}
    </FinanceSection>
  );
}
