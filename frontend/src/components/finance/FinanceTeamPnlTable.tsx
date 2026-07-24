import { useMemo, useState } from 'react';
import {
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Typography,
} from '@mui/material';
import { designTokens } from '../../theme/designTokens';
import { toFiniteNumber } from '../../utils/format';
import { financeMoney } from './FinanceCockpitPrimitives';

export type FinancePnlPeriod = 'month' | 'quarter' | 'half' | 'year';

export type TeamPnlRow = {
  team_id: string;
  team_name: string;
  is_overhead_home?: boolean;
  monthly_operating_cost_inr: number | string;
  planning_revenue_signal_inr: number | string;
  salary_cost_inr?: number | string;
  prosohm_opex_inr?: number | string;
  prosohm_capex_inr?: number | string;
  gross_profit_inr?: number | string;
  net_profit_inr?: number | string;
  gross_margin_percent?: number | string;
  net_margin_percent?: number | string;
  quarterly_revenue_signal_inr?: number | string;
  half_year_revenue_signal_inr?: number | string;
  year_revenue_signal_inr?: number | string;
  quarter_operating_cost_inr?: number | string;
  half_year_operating_cost_inr?: number | string;
  year_operating_cost_inr?: number | string;
  quarter_salary_cost_inr?: number | string;
  half_year_salary_cost_inr?: number | string;
  year_salary_cost_inr?: number | string;
  estimated_cost_inr?: number | string;
};

type SortKey = 'team_name' | 'revenue' | 'operating' | 'gross' | 'net' | 'net_margin';

const PERIOD_SUFFIX: Record<FinancePnlPeriod, string> = {
  month: '/ mo',
  quarter: '/ qtr',
  half: '/ half',
  year: '/ FY',
};

function periodMetrics(row: TeamPnlRow, period: FinancePnlPeriod) {
  if (period === 'month') {
    const revenue = toFiniteNumber(row.planning_revenue_signal_inr);
    const operating = toFiniteNumber(row.monthly_operating_cost_inr);
    const gross = toFiniteNumber(row.gross_profit_inr);
    const net = toFiniteNumber(row.net_profit_inr);
    const netMargin = toFiniteNumber(row.net_margin_percent);
    return {
      revenue,
      operating,
      salary: toFiniteNumber(row.salary_cost_inr),
      opex: toFiniteNumber(row.prosohm_opex_inr),
      capex: toFiniteNumber(row.prosohm_capex_inr),
      gross,
      net,
      netMargin,
    };
  }

  const revenue =
    period === 'quarter'
      ? toFiniteNumber(row.quarterly_revenue_signal_inr)
      : period === 'half'
        ? toFiniteNumber(row.half_year_revenue_signal_inr)
        : toFiniteNumber(row.year_revenue_signal_inr);
  const operating =
    period === 'quarter'
      ? toFiniteNumber(row.quarter_operating_cost_inr)
      : period === 'half'
        ? toFiniteNumber(row.half_year_operating_cost_inr)
        : toFiniteNumber(row.year_operating_cost_inr);
  const salary =
    period === 'quarter'
      ? toFiniteNumber(row.quarter_salary_cost_inr)
      : period === 'half'
        ? toFiniteNumber(row.half_year_salary_cost_inr)
        : toFiniteNumber(row.year_salary_cost_inr);
  const estimated = toFiniteNumber(row.estimated_cost_inr);
  const gross = revenue - estimated;
  const net = gross - operating;
  const netMargin = revenue > 0 ? (net / revenue) * 100 : 0;
  return {
    revenue,
    operating,
    salary,
    opex: Math.max(0, operating - salary),
    capex: 0,
    gross,
    net,
    netMargin,
  };
}

function marginChip(value: number) {
  if (value >= 15) {
    return <Chip size="small" color="success" label={`${value.toFixed(1)}%`} sx={{ fontWeight: 700 }} />;
  }
  if (value >= 0) {
    return <Chip size="small" color="default" label={`${value.toFixed(1)}%`} sx={{ fontWeight: 700 }} />;
  }
  return <Chip size="small" color="error" label={`${value.toFixed(1)}%`} sx={{ fontWeight: 700 }} />;
}

