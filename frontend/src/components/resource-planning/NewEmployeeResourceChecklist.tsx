import { Alert, Chip, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import {
  fetchPlanningPackages,
  previewResourcePackage,
  resourcePlanningQueryKeys,
} from '../../api/resourcePlanning';
import { LoadingState } from '../common/LoadingState';

type Props = {
  userId: string;
  userName?: string;
};

export function NewEmployeeResourceChecklist({ userId, userName }: Props) {
  const packagesQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.packages(),
    queryFn: fetchPlanningPackages,
  });
  const packageId = (packagesQuery.data ?? []).find((row) => row.is_active !== false)?.id ?? '';
  const previewQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.packagePreview(packageId, userId),
    queryFn: () => previewResourcePackage(packageId, userId),
    enabled: Boolean(packageId) && Boolean(userId),
  });

  if (packagesQuery.isLoading || previewQuery.isLoading) {
    return <LoadingState message="Checking package availability…" />;
  }
  const preview = previewQuery.data;
  if (!preview) {
    return (
      <Typography variant="body2" color="text.secondary">
        No active resource package is configured, so a new-hire checklist cannot be generated.
      </Typography>
    );
  }

  const shortages = preview.shortages ?? [];
  return (
    <Stack spacing={1.25}>
      <Typography variant="subtitle2">
        {preview.package_name}
        {userName ? ` — ${userName}` : ''}
      </Typography>
      <Alert severity={shortages.length ? 'warning' : 'success'}>
        {shortages.length
          ? `${shortages.length} shortage(s) before onboarding this person.`
          : 'Standard package items are available in inventory.'}
      </Alert>
      {preview.hardware.map((line) => {
        const ok = line.available_count >= line.quantity;
        return (
          <Stack key={line.asset_type_id} direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <Chip size="small" color={ok ? 'success' : 'error'} label={ok ? 'Available' : 'Shortage'} />
            <Typography variant="body2">
              {line.asset_type_name} × {line.quantity}
              {line.candidates[0]
                ? ` · e.g. ${line.candidates[0].asset_number}${
                    line.candidates[0].make ? ` ${line.candidates[0].make}` : ''
                  }`
                : ''}
            </Typography>
          </Stack>
        );
      })}
      {preview.software.map((line) => {
        const ok = line.available_seats >= line.seats;
        return (
          <Stack key={line.software_id} direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <Chip size="small" color={ok ? 'success' : 'error'} label={ok ? 'License' : 'Shortage'} />
            <Typography variant="body2">
              {line.software_name} · {line.available_seats} seat(s) free
            </Typography>
          </Stack>
        );
      })}
      {preview.requires_ip ? (
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Chip
            size="small"
            color={preview.ip.available_count > 0 ? 'success' : 'error'}
            label={preview.ip.available_count > 0 ? 'IP' : 'No IP'}
          />
          <Typography variant="body2">
            {preview.ip.candidates[0]?.address ?? `${preview.ip.available_count} available`}
          </Typography>
        </Stack>
      ) : null}
    </Stack>
  );
}
