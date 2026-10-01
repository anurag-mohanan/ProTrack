import { useEffect } from 'react';
import { Alert, Checkbox, FormControlLabel, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { checkAllocation, itAllocationKeys } from '../../../api/itAllocation';
import { getErrorMessage } from '../../../api/client';
import type { AllocationCheckRequest, AllocationCheckResult } from '../../../types/itAllocation';
import { FormField } from '../../ui/design-system';
import type { OverrideState } from './allocationWindow';

type Props = {
  request: AllocationCheckRequest | null;
  override?: OverrideState;
  onOverrideChange?: (next: OverrideState) => void;
  onResult?: (result: AllocationCheckResult | undefined) => void;
};

function severity(result: AllocationCheckResult): 'success' | 'info' | 'warning' | 'error' {
  if (result.available) return 'success';
  if (result.status === 'ASSIGNED') return 'info';
  if (result.status === 'CONFLICT' || result.status === 'RESERVED') return 'warning';
  return 'error';
}

/** Live engine verdict for an assignment; the save endpoint re-validates on the server. */
export function AllocationCheckPanel({ request, override, onOverrideChange, onResult }: Props) {
  const query = useQuery({
    queryKey: itAllocationKeys.check(request ?? ({} as AllocationCheckRequest)),
    queryFn: () => checkAllocation(request!),
    enabled: Boolean(request),
    retry: false,
  });

  useEffect(() => {
    onResult?.(request ? query.data : undefined);
  }, [query.data, request, onResult]);

  if (!request) {
    return (
      <Typography variant="caption" color="text.secondary">
        Select the employee and usage window to check availability.
      </Typography>
    );
  }
  if (query.isError) {
    return <Alert severity="error">{getErrorMessage(query.error)}</Alert>;
  }
  const result = query.data;
  if (!result) {
    return (
      <Typography variant="caption" color="text.secondary">
        Checking availability…
      </Typography>
    );
  }
  return (
    <Stack spacing={1}>
      <Alert severity={severity(result)}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {result.available ? 'AVAILABLE' : result.status.replace('_', ' ')}
          {result.requested_window ? ` · ${result.requested_window}` : ''}
        </Typography>
        <Typography variant="body2">{result.reason}</Typography>
        {result.metric_label ? (
          <Typography variant="caption" color="text.secondary" component="div">
            Metric: {result.metric_label}
            {result.rights_owned !== undefined ? ` · Rights owned: ${result.rights_owned}` : ''}
            {result.remaining_capacity !== undefined && result.remaining_capacity !== null
              ? ` · Remaining: ${result.remaining_capacity}`
              : ''}
          </Typography>
        ) : null}
      </Alert>
      {result.conflicting_assignments.length > 0 ? (
        <Stack spacing={0.5}>
          <Typography variant="subtitle2">Conflicts</Typography>
          {result.conflicting_assignments.map((c) => (
            <Typography key={`${c.kind}-${c.id}`} variant="body2">
              {c.user_name || (c.kind === 'reservation' ? 'Reservation' : 'Assignment')} · {c.window}
              {c.overlap ? ` · Overlap: ${c.overlap}` : ''}
              {c.legacy ? ' · LEGACY / NEEDS REVIEW' : ''}
              <Typography component="span" variant="caption" color="text.secondary">
                {' '}
                ({c.dates})
              </Typography>
            </Typography>
          ))}
        </Stack>
      ) : null}
      {!result.available && result.overridable && result.can_override && override && onOverrideChange ? (
        <Stack spacing={1}>
          <FormControlLabel
            control={
              <Checkbox
                checked={override.enabled}
                onChange={(event) => onOverrideChange({ ...override, enabled: event.target.checked })}
              />
            }
            label="Override this conflict (audited)"
          />
          {override.enabled ? (
            <FormField
              label="Override reason"
              required
              value={override.reason}
              onChange={(event) => onOverrideChange({ ...override, reason: event.target.value })}
              maxLength={500}
            />
          ) : null}
        </Stack>
      ) : null}
    </Stack>
  );
}