export function FinanceTeamPnlTable({
  rows,
  currency,
  period = 'month',
}: {
  rows: TeamPnlRow[];
  currency: string;
  period?: FinancePnlPeriod;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('net_margin');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const deliveryRows = useMemo(
    () => rows.filter((row) => !row.is_overhead_home),
    [rows],
  );
  const overheadRows = useMemo(
    () => rows.filter((row) => row.is_overhead_home),
    [rows],
  );

  const sorted = useMemo(() => {
    const list = [...deliveryRows];
    const dir = sortDir === 'asc' ? 1 : -1;
    list.sort((a, b) => {
      const pick = (row: TeamPnlRow): number => {
        const m = periodMetrics(row, period);
        switch (sortKey) {
          case 'team_name':
            return 0;
          case 'revenue':
            return m.revenue;
          case 'operating':
            return m.operating;
          case 'gross':
            return m.gross;
          case 'net':
            return m.net;
          case 'net_margin':
          default:
            return m.netMargin;
        }
      };
      if (sortKey === 'team_name') {
        return a.team_name.localeCompare(b.team_name) * dir;
      }
      return (pick(a) - pick(b)) * dir;
    });
    return list;
  }, [deliveryRows, period, sortDir, sortKey]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(key);
    setSortDir(key === 'team_name' ? 'asc' : 'desc');
  };

  if (!deliveryRows.length && !overheadRows.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No team P&amp;L rollups yet — add quotes, fees, and people costs per team.
      </Typography>
    );
  }

  const suffix = PERIOD_SUFFIX[period];
  const headCell = (key: SortKey, label: string, align: 'left' | 'right' = 'right') => (
    <TableCell align={align} sx={{ fontWeight: 700, whiteSpace: 'nowrap' }}>
      <TableSortLabel
        active={sortKey === key}
        direction={sortKey === key ? sortDir : 'desc'}
        onClick={() => toggleSort(key)}
      >
        {label}
      </TableSortLabel>
    </TableCell>
  );

  return (
    <>
      <TableContainer sx={{ borderRadius: `${designTokens.radius.md}px`, border: '1px solid', borderColor: 'divider' }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: designTokens.semantic.primarySoft }}>
              {headCell('team_name', 'Team', 'left')}
              {headCell('revenue', `Revenue ${suffix}`)}
              {headCell('operating', `Op cost ${suffix}`)}
              {headCell('gross', 'Gross profit')}
              {headCell('net', 'Net profit')}
              {headCell('net_margin', 'Net margin')}
            </TableRow>
          </TableHead>
          <TableBody>
            {sorted.map((row) => {
              const m = periodMetrics(row, period);
              return (
                <TableRow key={row.team_id} hover>
                  <TableCell sx={{ fontWeight: 650 }}>{row.team_name}</TableCell>
                  <TableCell align="right">{financeMoney(m.revenue, currency)}</TableCell>
                  <TableCell
                    align="right"
                    title={
                      period === 'month'
                        ? [
                            `Salary ${financeMoney(m.salary, currency)}`,
                            `OpEx ${financeMoney(m.opex, currency)}`,
                            `CapEx ${financeMoney(m.capex, currency)}`,
                          ].join(' · ')
                        : `Salary ${financeMoney(m.salary, currency)} · Other op ${financeMoney(m.opex, currency)}`
                    }
                  >
                    {financeMoney(m.operating, currency)}
                  </TableCell>
                  <TableCell align="right">{financeMoney(m.gross, currency)}</TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontWeight: 700,
                      color:
                        m.net > 0
                          ? designTokens.semantic.success
                          : m.net < 0
                            ? designTokens.semantic.danger
                            : 'text.primary',
                    }}
                  >
                    {financeMoney(m.net, currency)}
                  </TableCell>
                  <TableCell align="right">{marginChip(m.netMargin)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      {overheadRows.length ? (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
          Overhead home ({overheadRows.map((r) => r.team_name).join(', ')}) is excluded from delivery
          performance ranking — HQ salaries and Corporate-assigned OpEx feed the overhead pool CPR.
          Team-assigned software / hardware still hit each delivery team’s op cost (hover Op cost for
          salary · OpEx · CapEx).
        </Typography>
      ) : null}
    </>
  );
}
