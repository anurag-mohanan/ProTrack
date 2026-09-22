import { Alert, Chip, Stack, Typography } from '@mui/material';
import type { AssignmentPreview, ComputerRecommendation } from '../../types/itOperations';
import { LoadingState } from '../common/LoadingState';
import { ProsohmButton } from '../ui/ProsohmButton';

type Props = {
  preview?: AssignmentPreview;
  loading?: boolean;
  recommendations?: ComputerRecommendation[];
  currentAssetId?: string;
  onSelectRecommendation?: (row: ComputerRecommendation) => void;
};

export function AssignmentAvailabilityPanel({
  preview,
  loading,
  recommendations,
  currentAssetId,
  onSelectRecommendation,
}: Props) {
  if (loading && !preview) {
    return <LoadingState message="Checking availability…" />;
  }
  if (!preview && !(recommendations ?? []).length) {
    return null;
  }

  return (
    <Stack spacing={1.25}>
      {preview ? (
        <>
          <Typography variant="body2">
            {[preview.computer_name || preview.asset_number, preview.primary_ip, preview.status]
              .filter(Boolean)
              .join(' · ')}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Team and shift are derived from Resource Planning for the selected person. They are not
            written on the employee master from this dialog.
          </Typography>
          {preview.checks.map((check) => (
            <Alert key={check.code} severity={check.ok ? 'success' : 'warning'}>
              {check.message}
              {check.derived ? ' (from Resource Planning)' : ''}
              {check.team ? ` · Team: ${check.team}` : ''}
            </Alert>
          ))}
        </>
      ) : null}
      {(recommendations ?? []).length > 0 ? (
        <Stack spacing={0.75}>
          <Typography variant="subtitle2">Recommended spare computers</Typography>
          {(recommendations ?? []).map((row) => {
            const selected = currentAssetId === row.asset_id;
            return (
              <Stack
                key={row.asset_id}
                direction="row"
                spacing={1}
                sx={{ alignItems: 'center', flexWrap: 'wrap' }}
              >
                <Chip size="small" color={selected ? 'primary' : 'default'} label="Recommended" />
                <Typography variant="body2">
                  {row.computer_name}
                  {row.asset_number ? ` · ${row.asset_number}` : ''}
                  {row.primary_ip ? ` · ${row.primary_ip}` : ''}
                </Typography>
                {onSelectRecommendation && !selected ? (
                  <ProsohmButton
                    size="small"
                    buttonVariant="outlined"
                    onClick={() => onSelectRecommendation(row)}
                  >
                    Use this
                  </ProsohmButton>
                ) : null}
                <Typography variant="caption" color="text.secondary">
                  {row.reasons.join('; ')}
                </Typography>
              </Stack>
            );
          })}
        </Stack>
      ) : null}
    </Stack>
  );
}
