import {
  Box,
  Chip,
  Drawer,
  IconButton,
  LinearProgress,
  Stack,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { designTokens } from '../../theme/designTokens';
import { toFiniteNumber } from '../../utils/format';
import { LoadingState } from '../common/LoadingState';
import { financeMoney } from './FinanceCockpitPrimitives';

export type KpiBreakdownMetric =
  | 'operating_cost'
  | 'overhead_salaries'
  | 'overhead_opex'
  | 'overhead_pool'
  | 'overhead_cpr'
  | 'team_fees'
  | 'revenue_quarter';

type BreakdownLine = {
  id: string;
  label: string;
  detail?: string | null;
  amount_inr: number | string;
  share_pct: number | string;
  band: string;
  kind?: string;
};

type BreakdownGroup = {
  label: string;
  total_inr: number | string;
  lines: BreakdownLine[];
};

type BreakdownPayload = {
  metric: string;
  title: string;
  subtitle: string;
  total_inr: number | string;
  currency_code: string;
  formula?: string | null;
  insights: string[];
  groups: BreakdownGroup[];
  empty_hints: BreakdownLine[];
  meta?: Record<string, number | string>;
};

function bandColor(band: string): string {
  if (band === 'high') return designTokens.semantic.danger;
  if (band === 'thin') return designTokens.semantic.warning;
  if (band === 'empty') return designTokens.semantic.neutral;
  return designTokens.semantic.primary;
}

function bandLabel(band: string): string {
  if (band === 'high') return 'High spend';
  if (band === 'thin') return 'Low share';
  if (band === 'empty') return 'Not spent';
  return 'Normal';
}

function LineRow({
  line,
  currency,
}: {
  line: BreakdownLine;
  currency: string;
}) {
  const share = toFiniteNumber(line.share_pct);
  const amount = toFiniteNumber(line.amount_inr);
  const color = bandColor(line.band);
  return (
    <Box
      sx={{
        py: 1,
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 1, mb: 0.5 }}>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography sx={{ fontWeight: 650, fontSize: '0.9rem' }} noWrap title={line.label}>
            {line.label}
          </Typography>
          {line.detail ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }} noWrap>
              {line.detail}
            </Typography>
          ) : null}
        </Box>
        <Stack sx={{ alignItems: 'flex-end', flexShrink: 0 }}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.9rem' }}>
            {financeMoney(amount, currency)}
          </Typography>
          <Chip
            size="small"
            label={bandLabel(line.band)}
            sx={{
              height: 20,
              fontSize: '0.65rem',
              bgcolor: `${color}22`,
              color,
              fontWeight: 700,
            }}
          />
        </Stack>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={Math.min(100, share)}
        sx={{
          height: 6,
          borderRadius: 99,
          bgcolor: designTokens.semantic.neutralSoft,
          '& .MuiLinearProgress-bar': { bgcolor: color, borderRadius: 99 },
        }}
      />
      <Typography variant="caption" color="text.secondary">
        {share.toFixed(1)}% of group
      </Typography>
    </Box>
  );
}

export function FinanceKpiBreakdownDrawer({
  open,
  metric,
  teamId,
  onClose,
}: {
  open: boolean;
  metric: KpiBreakdownMetric | null;
  teamId: string;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: ['finance-kpi-breakdown', metric, teamId || 'all'],
    enabled: open && Boolean(metric),
    queryFn: async () => {
      const params = new URLSearchParams({ metric: metric! });
      if (teamId) params.set('team_id', teamId);
      return (
        await apiClient.get<BreakdownPayload>(`/finance/kpi-breakdown?${params.toString()}`)
      ).data;
    },
  });

  const data = query.data;
  const currency = data?.currency_code ?? 'INR';

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        paper: {
          sx: {
            width: { xs: '100%', sm: 440 },
            p: 0,
            bgcolor: designTokens.semantic.card,
          },
        },
      }}
    >
      <Stack sx={{ height: '100%' }}>
        <Box
          sx={{
            px: 2,
            py: 1.5,
            borderBottom: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'flex-start',
            gap: 1,
          }}
        >
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography sx={{ fontWeight: 800, letterSpacing: '-0.02em' }}>
              {data?.title ?? 'KPI breakdown'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {data?.subtitle ?? 'Loading composition…'}
            </Typography>
          </Box>
          <IconButton aria-label="Close" onClick={onClose} size="small">
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>

        <Box sx={{ px: 2, py: 2, overflow: 'auto', flex: 1 }}>
          {query.isLoading ? <LoadingState message="Loading breakdown…" /> : null}
          {query.isError ? (
            <Typography color="error">Could not load breakdown for this KPI.</Typography>
          ) : null}
          {data ? (
            <Stack spacing={2}>
              <Box
                sx={{
                  p: 1.5,
                  borderRadius: `${designTokens.radius.md}px`,
                  bgcolor: designTokens.semantic.primarySoft,
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  Total
                </Typography>
                <Typography sx={{ fontWeight: 800, fontSize: '1.35rem' }}>
                  {financeMoney(data.total_inr, currency)}
                </Typography>
                {data.formula ? (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                    {data.formula}
                  </Typography>
                ) : null}
              </Box>

              {(data.insights ?? []).length > 0 ? (
                <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', gap: 0.75 }}>
                  {data.insights.map((insight) => (
                    <Chip key={insight} size="small" label={insight} variant="outlined" />
                  ))}
                </Stack>
              ) : null}

              {(data.groups ?? []).map((group) => (
                <Box key={group.label}>
                  <Stack
                    direction="row"
                    sx={{ justifyContent: 'space-between', alignItems: 'baseline', mb: 0.5 }}
                  >
                    <Typography sx={{ fontWeight: 700 }}>{group.label}</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {financeMoney(group.total_inr, currency)}
                    </Typography>
                  </Stack>
                  {group.lines.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      No lines in this group.
                    </Typography>
                  ) : (
                    group.lines.map((line) => (
                      <LineRow key={line.id} line={line} currency={currency} />
                    ))
                  )}
                </Box>
              ))}

              {(data.empty_hints ?? []).length > 0 ? (
                <Box>
                  <Typography sx={{ fontWeight: 700, mb: 0.5 }}>Not spent enough yet</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                    Catalogue categories with no Prosohm OpEx booked this FY.
                  </Typography>
                  {data.empty_hints.map((line) => (
                    <LineRow key={line.id} line={line} currency={currency} />
                  ))}
                </Box>
              ) : null}
            </Stack>
          ) : null}
        </Box>
      </Stack>
    </Drawer>
  );
}
