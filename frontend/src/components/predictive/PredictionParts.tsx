import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Chip,
  Stack,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import type { Prediction, PredictionFactor, PredictionFreshness, ScenarioOutcome } from '../../types/Predictive';
import { dateText, FORECAST_CAVEAT } from './predictiveFormat';

export function FreshnessBanner({ freshness }: { freshness: PredictionFreshness }) {
  const disabled = freshness.disabled_types.length
    ? ` Disabled by an administrator: ${freshness.disabled_types.join(', ')}.`
    : '';
  if (freshness.stale) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        {freshness.message}
        {disabled}
      </Alert>
    );
  }
  return (
    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
      {freshness.message} {FORECAST_CAVEAT}
      {disabled}
    </Typography>
  );
}

export function ForecastChip() {
  return <Chip size="small" color="secondary" variant="outlined" label="Forecast" sx={{ height: 20, fontSize: 11 }} />;
}

export function ActualChip({ label = 'Recorded' }: { label?: string }) {
  return <Chip size="small" variant="outlined" label={label} sx={{ height: 20, fontSize: 11 }} />;
}

export function FactorList({ factors }: { factors: PredictionFactor[] }) {
  if (!factors.length) return null;
  return (
    <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
      {factors.map((f, index) => (
        <li key={`${f.name}-${index}`}>
          <Typography variant="body2">
            <strong>{f.name}</strong>
            {f.value !== null && f.value !== '' ? `: ${String(f.value)}` : ''}
            {f.role === 'calculation' ? (
              <Typography component="span" variant="caption" color="text.secondary">
                {' '}
                (used in the calculation)
              </Typography>
            ) : null}
          </Typography>
          {f.detail ? (
            <Typography variant="caption" color="text.secondary">
              {f.detail}
            </Typography>
          ) : null}
        </li>
      ))}
    </Box>
  );
}

type Explainable = Pick<
  Prediction | ScenarioOutcome,
  'factors' | 'warnings' | 'sample_size' | 'comparison_group' | 'reason' | 'status'
> & { model_version?: string; as_of?: string; range_basis?: string | null };

export function PredictionExplain({ prediction, title = 'Why this forecast' }: { prediction: Explainable; title?: string }) {
  return (
    <Accordion disableGutters elevation={0} sx={{ '&:before': { display: 'none' }, bgcolor: 'transparent' }}>
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />} sx={{ px: 0, minHeight: 36 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {title}
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ px: 0, pt: 0 }}>
        <Stack spacing={1}>
          {prediction.status === 'insufficient_data' && prediction.reason ? (
            <Typography variant="body2">{prediction.reason}</Typography>
          ) : null}
          <FactorList factors={prediction.factors} />
          <Typography variant="caption" color="text.secondary">
            {prediction.comparison_group ? `Compared with: ${prediction.comparison_group}. ` : ''}
            {prediction.sample_size !== null && prediction.sample_size !== undefined
              ? `Comparable outcomes: ${prediction.sample_size}. `
              : ''}
            {prediction.range_basis ? `Range: ${prediction.range_basis}. ` : ''}
            {prediction.model_version ? `Model ${prediction.model_version}` : ''}
            {prediction.as_of ? `, as of ${dateText(prediction.as_of)}.` : ''}
          </Typography>
          {prediction.warnings.length ? (
            <Box>
              <Typography variant="caption" sx={{ fontWeight: 700 }}>
                Limitations
              </Typography>
              <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                {prediction.warnings.map((w) => (
                  <li key={w}>
                    <Typography variant="caption">{w}</Typography>
                  </li>
                ))}
              </Box>
            </Box>
          ) : null}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}

export function InsufficientList({ rows, title }: { rows: Prediction[]; title: string }) {
  if (!rows.length) return null;
  return (
    <Accordion disableGutters variant="outlined" sx={{ '&:before': { display: 'none' } }}>
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {title} ({rows.length})
        </Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
          {rows.map((r) => (
            <li key={r.id}>
              <Typography variant="body2">
                <strong>{r.subject_label}</strong>: {r.reason ?? 'No reason recorded.'}
              </Typography>
            </li>
          ))}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
