import { Box, Chip, Stack, Tooltip, Typography } from '@mui/material';
import type { SkLevel, SkMatrixCell, SkState } from '../../types/Skills';
import { cellStyle, cellText, cellTooltip, STATE_COLOR, STATE_LABELS } from './skillFormat';

export function StateChip({ state, label }: { state: SkState; label?: string }) {
  return (
    <Chip
      size="small"
      label={label ?? STATE_LABELS[state]}
      color={STATE_COLOR[state]}
      variant={state === 'verified' ? 'filled' : 'outlined'}
      sx={state === 'no_record' ? { borderStyle: 'dashed' } : undefined}
    />
  );
}

export function HeatLegend({ levels }: { levels: SkLevel[] }) {
  const sample = (state: SkState, verified: number | null, declared: number | null): SkMatrixCell => ({
    record_id: null,
    state,
    verified_level: verified,
    declared_level: declared,
    claim_pending: false,
    last_verified_at: null,
    matches: true,
  });
  const items: { cell: SkMatrixCell; label: string }[] = [
    ...levels.map((l) => ({ cell: sample('verified', l.level, l.level), label: `Verified L${l.level}` })),
    { cell: sample('claimed', null, 3), label: 'Claim (unverified)' },
    { cell: sample('reassessment', 3, 3), label: 'Needs reassessment' },
    { cell: sample('rejected', null, 2), label: 'Not confirmed' },
    { cell: sample('no_record', null, null), label: 'No record (unknown)' },
  ];
  return (
    <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
      {items.map(({ cell, label }) => (
        <Stack key={label} direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
          <HeatCell cell={cell} levels={levels} />
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
        </Stack>
      ))}
      <Typography variant="caption" color="text.secondary">
        * new claim awaiting review
      </Typography>
    </Stack>
  );
}

export function HeatCell({
  cell,
  levels,
  onClick,
  dimmed,
}: {
  cell: SkMatrixCell;
  levels: SkLevel[];
  onClick?: () => void;
  dimmed?: boolean;
}) {
  return (
    <Tooltip title={cellTooltip(cell, levels)}>
      <Box
        component={onClick ? 'button' : 'span'}
        type={onClick ? 'button' : undefined}
        onClick={onClick}
        sx={{
          ...cellStyle(cell),
          width: 34,
          height: 26,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 0.75,
          fontSize: 12,
          fontWeight: 600,
          cursor: onClick ? 'pointer' : 'default',
          opacity: dimmed ? 0.3 : 1,
          p: 0,
          fontFamily: 'inherit',
        }}
      >
        {cellText(cell)}
      </Box>
    </Tooltip>
  );
}
