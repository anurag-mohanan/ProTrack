import { useState } from 'react';
import {
  Box,
  Chip,
  Drawer,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { LoadingState } from '../common/LoadingState';
import { AnalyticsBarChart } from '../analytics/AnalyticsCharts';
import { FinanceSection, financeMoney } from './FinanceCockpitPrimitives';
import { teamQueryParam } from './FinanceTeamFilter';
import { toFiniteNumber } from '../../utils/format';

type MonthlyPnlRow = {
  index: number;
  label: string;
  short_label: string;
  is_elapsed: boolean;
  is_current_month: boolean;
  turnover_inr: number | string;
  direct_cost_inr: number | string;
  gross_profit_inr: number | string;
  gross_margin_percent: number | string;
  finance_cost_inr: number | string;
  other_income_inr: number | string;
  capex_inr: number | string;
  net_profit_inr: number | string;
};

type MonthlyPnl = {
  fy_label?: string;
  months?: MonthlyPnlRow[];
  fytd?: {
    turnover_inr?: number | string;
    gross_profit_inr?: number | string;
    net_profit_inr?: number | string;
    gross_margin_percent?: number | string;
  };
  method_notes?: Record<string, string>;
};

type Drilldown = {
  title?: string;
  explanation?: string;
  total_inr?: number | string;
  items?: Array<{ id: string; label: string; amount_inr: number | string; date?: string; note?: string }>;
};

const LINE_KEYS = [
  { key: 'turnover', label: 'Turnover' },
  { key: 'direct_cost', label: 'Direct cost' },
  { key: 'finance', label: 'Finance cost' },
  { key: 'other_income', label: 'Other income' },
  { key: 'capex', label: 'CapEx' },
] as const;

export function FinanceMonthlyPnlSection({
  teamId,
  currency = 'INR',
}: {
  teamId: string;
  currency?: string;
}) {
  const q = teamQueryParam(teamId);
  const [drill, setDrill] = useState<{ monthIndex: number; line: string; label: string } | null>(
    null,
  );

  const pnlQuery = useQuery({
    queryKey: ['finance-monthly-pnl', teamId || 'all'],
    queryFn: async () => (await apiClient.get<MonthlyPnl>(`/finance/reports/monthly-pnl${q}`)).data,
  });

  const drillQuery = useQuery({
    queryKey: ['finance-monthly-pnl-drill', drill?.monthIndex, drill?.line, teamId || 'all'],
    enabled: Boolean(drill),
    queryFn: async () => {
      const params = new URLSearchParams({ line: drill!.line });
      if (teamId) params.set('team_id', teamId);
      return (
        await apiClient.get<Drilldown>(
          `/finance/reports/monthly-pnl/${drill!.monthIndex}/drilldown?${params.toString()}`,
        )
      ).data;
    },
  });

  if (pnlQuery.isLoading || !pnlQuery.data) {
    return <LoadingState message="Loading monthly P&L…" />;
  }

  const data = pnlQuery.data;
  const months = data.months ?? [];
  const elapsed = months.filter((m) => m.is_elapsed);

  return (
    <FinanceSection
      title={`Monthly P&L — ${data.fy_label ?? 'Current FY'}`}
      subtitle="Turnover by invoice date. Finance cost = interest only (not principal). CapEx shown separately from OpEx. Click a figure to drill down."
      action={
        <Chip
          size="small"
          variant="outlined"
          label={`FYTD net ${financeMoney(data.fytd?.net_profit_inr, currency)}`}
        />
      }
    >
      <Grid container spacing={1.5} sx={{ mb: 2 }}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Tooltip title={data.method_notes?.turnover}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                FYTD turnover
              </Typography>
              <Typography sx={{ fontWeight: 700 }}>
                {financeMoney(data.fytd?.turnover_inr, currency)}
              </Typography>
            </Box>
          </Tooltip>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Tooltip title="Gross profit = turnover − salary − OpEx">
            <Box>
              <Typography variant="caption" color="text.secondary">
                FYTD gross profit
              </Typography>
              <Typography sx={{ fontWeight: 700 }}>
                {financeMoney(data.fytd?.gross_profit_inr, currency)} (
                {toFiniteNumber(data.fytd?.gross_margin_percent).toFixed(1)}%)
              </Typography>
            </Box>
          </Tooltip>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              FYTD net (after finance / CapEx)
            </Typography>
            <Typography sx={{ fontWeight: 700 }}>
              {financeMoney(data.fytd?.net_profit_inr, currency)}
            </Typography>
          </Box>
        </Grid>
      </Grid>

      {elapsed.length > 0 ? (
        <Box sx={{ mb: 2 }}>
          <AnalyticsBarChart
            categories={elapsed.map((m) => m.short_label)}
            height={240}
            series={[
              {
                label: 'Turnover',
                data: elapsed.map((m) => toFiniteNumber(m.turnover_inr)),
              },
              {
                label: 'Net profit',
                data: elapsed.map((m) => toFiniteNumber(m.net_profit_inr)),
              },
            ]}
          />
        </Box>
      ) : null}

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 700 }}>Month</TableCell>
            <TableCell align="right" sx={{ fontWeight: 700 }}>
              Turnover
            </TableCell>
            <TableCell align="right" sx={{ fontWeight: 700 }}>
              Direct cost
            </TableCell>
            <TableCell align="right" sx={{ fontWeight: 700 }}>
              Gross
            </TableCell>
            <TableCell align="right" sx={{ fontWeight: 700 }}>
              Finance
            </TableCell>
            <TableCell align="right" sx={{ fontWeight: 700 }}>
              CapEx
            </TableCell>
            <TableCell align="right" sx={{ fontWeight: 700 }}>
              Net
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {months.map((row) => (
            <TableRow
              key={row.index}
              hover
              selected={row.is_current_month}
              sx={{ opacity: row.is_elapsed ? 1 : 0.45 }}
            >
              <TableCell>
                {row.short_label}
                {row.is_current_month ? (
                  <Chip size="small" label="Now" sx={{ ml: 1 }} color="primary" />
                ) : null}
              </TableCell>
              <TableCell align="right">
                <Typography
                  component="button"
                  onClick={() =>
                    setDrill({ monthIndex: row.index, line: 'turnover', label: row.label })
                  }
                  sx={{
                    border: 0,
                    background: 'none',
                    cursor: 'pointer',
                    fontWeight: 600,
                    color: 'primary.main',
                    p: 0,
                  }}
                >
                  {financeMoney(row.turnover_inr, currency)}
                </Typography>
              </TableCell>
              <TableCell align="right">{financeMoney(row.direct_cost_inr, currency)}</TableCell>
              <TableCell align="right">
                {financeMoney(row.gross_profit_inr, currency)}
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {toFiniteNumber(row.gross_margin_percent).toFixed(1)}%
                </Typography>
              </TableCell>
              <TableCell align="right">
                <Typography
                  component="button"
                  onClick={() =>
                    setDrill({ monthIndex: row.index, line: 'finance', label: row.label })
                  }
                  sx={{
                    border: 0,
                    background: 'none',
                    cursor: 'pointer',
                    fontWeight: 600,
                    color: 'primary.main',
                    p: 0,
                  }}
                >
                  {financeMoney(row.finance_cost_inr, currency)}
                </Typography>
              </TableCell>
              <TableCell align="right">
                <Typography
                  component="button"
                  onClick={() => setDrill({ monthIndex: row.index, line: 'capex', label: row.label })}
                  sx={{
                    border: 0,
                    background: 'none',
                    cursor: 'pointer',
                    fontWeight: 600,
                    color: 'primary.main',
                    p: 0,
                  }}
                >
                  {financeMoney(row.capex_inr, currency)}
                </Typography>
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                {financeMoney(row.net_profit_inr, currency)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Drawer anchor="right" open={Boolean(drill)} onClose={() => setDrill(null)}>
        <Box sx={{ width: { xs: 320, sm: 420 }, p: 2 }}>
          <Typography sx={{ fontWeight: 700, mb: 0.5 }}>
            {drillQuery.data?.title ?? 'Drill-down'}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {drill?.label} · {drillQuery.data?.explanation}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
            {LINE_KEYS.map((item) => (
              <Chip
                key={item.key}
                size="small"
                label={item.label}
                color={drill?.line === item.key ? 'primary' : 'default'}
                onClick={() => drill && setDrill({ ...drill, line: item.key })}
              />
            ))}
          </Box>
          <Typography sx={{ fontWeight: 700, mb: 1 }}>
            Total {financeMoney(drillQuery.data?.total_inr, currency)}
          </Typography>
          {(drillQuery.data?.items ?? []).length === 0 ? (
            <Typography color="text.secondary">No contributing rows for this line.</Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {(drillQuery.data?.items ?? []).map((item) => (
                <Box key={item.id} sx={{ p: 1, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {item.label}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {item.date} · {financeMoney(item.amount_inr, currency)}
                    {item.note ? ` · ${item.note}` : ''}
                  </Typography>
                </Box>
              ))}
            </Box>
          )}
        </Box>
      </Drawer>
    </FinanceSection>
  );
}
