import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Grid,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../context/ToastContext';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';

type FinanceDashboard = {
  base_currency: string;
  revenue: Record<string, number | string>;
  cost: Record<string, number | string>;
  profitability: Record<string, number | string>;
  budget: Record<string, number | string>;
  productivity: Record<string, number | string>;
  ai_placeholders: Array<{ id: string; kind: string; title: string; description?: string }>;
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

export function FinanceDashboardPage() {
  const [tab, setTab] = useState(0);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard'],
    queryFn: async () => (await api.get<FinanceDashboard>('/finance/dashboard')).data,
  });

  const quotesQuery = useQuery({
    queryKey: ['finance-quotes'],
    queryFn: async () => (await api.get('/finance/quotes')).data,
  });

  const budgetsQuery = useQuery({
    queryKey: ['finance-budgets'],
    queryFn: async () => (await api.get('/finance/budgets')).data,
  });

  const costCentresQuery = useQuery({
    queryKey: ['finance-cost-centres'],
    queryFn: async () => (await api.get('/finance/cost-centres')).data,
  });

  const importMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return (await api.post('/finance/quotes/import', form)).data;
    },
    onSuccess: (data) => {
      showSuccess(`Imported ${data.imported_count} quote(s)`);
      queryClient.invalidateQueries({ queryKey: ['finance-quotes'] });
      queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Quote import failed');
    },
  });

  const sections = useMemo(() => {
    const data = dashboardQuery.data;
    if (!data) return [];
    return [
      { key: 'revenue', title: 'Revenue', rows: data.revenue },
      { key: 'cost', title: 'Cost', rows: data.cost },
      { key: 'profitability', title: 'Profitability', rows: data.profitability },
      { key: 'budget', title: 'Budget', rows: data.budget },
      { key: 'productivity', title: 'Productivity', rows: data.productivity },
    ];
  }, [dashboardQuery.data]);

  if (dashboardQuery.isLoading) return <LoadingState message="Loading financial dashboard…" />;

  return (
    <Box>
      <PageHeader
        title="Financial Planning"
        subtitle={`Multi-currency dashboard (base ${dashboardQuery.data?.base_currency ?? 'INR'})`}
      />

      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 2 }}>
        <Tab label="Dashboard" />
        <Tab label="Quote Import" />
        <Tab label="Cost Centres" />
        <Tab label="Budgets" />
        <Tab label="Reports" />
        <Tab label="AI Placeholders" />
      </Tabs>

      {tab === 0 && (
        <Stack spacing={3}>
          {sections.map((section) => (
            <Box key={section.key}>
              <Typography variant="h6" sx={{ mb: 1 }}>
                {section.title}
              </Typography>
              <Grid container spacing={1.5}>
                {Object.entries(section.rows).map(([key, value]) => (
                  <Grid key={key} size={{ xs: 12, sm: 6, md: 3 }}>
                    <MetricCard
                      title={key.replaceAll('_', ' ')}
                      value={typeof value === 'number' ? value.toLocaleString() : String(value)}
                      suffix={
                        key.includes('percent') || key.includes('rate') || key.includes('margin')
                          ? '%'
                          : dashboardQuery.data?.base_currency
                      }
                    />
                  </Grid>
                ))}
              </Grid>
            </Box>
          ))}
        </Stack>
      )}

      {tab === 1 && (
        <Stack spacing={2}>
          <Typography>
            Import commercial quotes from Excel or CSV. Revisions are stored immutably. PDF import is planned.
          </Typography>
          <Button variant="contained" component="label" disabled={importMutation.isPending}>
            Upload Quote File
            <input
              hidden
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) importMutation.mutate(file);
              }}
            />
          </Button>
          <Typography variant="subtitle2">Recent quotes</Typography>
          <Stack spacing={1}>
            {(quotesQuery.data ?? []).map((quote: { id: string; tool_number: string; currency_code: string; current_revision: string }) => (
              <Card key={quote.id} variant="outlined">
                <CardContent>
                  <Typography fontWeight={600}>{quote.tool_number}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {quote.currency_code} · rev {quote.current_revision}
                  </Typography>
                </CardContent>
              </Card>
            ))}
          </Stack>
        </Stack>
      )}

      {tab === 2 && (
        <Grid container spacing={1.5}>
          {(costCentresQuery.data ?? []).map((centre: { id: string; code: string; name: string; nature: string }) => (
            <Grid key={centre.id} size={{ xs: 12, sm: 6, md: 4 }}>
              <Card variant="outlined">
                <CardContent>
                  <Typography fontWeight={600}>{centre.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {centre.code} · {centre.nature}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {tab === 3 && (
        <Stack spacing={1}>
          {(budgetsQuery.data ?? []).map((budget: { id: string; name: string; allocated: number; remaining: number; approval_status: string }) => (
            <Card key={budget.id} variant="outlined">
              <CardContent>
                <Typography fontWeight={600}>{budget.name}</Typography>
                <Typography variant="body2">
                  Allocated {budget.allocated} · Remaining {budget.remaining} · {budget.approval_status}
                </Typography>
              </CardContent>
            </Card>
          ))}
          {!budgetsQuery.data?.length ? (
            <Typography color="text.secondary">No budgets yet. Create via API or upcoming budget wizard.</Typography>
          ) : null}
        </Stack>
      )}

      {tab === 4 && (
        <Typography>
          Financial reports: Profit &amp; Loss, Project Profitability, Budget vs Actual. Use Exports with Financial Planning export permission.
        </Typography>
      )}

      {tab === 5 && (
        <Grid container spacing={1.5}>
          {(dashboardQuery.data?.ai_placeholders ?? []).map((item) => (
            <Grid key={item.id} size={{ xs: 12, sm: 6, md: 4 }}>
              <Card variant="outlined">
                <CardContent>
                  <Typography fontWeight={600}>{item.title}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {item.description}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
}

export default FinanceDashboardPage;
