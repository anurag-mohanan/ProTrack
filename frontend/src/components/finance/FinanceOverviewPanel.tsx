import { useEffect } from 'react';
import { Box, Card, CardContent, Grid, Stack, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';

type FinanceDashboard = {
  base_currency: string;
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
  }>;
  pass_through_opex_inr?: number;
  salary_cost_inr?: number;
  team_commercial_fee_monthly_inr?: number;
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

export function FinanceOverviewPanel() {
  const { showSuccess } = useToast();
  const queryClient = useQueryClient();

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard'],
    queryFn: async () => (await apiClient.get<FinanceDashboard>('/finance/dashboard')).data,
  });

  const notifyMutation = useMutation({
    mutationFn: async () => (await apiClient.post('/finance/renewals/notify')).data,
    onSuccess: (data: { notified_count: number }) => {
      if (data.notified_count > 0) {
        showSuccess(`Sent ${data.notified_count} renewal notification(s)`);
      }
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: () => {
      // View-only finance users cannot trigger notify; Overview still loads renewals from dashboard.
    },
  });

  useEffect(() => {
    notifyMutation.mutate();
    // Run once on Overview mount to refresh in-app renewal alerts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const data = dashboardQuery.data;
  const currency = data?.base_currency ?? 'INR';

  if (dashboardQuery.isLoading || !data) {
    return <Typography color="text.secondary">Loading overview…</Typography>;
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Company cost snapshot
        </Typography>
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

      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Upcoming renewals (≤ notify window)
        </Typography>
        {(data.upcoming_renewals ?? []).length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No renewals in the notification window. Set next renewal date on software / subscription expenses.
          </Typography>
        ) : (
          <Stack spacing={1}>
            {(data.upcoming_renewals ?? []).map((row) => (
              <Card key={row.expense_id} variant="outlined">
                <CardContent>
                  <Typography sx={{ fontWeight: 600 }}>
                    {row.name}
                    {row.vendor_name ? ` · ${row.vendor_name}` : ''}
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
