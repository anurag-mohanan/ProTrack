import { Box, Button, Chip, Stack, Step, StepLabel, Stepper, TextField, Typography } from '@mui/material';
import { useState } from 'react';

const STAGES = [
  { key: 'self', label: 'Self review' },
  { key: 'manager', label: 'Manager' },
  { key: 'calibration', label: 'Calibration' },
  { key: 'final', label: 'Final' },
  { key: 'acknowledged', label: 'Acknowledged' },
] as const;

export type ReviewWorkflowFlags = {
  stage?: string | null;
  can_submit_self?: boolean;
  can_submit_manager?: boolean;
  can_calibrate?: boolean;
  can_acknowledge?: boolean;
  calibration_required?: boolean;
  calibration_notes?: string | null;
  acknowledgement_signature?: string | null;
};

type Props = {
  review: ReviewWorkflowFlags;
  busy?: boolean;
  onAction: (action: string, extras?: { acknowledgement_signature?: string; calibration_notes?: string }) => void;
};

function activeStepIndex(stage: string | null | undefined, calibrationRequired: boolean): number {
  const visible = STAGES.filter((row) => row.key !== 'calibration' || calibrationRequired);
  const idx = visible.findIndex((row) => row.key === (stage || 'self'));
  return idx >= 0 ? idx : 0;
}

export function PerformanceReviewStageStepper({ review, busy, onAction }: Props) {
  const calibrationRequired = Boolean(review.calibration_required);
  const steps = STAGES.filter((row) => row.key !== 'calibration' || calibrationRequired);
  const [signature, setSignature] = useState(review.acknowledgement_signature ?? '');
  const [calNotes, setCalNotes] = useState(review.calibration_notes ?? '');

  return (
    <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: 2, border: 1, borderColor: 'divider' }}>
      <Stack direction="row" spacing={1} sx={{ mb: 1.5, alignItems: 'center' }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Review workflow
        </Typography>
        <Chip size="small" label={(review.stage || 'self').replace('_', ' ')} />
      </Stack>
      <Stepper activeStep={activeStepIndex(review.stage, calibrationRequired)} alternativeLabel sx={{ mb: 2 }}>
        {steps.map((step) => (
          <Step key={step.key}>
            <StepLabel>{step.label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ flexWrap: 'wrap' }}>
        {review.can_submit_self ? (
          <Button variant="contained" disabled={busy} onClick={() => onAction('submit-self')}>
            Submit self-review
          </Button>
        ) : null}
        {review.can_submit_manager ? (
          <Button variant="contained" disabled={busy} onClick={() => onAction('submit-manager')}>
            Submit manager review
          </Button>
        ) : null}
        {review.can_calibrate ? (
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ flex: 1 }}>
            <TextField
              size="small"
              label="Calibration notes"
              value={calNotes}
              onChange={(e) => setCalNotes(e.target.value)}
              sx={{ minWidth: 220, flex: 1 }}
            />
            <Button
              variant="contained"
              color="secondary"
              disabled={busy}
              onClick={() => onAction('calibrate', { calibration_notes: calNotes })}
            >
              Complete calibration
            </Button>
          </Stack>
        ) : null}
        {review.can_acknowledge ? (
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ flex: 1 }}>
            <TextField
              size="small"
              label="Type your name to acknowledge"
              value={signature}
              onChange={(e) => setSignature(e.target.value)}
              sx={{ minWidth: 240, flex: 1 }}
            />
            <Button
              variant="contained"
              color="success"
              disabled={busy || !signature.trim()}
              onClick={() => onAction('acknowledge', { acknowledgement_signature: signature.trim() })}
            >
              Acknowledge
            </Button>
          </Stack>
        ) : null}
      </Stack>
    </Box>
  );
}
