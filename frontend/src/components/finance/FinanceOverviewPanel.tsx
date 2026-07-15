import { useEffect } from 'react';
import { Box, Card, CardContent, Grid, Stack, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { teamQueryParam } from './FinanceTeamFilter';

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
  by_team?: Array<{
    team_id: string;
    team_name: string;
    monthly_operating_cost_inr: number;
    pass_through_opex_inr: number;
    team_commercial_fee_monthly_inr: number;
  }>;
};

function MetricCard({ title, value, suffix }: { title: string; value: string | number; suffix?: string }) {
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="caption" color="text.secondary">
          {title}
        </Typography>
        <Typography variant="h6" sx={{ mt: 0.5 }}>
          {value}
          {suffix ? ` ${suffix}` : ''}
        </Typography>
      </CardContent>
    </Card>
  );
}

function fmt(value: number | string | undefined) {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n.toLocaleString() : String(value ?? '—');
}

export function FinanceOverviewPanel({ teamId }: { teamId: string }) {
  const { showSuccess } = useToast();
  const queryClient = useQueryClient();
  const q = teamQueryParam(teamId);

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
    return <Typography color="text.secondary">Loading overview…</Typography>;
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {data.selected_team_name
            ? `Cost snapshot · ${data.selected_team_name}`
            : 'Company cost snapshot (all teams)'}
        </Typography>
        {data.planning_fy_label ? (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Planning opex / pass-through uses {data.planning_fy_label} purchases only (from{' '}
            {data.planning_fy_start}).
          </Typography>
        ) : null}
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Operating cost (Prosohm)"
              value={fmt(data.cost.monthly_operating_cost)}
              suffix={currency}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard title="Salaries" value={fmt(data.salary_cost_inr ?? data.cost.salary_cost)} suffix={currency} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Pass-through (customer-paid)"
              value={fmt(data.pass_through_opex_inr ?? data.cost.pass_through_opex)}
              suffix={currency}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Team commercial fees / mo"
              value={fmt(data.team_commercial_fee_monthly_inr ?? data.revenue.team_commercial_fee_monthly)}
              suffix={currency}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard title="Planning revenue" value={fmt(data.revenue.monthly_revenue)} suffix={currency} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard title="Gross profit" value={fmt(data.profitability.gross_profit)} suffix={currency} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard title="Net margin" value={fmt(data.profitability.net_margin)} suffix="%" />
          </Grid>
        </Grid>
      </Box>

      {!teamId && (data.by_team?.length ?? 0) > 0 ? (
        <Box>
          <Typography variant="h6" sx={{ mb: 1 }}>
            Per-team breakdown
          </Typography>
          <Grid container spacing={1.5}>
            {(data.by_team ?? []).map((row) => (
              <Grid key={row.team_id} size={{ xs: 12, sm: 6, md: 4 }}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography sx={{ fontWeight: 700 }}>{row.team_name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      OpEx {fmt(row.monthly_operating_cost_inr)} · Pass-through{' '}
                      {fmt(row.pass_through_opex_inr)} · Fee {fmt(row.team_commercial_fee_monthly_inr)}{' '}
                      {currency}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      ) : null}

      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Upcoming renewals (≤ notify window)
        </Typography>
        {(data.upcoming_renewals ?? []).length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No renewals in the notification window for this scope.
          </Typography>
        ) : (
          <Stack spacing={1}>
            {(data.upcoming_renewals ?? []).map((row) => (
              <Card key={row.expense_id} variant="outlined">
                <CardContent>
                  <Typography sx={{ fontWeight: 600 }}>
                    {row.name}
                    {row.vendor_name ? ` · ${row.vendor_name}` : ''}
                    {row.team_name ? ` · ${row.team_name}` : ''}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Renews {row.next_renewal_date} ({row.days_until} day
                    {row.days_until === 1 ? '' : 's'}) · {row.amount} {row.currency_code} · Paid by{' '}
                    {row.paid_by}
                  </Typography>
                </CardContent>
              </Card>
            ))}
          </Stack>
        )}
      </Box>
    </Stack>
  );
}
