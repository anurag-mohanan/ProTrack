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

export type TeamPnlRow = {
  team_id: string;
  team_name: string;
  is_overhead_home?: boolean;
  monthly_operating_cost_inr: number | string;
  planning_revenue_signal_inr: number | string;
  gross_profit_inr?: number | string;
  net_profit_inr?: number | string;
  gross_margin_percent?: number | string;
  net_margin_percent?: number | string;
  quarterly_revenue_signal_inr?: number | string;
};

type SortKey = 'team_name' | 'revenue' | 'operating' | 'gross' | 'net' | 'net_margin';

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
}: {
  rows: TeamPnlRow[];
  currency: string;
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
        switch (sortKey) {
          case 'team_name':
            return 0;
          case 'revenue':
            return toFiniteNumber(row.planning_revenue_signal_inr);
          case 'operating':
            return toFiniteNumber(row.monthly_operating_cost_inr);
          case 'gross':
            return toFiniteNumber(row.gross_profit_inr);
          case 'net':
            return toFiniteNumber(row.net_profit_inr);
          case 'net_margin':
          default:
            return toFiniteNumber(row.net_margin_percent);
        }
      };
      if (sortKey === 'team_name') {
        return a.team_name.localeCompare(b.team_name) * dir;
      }
      return (pick(a) - pick(b)) * dir;
    });
    return list;
  }, [deliveryRows, sortDir, sortKey]);

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
              {headCell('revenue', 'Revenue / mo')}
              {headCell('operating', 'Op cost / mo')}
              {headCell('gross', 'Gross profit')}
              {headCell('net', 'Net profit')}
              {headCell('net_margin', 'Net margin')}
            </TableRow>
          </TableHead>
          <TableBody>
            {sorted.map((row) => {
              const netMargin = toFiniteNumber(row.net_margin_percent);
              const netProfit = toFiniteNumber(row.net_profit_inr);
              return (
                <TableRow key={row.team_id} hover>
                  <TableCell sx={{ fontWeight: 650 }}>{row.team_name}</TableCell>
                  <TableCell align="right">
                    {financeMoney(row.planning_revenue_signal_inr, currency)}
                  </TableCell>
                  <TableCell align="right">
                    {financeMoney(row.monthly_operating_cost_inr, currency)}
                  </TableCell>
                  <TableCell align="right">
                    {financeMoney(row.gross_profit_inr, currency)}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontWeight: 700,
                      color:
                        netProfit > 0
                          ? designTokens.semantic.success
                          : netProfit < 0
                            ? designTokens.semantic.danger
                            : 'text.primary',
                    }}
                  >
                    {financeMoney(row.net_profit_inr, currency)}
                  </TableCell>
                  <TableCell align="right">{marginChip(netMargin)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      {overheadRows.length ? (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
          Overhead home ({overheadRows.map((r) => r.team_name).join(', ')}) is excluded from delivery
          performance ranking — salaries and OpEx there feed the overhead pool CPR.
        </Typography>
      ) : null}
    </>
  );
}
