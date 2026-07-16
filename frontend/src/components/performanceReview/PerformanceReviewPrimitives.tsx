import {
  Box,
  Chip,
  LinearProgress,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import { designTokens } from '../../theme/designTokens';
import { chartTheme } from '../../theme/chartTheme';
import { formatScore } from './performanceReviewConstants';

export function PerformanceReviewHero({
  formCode,
  formTitle,
  periodLabel,
  status,
}: {
  formCode: string;
  formTitle: string;
  periodLabel?: string;
  status?: string;
}) {
  const theme = useTheme();
  return (
    <Paper
      elevation={0}
      sx={{
        borderRadius: `${designTokens.radius.lg}px`,
        border: `1px solid ${theme.palette.divider}`,
        boxShadow: designTokens.elevation.card,
        overflow: 'hidden',
        background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.12)} 0%, ${alpha(theme.palette.secondary.main, 0.08)} 55%, ${designTokens.semantic.card} 100%)`,
      }}
    >
      <Box sx={{ px: 2.5, py: 2.25 }}>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={1.5}
          sx={{ justifyContent: 'space-between', alignItems: { md: 'center' } }}
        >
          <Box>
            <Typography variant="overline" sx={{ color: chartTheme.ink.secondary, letterSpacing: 1.2 }}>
              {formCode}
            </Typography>
            <Typography sx={{ fontWeight: 800, fontSize: 28, letterSpacing: '-0.03em' }}>
              {formTitle}
            </Typography>
            <Typography variant="body2" sx={{ color: chartTheme.ink.secondary, mt: 0.5 }}>
              Structured annual review aligned to Prosohm HR form PP-HRD-FO-20.
            </Typography>
          </Box>
          <Stack direction="row" spacing={1}>
            {periodLabel ? <Chip label={periodLabel} color="primary" variant="outlined" /> : null}
            {status ? <Chip label={status} variant="filled" /> : null}
          </Stack>
        </Stack>
      </Box>
    </Paper>
  );
}

export function PerformanceReviewCompletionMeter({
  percent,
  rated,
  total,
}: {
  percent: number;
  rated: number;
  total: number;
}) {
  return (
    <Box>
      <Stack direction="row" sx={{ justifyContent: 'space-between', mb: 0.75 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          Rating completion
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {rated}/{total} ({percent}%)
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={percent}
        sx={{ height: 8, borderRadius: 99 }}
      />
    </Box>
  );
}

export function PerformanceReviewScoreBadge({
  label,
  score,
  scoreLabel,
}: {
  label: string;
  score?: number | string | null;
  scoreLabel?: string | null;
}) {
  const theme = useTheme();
  const shown = formatScore(score);
  return (
    <Paper
      elevation={0}
      sx={{
        p: 1.5,
        borderRadius: 2,
        border: `1px solid ${theme.palette.divider}`,
        bgcolor: alpha(theme.palette.primary.main, 0.04),
      }}
    >
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 800, fontSize: 24, lineHeight: 1.1 }}>
        {shown}
      </Typography>
      {scoreLabel ? (
        <Typography variant="caption" color="text.secondary">
          {scoreLabel}
        </Typography>
      ) : null}
    </Paper>
  );
}
