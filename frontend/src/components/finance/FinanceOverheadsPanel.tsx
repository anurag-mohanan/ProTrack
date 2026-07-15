import { Box, Card, CardContent, Grid, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { teamQueryParam } from './FinanceTeamFilter';

type OverheadExpense = {
  id: string;
  name: string;
  amount: number;
  currency_code: string;
  nature: string;
  paid_by: string;
  vendor_name?: string | null;
  purchase_date?: string | null;
  prior_fy_excluded_from_overview?: boolean;
};

type OverheadDash = {
  base_currency: string;
  planning_fy_label?: string | null;
  overhead?: {
    corporate_team_id?: string;
    corporate_team_name?: string;
    overhead_salary_inr?: number | string;
    overhead_opex_inr?: number | string;
    overhead_pool_monthly_inr?: number | string;
    billable_resource_count?: number;
    overhead_cost_per_resource_inr?: number | string;
    team_billable_resource_count?: number;
    allocated_overhead_for_filter_inr?: number | string;
  };
};

function fmt(value: number | string | undefined) {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n.toLocaleString() : String(value ?? '—');
}

function MetricCard({
  title,
  value,
  suffix,
  hint,
}: {
  title: string;
  value: string | number;
  suffix?: string;
  hint?: string;
}) {
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
        {hint ? (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            {hint}
          </Typography>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function FinanceOverheadsPanel({ teamId }: { teamId: string }) {
  const dashQ = teamQueryParam(teamId);

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard', teamId || 'all'],
    queryFn: async () => (await apiClient.get<OverheadDash>(`/finance/dashboard${dashQ}`)).data,
  });

  const corporateId = dashboardQuery.data?.overhead?.corporate_team_id;
  const expensesQuery = useQuery({
    queryKey: ['finance-overhead-expenses', corporateId || 'none'],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (corporateId) params.set('team_id', corporateId);
      params.set('current_fy_only', 'true');
      return (
        await apiClient.get<OverheadExpense[]>(`/finance/expenses?${params.toString()}`)
      ).data;
    },
    enabled: Boolean(corporateId),
  });

  const overhead = dashboardQuery.data?.overhead;
  const currency = dashboardQuery.data?.base_currency ?? 'INR';
  const expenses = (expensesQuery.data ?? []).filter(
    (row) => row.paid_by === 'prosohm' && row.nature === 'opex',
  );

  if (dashboardQuery.isLoading) {
    return <Typography color="text.secondary">Loading overheads…</Typography>;
  }

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Overheads
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Management / HQ costs on{' '}
          <strong>{overhead?.corporate_team_name ?? 'Corporate / Shared Services'}</strong>. Pool ÷
          delivery billable resources = overhead cost per resource (P&amp;L absorption). Maintain
          rows in People costs and Expenses (Corporate team). Annual Plan “Overhead” line stays a
          separate planning ledger.
          {dashboardQuery.data?.planning_fy_label
            ? ` OpEx uses ${dashboardQuery.data.planning_fy_label} purchases only.`
            : ''}
        </Typography>

        <Grid container spacing={1.5} sx={{ mb: 2 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Overhead salaries"
              value={fmt(overhead?.overhead_salary_inr)}
              suffix={currency}
              hint="Corporate primary / overhead roster"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Overhead OpEx (Prosohm)"
              value={fmt(overhead?.overhead_opex_inr)}
              suffix={currency}
              hint="Corporate current-FY OpEx"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Overhead pool / mo"
              value={fmt(overhead?.overhead_pool_monthly_inr)}
              suffix={currency}
              hint="Salaries + Prosohm OpEx"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Cost per billable resource"
              value={fmt(overhead?.overhead_cost_per_resource_inr)}
              suffix={currency}
              hint={`÷ ${overhead?.billable_resource_count ?? 0} delivery billable FTE`}
            />
          </Grid>
          {Number(overhead?.team_billable_resource_count ?? 0) > 0 ? (
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <MetricCard
                title="Allocated to filtered team"
                value={fmt(overhead?.allocated_overhead_for_filter_inr)}
                suffix={currency}
                hint={`CPR × ${overhead?.team_billable_resource_count} billable on this team`}
              />
            </Grid>
          ) : null}
        </Grid>
      </Box>

      <Typography variant="subtitle2">Corporate overhead expenses (current FY)</Typography>
      <Stack spacing={1}>
        {expenses.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No Corporate Prosohm OpEx in the current FY. Add expenses under Expenses &amp;
            subscriptions with team Corporate / Shared Services.
          </Typography>
        ) : (
          expenses.map((row) => (
            <Card key={row.id} variant="outlined">
              <CardContent>
                <Typography sx={{ fontWeight: 600 }}>{row.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {row.amount} {row.currency_code} · {row.nature} · Paid by {row.paid_by}
                  {row.purchase_date ? ` · Purchased ${row.purchase_date}` : ''}
                  {row.vendor_name ? ` · ${row.vendor_name}` : ''}
                </Typography>
              </CardContent>
            </Card>
          ))
        )}
      </Stack>
    </Stack>
  );
}
